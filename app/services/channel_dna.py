"""
Multi-Channel DNA Differentiation — Unique fingerprint per channel.

Each channel has unique:
- Pacing signature
- Subtitle style
- Emotional tone bias
- Hook archetype frequency
- Visual color grading mood

Prevents cross-channel fingerprint overlap detection.
"""

import json
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from loguru import logger


# ── Channel DNA Profile ──────────────────────────────────────────────────────

@dataclass
class ChannelDNA:
    """Unique DNA fingerprint for a content channel."""
    channel_id: str = ""
    channel_name: str = ""

    # Pacing signature
    avg_clip_duration: float = 3.0        # seconds
    hook_duration: float = 1.5
    cut_frequency: str = "moderate"       # "fast", "moderate", "slow"

    # Subtitle style
    subtitle_position: str = "bottom"     # "bottom", "center", "top"
    subtitle_font_size: int = 60
    subtitle_color: str = "#FFFFFF"
    subtitle_stroke_color: str = "#000000"
    subtitle_stroke_width: float = 1.5
    subtitle_animation: str = "none"      # "none", "fade", "typewriter", "bounce"

    # Emotional tone bias
    primary_emotions: List[str] = field(default_factory=lambda: ["curiosity", "tension"])
    emotion_intensity_bias: float = 0.5   # 0.0 = calm, 1.0 = intense
    controversy_range: List[float] = field(default_factory=lambda: [0.2, 0.6])

    # Hook archetype frequency
    hook_type_weights: Dict[str, float] = field(default_factory=lambda: {
        "fear": 0.2, "curiosity": 0.25, "shock": 0.2,
        "desire": 0.15, "authority": 0.1, "mistake_revelation": 0.1,
    })

    # Visual color grading mood
    color_mood: str = "neutral"           # "dark", "bright", "warm", "cool", "neutral"
    brightness_bias: float = 0.0          # -0.5 to +0.5
    saturation_bias: float = 0.0          # -0.3 to +0.3

    # Audio signature
    voice_name: str = ""
    voice_rate: float = 1.0
    bgm_mood: str = "random"

    # Video style
    preferred_style: str = ""             # style preset name
    transition_style: str = "hard_cut"

    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelDNA":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def fingerprint_vector(self) -> List[float]:
        """
        Convert DNA to a numeric vector for similarity comparison.
        """
        emotion_map = {"curiosity": 0, "tension": 1, "fear": 2, "motivation": 3,
                       "luxury": 4, "sadness": 5, "inspiration": 6, "mystery": 7}
        mood_map = {"dark": 0, "cool": 0.25, "neutral": 0.5, "warm": 0.75, "bright": 1.0}
        cut_map = {"fast": 0, "moderate": 0.5, "slow": 1.0}
        pos_map = {"top": 0, "center": 0.5, "bottom": 1.0}

        vec = [
            self.avg_clip_duration / 5.0,
            self.hook_duration / 3.0,
            cut_map.get(self.cut_frequency, 0.5),
            pos_map.get(self.subtitle_position, 1.0),
            self.subtitle_font_size / 100.0,
            self.emotion_intensity_bias,
            mood_map.get(self.color_mood, 0.5),
            self.brightness_bias + 0.5,
            self.saturation_bias + 0.5,
            self.voice_rate / 2.0,
        ]

        # Add primary emotion encoding
        emo_vec = [0.0] * len(emotion_map)
        for emo in self.primary_emotions:
            if emo in emotion_map:
                emo_vec[emotion_map[emo]] = 1.0
        vec.extend(emo_vec)

        return vec


# ── Channel DNA Store ────────────────────────────────────────────────────────

class ChannelDNAStore:
    """JSON-file-per-channel storage in storage/channels/."""

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            storage_dir = os.path.join(root, "storage", "channels")
        os.makedirs(storage_dir, exist_ok=True)
        self.storage_dir = storage_dir

    def save(self, dna: ChannelDNA) -> str:
        path = os.path.join(self.storage_dir, f"{dna.channel_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dna.to_dict(), f, indent=2)
        logger.info(f"channel DNA saved: {dna.channel_id}")
        return path

    def load(self, channel_id: str) -> Optional[ChannelDNA]:
        path = os.path.join(self.storage_dir, f"{channel_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return ChannelDNA.from_dict(json.load(f))

    def load_all(self) -> List[ChannelDNA]:
        channels = []
        if not os.path.exists(self.storage_dir):
            return channels
        for fname in os.listdir(self.storage_dir):
            if fname.endswith(".json"):
                try:
                    path = os.path.join(self.storage_dir, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        channels.append(ChannelDNA.from_dict(json.load(f)))
                except Exception as e:
                    logger.warning(f"failed to load channel {fname}: {e}")
        return channels


# ── DNA Generation ───────────────────────────────────────────────────────────

EMOTION_POOLS = [
    ["curiosity", "tension"], ["fear", "mystery"], ["motivation", "inspiration"],
    ["luxury", "desire"], ["curiosity", "fear"], ["tension", "motivation"],
    ["mystery", "sadness"], ["inspiration", "curiosity"],
]

MOOD_OPTIONS = ["dark", "bright", "warm", "cool", "neutral"]
CUT_OPTIONS = ["fast", "moderate", "slow"]
POSITION_OPTIONS = ["bottom", "center", "top"]
TRANSITION_OPTIONS = ["hard_cut", "fade", "slide"]
ANIMATION_OPTIONS = ["none", "fade", "typewriter", "bounce"]


def create_channel(
    name: str,
    channel_id: str = "",
    store: ChannelDNAStore = None,
) -> ChannelDNA:
    """
    Auto-generate a unique channel DNA differentiated from all existing channels.
    """
    if not store:
        store = ChannelDNAStore()

    existing = store.load_all()

    if not channel_id:
        channel_id = f"ch_{name.lower().replace(' ', '_')}_{random.randint(100, 999)}"

    dna = ChannelDNA(
        channel_id=channel_id,
        channel_name=name,
        avg_clip_duration=round(random.uniform(2.0, 4.5), 1),
        hook_duration=round(random.uniform(1.0, 2.5), 1),
        cut_frequency=random.choice(CUT_OPTIONS),
        subtitle_position=random.choice(POSITION_OPTIONS),
        subtitle_font_size=random.choice([48, 52, 56, 60, 64, 68]),
        subtitle_color=random.choice(["#FFFFFF", "#F0F0F0", "#FFFDE7", "#E3F2FD"]),
        subtitle_animation=random.choice(ANIMATION_OPTIONS),
        primary_emotions=random.choice(EMOTION_POOLS),
        emotion_intensity_bias=round(random.uniform(0.3, 0.8), 2),
        controversy_range=[round(random.uniform(0.1, 0.4), 2), round(random.uniform(0.5, 0.8), 2)],
        color_mood=random.choice(MOOD_OPTIONS),
        brightness_bias=round(random.uniform(-0.3, 0.3), 2),
        saturation_bias=round(random.uniform(-0.2, 0.2), 2),
        voice_rate=round(random.uniform(0.9, 1.3), 1),
        bgm_mood=random.choice(["dark", "epic", "calm", "upbeat", "random"]),
        transition_style=random.choice(TRANSITION_OPTIONS),
    )

    # Distribute hook type weights uniquely
    hook_types = ["fear", "curiosity", "shock", "desire", "authority", "mistake_revelation"]
    weights = [random.uniform(0.05, 0.35) for _ in hook_types]
    total = sum(weights)
    dna.hook_type_weights = {ht: round(w / total, 2) for ht, w in zip(hook_types, weights)}

    # Ensure differentiation from existing channels
    max_attempts = 10
    for attempt in range(max_attempts):
        too_similar = False
        for existing_dna in existing:
            overlap = detect_fingerprint_overlap(dna, existing_dna)
            if overlap > 0.6:
                too_similar = True
                break

        if not too_similar:
            break

        # Re-randomize key differentiators
        dna.color_mood = random.choice(MOOD_OPTIONS)
        dna.cut_frequency = random.choice(CUT_OPTIONS)
        dna.primary_emotions = random.choice(EMOTION_POOLS)
        dna.emotion_intensity_bias = round(random.uniform(0.3, 0.8), 2)

    store.save(dna)
    logger.info(f"created channel DNA: {channel_id} ({name})")
    return dna


# ── Fingerprint Overlap Detection ────────────────────────────────────────────

def detect_fingerprint_overlap(channel_a: ChannelDNA, channel_b: ChannelDNA) -> float:
    """
    Compute similarity between two channel fingerprints (0.0 = different, 1.0 = identical).
    """
    vec_a = channel_a.fingerprint_vector()
    vec_b = channel_b.fingerprint_vector()

    if len(vec_a) != len(vec_b):
        return 0.0

    # Euclidean distance normalized to 0-1 similarity
    import math
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))
    max_dist = math.sqrt(len(vec_a))  # max possible distance
    similarity = 1.0 - (dist / max_dist) if max_dist > 0 else 0.0

    return round(similarity, 3)


def validate_channel_differentiation(store: ChannelDNAStore = None, min_diff: float = 0.4) -> Dict:
    """
    Validate all channels differ by at least min_diff.
    Returns {passed: bool, pairs: [{ch_a, ch_b, overlap}]}.
    """
    if not store:
        store = ChannelDNAStore()

    channels = store.load_all()
    violations = []

    for i in range(len(channels)):
        for j in range(i + 1, len(channels)):
            overlap = detect_fingerprint_overlap(channels[i], channels[j])
            if overlap > (1.0 - min_diff):
                violations.append({
                    "channel_a": channels[i].channel_id,
                    "channel_b": channels[j].channel_id,
                    "overlap": overlap,
                })

    passed = len(violations) == 0
    if not passed:
        logger.warning(f"channel differentiation failed: {len(violations)} pairs too similar")

    return {"passed": passed, "total_channels": len(channels), "violations": violations}


# ── Apply Channel DNA to Params ──────────────────────────────────────────────

def apply_channel_dna(params, channel_id: str, store: ChannelDNAStore = None):
    """
    Modify VideoParams with channel-specific overrides.
    Mutates params in-place.
    """
    if not store:
        store = ChannelDNAStore()

    dna = store.load(channel_id)
    if not dna:
        logger.warning(f"channel DNA not found: {channel_id}")
        return params

    # Apply voice settings
    if dna.voice_name and hasattr(params, "voice_name"):
        params.voice_name = dna.voice_name
    if hasattr(params, "voice_rate"):
        params.voice_rate = dna.voice_rate

    # Apply subtitle style
    if hasattr(params, "font_size"):
        params.font_size = dna.subtitle_font_size
    if hasattr(params, "subtitle_position"):
        params.subtitle_position = dna.subtitle_position
    if hasattr(params, "text_fore_color"):
        params.text_fore_color = dna.subtitle_color

    # Apply BGM mood
    if hasattr(params, "bgm_type"):
        params.bgm_type = dna.bgm_mood

    # Apply style
    if dna.preferred_style and hasattr(params, "video_style"):
        params.video_style = dna.preferred_style

    logger.info(
        f"applied channel DNA '{channel_id}': mood={dna.color_mood}, "
        f"pace={dna.cut_frequency}, emotions={dna.primary_emotions}"
    )
    return params
