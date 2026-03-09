"""
Viral Style Learning — Learn from reference channels and style inputs.

Allows the system to absorb pacing patterns, shot distributions,
and editing rhythms from reference videos or style tags to produce
videos that match specific viral aesthetics.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from loguru import logger


# ── Style Profile ────────────────────────────────────────────────────────────

@dataclass
class ViralStyleProfile:
    """
    A learned style profile from reference channels or manual input.

    Contains pacing rules, shot distribution preferences, and
    editing rhythm parameters that the cinematic engine uses
    to shape video output.
    """
    name: str = "custom"
    # Pacing parameters
    avg_shot_duration: float = 3.0       # average seconds per clip
    hook_duration: float = 1.5           # max seconds for hook clips
    climax_duration: float = 5.0         # hold time for emotional peak
    # Shot distribution (percentages, should sum to ~1.0)
    shot_distribution: Dict[str, float] = field(default_factory=lambda: {
        "wide": 0.20,
        "medium": 0.25,
        "closeup": 0.20,
        "detail": 0.10,
        "motion": 0.15,
        "silhouette": 0.05,
        "atmospheric": 0.05,
    })
    # Editing rhythm
    cut_frequency: str = "moderate"      # "fast", "moderate", "slow"
    transition_style: str = "hard_cut"   # "hard_cut", "fade", "slide"
    # Visual preferences
    visual_tags: List[str] = field(default_factory=list)
    color_mood: str = "neutral"          # "dark", "bright", "warm", "cool", "neutral"
    motion_intensity: str = "moderate"   # "minimal", "moderate", "dynamic"

    def to_dict(self) -> dict:
        return asdict(self)


# ── Style Tag Mapping ────────────────────────────────────────────────────────

TAG_PRESETS = {
    # Pacing tags
    "fast-paced":    {"avg_shot_duration": 1.5, "hook_duration": 1.0, "cut_frequency": "fast"},
    "slow-paced":    {"avg_shot_duration": 4.5, "hook_duration": 3.0, "cut_frequency": "slow"},
    "moderate-paced": {"avg_shot_duration": 3.0, "hook_duration": 2.0, "cut_frequency": "moderate"},

    # Visual mood tags
    "dark":          {"color_mood": "dark", "visual_tags": ["dark", "shadow", "moody"]},
    "bright":        {"color_mood": "bright", "visual_tags": ["bright", "clean", "light"]},
    "warm":          {"color_mood": "warm", "visual_tags": ["warm", "golden", "sunset"]},
    "cool":          {"color_mood": "cool", "visual_tags": ["cool", "blue", "night"]},

    # Motion tags
    "cinematic":     {"motion_intensity": "moderate", "visual_tags": ["cinematic", "4k", "film"]},
    "dynamic":       {"motion_intensity": "dynamic", "visual_tags": ["action", "fast", "energy"]},
    "minimal":       {"motion_intensity": "minimal", "visual_tags": ["minimal", "calm", "soft"]},

    # Editing style tags
    "hard-cuts":     {"transition_style": "hard_cut", "cut_frequency": "fast"},
    "smooth":        {"transition_style": "fade", "cut_frequency": "slow"},
    "mixed":         {"transition_style": "slide", "cut_frequency": "moderate"},

    # Shot style tags
    "closeup-heavy": {"shot_distribution": {"closeup": 0.35, "detail": 0.15, "medium": 0.20, "wide": 0.10, "motion": 0.10, "silhouette": 0.05, "atmospheric": 0.05}},
    "cinematic-wide": {"shot_distribution": {"wide": 0.35, "atmospheric": 0.15, "medium": 0.20, "closeup": 0.10, "motion": 0.10, "detail": 0.05, "silhouette": 0.05}},
    "action-motion": {"shot_distribution": {"motion": 0.30, "closeup": 0.20, "medium": 0.20, "wide": 0.10, "detail": 0.10, "silhouette": 0.05, "atmospheric": 0.05}},
}


# ── Profile Creation ─────────────────────────────────────────────────────────

def create_style_from_tags(tags: List[str]) -> ViralStyleProfile:
    """
    Build a ViralStyleProfile from a list of style tags.

    Tags are applied in order — later tags override earlier ones
    for conflicting properties. Unknown tags are stored as visual_tags.

    Example:
        create_style_from_tags(["fast-paced", "dark", "cinematic", "hard-cuts"])
    """
    profile = ViralStyleProfile(name="custom_from_tags")
    all_visual_tags = []

    for tag in tags:
        tag_lower = tag.lower().strip()

        if tag_lower in TAG_PRESETS:
            preset = TAG_PRESETS[tag_lower]
            for key, value in preset.items():
                if key == "visual_tags":
                    all_visual_tags.extend(value)
                elif key == "shot_distribution":
                    profile.shot_distribution = value
                elif hasattr(profile, key):
                    setattr(profile, key, value)
        else:
            # Unknown tag — treat as a visual tag
            all_visual_tags.append(tag_lower)

    profile.visual_tags = list(set(all_visual_tags))
    logger.info(
        f"created style profile from tags: {tags} → "
        f"pace={profile.avg_shot_duration}s, mood={profile.color_mood}, "
        f"cuts={profile.cut_frequency}, motion={profile.motion_intensity}"
    )
    return profile


# ── Pacing Pattern Extraction ────────────────────────────────────────────────

def extract_pacing_pattern(reference_data: dict) -> Dict:
    """
    Extract pacing patterns from reference video data.

    Input reference_data should contain:
      - total_duration: float (seconds)
      - cut_count: int (number of scene changes)
      - shot_durations: list of floats (each shot's duration)
      - shot_types: list of strings (shot type per clip)

    Returns a dict with extracted pacing parameters.
    """
    result = {}

    total_duration = reference_data.get("total_duration", 0)
    cut_count = reference_data.get("cut_count", 0)
    shot_durations = reference_data.get("shot_durations", [])
    shot_types = reference_data.get("shot_types", [])

    # Average shot duration
    if shot_durations:
        result["avg_shot_duration"] = round(sum(shot_durations) / len(shot_durations), 2)
    elif cut_count > 0 and total_duration > 0:
        result["avg_shot_duration"] = round(total_duration / cut_count, 2)

    # Hook duration (first 3 shots average)
    if len(shot_durations) >= 3:
        result["hook_duration"] = round(sum(shot_durations[:3]) / 3, 2)
    elif shot_durations:
        result["hook_duration"] = shot_durations[0]

    # Cut frequency classification
    avg_dur = result.get("avg_shot_duration", 3.0)
    if avg_dur < 2.0:
        result["cut_frequency"] = "fast"
    elif avg_dur > 4.0:
        result["cut_frequency"] = "slow"
    else:
        result["cut_frequency"] = "moderate"

    # Shot type distribution
    if shot_types:
        total = len(shot_types)
        distribution = {}
        for st in set(shot_types):
            distribution[st] = round(shot_types.count(st) / total, 2)
        result["shot_distribution"] = distribution

    logger.info(f"extracted pacing pattern: {result}")
    return result


# ── Apply Learned Style ──────────────────────────────────────────────────────

def apply_learned_style(profile: ViralStyleProfile, scenes: list) -> list:
    """
    Apply a learned viral style profile to a scene sequence.

    Adjustments:
      1. Pacing: override intensity-based durations with learned avg_shot_duration
      2. Shot distribution: adjust shot type assignment to match learned distribution
      3. Visual tags: inject learned visual tags into scene search queries

    Returns modified scenes.
    """
    if not scenes or not profile:
        return scenes

    # 1. Inject visual tags into search queries
    if profile.visual_tags:
        tag_str = " ".join(profile.visual_tags[:2])
        for scene in scenes:
            if scene.search_query and tag_str not in scene.search_query:
                scene.search_query = f"{scene.search_query} {tag_str}"

    # 2. Adjust shot types based on learned distribution
    if profile.shot_distribution:
        _apply_shot_distribution(scenes, profile.shot_distribution)

    logger.info(
        f"applied viral style '{profile.name}': "
        f"visual_tags={profile.visual_tags}, "
        f"avg_shot={profile.avg_shot_duration}s"
    )
    return scenes


def _apply_shot_distribution(scenes: list, distribution: Dict[str, float]):
    """
    Adjust shot types to approximately match the target distribution.
    Only modifies 'body' scenes — hook/climax/ending keep their assigned types.
    """
    body_scenes = [s for s in scenes if getattr(s, "narrative_role", "body") == "body"]
    if not body_scenes:
        return

    # Sort shot types by target frequency (descending)
    sorted_shots = sorted(distribution.items(), key=lambda x: x[1], reverse=True)

    # Calculate how many body scenes should get each shot type
    n = len(body_scenes)
    assignments = []
    for shot_type, fraction in sorted_shots:
        count = max(1, round(fraction * n))
        assignments.extend([shot_type] * count)

    # Trim or pad to exact count
    assignments = assignments[:n]
    while len(assignments) < n:
        assignments.append(sorted_shots[0][0])  # fill with most common

    # Assign — avoid same shot back-to-back
    import random
    random.shuffle(assignments)
    for i, scene in enumerate(body_scenes):
        scene.shot_type = assignments[i]
