"""
YouTube Upload Service — OAuth flow, token management, and video upload.

Wraps google-api-python-client with DB-backed credential storage.
"""

import os
import json
import re
import unicodedata
from datetime import datetime
from typing import Optional, Dict, Any

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import VideoJob, UploadHistory

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    HAS_GOOGLE_API = True
except ImportError:
    HttpError = Exception
    HAS_GOOGLE_API = False
    logger.warning("Google API libraries not fully installed. YouTube features will be limited.")


# YouTube API scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# OAuth client config (try environment variables first, fallback to config.toml)
from app.config import config

def _get_client_id():
    return os.environ.get("YOUTUBE_CLIENT_ID") or config.youtube.get("client_id", "")

def _get_client_secret():
    return os.environ.get("YOUTUBE_CLIENT_SECRET") or config.youtube.get("client_secret", "")

_REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8080/api/v1/youtube/callback")


def _sanitize_youtube_text(value: str, max_len: int) -> str:
    """
    Keep text YouTube-safe: normalize Unicode, drop control chars, and trim length.
    """
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove non-printable control characters except newline/tab.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _ascii_safe_text(value: str, max_len: int) -> str:
    """
    Strict fallback for YouTube metadata when provider returns problematic text.
    Keeps only printable ASCII + newlines.
    """
    text = _sanitize_youtube_text(value, max_len=max_len)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\x20-\x7E\n\t]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


# ── OAuth Flow ───────────────────────────────────────────────────────────────

def get_auth_url(channel_id: str) -> str:
    """Generate YouTube OAuth consent URL."""
    _client_id = _get_client_id()
    _client_secret = _get_client_secret()

    if not _client_id or not _client_secret:
        raise ValueError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set")

    client_config = {
        "web": {
            "client_id": _client_id,
            "client_secret": _client_secret,
            "redirect_uris": [_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = _REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=channel_id,  # Embed channel_id in state param
    )
    return auth_url


def handle_oauth_callback(db: Session, code: str, state: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens and store them."""
    channel_id = state
    _client_id = _get_client_id()
    _client_secret = _get_client_secret()

    client_config = {
        "web": {
            "client_id": _client_id,
            "client_secret": _client_secret,
            "redirect_uris": [_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = _REDIRECT_URI
    flow.fetch_token(code=code)

    credentials = flow.credentials
    creds_data = {
        "client_id": _client_id,
        "client_secret": _client_secret,
        "refresh_token": credentials.refresh_token,
        "token": credentials.token,
        "token_uri": credentials.token_uri,
    }

    # Store encrypted credentials
    from app.services.channel_service import store_oauth
    store_oauth(db, channel_id, creds_data)

    return {"success": True, "channel_id": channel_id}


def _get_youtube_service(db: Session, channel_id: str):
    """Build authenticated YouTube API service from stored credentials."""
    from app.services.channel_service import get_oauth
    creds_data = get_oauth(db, channel_id)

    if not creds_data:
        raise ValueError(f"No OAuth credentials for channel {channel_id}")

    credentials = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
    )

    return build("youtube", "v3", credentials=credentials)


# ── Video Upload ─────────────────────────────────────────────────────────────

def upload_video(db: Session, job: VideoJob, monetization_meta=None) -> Dict[str, Any]:
    """
    Upload a video to YouTube for the job's channel.

    Uses provided monetization_meta if available; otherwise falls back to basic generation.
    """
    if not HAS_GOOGLE_API:
        return {"success": False, "error": "Google API libraries not installed"}

    if not job.video_path or not os.path.exists(job.video_path):
        return {"success": False, "error": f"Video file not found: {job.video_path}"}

    try:
        youtube = _get_youtube_service(db, job.channel_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Generate or use provided metadata
    if monetization_meta:
        # Support both Pydantic object and dict payloads
        if isinstance(monetization_meta, dict):
            title = monetization_meta.get("title", "")
            description = monetization_meta.get("description", "")
            tags_raw = monetization_meta.get("tags", [])
        else:
            title = getattr(monetization_meta, "title", "")
            description = getattr(monetization_meta, "description", "")
            tags_raw = getattr(monetization_meta, "tags", [])
        # Ensure tags is a list
        tags = tags_raw if isinstance(tags_raw, list) else [tags_raw]
    else:
        title = _generate_title(job.topic, job.style)
        description = _generate_description(job.topic, job.style)
        tags = _generate_tags(job.topic, job.style)

    privacy_status = (config.youtube.get("privacy_status", "public") or "public").strip().lower()
    if privacy_status not in {"public", "private", "unlisted"}:
        logger.warning(f"Invalid youtube.privacy_status='{privacy_status}', fallback to 'public'")
        privacy_status = "public"

    clean_title = _ascii_safe_text(title, 100) or _ascii_safe_text(job.topic, 100) or "New Video"
    # Use a strict safe description to avoid YouTube invalidDescription rejects.
    clean_description = _ascii_safe_text(description, 5000)
    if not clean_description:
        clean_description = _ascii_safe_text(_generate_description(job.topic, job.style), 5000)
    topic_line = _ascii_safe_text(job.topic, 120) or "Short video"
    if not clean_description:
        clean_description = f"{topic_line}\n\nGenerated by automation."
    clean_tags = [_ascii_safe_text(str(t), 80) for t in (tags or [])]
    clean_tags = [t for t in clean_tags if t]

    body = {
        "snippet": {
            "title": clean_title,
            "description": clean_description,
            "tags": clean_tags[:30],
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    fallback_body = {
        "snippet": {
            # Keep fallback metadata very strict and short.
            "title": _ascii_safe_text(job.topic, 80) or "Short video",
            "description": "Auto upload.",
            "tags": ["shorts", "automation"],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    def _execute_upload(payload: Dict[str, Any]) -> Dict[str, Any]:
        media = MediaFileUpload(
            job.video_path,
            chunksize=1024 * 1024 * 10,  # 10MB chunks
            resumable=True,
        )
        request = youtube.videos().insert(
            part="snippet,status",
            body=payload,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload progress: {int(status.progress() * 100)}%")
        return response or {}

    try:
        response = _execute_upload(body)
    except HttpError as e:
        err_text = str(e)
        if "invalidDescription" in err_text:
            logger.warning("Retrying upload with ultra-safe fallback metadata due to invalidDescription")
            try:
                response = _execute_upload(fallback_body)
                # Persist what was actually used for upload history.
                clean_title = fallback_body["snippet"]["title"]
                clean_description = fallback_body["snippet"]["description"]
                clean_tags = fallback_body["snippet"]["tags"]
            except Exception as retry_e:
                logger.error(f"YouTube upload retry failed: {retry_e}")
                return {"success": False, "error": str(retry_e)}
        else:
            logger.error(f"YouTube upload error: {e}")
            return {"success": False, "error": err_text}
    except Exception as e:
        logger.error(f"YouTube upload error: {e}")
        return {"success": False, "error": str(e)}

    try:
        video_id = response.get("id", "")
        logger.info(f"Upload successful! YouTube video ID: {video_id}")

        # Upload custom thumbnail if provided
        thumbnail_url = ""
        if monetization_meta and hasattr(monetization_meta, 'thumbnail_path') and monetization_meta.thumbnail_path:
            logger.info(f"Uploading custom thumbnail from {monetization_meta.thumbnail_path}...")
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(monetization_meta.thumbnail_path, mimetype='image/jpeg', resumable=True)
                ).execute()
                logger.info("Custom thumbnail uploaded successfully!")
                
                # Get the URL of the uploaded thumbnail (YouTube default format)
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            except Exception as e:
                logger.error(f"Failed to upload custom thumbnail: {e}")

        # Record in upload history
        upload_record = UploadHistory(
            job_id=job.id,
            channel_id=job.channel_id,
            youtube_video_id=video_id,
            title=clean_title,
            description=clean_description,
            tags=",".join(clean_tags),
            privacy_status=privacy_status,
            uploaded_at=datetime.utcnow(),
            thumbnail_url=thumbnail_url,
            external_ids_json=json.dumps({"youtube": video_id}),
            platform_results_json=json.dumps({
                "youtube": {
                    "success": True,
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                }
            }),
        )
        db.add(upload_record)
        db.commit()

        # Clean up generated thumbnail
        if monetization_meta and hasattr(monetization_meta, 'thumbnail_path') and monetization_meta.thumbnail_path:
            try:
                if os.path.exists(monetization_meta.thumbnail_path):
                    os.remove(monetization_meta.thumbnail_path)
            except Exception as e:
                logger.warning(f"Failed to clean up thumbnail {monetization_meta.thumbnail_path}: {e}")

        return {
            "success": True,
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": thumbnail_url,
        }

    except Exception as e:
        logger.error(f"YouTube upload error: {e}")
        return {"success": False, "error": str(e)}


def get_upload_history(
    db: Session,
    channel_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list:
    """Get upload history records."""
    query = db.query(UploadHistory)
    if channel_id:
        query = query.filter(UploadHistory.channel_id == channel_id)
    return query.order_by(UploadHistory.uploaded_at.desc()).offset(skip).limit(limit).all()


def count_uploads(db: Session, channel_id: Optional[str] = None) -> int:
    query = db.query(UploadHistory)
    if channel_id:
        query = query.filter(UploadHistory.channel_id == channel_id)
    return query.count()


# ── Metadata Generation Helpers ──────────────────────────────────────────────

def _generate_title(topic: str, style: str) -> str:
    """Generate a YouTube-optimized title."""
    style_hooks = {
        "dark_psychology": "🧠 ",
        "motivation": "🔥 ",
        "luxury_lifestyle": "💰 ",
        "stoic_philosophy": "📚 ",
        "viral_facts": "🤯 ",
    }
    prefix = style_hooks.get(style, "")
    return f"{prefix}{topic}"


def _generate_description(topic: str, style: str) -> str:
    """Generate a YouTube description."""
    return (
        f"{topic}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Style: {style.replace('_', ' ').title()}\n\n"
        f"👉 Subscribe for more content like this!\n"
        f"🔔 Turn on notifications to never miss a video.\n\n"
        f"#shorts #viral #{style.replace('_', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def _generate_tags(topic: str, style: str) -> list:
    """Generate tags from topic and style."""
    base_tags = ["shorts", "viral", style.replace("_", " ")]
    # Extract words from topic as tags
    topic_words = [w.strip().lower() for w in topic.split() if len(w) > 3]
    return base_tags + topic_words[:10]
