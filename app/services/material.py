import os
import random
from typing import List, Optional
from urllib.parse import urlencode

import requests
from loguru import logger
from moviepy.video.io.VideoFileClip import VideoFileClip

from app.config import config
from app.models.schema import MaterialInfo, VideoAspect, VideoConcatMode
from app.utils import utils

requested_count = 0


# ── Quality Scoring ──────────────────────────────────────────────────────────

def score_clip_quality(
    width: int = 0,
    height: int = 0,
    duration: int = 0,
    has_hd: bool = False,
) -> float:
    """
    Score a clip's quality on a 0-10 scale.
    Prefers: high resolution, moderate duration, HD flag.
    """
    score = 0.0

    # Resolution scoring (0-4 points)
    max_dim = max(width, height)
    if max_dim >= 1920:
        score += 4.0  # 4K/Full HD
    elif max_dim >= 1280:
        score += 3.0  # HD
    elif max_dim >= 720:
        score += 2.0  # SD
    elif max_dim >= 480:
        score += 1.0

    # Duration scoring (0-3 points)
    if 3 <= duration <= 15:
        score += 3.0  # ideal range for clips
    elif 2 <= duration < 3:
        score += 2.0
    elif duration > 15:
        score += 1.5  # usable but long
    elif duration >= 1:
        score += 1.0

    # HD flag bonus (0-2 points)
    if has_hd:
        score += 2.0

    # Camera movement heuristic: longer clips > 3s are more likely
    # to have camera movement (0-1 point)
    if duration >= 4:
        score += 1.0

    return min(10.0, score)


def get_api_key(cfg_key: str):
    api_keys = config.app.get(cfg_key)
    if not api_keys:
        raise ValueError(
            f"\n\n##### {cfg_key} is not set #####\n\nPlease set it in the config.toml file: {config.config_file}\n\n"
            f"{utils.to_json(config.app)}"
        )

    # if only one key is provided, return it
    if isinstance(api_keys, str):
        return api_keys

    global requested_count
    requested_count += 1
    return api_keys[requested_count % len(api_keys)]


def search_videos_pexels(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)
    video_orientation = aspect.name
    video_width, video_height = aspect.to_resolution()
    api_key = get_api_key("pexels_api_keys")
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
    # Build URL
    params = {"query": search_term, "per_page": 20, "orientation": video_orientation}
    query_url = f"https://api.pexels.com/videos/search?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=False,
            timeout=(30, 60),
        )
        response = r.json()
        video_items = []
        if "videos" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["videos"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["video_files"]
            # loop through each url to determine the best quality
            for video in video_files:
                w = int(video["width"])
                h = int(video["height"])
                if w == video_width and h == video_height:
                    quality = score_clip_quality(
                        width=w, height=h, duration=duration,
                        has_hd=(video.get("quality", "") == "hd"),
                    )
                    item = MaterialInfo()
                    item.provider = "pexels"
                    item.url = video["link"]
                    item.duration = duration
                    item.quality_score = quality
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def search_videos_pixabay(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)

    video_width, video_height = aspect.to_resolution()

    api_key = get_api_key("pixabay_api_keys")
    # Build URL
    params = {
        "q": search_term,
        "video_type": "all",  # Accepted values: "all", "film", "animation"
        "per_page": 50,
        "key": api_key,
    }
    query_url = f"https://pixabay.com/api/videos/?{urlencode(params)}"
    logger.info(f"searching videos: {query_url}, with proxies: {config.proxy}")

    try:
        r = requests.get(
            query_url, proxies=config.proxy, verify=False, timeout=(30, 60)
        )
        response = r.json()
        video_items = []
        if "hits" not in response:
            logger.error(f"search videos failed: {response}")
            return video_items
        videos = response["hits"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["videos"]
            # loop through each url to determine the best quality
            for video_type in video_files:
                video = video_files[video_type]
                w = int(video["width"])
                # h = int(video["height"])
                if w >= video_width:
                    h = int(video.get("height", 0))
                    quality = score_clip_quality(
                        width=w, height=h, duration=duration,
                        has_hd=(video_type in ["large", "medium"]),
                    )
                    item = MaterialInfo()
                    item.provider = "pixabay"
                    item.url = video["url"]
                    item.duration = duration
                    item.quality_score = quality
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(f"search videos failed: {str(e)}")

    return []


def save_video(video_url: str, save_dir: str = "") -> str:
    if not save_dir:
        save_dir = utils.storage_dir("cache_videos")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    url_without_query = video_url.split("?")[0]
    url_hash = utils.md5(url_without_query)
    video_id = f"vid-{url_hash}"
    video_path = f"{save_dir}/{video_id}.mp4"

    # if video already exists, return the path
    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"video already exists: {video_path}")
        return video_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # if video does not exist, download it
    with open(video_path, "wb") as f:
        f.write(
            requests.get(
                video_url,
                headers=headers,
                proxies=config.proxy,
                verify=False,
                timeout=(60, 240),
            ).content
        )

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            clip.close()
            if duration > 0 and fps > 0:
                return video_path
        except Exception as e:
            try:
                os.remove(video_path)
            except Exception:
                pass
            logger.warning(f"invalid video file: {video_path} => {str(e)}")
    return ""


def download_videos(
    task_id: str,
    search_terms: List[str],
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_contact_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> List[str]:
    max_material_clips = int(config.app.get("max_material_clips", 12) or 12)
    valid_video_items = []
    valid_video_urls = []
    found_duration = 0.0
    search_videos = search_videos_pexels
    if source == "pixabay":
        search_videos = search_videos_pixabay

    for search_term in search_terms:
        video_items = search_videos(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        for item in video_items:
            if item.url not in valid_video_urls:
                valid_video_items.append(item)
                valid_video_urls.append(item.url)
                found_duration += item.duration

    # Sort by quality score (best first)
    valid_video_items.sort(key=lambda x: x.quality_score, reverse=True)

    # Filter out very low quality clips (score < 3)
    quality_threshold = 3.0
    quality_filtered = [v for v in valid_video_items if v.quality_score >= quality_threshold]
    if quality_filtered:
        logger.info(f"quality filter: {len(valid_video_items)} → {len(quality_filtered)} clips (threshold={quality_threshold})")
        valid_video_items = quality_filtered
    else:
        logger.warning("quality filter would remove all clips, keeping all")

    logger.info(
        f"found total videos: {len(valid_video_items)}, required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )
    video_paths = []

    material_directory = config.app.get("material_directory", "").strip()
    if material_directory == "task":
        material_directory = utils.task_dir(task_id)
    elif material_directory and not os.path.isdir(material_directory):
        material_directory = ""

    if video_contact_mode.value == VideoConcatMode.random.value:
        random.shuffle(valid_video_items)

    total_duration = 0.0
    for item in valid_video_items:
        try:
            logger.info(f"downloading video: {item.url} (quality={item.quality_score:.1f})")
            saved_video_path = save_video(
                video_url=item.url, save_dir=material_directory
            )
            if saved_video_path:
                logger.info(f"video saved: {saved_video_path}")
                video_paths.append(saved_video_path)
                seconds = min(max_clip_duration, item.duration)
                total_duration += seconds
                if total_duration > audio_duration:
                    logger.info(
                        f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
                    )
                    break
                if len(video_paths) >= max_material_clips:
                    logger.info(
                        f"material clip cap reached: {len(video_paths)} clips (max_material_clips={max_material_clips})"
                    )
                    break
        except Exception as e:
            logger.error(f"failed to download video: {utils.to_json(item)} => {str(e)}")
    logger.success(f"downloaded {len(video_paths)} videos")
    return video_paths


# ── Emotion-Aware Per-Scene Search ───────────────────────────────────────────

def download_videos_for_scenes(
    task_id: str,
    scenes: list,
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
) -> List[str]:
    """
    Download videos using per-scene emotion-enriched search queries.
    Searches for each scene's query separately for better emotional matching,
    applies quality filtering, and enforces variety.
    """
    from app.services.visual_variety import deduplicate_clips

    max_material_clips = int(config.app.get("max_material_clips", 12) or 12)
    search_videos = search_videos_pexels
    if source == "pixabay":
        search_videos = search_videos_pixabay

    all_video_items = []
    used_urls = set()

    for scene in scenes:
        query = scene.search_query
        if not query:
            logger.warning(f"scene {scene.scene_index}: no search query, skipping")
            continue

        logger.info(f"scene {scene.scene_index} [{scene.emotion}]: searching '{query}'")

        video_items = search_videos(
            search_term=query,
            minimum_duration=max(2, max_clip_duration - 2),  # slightly relaxed
            video_aspect=video_aspect,
        )

        # Tag items with scene metadata
        for item in video_items:
            item.scene_index = scene.scene_index
            item.emotion = scene.emotion

        # Deduplicate against already-found clips
        novel_items = deduplicate_clips(video_items, used_urls)

        # Sort by quality
        novel_items.sort(key=lambda x: x.quality_score, reverse=True)

        # Take top candidates (max 5 per scene for variety)
        top_items = novel_items[:5]

        for item in top_items:
            if item.url not in used_urls:
                all_video_items.append(item)
                used_urls.add(item.url)

        logger.info(f"scene {scene.scene_index}: found {len(video_items)} clips, selected {len(top_items)} (quality-ranked)")

        # If a scene finds nothing, try a simpler fallback query
        if not top_items and scene.topic:
            logger.warning(f"scene {scene.scene_index}: no results for '{query}', trying fallback '{scene.topic}'")
            fallback_items = search_videos(
                search_term=scene.topic,
                minimum_duration=max(2, max_clip_duration - 2),
                video_aspect=video_aspect,
            )
            for fi in fallback_items[:3]:
                fi.scene_index = scene.scene_index
                fi.emotion = scene.emotion
                if fi.url not in used_urls:
                    all_video_items.append(fi)
                    used_urls.add(fi.url)

    # Quality filter on combined results
    quality_threshold = 3.0
    quality_items = [v for v in all_video_items if v.quality_score >= quality_threshold]
    if quality_items:
        all_video_items = quality_items
        logger.info(f"quality filter: kept {len(quality_items)} clips")

    found_duration = sum(item.duration for item in all_video_items)
    logger.info(
        f"emotion search: {len(all_video_items)} total clips, "
        f"required: {audio_duration}s, found: {found_duration}s"
    )

    # Download
    material_directory = config.app.get("material_directory", "").strip()
    if material_directory == "task":
        material_directory = utils.task_dir(task_id)
    elif material_directory and not os.path.isdir(material_directory):
        material_directory = ""

    video_paths = []
    total_duration = 0.0

    for item in all_video_items:
        try:
            logger.info(f"downloading: [{item.emotion}] {item.url} (quality={item.quality_score:.1f})")
            saved_video_path = save_video(video_url=item.url, save_dir=material_directory)
            if saved_video_path:
                video_paths.append(saved_video_path)
                seconds = min(max_clip_duration, item.duration)
                total_duration += seconds
                if total_duration > audio_duration:
                    logger.info(f"sufficient footage downloaded: {total_duration:.1f}s")
                    break
                if len(video_paths) >= max_material_clips:
                    logger.info(
                        f"material clip cap reached: {len(video_paths)} clips (max_material_clips={max_material_clips})"
                    )
                    break
        except Exception as e:
            logger.error(f"failed to download video: {str(e)}")

    logger.success(f"emotion-aware download complete: {len(video_paths)} videos")
    return video_paths


if __name__ == "__main__":
    download_videos(
        "test123", ["Money Exchange Medium"], audio_duration=100, source="pixabay"
    )
