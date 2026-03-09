"""
Scheduler Controller — Endpoints for schedule management and manual triggers.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.services import scheduler as scheduler_service

router = APIRouter(
    prefix="/api/v1/scheduler",
    tags=["Scheduler"],
)


class SchedulerBulkToggleBody(BaseModel):
    channel_ids: List[str] = Field(default_factory=list)
    active: bool = True


class SchedulerBulkTriggerBody(BaseModel):
    channel_ids: List[str] = Field(default_factory=list)
    only_active: bool = True
    limit: int = Field(default=200, ge=1, le=2000)


class SchedulerActivateAndTriggerBody(BaseModel):
    limit: int = Field(default=200, ge=1, le=2000)
    activate_only_active_channels: bool = True


@router.get("/status")
def get_scheduler_status(db: Session = Depends(get_db)):
    """Get all channel schedules with status info."""
    schedules = scheduler_service.get_all_schedules(db)
    return {
        "total": len(schedules),
        "schedules": schedules,
    }


@router.post("/{channel_id}/trigger")
def trigger_channel(channel_id: str, db: Session = Depends(get_db)):
    """Manually trigger a batch generation for a channel."""
    from app.db.models import Channel
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    result = scheduler_service.trigger_channel_batch(channel_id)
    return {"message": f"Batch triggered for {channel.name}", **result}


@router.post("/{channel_id}/toggle")
def toggle_schedule(channel_id: str, active: bool = True, db: Session = Depends(get_db)):
    """Activate or deactivate a channel's schedule."""
    schedule = scheduler_service.toggle_schedule(db, channel_id, active)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found for this channel")
    return {"channel_id": channel_id, "is_active": schedule.is_active}


@router.post("/toggle/bulk")
def toggle_schedule_bulk(body: SchedulerBulkToggleBody, db: Session = Depends(get_db)):
    """Activate/deactivate schedules for many channels."""
    from app.db.models import ScheduleConfig

    channel_ids = [x.strip() for x in body.channel_ids if str(x).strip()]
    if not channel_ids:
        raise HTTPException(status_code=400, detail="channel_ids is required")

    updated = 0
    missing = 0
    for channel_id in channel_ids:
        schedule = db.query(ScheduleConfig).filter(
            ScheduleConfig.channel_id == channel_id
        ).first()
        if not schedule:
            missing += 1
            continue
        schedule.is_active = bool(body.active)
        updated += 1

    db.commit()
    return {
        "success": True,
        "active": bool(body.active),
        "requested": len(channel_ids),
        "updated": updated,
        "missing": missing,
    }


@router.post("/trigger/bulk")
def trigger_channels_bulk(body: SchedulerBulkTriggerBody, db: Session = Depends(get_db)):
    """Manually trigger many channels in one request."""
    from app.db.models import Channel, ScheduleConfig

    requested_ids: List[str]
    if body.channel_ids:
        requested_ids = [x.strip() for x in body.channel_ids if str(x).strip()]
    else:
        q = db.query(Channel.id).join(
            ScheduleConfig,
            ScheduleConfig.channel_id == Channel.id,
        )
        if body.only_active:
            q = q.filter(Channel.is_active == True).filter(ScheduleConfig.is_active == True)  # noqa: E712
        requested_ids = [row[0] for row in q.limit(body.limit).all()]

    if not requested_ids:
        return {
            "success": True,
            "requested": 0,
            "triggered": 0,
            "skipped": 0,
            "tasks": [],
        }

    triggered = 0
    skipped = 0
    tasks: List[dict] = []
    for channel_id in requested_ids[: body.limit]:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            skipped += 1
            continue
        if body.only_active and not channel.is_active:
            skipped += 1
            continue
        result = scheduler_service.trigger_channel_batch(channel_id)
        tasks.append({
            "channel_id": channel_id,
            "channel_name": channel.name,
            "task_id": result.get("task_id", ""),
        })
        triggered += 1

    return {
        "success": True,
        "requested": len(requested_ids[: body.limit]),
        "triggered": triggered,
        "skipped": skipped,
        "tasks": tasks,
    }


@router.post("/trigger/all-active")
def trigger_all_active(limit: int = Query(200, ge=1, le=2000), db: Session = Depends(get_db)):
    """Trigger all active channels that have active schedules."""
    return trigger_channels_bulk(
        body=SchedulerBulkTriggerBody(
            channel_ids=[],
            only_active=True,
            limit=limit,
        ),
        db=db,
    )


@router.post("/activate-and-trigger-all")
def activate_and_trigger_all(body: Optional[SchedulerActivateAndTriggerBody] = None, db: Session = Depends(get_db)):
    """
    One-click scale mode:
      1) Activate schedules in bulk
      2) Trigger active channels immediately
    """
    from app.db.models import Channel, ScheduleConfig

    payload = body or SchedulerActivateAndTriggerBody()
    limit = int(payload.limit)

    query = (
        db.query(ScheduleConfig, Channel)
        .join(Channel, ScheduleConfig.channel_id == Channel.id)
    )
    if payload.activate_only_active_channels:
        query = query.filter(Channel.is_active == True)  # noqa: E712

    rows = query.limit(limit).all()
    schedule_updates = 0
    channel_ids: List[str] = []

    for schedule, channel in rows:
        if not schedule.is_active:
            schedule.is_active = True
            schedule_updates += 1
        if channel.is_active:
            channel_ids.append(channel.id)

    db.commit()

    trigger_result = trigger_channels_bulk(
        body=SchedulerBulkTriggerBody(
            channel_ids=channel_ids,
            only_active=True,
            limit=limit,
        ),
        db=db,
    )

    return {
        "success": True,
        "limit": limit,
        "schedules_activated": schedule_updates,
        "channels_considered": len(rows),
        **trigger_result,
    }


@router.get("/mutation/preview")
def preview_mutations(
    style: str = Query("dark_psychology"),
    intensity: float = Query(None),
):
    """Preview style mutations that would be applied to a video."""
    from app.services.style_mutation import preview_mutation
    return preview_mutation(style=style, intensity=intensity)
