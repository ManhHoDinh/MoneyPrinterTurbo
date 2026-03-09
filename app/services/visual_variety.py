"""
Visual Variety System — Prevents repetitive footage.

Enforces shot composition diversity, URL deduplication,
and environment variation across clip selections.
"""

from typing import List, Set, Dict, Optional
from loguru import logger


# ── Shot Sequence ────────────────────────────────────────────────────────────

SHOT_SEQUENCE = ["wide", "medium", "closeup", "motion"]


def deduplicate_clips(
    candidates: list,
    used_urls: Set[str],
) -> list:
    """
    Remove clips whose URLs have already been used.
    Returns only novel clips.
    """
    novel = []
    for clip in candidates:
        url = ""
        if isinstance(clip, dict):
            url = clip.get("url", "")
        elif hasattr(clip, "url"):
            url = clip.url

        if url and url not in used_urls:
            novel.append(clip)

    removed = len(candidates) - len(novel)
    if removed > 0:
        logger.debug(f"deduplication removed {removed} already-used clips")

    return novel


def enforce_variety(
    candidates: list,
    previous_clips: list,
    max_same_domain: int = 2,
) -> list:
    """
    Score and sort candidates to prefer clips that differ from
    recently used ones. Promotes visual diversity.

    Scoring:
      - Different URL domain from previous clips: +2
      - Different aspect from previous clip: +1
      - Same domain as recent clip: -1 per occurrence
      - Different environment from previous clip: +2 / same: -2
      - Different camera angle from previous clip: +1.5 / same: -1.5
      - Natural motion in clip: +1.5
    """
    if not candidates or not previous_clips:
        return candidates

    # Extract domains from previous clips for comparison
    prev_domains = set()
    for clip in previous_clips[-3:]:  # last 3 clips
        url = clip.get("url", "") if isinstance(clip, dict) else getattr(clip, "url", "")
        domain = _extract_domain(url)
        if domain:
            prev_domains.add(domain)

    # Extract environments and shot types from previous clips
    prev_environments = set()
    prev_shot_types = []
    for clip in previous_clips[-2:]:  # last 2 clips for angle/env
        env = _extract_environment(clip)
        if env:
            prev_environments.add(env)
        shot = clip.get("shot_type", "") if isinstance(clip, dict) else getattr(clip, "shot_type", "")
        if shot:
            prev_shot_types.append(shot)

    scored = []
    for clip in candidates:
        score = 0.0
        url = clip.get("url", "") if isinstance(clip, dict) else getattr(clip, "url", "")
        domain = _extract_domain(url)

        # Reward novel domains
        if domain and domain not in prev_domains:
            score += 2.0
        elif domain in prev_domains:
            score -= 1.0

        # Reward longer duration (more editing flexibility)
        duration = clip.get("duration", 0) if isinstance(clip, dict) else getattr(clip, "duration", 0)
        if duration >= 5:
            score += 1.0

        # Anti-stock-look: Environment dedup
        clip_env = _extract_environment(clip)
        if clip_env and clip_env in prev_environments:
            score -= 2.0  # penalize same environment back-to-back
        elif clip_env and clip_env not in prev_environments:
            score += 2.0  # reward different environment

        # Anti-stock-look: Camera angle dedup
        clip_shot = clip.get("shot_type", "") if isinstance(clip, dict) else getattr(clip, "shot_type", "")
        if clip_shot and prev_shot_types and clip_shot == prev_shot_types[-1]:
            score -= 1.5  # penalize same angle back-to-back
        elif clip_shot and prev_shot_types and clip_shot != prev_shot_types[-1]:
            score += 1.5  # reward different angle

        # Anti-stock-look: Prefer natural motion footage
        if _has_natural_motion(clip):
            score += 1.5

        scored.append((score, clip))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [clip for _, clip in scored]


def _extract_domain(url: str) -> str:
    """Extract a simplified domain from a URL for comparison."""
    if not url:
        return ""
    try:
        # Simple extraction: between :// and first /
        parts = url.split("://", 1)
        if len(parts) > 1:
            domain = parts[1].split("/")[0]
            return domain
        return url.split("/")[0]
    except Exception:
        return ""


def _extract_environment(clip_data) -> str:
    """
    Extract environment type from clip metadata for variety scoring.
    Returns: 'indoor', 'outdoor', 'urban', 'nature', or '' if unknown.
    """
    text = ""
    if isinstance(clip_data, dict):
        text = " ".join([
            str(clip_data.get("tags", "")),
            str(clip_data.get("description", "")),
            str(clip_data.get("alt", "")),
        ]).lower()
    elif hasattr(clip_data, "tags"):
        text = str(getattr(clip_data, "tags", "")).lower()

    if not text:
        return ""

    # Environment classification by keyword matching
    env_keywords = {
        "indoor": {"room", "office", "interior", "inside", "kitchen", "studio", "gym", "home"},
        "outdoor": {"outdoor", "outside", "park", "field", "garden", "beach", "road", "street"},
        "urban": {"city", "urban", "building", "skyscraper", "traffic", "downtown", "skyline"},
        "nature": {"forest", "mountain", "ocean", "river", "tree", "sunset", "sky", "lake", "sea"},
    }

    best_env = ""
    best_count = 0
    for env, keywords in env_keywords.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_count:
            best_count = hits
            best_env = env

    return best_env if best_count >= 1 else ""


def _has_natural_motion(clip_data) -> bool:
    """
    Check if a clip appears to have natural camera motion
    (not static) based on metadata keywords.
    """
    text = ""
    if isinstance(clip_data, dict):
        text = " ".join([
            str(clip_data.get("tags", "")),
            str(clip_data.get("description", "")),
        ]).lower()
    elif hasattr(clip_data, "tags"):
        text = str(getattr(clip_data, "tags", "")).lower()

    motion_keywords = {
        "movement", "tracking", "aerial", "timelapse", "drone",
        "handheld", "panning", "dolly", "gimbal", "steadicam",
        "moving", "flying", "walking", "driving",
    }

    return any(kw in text for kw in motion_keywords)


# ── Clip Selection with Variety ──────────────────────────────────────────────

def select_best_clips(
    candidates_per_scene: Dict[int, list],
    scenes: list,
    max_per_scene: int = 2,
) -> Dict[int, list]:
    """
    Select the best clips for each scene while maintaining variety
    across the entire video.

    Args:
        candidates_per_scene: dict mapping scene_index → list of candidate clips
        scenes: list of SceneSegment objects
        max_per_scene: max clips to select per scene

    Returns:
        dict mapping scene_index → selected clips (best matches)
    """
    used_urls: Set[str] = set()
    selected: Dict[int, list] = {}
    previous_clips: list = []

    for scene in scenes:
        idx = scene.scene_index
        candidates = candidates_per_scene.get(idx, [])

        if not candidates:
            logger.warning(f"scene {idx}: no candidates available")
            selected[idx] = []
            continue

        # Remove already-used clips
        novel = deduplicate_clips(candidates, used_urls)

        # If all clips are used, allow reuse but penalize
        if not novel:
            logger.debug(f"scene {idx}: all candidates used, allowing reuse")
            novel = candidates

        # Enforce variety relative to previous selections
        diverse = enforce_variety(novel, previous_clips)

        # Take top N
        chosen = diverse[:max_per_scene]
        selected[idx] = chosen

        # Track used URLs
        for clip in chosen:
            url = clip.get("url", "") if isinstance(clip, dict) else getattr(clip, "url", "")
            if url:
                used_urls.add(url)
            previous_clips.append(clip)

        logger.debug(f"scene {idx}: selected {len(chosen)} clips from {len(candidates)} candidates")

    return selected


# ── Anti-AI Visual System ────────────────────────────────────────────────────

CAMERA_MOTION_POOL = [
    "ken_burns_zoom", "slow_zoom_in", "slow_zoom_out",
    "pan_left", "pan_right", "parallax_effect", "zoom_in_effect",
]


def enforce_motion_diversity(
    clip_motions: list,
) -> list:
    """
    Ensure no two consecutive clips use the same camera motion effect.

    If a repeat is detected, swap it with a different motion from the pool.
    This prevents the robotic, AI-generated look of uniform camera movements.
    """
    if len(clip_motions) < 2:
        return clip_motions

    import random as _random
    result = list(clip_motions)

    for i in range(1, len(result)):
        if result[i] == result[i - 1]:
            alternatives = [m for m in CAMERA_MOTION_POOL if m != result[i]]
            # Also avoid matching the next clip if possible
            if i + 1 < len(result):
                alternatives = [m for m in alternatives if m != result[i + 1]]
            if alternatives:
                result[i] = _random.choice(alternatives)

    swaps = sum(1 for a, b in zip(clip_motions, result) if a != b)
    if swaps > 0:
        logger.info(f"motion diversity: {swaps} motions swapped to prevent repeats")

    return result


def add_pacing_jitter(
    clip_durations: list,
    jitter_range: float = 0.3,
    min_duration: float = 0.8,
) -> list:
    """
    Add random ±jitter to clip durations to prevent uniform, robotic timing.

    Creates natural-feeling pacing with slight duration variations.
    """
    if not clip_durations:
        return clip_durations

    import random as _random
    jittered = []
    for dur in clip_durations:
        jitter = _random.uniform(-jitter_range, jitter_range)
        new_dur = max(min_duration, dur + jitter)
        jittered.append(round(new_dur, 2))

    return jittered


def randomize_transition_sequence(
    transitions: list,
) -> list:
    """
    Prevent repeating the same transition type consecutively.

    Swaps consecutive identical transitions with alternatives.
    """
    if len(transitions) < 3:
        return transitions

    import random as _random
    TRANSITION_OPTIONS = [None, "FadeIn", "SlideIn"]
    result = list(transitions)

    for i in range(2, len(result)):
        if result[i] == result[i - 1] and result[i] == result[i - 2]:
            # Three in a row — swap the middle one
            alternatives = [t for t in TRANSITION_OPTIONS if t != result[i]]
            if alternatives:
                result[i] = _random.choice(alternatives)

    return result

