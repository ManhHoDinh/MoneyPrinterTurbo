import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from loguru import logger


PlatformUploader = Callable[[str, dict], dict]


def _metadata_to_dict(monetization_meta: Any) -> dict:
    if hasattr(monetization_meta, "to_dict"):
        meta_dict = monetization_meta.to_dict()
    else:
        meta_dict = monetization_meta or {}
    if not isinstance(meta_dict, dict):
        meta_dict = {}
    meta_dict.setdefault("title", "")
    return meta_dict


def _normalize_platforms(platforms: Optional[Iterable[str]]) -> List[str]:
    normalized = []
    seen = set()
    for item in platforms or []:
        value = str(item or "").strip().lower()
        if not value or value == "youtube" or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _stub_upload(platform_code: str, prefix: str, video_path: str, metadata: dict) -> dict:
    logger.info(f"[{platform_code}] Uploading video: {video_path}")
    logger.info(f"[{platform_code}] Metadata: {metadata.get('title', '')}")
    return {
        "success": True,
        "video_id": f"{prefix}_{random.randint(100000, 999999)}",
        "platform": platform_code,
        "provider": "stub",
    }


def upload_tiktok(video_path: str, metadata: dict) -> dict:
    return _stub_upload("tiktok", "tt", video_path, metadata)


def upload_instagram(video_path: str, metadata: dict) -> dict:
    return _stub_upload("instagram", "ig", video_path, metadata)


def upload_facebook(video_path: str, metadata: dict) -> dict:
    return _stub_upload("facebook", "fb", video_path, metadata)


def upload_x(video_path: str, metadata: dict) -> dict:
    return _stub_upload("x", "x", video_path, metadata)


def upload_linkedin(video_path: str, metadata: dict) -> dict:
    return _stub_upload("linkedin", "li", video_path, metadata)


def upload_pinterest(video_path: str, metadata: dict) -> dict:
    return _stub_upload("pinterest", "pin", video_path, metadata)


def upload_snapchat(video_path: str, metadata: dict) -> dict:
    return _stub_upload("snapchat", "snap", video_path, metadata)


def upload_telegram(video_path: str, metadata: dict) -> dict:
    return _stub_upload("telegram", "tg", video_path, metadata)


UPLOADERS: Dict[str, PlatformUploader] = {
    "tiktok": upload_tiktok,
    "instagram": upload_instagram,
    "facebook": upload_facebook,
    "x": upload_x,
    "linkedin": upload_linkedin,
    "pinterest": upload_pinterest,
    "snapchat": upload_snapchat,
    "telegram": upload_telegram,
}


def get_enabled_secondary_platforms(
    target_platforms: Union[Iterable[str], str, None],
    platform_settings_json: str = "",
) -> List[str]:
    if isinstance(target_platforms, str):
        target_platforms = target_platforms.split(",")
    enabled = _normalize_platforms(target_platforms)

    try:
        settings = json.loads(platform_settings_json or "{}")
    except Exception:
        settings = {}

    filtered = []
    for platform in enabled:
        platform_settings = settings.get(platform, {})
        if isinstance(platform_settings, dict) and platform_settings.get("enabled") is False:
            continue
        filtered.append(platform)
    return filtered


def multi_platform_upload(
    video_path: str,
    monetization_meta: Any,
    target_platforms: Union[Iterable[str], str, None] = None,
    platform_settings_json: str = "",
    max_workers: int = 3,
) -> Dict[str, dict]:
    """
    Upload the same video to enabled secondary platforms in parallel.

    YouTube is handled separately by youtube_service; this service focuses on
    additional distribution targets with a stable result contract.
    """
    meta_dict = _metadata_to_dict(monetization_meta)
    enabled_platforms = get_enabled_secondary_platforms(
        target_platforms=target_platforms,
        platform_settings_json=platform_settings_json,
    )
    if not enabled_platforms:
        return {}

    results: Dict[str, dict] = {}
    worker_count = max(1, min(max_workers, len(enabled_platforms)))

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="multi-upload") as executor:
        future_map = {}
        for platform in enabled_platforms:
            uploader = UPLOADERS.get(platform)
            if uploader is None:
                results[platform] = {
                    "success": False,
                    "platform": platform,
                    "error": f"No uploader registered for platform '{platform}'",
                }
                continue
            future_map[executor.submit(uploader, video_path, meta_dict)] = platform

        for future in as_completed(future_map):
            platform = future_map[future]
            try:
                upload_result = future.result()
                if not isinstance(upload_result, dict):
                    raise ValueError("Uploader must return a dict")
                upload_result.setdefault("platform", platform)
                upload_result.setdefault("success", False)
                results[platform] = upload_result
            except Exception as e:
                logger.error(f"{platform} upload failed: {e}")
                results[platform] = {
                    "success": False,
                    "platform": platform,
                    "error": str(e),
                }

    logger.info(f"Multi-platform upload complete. Results: {results}")
    return results
