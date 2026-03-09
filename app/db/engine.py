"""
Database engine and session management.

Uses SQLite stored at storage/contentfarm.db.
Auto-creates all tables on first import.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Resolve DB path relative to project root
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_storage_dir = os.path.join(_project_root, "storage")
os.makedirs(_storage_dir, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(_storage_dir, 'contentfarm.db')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + threads
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
    finally:
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency - yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist."""
    from app.db.models import (
        Channel,
        VideoJob,
        UploadHistory,
        ScheduleConfig,
        MonetizationEvent,
        RevenueTag,
        OfferRotationStat,
    )

    Base.metadata.create_all(bind=engine)
    _run_lightweight_sqlite_migrations()


def _run_lightweight_sqlite_migrations():
    """
    Backfill newly introduced columns for existing SQLite deployments.
    """
    table_columns = {
        "revenue_tags": {
            "offer_id": "TEXT DEFAULT ''",
            "conversion_count": "INTEGER DEFAULT 0",
            "conversion_rate": "FLOAT DEFAULT 0.0",
            "estimated_revenue": "FLOAT DEFAULT 0.0",
        },
        "offer_rotation_stats": {
            "conversions": "INTEGER DEFAULT 0",
            "conversion_rate": "FLOAT DEFAULT 0.0",
        },
        "channels": {
            "target_platforms": "TEXT DEFAULT 'youtube'",
            "max_pending_jobs": "INTEGER DEFAULT 6",
            "platform_settings_json": "TEXT DEFAULT '{}'",
        },
        "upload_history": {
            "external_ids_json": "TEXT DEFAULT '{}'",
            "platform_results_json": "TEXT DEFAULT '{}'",
        },
    }
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_channels_active_updated ON channels (is_active, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_video_jobs_channel_status_created ON video_jobs (channel_id, status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_video_jobs_status_created ON video_jobs (status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_upload_history_channel_uploaded ON upload_history (channel_id, uploaded_at)",
        "CREATE INDEX IF NOT EXISTS ix_upload_history_job_uploaded ON upload_history (job_id, uploaded_at)",
        "CREATE INDEX IF NOT EXISTS ix_monetization_events_channel_created ON monetization_events (channel_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_revenue_tags_channel_created ON revenue_tags (channel_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_revenue_tags_youtube_video_id ON revenue_tags (youtube_video_id)",
        "CREATE INDEX IF NOT EXISTS ix_offer_rotation_stats_niche_updated ON offer_rotation_stats (niche, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_schedule_configs_active_next_run ON schedule_configs (is_active, next_run_at)",
    ]
    with engine.begin() as conn:
        for table_name, cols in table_columns.items():
            existing = set()
            try:
                rows = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
                existing = {str(r[1]) for r in rows}
            except Exception:
                continue
            for col, ddl in cols.items():
                if col in existing:
                    continue
                try:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {ddl}"))
                except Exception:
                    pass
        for ddl in indexes:
            try:
                conn.execute(text(ddl))
            except Exception:
                pass
