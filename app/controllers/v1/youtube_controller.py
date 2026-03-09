"""
YouTube Controller — OAuth flow and upload endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.services import youtube_service

router = APIRouter(
    prefix="/api/v1/youtube",
    tags=["YouTube"],
)


@router.get("/auth/{channel_id}")
def get_oauth_url(channel_id: str, db: Session = Depends(get_db)):
    """Get YouTube OAuth consent URL for a channel."""
    from app.db.models import Channel
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        url = youtube_service.get_auth_url(channel_id)
        return {"auth_url": url, "channel_id": channel_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """Handle YouTube OAuth callback."""
    try:
        result = youtube_service.handle_oauth_callback(db, code, state)
        # Redirect back to dashboard with success message
        return RedirectResponse(url=f"/dashboard/#/channels?oauth=success&channel={state}")
    except Exception as e:
        return RedirectResponse(url=f"/dashboard/#/channels?oauth=error&message={str(e)[:100]}")


@router.post("/upload/{job_id}")
def upload_video(job_id: str, db: Session = Depends(get_db)):
    """Manually trigger upload of a completed video to YouTube."""
    from app.db.models import VideoJob
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.video_path:
        raise HTTPException(status_code=400, detail="Video not yet generated for this job")

    # Queue async upload
    from app.worker.tasks import upload_video_task
    result = upload_video_task.delay(job_id)
    return {"message": "Upload queued", "celery_task_id": result.id, "job_id": job_id}


@router.get("/history")
def get_upload_history(
    channel_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get YouTube upload history."""
    uploads = youtube_service.get_upload_history(db, channel_id=channel_id, skip=skip, limit=limit)
    total = youtube_service.count_uploads(db, channel_id=channel_id)
    return {
        "total": total,
        "uploads": [
            {
                "id": u.id,
                "job_id": u.job_id,
                "channel_id": u.channel_id,
                "youtube_video_id": u.youtube_video_id,
                "title": u.title,
                "description": u.description,
                "tags": u.tags,
                "privacy_status": u.privacy_status,
                "thumbnail_url": u.thumbnail_url,
                "published_at": u.published_at.isoformat() if u.published_at else None,
                "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
            }
            for u in uploads
        ],
    }
