"""
Retention Optimization Logic — Enforce visual change rules for maximum retention.

Applies scientific retention rules:
- Visual change every 2-4 seconds
- New visual element every 5-7 seconds
- Surprise moment every 10-15 seconds
"""

import random
from typing import List, Dict, Optional, Tuple
from loguru import logger


# ── Retention Rules ──────────────────────────────────────────────────────────

DEFAULT_RETENTION_RULES = {
    "visual_change_interval": (2.0, 4.0),     # visual change every 2-4 seconds
    "new_element_interval": (5.0, 7.0),        # new visual element every 5-7 seconds
    "surprise_interval": (10.0, 15.0),         # surprise moment every 10-15 seconds
    "max_static_duration": 4.0,                # never hold static longer than 4s
    "min_clip_duration": 1.0,                  # never cut shorter than 1s
}

# Surprise effect types used to break visual monotony
SURPRISE_EFFECTS = [
    "zoom_punch",       # quick zoom-in then back
    "pan_switch",       # switch pan direction
    "speed_ramp",       # brief speed change
    "contrast_flash",   # brightness pulse
    "camera_shake",     # subtle shake effect
]

# Camera motion types for diversity
CAMERA_MOTIONS = [
    "ken_burns_zoom",
    "slow_zoom_in",
    "slow_zoom_out",
    "pan_left",
    "pan_right",
    "parallax_effect",
    "zoom_in_effect",
    "static",
]


# ── Retention Optimization ──────────────────────────────────────────────────

def optimize_retention(
    clip_durations: List[float],
    scenes: list = None,
    rules: dict = None,
) -> List[float]:
    """
    Adjust clip durations to enforce retention rules.

    Ensures:
    - No clip exceeds max_static_duration
    - Visual changes happen within the 2-4 second window
    - Clips aren't too short (min 1s)

    Returns adjusted clip durations.
    """
    if not clip_durations:
        return clip_durations

    config = {**DEFAULT_RETENTION_RULES, **(rules or {})}
    max_dur = config["max_static_duration"]
    min_dur = config["min_clip_duration"]
    visual_min, visual_max = config["visual_change_interval"]

    optimized = []
    for i, dur in enumerate(clip_durations):
        # Cap maximum duration
        if dur > max_dur:
            dur = max_dur

        # Ensure minimum duration
        if dur < min_dur:
            dur = min_dur

        # For body scenes, target the visual change window
        if scenes and i < len(scenes):
            role = getattr(scenes[i], "narrative_role", "body")
            if role == "hook":
                # Hook clips should be fast
                dur = min(dur, 2.0)
            elif role == "climax":
                # Climax can hold slightly longer
                dur = min(dur, max_dur + 1.0)

        # Clamp to visual change interval
        dur = max(min_dur, min(dur, visual_max))

        optimized.append(round(dur, 2))

    logger.info(
        f"retention optimizer: adjusted {len(optimized)} clips, "
        f"avg duration {sum(optimized)/len(optimized):.1f}s"
    )
    return optimized


# ── Surprise Moment Insertion ────────────────────────────────────────────────

def plan_surprise_moments(
    total_duration: float,
    rules: dict = None,
) -> List[Dict]:
    """
    Plan surprise moments throughout the video at strategic intervals.

    Returns a list of dicts with:
    - timestamp: when the surprise should occur (seconds)
    - effect: which surprise effect to apply
    """
    config = {**DEFAULT_RETENTION_RULES, **(rules or {})}
    surprise_min, surprise_max = config["surprise_interval"]

    moments = []
    t = random.uniform(surprise_min, surprise_max)

    while t < total_duration - 2.0:  # don't add surprise in last 2 seconds
        effect = random.choice(SURPRISE_EFFECTS)
        moments.append({
            "timestamp": round(t, 2),
            "effect": effect,
        })
        t += random.uniform(surprise_min, surprise_max)

    logger.info(f"planned {len(moments)} surprise moments across {total_duration:.0f}s video")
    return moments


def assign_surprise_to_clips(
    clip_durations: List[float],
    surprise_moments: List[Dict],
) -> List[Dict]:
    """
    Map surprise moments to specific clip indices.

    Returns a list of dicts with clip_index and effect name.
    """
    if not clip_durations or not surprise_moments:
        return []

    # Build cumulative timestamps
    cum_times = []
    t = 0.0
    for dur in clip_durations:
        t += dur
        cum_times.append(t)

    assignments = []
    for moment in surprise_moments:
        ts = moment["timestamp"]
        # Find which clip this falls into
        for i, end_time in enumerate(cum_times):
            start_time = cum_times[i - 1] if i > 0 else 0.0
            if start_time <= ts < end_time:
                assignments.append({
                    "clip_index": i,
                    "effect": moment["effect"],
                    "timestamp": ts,
                })
                break

    return assignments


# ── Camera Motion Diversity (Anti-AI) ────────────────────────────────────────

def diversify_camera_motions(
    clip_count: int,
    scenes: list = None,
) -> List[str]:
    """
    Assign diverse camera motions to clips, preventing consecutive repeats.

    Rules:
    - No same motion twice in a row
    - Hook clips get dynamic motions
    - Climax clips get slow push-in
    - Ending clips get slow zoom-out
    - Body clips cycle through varied motions
    """
    if clip_count <= 0:
        return []

    motions = []
    body_pool = ["ken_burns_zoom", "pan_left", "pan_right", "parallax_effect", "slow_zoom_in"]
    body_idx = 0

    for i in range(clip_count):
        role = "body"
        if scenes and i < len(scenes):
            role = getattr(scenes[i], "narrative_role", "body")

        if role == "hook":
            motion = "ken_burns_zoom"
        elif role == "climax":
            motion = "slow_zoom_in"
        elif role == "ending":
            motion = "slow_zoom_out"
        else:
            motion = body_pool[body_idx % len(body_pool)]
            body_idx += 1

        # Prevent same motion consecutive
        if motions and motion == motions[-1]:
            alternatives = [m for m in body_pool if m != motion]
            motion = random.choice(alternatives) if alternatives else motion

        motions.append(motion)

    logger.info(f"assigned {len(motions)} diverse camera motions (unique: {len(set(motions))})")
    return motions


# ── Pacing Jitter (Natural Feel) ─────────────────────────────────────────────

def add_pacing_jitter(
    clip_durations: List[float],
    jitter_range: float = 0.3,
) -> List[float]:
    """
    Add random ±jitter to clip durations for natural, non-robotic pacing.

    This prevents the AI-generated feel of perfectly uniform clip lengths.
    """
    if not clip_durations:
        return clip_durations

    jittered = []
    for dur in clip_durations:
        jitter = random.uniform(-jitter_range, jitter_range)
        new_dur = max(0.8, dur + jitter)  # minimum 0.8s
        jittered.append(round(new_dur, 2))

    return jittered


# ── Retention Scoring ────────────────────────────────────────────────────────

def validate_retention(
    clip_durations: List[float],
    rules: dict = None,
) -> Dict:
    """
    Score a clip sequence on retention metrics.

    Returns a dict with:
    - score: 0-100 retention quality score
    - issues: list of identified problems
    - stats: duration statistics
    """
    if not clip_durations:
        return {"score": 0, "issues": ["no clips"], "stats": {}}

    config = {**DEFAULT_RETENTION_RULES, **(rules or {})}
    visual_min, visual_max = config["visual_change_interval"]
    max_static = config["max_static_duration"]

    issues = []
    score = 100

    # Stat calculations
    avg_dur = sum(clip_durations) / len(clip_durations)
    max_dur = max(clip_durations)
    min_dur = min(clip_durations)
    total_dur = sum(clip_durations)

    # Check for clips too long (boring)
    long_clips = [i for i, d in enumerate(clip_durations) if d > max_static]
    if long_clips:
        penalty = len(long_clips) * 10
        score -= penalty
        issues.append(f"{len(long_clips)} clips exceed {max_static}s static limit")

    # Check for clips too short (jarring)
    short_clips = [i for i, d in enumerate(clip_durations) if d < 0.5]
    if short_clips:
        penalty = len(short_clips) * 5
        score -= penalty
        issues.append(f"{len(short_clips)} clips shorter than 0.5s")

    # Check avg duration is in sweet spot
    if avg_dur > visual_max:
        score -= 15
        issues.append(f"avg clip duration ({avg_dur:.1f}s) too slow for retention")
    elif avg_dur < visual_min:
        score -= 10
        issues.append(f"avg clip duration ({avg_dur:.1f}s) too fast (may feel chaotic)")

    # Check for monotonous pacing (all same duration ±0.2s)
    if max_dur - min_dur < 0.3 and len(clip_durations) > 3:
        score -= 20
        issues.append("uniform pacing detected — feels robotic/AI-generated")

    # Check surprise interval coverage
    if total_dur > 15 and len(clip_durations) < total_dur / 5:
        score -= 10
        issues.append("not enough visual changes for retention")

    score = max(0, min(100, score))

    result = {
        "score": score,
        "issues": issues,
        "stats": {
            "total_duration": round(total_dur, 1),
            "clip_count": len(clip_durations),
            "avg_duration": round(avg_dur, 2),
            "min_duration": round(min_dur, 2),
            "max_duration": round(max_dur, 2),
        },
    }

    if issues:
        logger.warning(f"retention score: {score}/100 — {len(issues)} issues found")
        for issue in issues:
            logger.debug(f"  ⚠ {issue}")
    else:
        logger.info(f"retention score: {score}/100 — excellent")

    return result


# ── Retention Cadence Enforcement (GOD MODE) ─────────────────────────────────

PATTERN_INTERRUPT_EFFECTS = [
    "zoom_punch",
    "contrast_flash",
    "camera_shake",
    "speed_ramp",
]

IMPERFECTION_TYPES = [
    "slight_delay",       # 0.1-0.3s delay before cut
    "early_cut",          # cut 0.1-0.2s early
    "timing_drift",       # cut point slightly off-beat
    "hold_extend",        # hold 0.2-0.5s longer than expected
    "soft_cut",           # imprecise cut point
]


def enforce_retention_cadence(
    clip_durations: List[float],
    scenes: list = None,
    rules: dict = None,
) -> Dict:
    """
    Master retention function enforcing all three cadence rules:
    - Visual change every 2-4 seconds
    - Pattern interrupt every 6-10 seconds
    - Surprise element every 12-15 seconds
    
    If pacing becomes predictable → forces disruption.
    
    Returns:
        {
            "clip_durations": [...],       # adjusted durations
            "pattern_interrupts": [...],   # interrupt positions
            "surprise_moments": [...],     # surprise effect assignments
            "retention_score": 85,
            "disruptions_added": 2,
        }
    """
    if not clip_durations:
        return {"clip_durations": [], "pattern_interrupts": [],
                "surprise_moments": [], "retention_score": 0, "disruptions_added": 0}

    config = {**DEFAULT_RETENTION_RULES, **(rules or {})}

    # 1. Optimize clip durations (2-4s visual change cadence)
    adjusted = optimize_retention(clip_durations, scenes, rules)

    # 2. Add imperfection jitter for natural feel
    adjusted = inject_imperfections(adjusted)

    # 3. Detect and disrupt predictable patterns
    adjusted, disruption_count = detect_predictable_patterns(adjusted)

    # 4. Plan pattern interrupts every 6-10 seconds
    total_dur = sum(adjusted)
    pattern_interrupts = _plan_pattern_interrupts(adjusted, interval=(6.0, 10.0))

    # 5. Plan surprise moments every 12-15 seconds
    surprise_moments = plan_surprise_moments(total_dur, rules)
    surprise_assignments = assign_surprise_to_clips(adjusted, surprise_moments)

    # 6. Validate final sequence
    validation = validate_retention(adjusted, rules)

    return {
        "clip_durations": adjusted,
        "pattern_interrupts": pattern_interrupts,
        "surprise_moments": surprise_assignments,
        "retention_score": validation["score"],
        "disruptions_added": disruption_count,
        "stats": validation.get("stats", {}),
    }


def detect_predictable_patterns(
    clip_durations: List[float],
    tolerance: float = 0.3,
) -> Tuple[List[float], int]:
    """
    Detect and disrupt predictable pacing patterns.
    
    If 3+ consecutive clips have similar duration (within tolerance),
    force a disruption by shortening or lengthening one.
    
    Returns: (adjusted_durations, disruption_count)
    """
    if len(clip_durations) < 4:
        return clip_durations, 0

    result = list(clip_durations)
    disruptions = 0

    i = 0
    while i < len(result) - 2:
        # Check if 3 consecutive clips have similar duration
        d1, d2, d3 = result[i], result[i + 1], result[i + 2]
        if abs(d1 - d2) < tolerance and abs(d2 - d3) < tolerance:
            # Predictable pattern detected → disrupt middle clip
            if random.random() > 0.5:
                # Make it shorter (faster cut)
                result[i + 1] = max(0.8, d2 * 0.6)
            else:
                # Make it longer (hold for impact)
                result[i + 1] = min(5.0, d2 * 1.5)
            result[i + 1] = round(result[i + 1], 2)
            disruptions += 1
            i += 3  # skip past the disrupted section
        else:
            i += 1

    if disruptions > 0:
        logger.info(f"disrupted {disruptions} predictable pacing patterns")

    return result, disruptions


def inject_imperfections(
    clip_durations: List[float],
    imperfection_rate: float = 0.3,
) -> List[float]:
    """
    Add subtle timing imperfections to clip durations.
    
    Makes the video feel human-edited rather than AI-generated.
    Only affects ~30% of clips with small, natural-feeling adjustments.
    """
    if not clip_durations:
        return clip_durations

    result = []
    for dur in clip_durations:
        if random.random() < imperfection_rate:
            imperfection = random.choice(IMPERFECTION_TYPES)
            if imperfection == "slight_delay":
                dur += random.uniform(0.1, 0.3)
            elif imperfection == "early_cut":
                dur = max(0.8, dur - random.uniform(0.1, 0.2))
            elif imperfection == "timing_drift":
                dur += random.uniform(-0.15, 0.15)
            elif imperfection == "hold_extend":
                dur += random.uniform(0.2, 0.5)
            elif imperfection == "soft_cut":
                dur += random.uniform(-0.1, 0.1)

        result.append(round(max(0.8, dur), 2))

    return result


def _plan_pattern_interrupts(
    clip_durations: List[float],
    interval: Tuple[float, float] = (6.0, 10.0),
) -> List[Dict]:
    """
    Plan pattern interrupt positions at regular intervals.
    
    Returns list of dicts:
        [{"clip_index": 3, "timestamp": 8.5, "effect": "zoom_punch"}]
    """
    if not clip_durations:
        return []

    total_dur = sum(clip_durations)
    min_interval, max_interval = interval

    interrupts = []
    t = random.uniform(min_interval, max_interval)

    # Build cumulative timestamps
    cum_times = []
    cumulative = 0.0
    for dur in clip_durations:
        cumulative += dur
        cum_times.append(cumulative)

    while t < total_dur - 2.0:
        # Find clip index for this timestamp
        for i, end_time in enumerate(cum_times):
            start_time = cum_times[i - 1] if i > 0 else 0.0
            if start_time <= t < end_time:
                effect = random.choice(PATTERN_INTERRUPT_EFFECTS)
                interrupts.append({
                    "clip_index": i,
                    "timestamp": round(t, 2),
                    "effect": effect,
                })
                break
        t += random.uniform(min_interval, max_interval)

    logger.info(f"planned {len(interrupts)} pattern interrupts across {total_dur:.0f}s video")
    return interrupts
