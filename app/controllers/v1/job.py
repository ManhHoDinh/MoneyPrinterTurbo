"""
Video Job Controller — CRUD and batch endpoints for video generation jobs.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.models.job_schemas import (
    JobCreate,
    JobBatchCreate,
    JobStatusUpdate,
    JobListOut,
    JobOut,
    BatchCreateOut,
)
from app.services import job_service

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["Jobs"],
)


def _queue_generate_job(job_id: str) -> None:
    """Queue async generation for a job."""
    from app.worker.tasks import generate_video_task
    generate_video_task.delay(job_id)


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    """Create a single video generation job."""
    try:
        job = job_service.create_job(db, body)
        _queue_generate_job(job.id)
        return job_service.job_to_out(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=BatchCreateOut, status_code=201)
def create_batch_jobs(body: JobBatchCreate, db: Session = Depends(get_db)):
    """Create a batch of video generation jobs with auto-generated topics."""
    try:
        jobs = job_service.create_batch_jobs(db, body)
        for job in jobs:
            _queue_generate_job(job.id)
        return BatchCreateOut(
            channel_id=body.channel_id,
            jobs_created=len(jobs),
            job_ids=[j.id for j in jobs],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=JobListOut)
def list_jobs(
    channel_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List jobs with optional filters."""
    jobs = job_service.list_jobs(db, channel_id=channel_id, status=status, skip=skip, limit=limit)
    total = job_service.count_jobs(db, channel_id=channel_id, status=status)
    return JobListOut(
        total=total,
        jobs=[job_service.job_to_out(j) for j in jobs],
    )


@router.get("/logs/active")
def get_active_log_streams():
    """Get list of jobs that currently have active log buffers."""
    from app.services.job_logger import get_active_jobs
    return {"active_jobs": get_active_jobs()}


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job details by ID."""
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_service.job_to_out(job)


@router.patch("/{job_id}", response_model=JobOut)
def update_job_status(job_id: str, body: JobStatusUpdate, db: Session = Depends(get_db)):
    """Update job status."""
    try:
        job = job_service.update_job_status(db, job_id, body.status, body.error_message or "")
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if body.status == "pending":
            _queue_generate_job(job.id)
        return job_service.job_to_out(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete/cancel a job."""
    if not job_service.delete_job(db, job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return None


# ── Log Streaming ────────────────────────────────────────────────────────────

@router.get("/{job_id}/logs")
def get_job_logs(job_id: str):
    """Get all captured log entries for a job."""
    from app.services.job_logger import get_job_logs
    logs = get_job_logs(job_id)
    return {"job_id": job_id, "count": len(logs), "logs": logs}


@router.get("/{job_id}/logs/stream")
async def stream_job_logs_endpoint(job_id: str):
    """
    Stream job logs in real-time via Server-Sent Events (SSE).

    Connect with EventSource in the browser:
        const es = new EventSource('/api/v1/jobs/{job_id}/logs/stream');
        es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    from app.services.job_logger import stream_job_logs

    return StreamingResponse(
        stream_job_logs(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

