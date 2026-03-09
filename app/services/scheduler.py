"""
Scheduler Service — Manages per-channel automation schedules.

Loads schedule configs from DB and generates Celery Beat entries.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from app.db.models import ScheduleConfig, Channel


def get_all_schedules(db: Session) -> List[Dict[str, Any]]:
    """Get all schedules with channel info for the dashboard."""
    schedules = (
        db.query(ScheduleConfig)
        .join(Channel, ScheduleConfig.channel_id == Channel.id)
        .options(joinedload(ScheduleConfig.channel))
        .all()
    )

    result = []
    for s in schedules:
        result.append({
            "id": s.id,
            "channel_id": s.channel_id,
            "channel_name": s.channel.name if s.channel else "Unknown",
            "target_platforms": (s.channel.target_platforms or "youtube") if s.channel else "youtube",
            "target_languages": (s.channel.target_languages or "en") if s.channel else "en",
            "max_pending_jobs": int(getattr(s.channel, "max_pending_jobs", 6) or 6) if s.channel else 6,
            "cron_expression": s.cron_expression,
            "is_active": s.is_active,
            "videos_per_run": s.videos_per_run,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        })
    return result


def get_active_schedules(db: Session) -> List[ScheduleConfig]:
    """Get all active schedules."""
    return (
        db.query(ScheduleConfig)
        .join(Channel, ScheduleConfig.channel_id == Channel.id)
        .filter(ScheduleConfig.is_active == True)  # noqa: E712
        .filter(Channel.is_active == True)  # noqa: E712
        .all()
    )


def toggle_schedule(db: Session, channel_id: str, active: bool) -> Optional[ScheduleConfig]:
    """Activate or deactivate a schedule."""
    schedule = db.query(ScheduleConfig).filter(
        ScheduleConfig.channel_id == channel_id
    ).first()
    if not schedule:
        return None
    schedule.is_active = active
    db.commit()
    db.refresh(schedule)
    return schedule


def update_last_run(db: Session, channel_id: str):
    """Mark schedule as just ran."""
    schedule = db.query(ScheduleConfig).filter(
        ScheduleConfig.channel_id == channel_id
    ).first()
    if schedule:
        schedule.last_run_at = datetime.utcnow()
        # Simple next_run estimation (for display purposes)
        schedule.next_run_at = _estimate_next_run(schedule.cron_expression)
        db.commit()


def trigger_channel_batch(channel_id: str):
    """Manually trigger a batch generation for a channel."""
    from app.worker.tasks import run_scheduled_batch
    result = run_scheduled_batch.delay(channel_id)
    logger.info(f"[Scheduler] Manually triggered batch for channel {channel_id}, celery task: {result.id}")
    return {"task_id": result.id, "channel_id": channel_id}


def build_celery_beat_schedule(db: Session) -> Dict[str, Any]:
    """
    Build a Celery Beat schedule dict from active DB schedules.

    Returns dict compatible with celery_app.conf.beat_schedule.
    """
    schedules = get_active_schedules(db)
    beat_schedule = {}

    for s in schedules:
        parts = s.cron_expression.split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron expression for channel {s.channel_id}: {s.cron_expression}")
            continue

        from celery.schedules import crontab
        try:
            beat_schedule[f"schedule-{s.channel_id[:8]}"] = {
                "task": "run_scheduled_batch",
                "schedule": crontab(
                    minute=parts[0],
                    hour=parts[1],
                    day_of_month=parts[2],
                    month_of_year=parts[3],
                    day_of_week=parts[4],
                ),
                "args": (s.channel_id,),
            }
        except Exception as e:
            logger.error(f"Failed to create beat entry for {s.channel_id}: {e}")

    return beat_schedule


def _estimate_next_run(cron_expr: str) -> datetime:
    """Simple estimation of next run time from cron expression."""
    try:
        parts = cron_expr.split()
        if len(parts) != 5:
            return datetime.utcnow() + timedelta(hours=24)

        hour = int(parts[1]) if parts[1] != "*" else datetime.utcnow().hour
        minute = int(parts[0]) if parts[0] != "*" else 0

        next_run = datetime.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= datetime.utcnow():
            next_run += timedelta(days=1)
        return next_run
    except Exception:
        return datetime.utcnow() + timedelta(hours=24)
