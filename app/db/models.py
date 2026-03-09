"""
SQLAlchemy ORM models for the Content Farm Platform.

Tables:
  - channels        — YouTube channel profiles
  - video_jobs      — Video generation job pipeline
  - upload_history  — YouTube upload records
  - schedule_config — Per-channel automation schedules
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.engine import Base


def _uuid():
    return str(uuid.uuid4())


# ── Channel ──────────────────────────────────────────────────────────────────

class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        Index("ix_channels_active_updated", "is_active", "updated_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    youtube_account = Column(String(255), default="")
    niche_type = Column(String(100), default="general")
    style_preset = Column(String(100), default="dark_psychology")
    upload_frequency = Column(String(50), default="daily")  # daily, twice_daily, weekly
    daily_video_limit = Column(Integer, default=3)
    target_languages = Column(String(500), default="en") # e.g. "en,es,pt"
    target_platforms = Column(String(255), default="youtube")  # e.g. "youtube,tiktok,instagram"
    max_pending_jobs = Column(Integer, default=6)
    platform_settings_json = Column(Text, default="{}")
    # Encrypted OAuth JSON (Fernet); empty until user authenticates
    encrypted_oauth_credentials = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("VideoJob", back_populates="channel", cascade="all, delete-orphan")
    uploads = relationship("UploadHistory", back_populates="channel", cascade="all, delete-orphan")
    schedule = relationship("ScheduleConfig", back_populates="channel", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel {self.name} [{self.id[:8]}]>"


# ── VideoJob ─────────────────────────────────────────────────────────────────

class VideoJob(Base):
    __tablename__ = "video_jobs"
    __table_args__ = (
        Index("ix_video_jobs_channel_status_created", "channel_id", "status", "created_at"),
        Index("ix_video_jobs_status_created", "status", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    topic = Column(String(500), nullable=False)
    style = Column(String(100), default="dark_psychology")
    language = Column(String(10), default="en")
    status = Column(String(50), default="pending")
    # pending → generating → rendering → uploading → completed | failed
    task_id = Column(String(100), default="")         # Links to existing video engine task
    video_path = Column(String(1000), default="")     # Path to generated video file
    viral_score = Column(Float, default=0.0)
    error_message = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    channel = relationship("Channel", back_populates="jobs")
    upload = relationship("UploadHistory", back_populates="job", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<VideoJob {self.topic[:30]} status={self.status} [{self.id[:8]}]>"


# ── UploadHistory ────────────────────────────────────────────────────────────

class UploadHistory(Base):
    __tablename__ = "upload_history"
    __table_args__ = (
        Index("ix_upload_history_channel_uploaded", "channel_id", "uploaded_at"),
        Index("ix_upload_history_job_uploaded", "job_id", "uploaded_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    job_id = Column(String(36), ForeignKey("video_jobs.id"), nullable=False)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    youtube_video_id = Column(String(50), default="")
    tiktok_video_id = Column(String(50), default="")
    ig_video_id = Column(String(50), default="")
    fb_video_id = Column(String(50), default="")
    title = Column(String(500), default="")
    description = Column(Text, default="")
    tags = Column(Text, default="")           # Comma-separated
    privacy_status = Column(String(20), default="private")  # public, private, unlisted
    thumbnail_url = Column(String(1000), default="")
    external_ids_json = Column(Text, default="{}")
    platform_results_json = Column(Text, default="{}")
    published_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job = relationship("VideoJob", back_populates="upload")
    channel = relationship("Channel", back_populates="uploads")

    def __repr__(self):
        return f"<Upload {self.title[:30]} yt={self.youtube_video_id}>"


class MonetizationEvent(Base):
    __tablename__ = "monetization_events"
    __table_args__ = (
        Index("ix_monetization_events_channel_created", "channel_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    job_id = Column(String(36), ForeignKey("video_jobs.id"), nullable=False)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    niche = Column(String(100), default="")
    video_topic = Column(String(500), default="")
    youtube_video_id = Column(String(50), default="")
    monetization_link_used = Column(String(1000), default="")
    lead_magnet_link = Column(String(1000), default="")
    cta_tag = Column(String(100), default="")
    uploaded_at = Column(DateTime, nullable=True)
    revenue_priority_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MonetizationEvent job={self.job_id[:8]} yt={self.youtube_video_id}>"


class RevenueTag(Base):
    __tablename__ = "revenue_tags"
    __table_args__ = (
        Index("ix_revenue_tags_channel_created", "channel_id", "created_at"),
        Index("ix_revenue_tags_youtube_video_id", "youtube_video_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    job_id = Column(String(36), ForeignKey("video_jobs.id"), nullable=False)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    niche = Column(String(100), default="")
    topic = Column(String(500), default="")
    youtube_video_id = Column(String(50), default="")
    offer_id = Column(String(100), default="")
    offer_used = Column(String(255), default="")
    offer_url = Column(String(1000), default="")
    click_count = Column(Integer, default=0)
    conversion_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    views_count = Column(Integer, default=0)
    revenue_generated = Column(Float, default=0.0)
    estimated_revenue = Column(Float, default=0.0)
    epmv = Column(Float, default=0.0)
    upload_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RevenueTag job={self.job_id[:8]} offer={self.offer_used}>"


class OfferRotationStat(Base):
    __tablename__ = "offer_rotation_stats"
    __table_args__ = (
        Index("ix_offer_rotation_stats_niche_updated", "niche", "updated_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    niche = Column(String(100), nullable=False)
    offer_code = Column(String(100), nullable=False)
    offer_label = Column(String(255), default="")
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    revenue_generated = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<OfferRotationStat niche={self.niche} offer={self.offer_code}>"


# ── ScheduleConfig ───────────────────────────────────────────────────────────

class ScheduleConfig(Base):
    __tablename__ = "schedule_configs"
    __table_args__ = (
        Index("ix_schedule_configs_active_next_run", "is_active", "next_run_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False, unique=True)
    cron_expression = Column(String(100), default="0 9 * * *")  # Default: daily at 9 AM
    is_active = Column(Boolean, default=True)
    videos_per_run = Column(Integer, default=3)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    # Relationships
    channel = relationship("Channel", back_populates="schedule")

    def __repr__(self):
        return f"<Schedule ch={self.channel_id[:8]} cron={self.cron_expression}>"
