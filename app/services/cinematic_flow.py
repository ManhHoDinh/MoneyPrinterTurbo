"""
Cinematic Flow Engine — Intensity-based pacing and transitions.

Controls clip duration, transition selection, and temporal sequencing
based on emotion intensity to create cinematic continuity.
"""

from typing import List, Dict, Optional, Tuple
from loguru import logger


# ── Duration Calculation ─────────────────────────────────────────────────────

# Default pacing (can be overridden by style presets)
DEFAULT_PACING = {
    "hook_max_duration": 3.0,     # first scene: max 3 seconds
    "min_clip_duration": 1.5,     # never shorter than 1.5s
    "max_clip_duration": 5.0,     # never longer than 5s
    "max_static_duration": 5.0,   # avoid static > 5s
}


def calculate_clip_duration(
    intensity: float,
    is_hook: bool = False,
    style_pacing: Dict = None,
) -> float:
    """
    Calculate ideal clip duration based on emotion intensity.

    High intensity (0.7-1.0) → shorter, faster cuts (1.5-2.5s)
    Medium intensity (0.4-0.7) → moderate (2.5-3.5s)
    Low intensity (0.0-0.4) → longer, calmer shots (3.5-5.0s)

    Hook scenes are always ≤3s regardless of intensity.
    """
    pacing = {**DEFAULT_PACING, **(style_pacing or {})}

    min_dur = pacing["min_clip_duration"]
    max_dur = pacing["max_clip_duration"]

    if is_hook:
        max_dur = min(max_dur, pacing["hook_max_duration"])

    # Inverse relationship: higher intensity → shorter duration
    # intensity 1.0 → min_dur, intensity 0.0 → max_dur
    duration = max_dur - (intensity * (max_dur - min_dur))

    return round(max(min_dur, min(max_dur, duration)), 1)


# ── Sequence Planning ────────────────────────────────────────────────────────

def plan_sequence(
    scenes: list,
    audio_duration: float,
    style_pacing: Dict = None,
) -> List[Dict]:
    """
    Allocate a time budget per scene proportional to text length
    and emotion intensity.

    Returns a list of dicts with scene_index, target_duration, and
    clip_count (how many clips needed for that scene).
    """
    if not scenes:
        return []

    pacing = {**DEFAULT_PACING, **(style_pacing or {})}

    # Calculate ideal durations based on intensity
    ideal_durations = []
    for i, scene in enumerate(scenes):
        is_hook = (i == 0)
        dur = calculate_clip_duration(
            intensity=scene.intensity,
            is_hook=is_hook,
            style_pacing=pacing,
        )
        # Weight by text length (longer text = proportionally more time)
        text_weight = max(1.0, len(scene.text) / 50.0)  # normalize around 50 chars
        ideal_durations.append(dur * text_weight)

    # Scale to fit audio duration
    total_ideal = sum(ideal_durations)
    if total_ideal <= 0:
        scale = 1.0
    else:
        scale = audio_duration / total_ideal

    sequence = []
    for i, scene in enumerate(scenes):
        target_dur = round(ideal_durations[i] * scale, 1)

        # Enforce bounds
        target_dur = max(pacing["min_clip_duration"], target_dur)
        target_dur = min(pacing["max_clip_duration"] * 2, target_dur)  # allow slightly longer for scaled

        # Calculate clips needed
        max_single = pacing["max_clip_duration"]
        clip_count = max(1, int(target_dur / max_single) + (1 if target_dur % max_single > 0 else 0))

        sequence.append({
            "scene_index": scene.scene_index,
            "target_duration": target_dur,
            "clip_count": clip_count,
            "intensity": scene.intensity,
            "emotion": scene.emotion,
            "is_hook": i == 0,
        })

    logger.info(f"planned sequence: {len(sequence)} scenes, total target={sum(s['target_duration'] for s in sequence):.1f}s, audio={audio_duration:.1f}s")

    return sequence


# ── Transition Selection ─────────────────────────────────────────────────────

TRANSITION_MAP = {
    "hard_cut": None,            # No transition — sharp cut
    "fade": "FadeIn",            # Soft blend
    "slide": "SlideIn",          # Slide effect
    "shuffle": "Shuffle",        # Random transition
}


def select_transition(
    prev_intensity: float,
    next_intensity: float,
    style_transition: str = "",
) -> Optional[str]:
    """
    Select transition type based on intensity delta between scenes.

    Rules:
      - Large intensity jump (>0.3) → hard cut (no transition)
      - Small intensity change (<0.15) → fade (smooth)
      - Medium change → slide or shuffle
      - Style override takes precedence
    """
    # Style override
    if style_transition and style_transition in TRANSITION_MAP:
        return TRANSITION_MAP[style_transition]

    delta = abs(next_intensity - prev_intensity)

    if delta > 0.3:
        # Big emotional shift → hard cut for impact
        return None
    elif delta < 0.15:
        # Smooth emotional flow → gentle fade
        return "FadeIn"
    else:
        # Moderate shift → slide
        return "SlideIn"


def select_transitions_for_sequence(
    sequence: List[Dict],
    style_transition: str = "",
) -> List[Optional[str]]:
    """
    Compute transitions for an entire sequence.
    Returns a list of transition types — one per scene boundary.
    First scene has no transition (it's the start).
    """
    transitions = [None]  # first scene: no preceding transition

    for i in range(1, len(sequence)):
        prev = sequence[i - 1]
        curr = sequence[i]
        transition = select_transition(
            prev_intensity=prev["intensity"],
            next_intensity=curr["intensity"],
            style_transition=style_transition,
        )
        transitions.append(transition)

    return transitions


# ── Emotional Peak Detection ─────────────────────────────────────────────────

def find_emotional_peaks(scenes: list, threshold: float = 0.75) -> List[int]:
    """
    Identify scene indices that represent emotional peaks.
    These scenes should be paired with the most visually impactful footage.

    A peak is defined as a scene with intensity >= threshold that is
    a local maximum (higher than both neighbors).
    """
    peaks = []

    for i, scene in enumerate(scenes):
        if scene.intensity < threshold:
            continue

        # Check if local maximum
        prev_intensity = scenes[i - 1].intensity if i > 0 else 0
        next_intensity = scenes[i + 1].intensity if i < len(scenes) - 1 else 0

        if scene.intensity >= prev_intensity and scene.intensity >= next_intensity:
            peaks.append(i)

    if peaks:
        logger.info(f"emotional peaks detected at scenes: {peaks}")
    else:
        logger.debug("no emotional peaks above threshold detected")

    return peaks


# ── Emotion → Camera Motion Mapping ──────────────────────────────────────────

EMOTION_MOTION_MAP = {
    "motivation":  {"effect": "ken_burns_zoom",  "speed": 0.10},
    "tension":     {"effect": "slow_zoom_in",    "speed": 0.06},
    "curiosity":   {"effect": "pan_right",       "speed": 0.06},
    "calm":        {"effect": "slow_zoom_out",   "speed": 0.02},
    "luxury":      {"effect": "pan_right",       "speed": 0.03},
    "sadness":     {"effect": "slow_zoom_out",   "speed": 0.03},
    "inspiration": {"effect": "ken_burns_zoom",  "speed": 0.08},
    "mystery":     {"effect": "parallax",        "speed": 0.04},
    "dramatic":    {"effect": "slow_zoom_in",    "speed": 0.04},
    "energetic":   {"effect": "ken_burns_zoom",  "speed": 0.12},
}

# Narrative role overrides — certain roles force specific motion styles
NARRATIVE_MOTION_OVERRIDE = {
    "hook":    {"effect": "ken_burns_zoom",  "speed": 0.10},  # dynamic entry
    "climax":  {"effect": "slow_zoom_in",    "speed": 0.04},  # dramatic push-in
    "ending":  {"effect": "slow_zoom_out",   "speed": 0.02},  # calm release
}


def select_camera_motion(
    emotion: str = "dramatic",
    intensity: float = 0.5,
    narrative_role: str = "body",
) -> Dict:
    """
    Select camera motion effect based on emotion + narrative role.

    Returns a dict with:
      - effect: str (name of the video_effects function)
      - speed: float (motion parameter — higher = more movement)

    Narrative role overrides emotion-based selection for hook/climax/ending.
    Intensity modulates speed: higher intensity = faster motion.
    """
    # Narrative role takes priority for structural shots
    if narrative_role in NARRATIVE_MOTION_OVERRIDE:
        motion = NARRATIVE_MOTION_OVERRIDE[narrative_role].copy()
    else:
        motion = EMOTION_MOTION_MAP.get(emotion, {"effect": "ken_burns_zoom", "speed": 0.06}).copy()

    # Modulate speed by intensity (0.5x to 1.5x range)
    speed_multiplier = 0.5 + intensity
    motion["speed"] = round(motion["speed"] * speed_multiplier, 4)

    return motion


# ── Narrative Beat Timing ────────────────────────────────────────────────────

NARRATIVE_BEAT_TIMING = {
    "hook":    {"min": 1.0, "max": 2.0},   # fast cuts to grab attention
    "body":   {"min": 2.0, "max": 4.0},    # moderate pacing
    "climax": {"min": 3.0, "max": 6.0},    # hold for impact
    "ending": {"min": 3.0, "max": 5.0},    # calm reflection
}


def calculate_narrative_duration(
    intensity: float,
    narrative_role: str = "body",
    style_pacing: Dict = None,
) -> float:
    """
    Calculate clip duration using narrative role timing + intensity.

    Combines NARRATIVE_BEAT_TIMING bounds with intensity-based interpolation.
    Hook = fast, Body = moderate, Climax = long hold, Ending = calm.
    """
    timing = NARRATIVE_BEAT_TIMING.get(narrative_role, NARRATIVE_BEAT_TIMING["body"])
    min_dur = timing["min"]
    max_dur = timing["max"]

    # Apply style overrides if present
    if style_pacing:
        if narrative_role == "hook" and "hook_max_duration" in style_pacing:
            max_dur = min(max_dur, style_pacing["hook_max_duration"])
        if "min_clip_duration" in style_pacing:
            min_dur = max(min_dur, style_pacing["min_clip_duration"])

    # For hook and body: higher intensity → shorter (faster cuts)
    # For climax and ending: higher intensity → longer (hold for impact)
    if narrative_role in ("hook", "body"):
        duration = max_dur - (intensity * (max_dur - min_dur))
    else:
        duration = min_dur + (intensity * (max_dur - min_dur))

    return round(max(min_dur, min(max_dur, duration)), 1)


# ── Visual Story Arc ─────────────────────────────────────────────────────────

def build_visual_arc(scenes: list) -> list:
    """
    Analyze and smooth the intensity progression to ensure a proper
    visual narrative arc: beginning → tension → escalation → release.

    Adjusts intensity values slightly to create a smoother curve
    without destroying the LLM's original emotion analysis.

    Returns the scenes with adjusted intensity values.
    """
    if not scenes or len(scenes) < 3:
        return scenes

    n = len(scenes)

    # Calculate the ideal arc shape: rise to peak around 60-75%, then fall
    peak_position = int(n * 0.65)

    for i, scene in enumerate(scenes):
        original = scene.intensity
        position_ratio = i / max(1, n - 1)

        if scene.narrative_role == "hook":
            # Hook should be high intensity
            target = max(original, 0.8)
        elif scene.narrative_role == "ending":
            # Ending should be moderate-to-low
            target = min(original, 0.4)
        elif scene.narrative_role == "climax":
            # Climax should be the highest
            target = max(original, 0.85)
        else:
            # Body scenes: create gentle rise toward climax position
            if i <= peak_position:
                # Rising action — nudge intensity upward as we approach peak
                rise_factor = i / max(1, peak_position)
                target = original * (0.8 + 0.2 * rise_factor)
            else:
                # Falling action — ease down after peak
                fall_factor = (i - peak_position) / max(1, n - 1 - peak_position)
                target = original * (1.0 - 0.3 * fall_factor)

        # Blend: 70% original, 30% arc-shaped target (subtle adjustment)
        scene.intensity = round(max(0.0, min(1.0, original * 0.7 + target * 0.3)), 2)

    logger.info(
        f"visual arc applied: intensities = "
        + ", ".join(f"{s.intensity:.2f}" for s in scenes)
    )
    return scenes


# ── Emotion → Editing Rules ──────────────────────────────────────────────────

EMOTION_EDITING_RULES: Dict[str, Dict] = {
    "motivation":  {"cut_speed": "fast",   "zoom": "ken_burns_zoom",  "transition": "hard_cut",  "hold_multiplier": 0.8},
    "tension":     {"cut_speed": "fast",   "zoom": "slow_zoom_in",    "transition": "hard_cut",  "hold_multiplier": 0.7},
    "curiosity":   {"cut_speed": "medium", "zoom": "pan_right",       "transition": "fade",      "hold_multiplier": 1.0},
    "calm":        {"cut_speed": "slow",   "zoom": "slow_zoom_out",   "transition": "fade",      "hold_multiplier": 1.3},
    "luxury":      {"cut_speed": "slow",   "zoom": "pan_right",       "transition": "fade",      "hold_multiplier": 1.2},
    "sadness":     {"cut_speed": "slow",   "zoom": "slow_zoom_out",   "transition": "fade",      "hold_multiplier": 1.4},
    "inspiration": {"cut_speed": "medium", "zoom": "ken_burns_zoom",  "transition": "slide",     "hold_multiplier": 1.0},
    "mystery":     {"cut_speed": "medium", "zoom": "parallax_effect", "transition": "fade",      "hold_multiplier": 1.1},
    "dramatic":    {"cut_speed": "fast",   "zoom": "slow_zoom_in",    "transition": "hard_cut",  "hold_multiplier": 0.9},
    "energetic":   {"cut_speed": "fast",   "zoom": "ken_burns_zoom",  "transition": "hard_cut",  "hold_multiplier": 0.6},
}

# Cut speed → duration multiplier
CUT_SPEED_MULTIPLIERS = {
    "fast": 0.7,     # shorter clips
    "medium": 1.0,   # standard
    "slow": 1.3,     # longer, lingering shots
}


def map_emotion_to_editing(
    emotion: str,
    intensity: float = 0.5,
) -> Dict:
    """
    Map an emotion to concrete editing parameters.

    Returns a dict with:
      - cut_duration_multiplier: float (applied to base clip duration)
      - zoom_effect: str (camera motion to apply)
      - transition_type: str (transition between this and next scene)
      - hold_multiplier: float (how long to hold the shot relative to base)
    """
    rules = EMOTION_EDITING_RULES.get(emotion, EMOTION_EDITING_RULES["dramatic"])

    cut_speed = rules["cut_speed"]
    base_multiplier = CUT_SPEED_MULTIPLIERS.get(cut_speed, 1.0)

    # Intensity modulation: higher intensity → faster cuts
    intensity_factor = 1.0 - (intensity * 0.3)  # range 0.7 - 1.0
    cut_multiplier = base_multiplier * intensity_factor

    return {
        "cut_duration_multiplier": round(cut_multiplier, 3),
        "zoom_effect": rules["zoom"],
        "transition_type": rules["transition"],
        "hold_multiplier": rules["hold_multiplier"],
    }


def enforce_emotional_arc(
    scenes: list,
    target_arc: str = "standard",
) -> list:
    """
    Enforce a complete emotional arc on the scene sequence.

    Standard arc: curiosity → tension → escalation → peak → release

    Adjusts scene emotions and intensities to match the target arc
    without completely overriding the LLM analysis.
    """
    if not scenes or len(scenes) < 4:
        return scenes

    n = len(scenes)
    arc_phases = {
        "standard": [
            ("curiosity", 0.6),    # opening curiosity
            ("tension", 0.65),     # build tension
            ("escalation", 0.75),  # rising action
            ("dramatic", 0.9),     # peak
            ("calm", 0.4),         # release
        ],
    }

    phases = arc_phases.get(target_arc, arc_phases["standard"])
    phase_count = len(phases)

    for i, scene in enumerate(scenes):
        # Map scene position to arc phase
        phase_idx = min(int(i / n * phase_count), phase_count - 1)
        target_emotion, target_intensity = phases[phase_idx]

        # Soft blend: 60% original, 40% arc target
        # Don't override hook/climax/ending roles
        if scene.narrative_role in ("hook", "climax", "ending"):
            continue

        blended_intensity = scene.intensity * 0.6 + target_intensity * 0.4
        scene.intensity = round(max(0.0, min(1.0, blended_intensity)), 2)

    logger.info(f"emotional arc enforced ({target_arc})")
    return scenes


# ── Emotion Timeline (GOD MODE) ─────────────────────────────────────────────

def build_emotion_timeline(
    scenes: list,
    audio_duration: float,
) -> List[Dict]:
    """
    Generate a timestamp-indexed emotion map across the entire video duration.

    Each entry represents a time segment with its dominant emotion,
    intensity, and visual treatment rules.

    Returns:
        [{
            "start": 0.0,
            "end": 2.5,
            "emotion": "tension",
            "intensity": 0.8,
            "narrative_role": "hook",
            "shot_type": "motion",
            "camera_motion": {"effect": "ken_burns_zoom", "speed": 0.10}
        }]
    """
    if not scenes or audio_duration <= 0:
        return []

    # Calculate proportional duration per scene
    text_lengths = [max(len(getattr(s, 'text', '') or ''), 1) for s in scenes]
    total_text = sum(text_lengths)
    timeline = []
    current_time = 0.0

    for i, scene in enumerate(scenes):
        text_len = text_lengths[i]
        proportion = text_len / total_text
        segment_duration = audio_duration * proportion

        motion = select_camera_motion(
            emotion=scene.emotion,
            intensity=scene.intensity,
            narrative_role=scene.narrative_role,
        )

        timeline.append({
            "start": round(current_time, 2),
            "end": round(current_time + segment_duration, 2),
            "emotion": scene.emotion,
            "intensity": scene.intensity,
            "narrative_role": scene.narrative_role,
            "shot_type": scene.shot_type,
            "camera_motion": motion,
        })

        current_time += segment_duration

    logger.info(f"emotion timeline built: {len(timeline)} segments across {audio_duration:.1f}s")
    return timeline


# ── Shot Progression Rules ───────────────────────────────────────────────────

SHOT_PROGRESSION_RULES = {
    "hook": {
        "allowed_shots": ["motion", "closeup"],
        "required_motion": True,
        "max_duration": 3.0,
    },
    "escalation": {
        "progression": ["wide", "medium", "closeup"],
        "required_motion": False,
        "max_duration": 4.0,
    },
    "peak": {
        "allowed_shots": ["silhouette", "atmospheric", "closeup"],
        "required_motion": False,
        "max_duration": 6.0,
    },
    "ending": {
        "allowed_shots": ["wide", "atmospheric"],
        "required_motion": False,
        "max_duration": 5.0,
    },
}


def validate_shot_progression(scenes: list) -> List[str]:
    """
    Check and report shot ordering violations.

    Rules:
    - hook: must be motion-heavy or closeup
    - escalation (body scenes): should progress wide → medium → close
    - peak (climax): dramatic lighting / atmospheric
    - ending: calm, wide scene

    Returns list of violation descriptions (empty = all good).
    """
    if not scenes:
        return []

    violations = []

    for scene in scenes:
        role = scene.narrative_role
        shot = scene.shot_type

        if role == "hook":
            rules = SHOT_PROGRESSION_RULES["hook"]
            if shot not in rules["allowed_shots"]:
                violations.append(
                    f"scene {scene.scene_index}: hook should use "
                    f"{rules['allowed_shots']}, got '{shot}'"
                )
        elif role == "climax":
            rules = SHOT_PROGRESSION_RULES["peak"]
            if shot not in rules["allowed_shots"]:
                violations.append(
                    f"scene {scene.scene_index}: climax should use "
                    f"{rules['allowed_shots']}, got '{shot}'"
                )
        elif role == "ending":
            rules = SHOT_PROGRESSION_RULES["ending"]
            if shot not in rules["allowed_shots"]:
                violations.append(
                    f"scene {scene.scene_index}: ending should use "
                    f"{rules['allowed_shots']}, got '{shot}'"
                )

    # Check body scene progression (should vary, not repeat)
    body_scenes = [s for s in scenes if s.narrative_role == "body"]
    if len(body_scenes) >= 3:
        for i in range(len(body_scenes) - 1):
            if body_scenes[i].shot_type == body_scenes[i + 1].shot_type:
                violations.append(
                    f"scenes {body_scenes[i].scene_index}-{body_scenes[i+1].scene_index}: "
                    f"consecutive same shot type '{body_scenes[i].shot_type}'"
                )

    if violations:
        logger.warning(f"shot progression: {len(violations)} violations found")
    else:
        logger.info("shot progression: all rules passed")

    return violations


def match_motion_intensity(
    emotion: str,
    intensity: float,
    narrative_role: str = "body",
) -> Dict:
    """
    Map emotion intensity to precise camera motion speed.

    Returns:
        {"effect": "ken_burns_zoom", "speed": 0.08, "intensity_class": "high"}
    """
    motion = select_camera_motion(emotion, intensity, narrative_role)

    # Classify intensity
    if intensity >= 0.7:
        intensity_class = "high"
    elif intensity >= 0.4:
        intensity_class = "medium"
    else:
        intensity_class = "low"

    motion["intensity_class"] = intensity_class
    return motion
