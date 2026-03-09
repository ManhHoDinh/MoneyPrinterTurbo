"""
Color Mood Matching — Ensures visual color consistency aligned to emotion.

Maps emotion categories to expected color characteristics and provides
scoring/consistency checks for clip selection.
"""

from typing import Dict, List, Optional
from loguru import logger


# ── Emotion → Color Profile ─────────────────────────────────────────────────

EMOTION_COLOR_PROFILES: Dict[str, Dict] = {
    "dramatic": {
        "keywords": ["dark", "shadow", "contrast", "black", "dramatic", "cinematic", "night", "storm"],
        "brightness": "low",       # dark scenes
        "saturation": "moderate",
        "warmth": "cool",
    },
    "calm": {
        "keywords": ["warm", "soft", "golden", "pastel", "gentle", "sunset", "morning", "nature"],
        "brightness": "moderate",
        "saturation": "low",
        "warmth": "warm",
    },
    "luxury": {
        "keywords": ["gold", "bright", "clean", "modern", "elegant", "white", "marble", "crystal"],
        "brightness": "high",
        "saturation": "moderate",
        "warmth": "warm",
    },
    "tension": {
        "keywords": ["dark", "red", "night", "shadow", "rain", "grey", "cold", "harsh"],
        "brightness": "low",
        "saturation": "moderate",
        "warmth": "cool",
    },
    "motivation": {
        "keywords": ["bright", "sunrise", "golden", "warm", "epic", "sky", "powerful", "fire"],
        "brightness": "high",
        "saturation": "high",
        "warmth": "warm",
    },
    "curiosity": {
        "keywords": ["colorful", "vibrant", "light", "interesting", "detail", "macro", "nature"],
        "brightness": "moderate",
        "saturation": "high",
        "warmth": "neutral",
    },
    "sadness": {
        "keywords": ["grey", "rain", "cold", "muted", "blue", "empty", "quiet", "fog"],
        "brightness": "low",
        "saturation": "low",
        "warmth": "cool",
    },
    "inspiration": {
        "keywords": ["bright", "sky", "stars", "light", "space", "colorful", "vivid", "glow"],
        "brightness": "high",
        "saturation": "high",
        "warmth": "neutral",
    },
    "mystery": {
        "keywords": ["dark", "fog", "shadow", "night", "candle", "dim", "misty", "moody"],
        "brightness": "low",
        "saturation": "low",
        "warmth": "cool",
    },
    "energetic": {
        "keywords": ["neon", "bright", "vivid", "colorful", "fast", "dynamic", "electric", "bold"],
        "brightness": "high",
        "saturation": "high",
        "warmth": "neutral",
    },
}

# Brightness compatibility rules
BRIGHTNESS_LEVELS = {"low": 0, "moderate": 1, "high": 2}


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_color_mood(clip_data: dict, emotion: str) -> float:
    """
    Score how well a clip's metadata matches the expected color mood
    for a given emotion.

    Scoring (0-3 scale):
      - Keyword overlap with clip tags/description (0-2 points)
      - Brightness alignment based on clip metadata (0-1 point)

    Uses clip tags, description, and any available metadata from stock APIs.
    """
    profile = EMOTION_COLOR_PROFILES.get(emotion, EMOTION_COLOR_PROFILES["dramatic"])
    score = 0.0

    # Extract searchable text from clip data
    clip_text = ""
    if isinstance(clip_data, dict):
        clip_text = " ".join([
            str(clip_data.get("tags", "")),
            str(clip_data.get("description", "")),
            str(clip_data.get("alt", "")),
            str(clip_data.get("title", "")),
        ]).lower()

    # Keyword overlap scoring (0-2 points)
    if clip_text:
        mood_keywords = profile["keywords"]
        matches = sum(1 for kw in mood_keywords if kw in clip_text)
        keyword_score = min(2.0, matches * 0.5)  # 0.5 per match, max 2
        score += keyword_score

    # Brightness alignment (0-1 point)
    # Infer brightness from clip metadata if available
    clip_brightness = _infer_brightness(clip_data)
    expected_brightness = profile["brightness"]
    if clip_brightness and expected_brightness:
        expected_level = BRIGHTNESS_LEVELS.get(expected_brightness, 1)
        clip_level = BRIGHTNESS_LEVELS.get(clip_brightness, 1)
        if clip_level == expected_level:
            score += 1.0
        elif abs(clip_level - expected_level) == 1:
            score += 0.5
        # else: 0 points for opposing brightness

    return round(score, 2)


def _infer_brightness(clip_data: dict) -> Optional[str]:
    """
    Infer brightness level from clip metadata.
    Uses tags and description to guess if the clip is dark, moderate, or bright.
    """
    if not isinstance(clip_data, dict):
        return None

    text = " ".join([
        str(clip_data.get("tags", "")),
        str(clip_data.get("description", "")),
    ]).lower()

    dark_cues = {"dark", "night", "shadow", "dim", "black", "moody", "storm", "grey"}
    bright_cues = {"bright", "sunny", "light", "white", "gold", "vivid", "neon", "sunrise"}

    dark_hits = sum(1 for c in dark_cues if c in text)
    bright_hits = sum(1 for c in bright_cues if c in text)

    if dark_hits > bright_hits and dark_hits >= 2:
        return "low"
    elif bright_hits > dark_hits and bright_hits >= 2:
        return "high"
    return "moderate"


# ── Consistency Checking ─────────────────────────────────────────────────────

def check_color_consistency(
    selected_clips: list,
    scenes: list,
) -> List[Dict]:
    """
    Check color mood consistency across adjacent clips.
    Returns a list of warnings for mismatched adjacent scenes.

    Each warning includes:
      - scene_index: which scene pair is mismatched
      - severity: "low", "medium", "high"
      - message: description
    """
    warnings = []

    for i in range(1, min(len(selected_clips), len(scenes))):
        prev_emotion = scenes[i - 1].emotion if hasattr(scenes[i - 1], "emotion") else "dramatic"
        curr_emotion = scenes[i].emotion if hasattr(scenes[i], "emotion") else "dramatic"

        prev_profile = EMOTION_COLOR_PROFILES.get(prev_emotion, EMOTION_COLOR_PROFILES["dramatic"])
        curr_profile = EMOTION_COLOR_PROFILES.get(curr_emotion, EMOTION_COLOR_PROFILES["dramatic"])

        # Check brightness mismatch
        prev_level = BRIGHTNESS_LEVELS.get(prev_profile["brightness"], 1)
        curr_level = BRIGHTNESS_LEVELS.get(curr_profile["brightness"], 1)
        brightness_jump = abs(prev_level - curr_level)

        # Check warmth mismatch
        warmth_mismatch = prev_profile["warmth"] != curr_profile["warmth"]

        if brightness_jump >= 2 and warmth_mismatch:
            warnings.append({
                "scene_index": i,
                "severity": "high",
                "message": f"Sharp color mood shift: {prev_emotion}→{curr_emotion} (brightness + warmth mismatch)",
            })
        elif brightness_jump >= 2:
            warnings.append({
                "scene_index": i,
                "severity": "medium",
                "message": f"Brightness jump: {prev_emotion}→{curr_emotion}",
            })

    if warnings:
        logger.warning(f"color consistency: {len(warnings)} potential mismatches detected")
        for w in warnings:
            logger.debug(f"  scene {w['scene_index']}: [{w['severity']}] {w['message']}")

    return warnings
