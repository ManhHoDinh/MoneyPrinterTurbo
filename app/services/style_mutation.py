"""
Style Mutation System — Controlled variation layer for content uniqueness.

Introduces random-within-bounds mutations to prevent identical output structures
across videos. Each video gets a unique "mutation vector" that tweaks:

  - Subtitle timing offset
  - Zoom/Ken Burns speed
  - Scene clip duration
  - Voice pacing
  - Transition style
  - Hook intensity
  - Color mood bias

The mutations are deterministic per job_id (seeded RNG) so results are
reproducible for debugging, but unique across different jobs.

Usage:
    from app.services.style_mutation import mutate_params
    mutation = mutate_params(params, job_id="abc-123", intensity=0.5)
    # params is mutated in-place, mutation dict returned for logging
"""

import hashlib
import random
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from loguru import logger


# ── Mutation Bounds ──────────────────────────────────────────────────────────
# Each bound defines [min_delta, max_delta] relative to the base value.

MUTATION_BOUNDS = {
    "clip_duration": {
        "min": 2,       # seconds
        "max": 8,
        "step": 0.5,
    },
    "voice_rate": {
        "min": 0.85,
        "max": 1.25,
        "step": 0.05,
    },
    "subtitle_offset_y": {
        "options": [-5, -3, 0, 3, 5, 8],  # pixel offset from base position
    },
    "font_size": {
        "min": 48,
        "max": 72,
        "step": 2,
    },
    "stroke_width": {
        "min": 1.0,
        "max": 2.5,
        "step": 0.25,
    },
    "bgm_volume": {
        "min": 0.1,
        "max": 0.35,
        "step": 0.05,
    },
    "transition_style": {
        "options": [None, "Shuffle", "FadeIn", "FadeOut", "SlideIn"],
    },
    "subtitle_position": {
        "options": ["bottom", "center", "top"],
    },
    "hook_intensity": {
        "options": ["soft", "medium", "aggressive"],
    },
}

# Style-aware mutation intensity scales
# Some styles benefit from more variation, others need tighter control.
STYLE_INTENSITY_MAP = {
    "dark_psychology": 0.7,
    "motivation": 0.5,
    "luxury_lifestyle": 0.3,   # Luxury = tight, polished
    "stoic_philosophy": 0.4,
    "viral_facts": 0.8,        # Facts = maximum variety
    "minimal_calm": 0.2,       # Calm = subtle changes only
    "high_energy": 0.9,        # High energy = wild variation
}


@dataclass
class MutationVector:
    """Captured mutations applied to a video for logging/replay."""
    job_id: str = ""
    seed: int = 0
    intensity: float = 0.5
    mutations: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        parts = [f"{k}={v}" for k, v in self.mutations.items()]
        return f"seed={self.seed} intensity={self.intensity:.2f} | " + ", ".join(parts)


# ── Public API ───────────────────────────────────────────────────────────────

def mutate_params(
    params,
    job_id: str = "",
    style: str = "",
    intensity: Optional[float] = None,
    channel_id: str = "",
) -> MutationVector:
    """
    Apply controlled random mutations to VideoParams.

    Mutations are seeded by job_id for reproducibility.
    Intensity (0.0 = no change, 1.0 = maximum variation) can be
    auto-selected based on style or explicitly set.

    Args:
        params:      VideoParams object (mutated in-place)
        job_id:      Used as RNG seed for reproducibility
        style:       Style name for intensity auto-selection
        intensity:   Override mutation strength (0.0 to 1.0)
        channel_id:  For additional seed entropy

    Returns:
        MutationVector with all applied mutations logged.
    """
    # Determine intensity
    if intensity is None:
        intensity = STYLE_INTENSITY_MAP.get(style, 0.5)
    intensity = max(0.0, min(1.0, intensity))

    # Deterministic seed from job_id + channel_id
    seed_str = f"{job_id}:{channel_id}:{style}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    vector = MutationVector(job_id=job_id, seed=seed, intensity=intensity)

    # ── Apply each mutation ──────────────────────────────────────────

    # 1. Clip duration
    if rng.random() < intensity:
        bounds = MUTATION_BOUNDS["clip_duration"]
        new_dur = _rand_step(rng, bounds["min"], bounds["max"], bounds["step"])
        params.video_clip_duration = int(new_dur)
        vector.mutations["clip_duration"] = new_dur

    # 2. Voice rate
    if rng.random() < intensity:
        bounds = MUTATION_BOUNDS["voice_rate"]
        new_rate = _rand_step(rng, bounds["min"], bounds["max"], bounds["step"])
        params.voice_rate = new_rate
        vector.mutations["voice_rate"] = new_rate

    # 3. Font size
    if rng.random() < intensity * 0.7:  # Less frequent
        bounds = MUTATION_BOUNDS["font_size"]
        new_size = int(_rand_step(rng, bounds["min"], bounds["max"], bounds["step"]))
        params.font_size = new_size
        vector.mutations["font_size"] = new_size

    # 4. Stroke width
    if rng.random() < intensity * 0.6:
        bounds = MUTATION_BOUNDS["stroke_width"]
        new_stroke = _rand_step(rng, bounds["min"], bounds["max"], bounds["step"])
        params.stroke_width = round(new_stroke, 2)
        vector.mutations["stroke_width"] = params.stroke_width

    # 5. BGM volume
    if rng.random() < intensity * 0.8:
        bounds = MUTATION_BOUNDS["bgm_volume"]
        new_vol = _rand_step(rng, bounds["min"], bounds["max"], bounds["step"])
        params.bgm_volume = round(new_vol, 2)
        vector.mutations["bgm_volume"] = params.bgm_volume

    # 6. Transition style
    if rng.random() < intensity * 0.5:
        options = MUTATION_BOUNDS["transition_style"]["options"]
        chosen = rng.choice(options)
        if chosen is not None:
            try:
                from app.models.schema import VideoTransitionMode
                params.video_transition_mode = chosen
            except Exception:
                pass
        else:
            params.video_transition_mode = None
        vector.mutations["transition"] = chosen or "none"

    # 7. Subtitle position
    if rng.random() < intensity * 0.4:  # Rare mutation
        options = MUTATION_BOUNDS["subtitle_position"]["options"]
        chosen = rng.choice(options)
        params.subtitle_position = chosen
        vector.mutations["subtitle_pos"] = chosen

    # 8. Custom position offset (vertical shift)
    if rng.random() < intensity * 0.6:
        offsets = MUTATION_BOUNDS["subtitle_offset_y"]["options"]
        offset = rng.choice(offsets)
        base_pos = getattr(params, "custom_position", 70.0)
        params.custom_position = max(10.0, min(90.0, base_pos + offset))
        vector.mutations["subtitle_y_offset"] = offset

    logger.debug(f"[StyleMutation] {vector.summary()}")
    return vector


def get_mutation_intensity(style: str) -> float:
    """Get the recommended mutation intensity for a style."""
    return STYLE_INTENSITY_MAP.get(style, 0.5)


def preview_mutation(
    style: str = "",
    job_id: str = "preview-000",
    intensity: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Preview what mutations would be applied without a real VideoParams object.
    Useful for the dashboard UI to show expected variation range.
    """

    class _FakeParams:
        video_clip_duration = 5
        voice_rate = 1.0
        font_size = 60
        stroke_width = 1.5
        bgm_volume = 0.2
        video_transition_mode = None
        subtitle_position = "bottom"
        custom_position = 70.0

    fake = _FakeParams()
    vector = mutate_params(fake, job_id=job_id, style=style, intensity=intensity)

    return {
        "style": style,
        "intensity": vector.intensity,
        "mutations": vector.mutations,
        "preview": {
            "clip_duration": fake.video_clip_duration,
            "voice_rate": fake.voice_rate,
            "font_size": fake.font_size,
            "stroke_width": fake.stroke_width,
            "bgm_volume": fake.bgm_volume,
            "transition": str(fake.video_transition_mode),
            "subtitle_position": fake.subtitle_position,
            "custom_position": fake.custom_position,
        },
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rand_step(rng: random.Random, lo: float, hi: float, step: float) -> float:
    """Pick a random value between lo and hi, snapped to step increments."""
    steps = int((hi - lo) / step)
    chosen_step = rng.randint(0, steps)
    return round(lo + chosen_step * step, 4)
