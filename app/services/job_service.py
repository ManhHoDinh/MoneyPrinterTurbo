"""
Job Service — CRUD and batch operations for video generation jobs.
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import Channel, VideoJob
from app.models.job_schemas import JobCreate, JobBatchCreate, JobOut


# ── Valid status transitions ─────────────────────────────────────────────────

VALID_TRANSITIONS = {
    "pending": ["generating", "failed"],
    "generating": ["rendering", "failed"],
    "rendering": ["uploading", "completed", "failed"],
    "uploading": ["completed", "failed"],
    "completed": [],
    "failed": ["pending"],  # Allow retry
}


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_job(db: Session, payload: JobCreate) -> VideoJob:
    channel = db.query(Channel).filter(Channel.id == payload.channel_id).first()
    if not channel:
        raise ValueError(f"Channel {payload.channel_id} not found")

    style = payload.style or ""

    job = VideoJob(
        id=str(uuid.uuid4()),
        channel_id=channel.id,
        topic=payload.topic,
        style=style,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Created job [{job.id[:8]}] for channel [{channel.name}]: {job.topic[:50]}")
    return job


def create_batch_jobs(db: Session, payload: JobBatchCreate) -> List[VideoJob]:
    """Create a batch of jobs with auto-generated topics."""
    channel = db.query(Channel).filter(Channel.id == payload.channel_id).first()
    if not channel:
        raise ValueError(f"Channel {payload.channel_id} not found")

    # Try to use the batch generator for topic generation
    topics = _generate_topics(
        niche=payload.niche or channel.niche_type,
        count=payload.count,
        style=payload.style or channel.style_preset,
    )

    jobs = []
    for topic_info in topics:
        job = VideoJob(
            id=str(uuid.uuid4()),
            channel_id=channel.id,
            topic=topic_info["topic"],
            style=topic_info.get("style", channel.style_preset),
            status="pending",
        )
        db.add(job)
        jobs.append(job)

    db.commit()
    for job in jobs:
        db.refresh(job)
    logger.info(f"Created batch of {len(jobs)} jobs for channel [{channel.name}]")
    return jobs


def get_job(db: Session, job_id: str) -> Optional[VideoJob]:
    return db.query(VideoJob).filter(VideoJob.id == job_id).first()


def list_jobs(
    db: Session,
    channel_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[VideoJob]:
    query = db.query(VideoJob)
    if channel_id:
        query = query.filter(VideoJob.channel_id == channel_id)
    if status:
        query = query.filter(VideoJob.status == status)
    return query.order_by(VideoJob.created_at.desc()).offset(skip).limit(limit).all()


def count_jobs(
    db: Session,
    channel_id: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    query = db.query(VideoJob)
    if channel_id:
        query = query.filter(VideoJob.channel_id == channel_id)
    if status:
        query = query.filter(VideoJob.status == status)
    return query.count()


def update_job_status(db: Session, job_id: str, new_status: str, error_message: str = "") -> Optional[VideoJob]:
    job = get_job(db, job_id)
    if not job:
        return None

    # Validate transition
    allowed = VALID_TRANSITIONS.get(job.status, [])
    if new_status not in allowed:
        raise ValueError(f"Invalid transition: {job.status} → {new_status}. Allowed: {allowed}")

    job.status = new_status
    if new_status == "generating":
        job.started_at = datetime.utcnow()
    elif new_status in ("completed", "failed"):
        job.completed_at = datetime.utcnow()
    if error_message:
        job.error_message = error_message
    if new_status == "failed":
        job.retry_count += 1

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: str) -> bool:
    job = get_job(db, job_id)
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True


# ── Serialization ────────────────────────────────────────────────────────────

def job_to_out(job: VideoJob) -> JobOut:
    channel_name = job.channel.name if job.channel else ""
    yt_id = ""
    tt_id = ""
    platform_video_ids = {}
    try:
        if job.upload:
            yt_id = job.upload.youtube_video_id or ""
            tt_id = job.upload.tiktok_video_id or ""
            if getattr(job.upload, "external_ids_json", ""):
                platform_video_ids = json.loads(job.upload.external_ids_json or "{}")
    except Exception as e:
        logger.warning(f"job_to_out upload relation unavailable for job {job.id[:8]}: {e}")
    
    return JobOut(
        id=job.id,
        channel_id=job.channel_id,
        channel_name=channel_name,
        topic=job.topic,
        style=job.style,
        language=job.language or "en",
        status=job.status,
        task_id=job.task_id or "",
        video_path=job.video_path or "",
        viral_score=job.viral_score or 0.0,
        error_message=job.error_message or "",
        retry_count=job.retry_count or 0,
        youtube_video_id=yt_id,
        tiktok_video_id=tt_id,
        platform_video_ids=platform_video_ids,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ── Topic Generation Helper ─────────────────────────────────────────────────

def _generate_topics(niche: str, count: int, style: str) -> List[dict]:
    """Generate topics using the batch generator or fallback."""
    try:
        from app.services.batch_generator import generate_batch_topics
        raw_topics = generate_batch_topics(
            niche=niche,
            count=count,
            viral_threshold=0.5,
            styles=[style] if style else None,
        )
        return [
            {"topic": t.get("topic", t.get("title", f"Topic {i}")), "style": t.get("style", style)}
            for i, t in enumerate(raw_topics[:count])
        ]
    except Exception as e:
        logger.warning(f"Batch topic generation failed, using fallback: {e}")
        return [
            {"topic": f"{niche} topic #{i+1}", "style": style}
            for i in range(count)
        ]
