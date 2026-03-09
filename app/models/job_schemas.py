"""
Pydantic schemas for Video Job Pipeline API.
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    channel_id: str = Field(..., description="Channel to create job for")
    topic: str = Field(..., min_length=1, max_length=500)
    style: str = Field(default="", description="Style preset override; if empty, uses channel default")


class JobBatchCreate(BaseModel):
    channel_id: str
    count: int = Field(default=5, ge=1, le=50, description="Number of videos to generate")
    niche: str = Field(default="", description="Niche override for topic generation")
    style: str = Field(default="", description="Style override; if empty, rotates presets")


class JobStatusUpdate(BaseModel):
    status: str = Field(..., description="New status: pending, generating, rendering, uploading, completed, failed")
    error_message: Optional[str] = None


# ── Response Schemas ─────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: str
    channel_id: str
    channel_name: str = ""
    topic: str
    style: str
    language: str = "en"
    status: str
    task_id: str
    video_path: str
    viral_score: float
    error_message: str
    retry_count: int
    youtube_video_id: str = ""
    tiktok_video_id: str = ""
    platform_video_ids: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobListOut(BaseModel):
    total: int
    jobs: List[JobOut]


class BatchCreateOut(BaseModel):
    channel_id: str
    jobs_created: int
    job_ids: List[str]
