"""
Pydantic schemas for Channel Management API.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Channel display name")
    youtube_account: str = Field(default="", max_length=255)
    niche_type: str = Field(default="general", max_length=100)
    style_preset: str = Field(default="dark_psychology", max_length=100)
    upload_frequency: str = Field(default="daily")  # daily, twice_daily, weekly
    daily_video_limit: int = Field(default=3, ge=1, le=50)
    target_languages: List[str] = Field(default_factory=lambda: ["en"])
    target_platforms: List[str] = Field(default_factory=lambda: ["youtube"])
    max_pending_jobs: int = Field(default=6, ge=1, le=200)
    cron_expression: str = Field(default="0 9 * * *", description="Schedule cron expression")
    videos_per_run: int = Field(default=3, ge=1, le=20)


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    youtube_account: Optional[str] = None
    niche_type: Optional[str] = None
    style_preset: Optional[str] = None
    upload_frequency: Optional[str] = None
    daily_video_limit: Optional[int] = Field(None, ge=1, le=50)
    target_languages: Optional[List[str]] = None
    target_platforms: Optional[List[str]] = None
    max_pending_jobs: Optional[int] = Field(None, ge=1, le=200)
    is_active: Optional[bool] = None
    cron_expression: Optional[str] = None
    videos_per_run: Optional[int] = Field(None, ge=1, le=20)


class OAuthCredentialStore(BaseModel):
    """Used to store YouTube OAuth credentials for a channel."""
    client_id: str
    client_secret: str
    refresh_token: str


# ── Response Schemas ─────────────────────────────────────────────────────────

class ScheduleOut(BaseModel):
    id: str
    cron_expression: str
    is_active: bool
    videos_per_run: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChannelOut(BaseModel):
    id: str
    name: str
    youtube_account: str
    niche_type: str
    style_preset: str
    upload_frequency: str
    daily_video_limit: int
    target_languages: List[str] = Field(default_factory=list)
    target_platforms: List[str] = Field(default_factory=list)
    max_pending_jobs: int = 6
    is_active: bool
    has_oauth: bool = False  # Derived field
    created_at: datetime
    updated_at: datetime
    schedule: Optional[ScheduleOut] = None

    class Config:
        from_attributes = True


class ChannelListOut(BaseModel):
    total: int
    channels: List[ChannelOut]
