"""
Anti-Automation Fingerprint System — Randomize within cinematic constraints.

Prevents detection of automation patterns by adding bounded randomization to:
- Subtitle timing
- Zoom intensity
- Scene transition rhythm
- Music mood

Maintains cinematic consistency without pattern repetition.
"""

import random
from typing import Dict, List, Optional, Any
from loguru import logger


# ── Subtitle Timing Randomization ────────────────────────────────────────────

def randomize_subtitle_timing(
    timing_offsets: List[float],
    variance_ms: float = 150.0,
) -> List[float]:
    """
    Add ±random millisecond shifts to subtitle timing.
    Prevents perfectly aligned subtitle patterns.

    Args:
        timing_offsets: list of subtitle start times (in seconds)
        variance_ms: max variance in milliseconds (default ±150ms)

    Returns:
        Adjusted timing offsets
    """
    if not timing_offsets:
        return timing_offsets

    variance_s = variance_ms / 1000.0
    adjusted = []
    for offset in timing_offsets:
        shift = random.uniform(-variance_s, variance_s)
        adjusted.append(max(0.0, round(offset + shift, 3)))

    logger.debug(f"subtitle timing randomized: variance=±{variance_ms}ms, count={len(adjusted)}")
    return adjusted


# ── Zoom Intensity Variation ─────────────────────────────────────────────────

def vary_zoom_intensity(
    base_zoom: float = 1.0,
    variance: float = 0.05,
    count: int = 1,
) -> List[float]:
    """
    Generate per-clip zoom variations around a base zoom level.
    Keeps visual consistency while preventing uniform zoom patterns.

    Args:
        base_zoom: base zoom factor (1.0 = no zoom)
        variance: max deviation from base (default ±0.05)
        count: number of zoom values to generate

    Returns:
        List of zoom factors per clip
    """
    zooms = []
    for _ in range(count):
        variation = random.uniform(-variance, variance)
        zoom = max(0.9, min(1.3, base_zoom + variation))
        zooms.append(round(zoom, 3))

    return zooms


# ── Transition Rhythm Randomization ──────────────────────────────────────────

def randomize_transition_rhythm(
    durations: List[float],
    jitter_range: float = 0.25,
) -> List[float]:
    """
    Add mild jitter to transition timing to break uniform patterns.
    Prevents equally-spaced transitions that signal automation.

    Args:
        durations: list of clip durations (seconds)
        jitter_range: max jitter in seconds (default ±0.25s)

    Returns:
        Jittered durations
    """
    if not durations:
        return durations

    adjusted = []
    for dur in durations:
        jitter = random.uniform(-jitter_range, jitter_range)
        new_dur = max(0.8, round(dur + jitter, 2))
        adjusted.append(new_dur)

    return adjusted


# ── Music Mood Variation ─────────────────────────────────────────────────────

ADJACENT_MOODS = {
    "dark":    ["mysterious", "dramatic", "dark"],
    "epic":    ["dramatic", "powerful", "epic"],
    "calm":    ["peaceful", "gentle", "calm"],
    "upbeat":  ["energetic", "cheerful", "upbeat"],
    "dramatic": ["epic", "dark", "dramatic"],
    "mysterious": ["dark", "ethereal", "mysterious"],
    "random":  ["dark", "epic", "calm", "upbeat", "dramatic"],
}


def vary_music_mood(base_mood: str) -> str:
    """
    Add minor mood variation to music selection.
    Selects from adjacent moods to maintain tonal consistency.
    """
    adjacent = ADJACENT_MOODS.get(base_mood, [base_mood])
    if random.random() < 0.35:
        return random.choice(adjacent)
    return base_mood





# ── Per-Clip Fingerprint Variation ───────────────────────────────────────────

def generate_clip_fingerprints(clip_count: int) -> List[Dict[str, Any]]:
    """
    Generate per-clip anti-fingerprint variations.
    Each clip gets slightly different zoom, pan speed, and cut timing.
    """
    fingerprints = []

    for i in range(clip_count):
        fp = {
            "zoom_factor": round(1.0 + random.uniform(-0.04, 0.06), 3),
            "pan_speed": round(random.uniform(0.02, 0.08), 3),
            "cut_offset_ms": round(random.uniform(-100, 100), 0),
            "brightness_micro": round(random.uniform(-0.02, 0.02), 3),
            "speed_factor": round(random.uniform(0.97, 1.03), 3),
        }
        fingerprints.append(fp)

    return fingerprints


# ── Master Anti-Fingerprint Application ──────────────────────────────────────

def apply_anti_fingerprint(
    params=None,
    clip_count: int = 0,
    subtitle_timings: List[float] = None,
) -> Dict[str, Any]:
    """
    Master function applying all anti-fingerprint variations.

    Returns a dict of all variations to apply during rendering:
        {
            "subtitle_timings": [...],
            "zoom_values": [...],
            "music_mood": "...",
            "clip_fingerprints": [...],
        }
    """
    result = {}

    # Subtitle timing
    if subtitle_timings:
        result["subtitle_timings"] = randomize_subtitle_timing(subtitle_timings)
    else:
        result["subtitle_timings"] = []

    # Zoom variation
    result["zoom_values"] = vary_zoom_intensity(
        base_zoom=1.0,
        variance=0.05,
        count=max(clip_count, 1),
    )

    # Music mood
    base_mood = "random"
    if params and hasattr(params, "bgm_type"):
        base_mood = getattr(params, "bgm_type", "random")
    result["music_mood"] = vary_music_mood(base_mood)

    # Per-clip fingerprints
    result["clip_fingerprints"] = generate_clip_fingerprints(max(clip_count, 1))

    logger.info(
        f"anti-fingerprint applied: {clip_count} clips, "
        f"mood={result['music_mood']}"
    )
    return result
