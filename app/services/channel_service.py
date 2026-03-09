"""
Channel Service - CRUD operations with encrypted credential storage.
"""

import json
import os
from datetime import datetime
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import Channel, ScheduleConfig
from app.models.channel_schemas import ChannelCreate, ChannelUpdate, ChannelOut, ScheduleOut


# Stable encryption key storage
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_storage_dir = os.path.join(_project_root, "storage")
_key_file = os.path.join(_storage_dir, ".encryption_key")


def _normalize_csv_list(values, *, default: List[str]) -> str:
    if values is None:
        values = default
    if isinstance(values, str):
        raw_values = values.split(",")
    else:
        raw_values = list(values or [])
    normalized = []
    seen = set()
    for item in raw_values:
        value = str(item or "").strip().lower()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    if not normalized:
        normalized = list(default)
    return ",".join(normalized)


def _split_csv_list(value: str, *, default: List[str]) -> List[str]:
    if not value:
        return list(default)
    items = [part.strip().lower() for part in value.split(",") if part.strip()]
    return items or list(default)


def _get_or_create_encryption_key() -> str:
    env_key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if env_key:
        return env_key

    os.makedirs(_storage_dir, exist_ok=True)
    if os.path.isfile(_key_file):
        with open(_key_file, "r", encoding="utf-8") as f:
            file_key = f.read().strip()
            if file_key:
                os.environ["ENCRYPTION_KEY"] = file_key
                return file_key

    generated = Fernet.generate_key().decode()
    with open(_key_file, "w", encoding="utf-8") as f:
        f.write(generated)
    os.environ["ENCRYPTION_KEY"] = generated
    logger.warning(f"ENCRYPTION_KEY not set - generated and persisted to {_key_file}")
    return generated


def _get_fernet() -> Fernet:
    key = _get_or_create_encryption_key()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_credentials(data: dict) -> str:
    f = _get_fernet()
    return f.encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(token: str) -> dict:
    if not token:
        return {}
    try:
        f = _get_fernet()
        return json.loads(f.decrypt(token.encode()).decode())
    except InvalidToken as e:
        raise ValueError(
            "Stored OAuth credentials cannot be decrypted. "
            "Set a stable ENCRYPTION_KEY and reconnect YouTube OAuth for this channel."
        ) from e


def create_channel(db: Session, payload: ChannelCreate) -> Channel:
    channel = Channel(
        name=payload.name,
        youtube_account=payload.youtube_account,
        niche_type=payload.niche_type,
        style_preset=payload.style_preset,
        upload_frequency=payload.upload_frequency,
        daily_video_limit=payload.daily_video_limit,
        target_languages=_normalize_csv_list(payload.target_languages, default=["en"]),
        target_platforms=_normalize_csv_list(payload.target_platforms, default=["youtube"]),
        max_pending_jobs=payload.max_pending_jobs,
    )
    db.add(channel)
    db.flush()

    schedule = ScheduleConfig(
        channel_id=channel.id,
        cron_expression=payload.cron_expression,
        videos_per_run=payload.videos_per_run,
    )
    db.add(schedule)
    db.commit()
    db.refresh(channel)
    logger.info(f"Created channel: {channel.name} [{channel.id}]")
    return channel


def get_channel(db: Session, channel_id: str) -> Optional[Channel]:
    return db.query(Channel).filter(Channel.id == channel_id).first()


def list_channels(db: Session, skip: int = 0, limit: int = 100) -> List[Channel]:
    return db.query(Channel).offset(skip).limit(limit).all()


def count_channels(db: Session) -> int:
    return db.query(Channel).count()


def update_channel(db: Session, channel_id: str, payload: ChannelUpdate) -> Optional[Channel]:
    channel = get_channel(db, channel_id)
    if not channel:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    schedule_fields = {}
    if "cron_expression" in update_data:
        schedule_fields["cron_expression"] = update_data.pop("cron_expression")
    if "videos_per_run" in update_data:
        schedule_fields["videos_per_run"] = update_data.pop("videos_per_run")

    for field, value in update_data.items():
        if field == "target_languages":
            value = _normalize_csv_list(value, default=["en"])
        elif field == "target_platforms":
            value = _normalize_csv_list(value, default=["youtube"])
        setattr(channel, field, value)
    channel.updated_at = datetime.utcnow()

    if schedule_fields and channel.schedule:
        for field, value in schedule_fields.items():
            setattr(channel.schedule, field, value)

    db.commit()
    db.refresh(channel)
    logger.info(f"Updated channel: {channel.name} [{channel.id}]")
    return channel


def delete_channel(db: Session, channel_id: str) -> bool:
    channel = get_channel(db, channel_id)
    if not channel:
        return False
    db.delete(channel)
    db.commit()
    logger.info(f"Deleted channel: {channel_id}")
    return True


def store_oauth(db: Session, channel_id: str, credentials: dict) -> bool:
    channel = get_channel(db, channel_id)
    if not channel:
        return False
    channel.encrypted_oauth_credentials = encrypt_credentials(credentials)
    channel.updated_at = datetime.utcnow()
    db.commit()
    logger.info(f"Stored OAuth credentials for channel [{channel_id[:8]}]")
    return True


def get_oauth(db: Session, channel_id: str) -> dict:
    channel = get_channel(db, channel_id)
    if not channel or not channel.encrypted_oauth_credentials:
        return {}
    return decrypt_credentials(channel.encrypted_oauth_credentials)


def channel_to_out(channel: Channel) -> ChannelOut:
    schedule_out = None
    if channel.schedule:
        schedule_out = ScheduleOut.model_validate(channel.schedule)

    return ChannelOut(
        id=channel.id,
        name=channel.name,
        youtube_account=channel.youtube_account,
        niche_type=channel.niche_type,
        style_preset=channel.style_preset,
        upload_frequency=channel.upload_frequency,
        daily_video_limit=channel.daily_video_limit,
        target_languages=_split_csv_list(channel.target_languages, default=["en"]),
        target_platforms=_split_csv_list(channel.target_platforms, default=["youtube"]),
        max_pending_jobs=channel.max_pending_jobs or 6,
        is_active=channel.is_active,
        has_oauth=bool(channel.encrypted_oauth_credentials),
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        schedule=schedule_out,
    )
