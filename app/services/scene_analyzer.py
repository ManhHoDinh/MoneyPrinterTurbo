"""
Scene Emotion Analyzer — Cinematic Visual Intelligence.

Analyzes video scripts to extract micro-scenes with emotion tags,
builds emotion-enriched search queries, and assigns shot types
for cinematic visual matching.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from itertools import cycle

from loguru import logger


# ── Data Structures ──────────────────────────────────────────────────────────

EMOTION_CATEGORIES = [
    "motivation", "tension", "curiosity", "calm", "luxury",
    "sadness", "inspiration", "mystery", "dramatic", "energetic",
]

SHOT_TYPES = ["wide", "medium", "closeup", "detail", "motion", "silhouette", "atmospheric"]


@dataclass
class SceneSegment:
    """A micro-scene extracted from the script with emotion metadata."""
    text: str = ""
    topic: str = ""
    emotion: str = "dramatic"
    intensity: float = 0.5
    search_query: str = ""
    shot_type: str = "wide"
    scene_index: int = 0
    narrative_role: str = "body"  # hook | body | climax | ending

    def to_dict(self) -> dict:
        return asdict(self)


# ── Emotion Modifiers ────────────────────────────────────────────────────────
# Maps each emotion category to visual search modifiers that produce
# cinematic, mood-appropriate stock footage results.

EMOTION_MODIFIERS: Dict[str, List[str]] = {
    "motivation": [
        "sunrise mountain", "runner finishing race", "victory celebration",
        "fist pump", "bright light breakthrough",
    ],
    "tension": [
        "walking alone night", "rain window", "dark alley",
        "ticking clock closeup", "stressed hands",
    ],
    "curiosity": [
        "magnifying glass", "open book pages", "mysterious door",
        "question marks", "searching eyes",
    ],
    "calm": [
        "ocean waves sunset", "morning mist forest", "smooth water reflection",
        "meditation garden", "gentle breeze grass",
    ],
    "luxury": [
        "luxury car interior", "gold details closeup", "penthouse city view",
        "champagne pouring", "modern lifestyle aesthetic",
    ],
    "sadness": [
        "rain on window", "empty bench park", "wilted flower",
        "lonely silhouette", "grey sky clouds",
    ],
    "inspiration": [
        "lightbulb moment", "artist painting", "starry night sky",
        "child dreaming", "rocket launch",
    ],
    "mystery": [
        "fog dark forest", "shadow figure corridor", "old key lock",
        "candlelight darkness", "hidden path",
    ],
    "dramatic": [
        "storm clouds lightning", "intense eyes closeup", "chess piece falling",
        "slow motion impact", "dark cinematic shadows",
    ],
    "energetic": [
        "fast city timelapse", "sports action", "crowd cheering",
        "neon lights movement", "dance performance",
    ],
}

# Cinematic style tags added to ALL queries for higher-quality results
CINEMATIC_TAGS = ["cinematic", "4k", "slow motion"]

# Shot type search modifiers
SHOT_TYPE_MODIFIERS: Dict[str, str] = {
    "wide": "wide shot landscape",
    "medium": "medium shot person",
    "closeup": "close up detail",
    "detail": "extreme close up texture detail",
    "motion": "camera movement tracking",
    "silhouette": "silhouette backlight shadow",
    "atmospheric": "atmospheric fog misty mood",
}


# ── Scene Analysis via LLM ──────────────────────────────────────────────────

def analyze_scenes(
    script: str,
    video_subject: str,
    video_style: str = "",
) -> List[SceneSegment]:
    """
    Use the LLM to split a script into micro-scenes with emotion tags.

    Each scene gets:
      - text: the original sentence/segment
      - topic: main semantic topic (1-3 words)
      - emotion: one of EMOTION_CATEGORIES
      - intensity: 0.0 to 1.0

    Falls back to a simple sentence-split heuristic if LLM fails.
    """
    from app.services.llm import _generate_response

    emotion_list = ", ".join(EMOTION_CATEGORIES)
    prompt = f"""
# Role: Script Emotion Analyzer

## Task:
Analyze the following video script and split it into micro-scenes.
For EACH micro-scene, extract the semantic topic, emotional category, and intensity.

## Rules:
1. Return ONLY a JSON array — no markdown, no explanation
2. Split the script at natural sentence boundaries (1-2 sentences per scene)
3. Each object must have exactly these fields:
   - "text": the exact text from the script for this scene
   - "topic": main semantic topic in 1-3 words (English)
   - "emotion": MUST be one of: [{emotion_list}]
   - "intensity": a float from 0.0 (very mild) to 1.0 (very intense)
4. The first scene should typically have HIGH intensity (it's the hook)
5. Maintain emotional coherence — scenes should flow naturally
6. Use the FULL script — every word must appear in exactly one scene

## Video Subject:
{video_subject}

## Script:
{script}

Return ONLY valid JSON array.
""".strip()

    scenes: List[SceneSegment] = []

    for attempt in range(3):
        try:
            response = _generate_response(prompt)
            if not response or "Error: " in response:
                logger.warning(f"scene analysis attempt {attempt + 1} failed: {response}")
                continue

            # Extract JSON array from response
            raw = _extract_json_array(response)
            if not raw:
                logger.warning(f"could not extract JSON from response on attempt {attempt + 1}")
                continue

            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                continue

            for i, item in enumerate(parsed):
                emotion = item.get("emotion", "dramatic").lower().strip()
                if emotion not in EMOTION_CATEGORIES:
                    emotion = "dramatic"

                intensity = float(item.get("intensity", 0.5))
                intensity = max(0.0, min(1.0, intensity))

                scene = SceneSegment(
                    text=item.get("text", ""),
                    topic=item.get("topic", ""),
                    emotion=emotion,
                    intensity=intensity,
                    scene_index=i,
                )
                scenes.append(scene)

            if scenes:
                logger.success(f"analyzed {len(scenes)} scenes from script")
                break

        except Exception as e:
            logger.warning(f"scene analysis attempt {attempt + 1} error: {e}")

    # Fallback: simple sentence splitting with default emotions
    if not scenes:
        logger.warning("LLM scene analysis failed, using fallback sentence splitter")
        scenes = _fallback_scene_split(script)

    # Assign narrative roles, shot types, and build search queries
    scenes = assign_narrative_roles(scenes)
    scenes = assign_shot_types(scenes)
    scenes = build_all_search_queries(scenes, video_style)

    return scenes


def _extract_json_array(text: str) -> Optional[str]:
    """Extract a JSON array from LLM response text."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("["):
        # Find matching bracket
        bracket_count = 0
        for i, ch in enumerate(text):
            if ch == "[":
                bracket_count += 1
            elif ch == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    return text[: i + 1]

    # Regex fallback
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group()

    return None


def _fallback_scene_split(script: str) -> List[SceneSegment]:
    """Simple fallback: split by sentences, assign default emotions."""
    sentences = re.split(r"(?<=[.!?])\s+", script.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    # Simple heuristic: first sentence = dramatic (hook), rest = mixed
    default_emotions = cycle(["dramatic", "curiosity", "tension", "inspiration", "motivation"])

    scenes = []
    for i, sentence in enumerate(sentences):
        emotion = "dramatic" if i == 0 else next(default_emotions)
        intensity = 0.9 if i == 0 else 0.5 + (0.1 * (i % 3))

        scenes.append(SceneSegment(
            text=sentence,
            topic=_extract_simple_topic(sentence),
            emotion=emotion,
            intensity=min(1.0, intensity),
            scene_index=i,
        ))

    return scenes


def _extract_simple_topic(text: str) -> str:
    """Extract a simple 1-2 word topic from text (heuristic)."""
    # Remove common stop words and take first 2 meaningful words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "must",
        "this", "that", "these", "those", "i", "you", "he", "she",
        "it", "we", "they", "my", "your", "his", "her", "its",
        "our", "their", "me", "him", "us", "them", "and", "or",
        "but", "if", "of", "in", "on", "at", "to", "for", "with",
        "not", "no", "so", "just", "don", "t", "s", "re", "ve",
        "most", "people", "know", "think", "want", "get", "make",
    }
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    meaningful = [w for w in words if w not in stop_words and len(w) > 2]
    return " ".join(meaningful[:2]) if meaningful else "general"


# ── Narrative Role Assignment ────────────────────────────────────────────────

def assign_narrative_roles(scenes: List[SceneSegment]) -> List[SceneSegment]:
    """
    Assign narrative roles to create a visual story arc.

    Structure:
      - Scene 0 → "hook" (grab attention)
      - Scenes 1..N-2 → "body" (develop story)
      - Highest-intensity body scene → "climax" (emotional peak)
      - Last scene → "ending" (calm/reflective close)
    """
    if not scenes:
        return scenes

    # Default all to body
    for scene in scenes:
        scene.narrative_role = "body"

    # First scene = hook
    scenes[0].narrative_role = "hook"

    # Last scene = ending (if more than 1 scene)
    if len(scenes) > 1:
        scenes[-1].narrative_role = "ending"

    # Find climax (highest intensity in body scenes)
    if len(scenes) > 2:
        body_scenes = [(i, s) for i, s in enumerate(scenes) if s.narrative_role == "body"]
        if body_scenes:
            climax_idx, _ = max(body_scenes, key=lambda x: x[1].intensity)
            scenes[climax_idx].narrative_role = "climax"

    logger.info(
        f"narrative roles assigned: "
        + ", ".join(f"scene {s.scene_index}={s.narrative_role}" for s in scenes)
    )
    return scenes


# ── Shot Type Assignment ─────────────────────────────────────────────────────

# Body rotation pattern — cycles through varied shot types
BODY_SHOT_ROTATION = ["wide", "medium", "closeup", "detail"]

# Climax shot types — dramatic visual impact
CLIMAX_SHOTS = ["silhouette", "atmospheric"]


def assign_shot_types(scenes: List[SceneSegment]) -> List[SceneSegment]:
    """
    Assign shot types based on narrative role for cinematic sequencing.

    Mapping:
      - hook    → "motion" (dynamic energy, strong visual contrast)
      - body    → cycles [wide → medium → closeup → detail]
      - climax  → "silhouette" or "atmospheric" (dramatic impact)
      - ending  → "wide" (calm, reflective, gives closure)

    Prevents same shot type back-to-back.
    """
    if not scenes:
        return scenes

    body_cycle = cycle(BODY_SHOT_ROTATION)
    climax_cycle = cycle(CLIMAX_SHOTS)
    prev_shot = None

    for scene in scenes:
        role = scene.narrative_role

        if role == "hook":
            scene.shot_type = "motion"
        elif role == "climax":
            shot = next(climax_cycle)
            # Avoid same as previous
            if shot == prev_shot:
                shot = next(climax_cycle)
            scene.shot_type = shot
        elif role == "ending":
            scene.shot_type = "wide"
        else:  # body
            shot = next(body_cycle)
            # Avoid same as previous
            if shot == prev_shot:
                shot = next(body_cycle)
            scene.shot_type = shot

        prev_shot = scene.shot_type

    return scenes


# ── Search Query Builder ─────────────────────────────────────────────────────

# Pacing context tags used in elite search queries
PACING_CONTEXT_MODIFIERS = {
    "hook": "fast movement dynamic",
    "body": "cinematic",
    "climax": "slow motion dramatic",
    "ending": "calm peaceful",
}


def build_emotion_search_query(
    scene: SceneSegment,
    style_modifiers: List[str] = None,
) -> str:
    """
    Build an emotion-enriched search query for a single scene.

    Combines:
      1. Scene topic keywords
      2. Emotion-specific visual modifiers
      3. Shot type modifier
      4. Style-specific modifiers (if any)
      5. One cinematic tag

    Result: a 3-6 word search string optimized for stock footage APIs.
    """
    parts = []

    # 1. Topic keyword (1-2 words)
    if scene.topic:
        parts.append(scene.topic)

    # 2. Emotion modifier — pick one that's most relevant
    emotion_mods = EMOTION_MODIFIERS.get(scene.emotion, EMOTION_MODIFIERS["dramatic"])
    # Use intensity to pick: high intensity → earlier (more dramatic) modifiers
    mod_index = min(int(scene.intensity * len(emotion_mods)), len(emotion_mods) - 1)
    parts.append(emotion_mods[mod_index])

    # 3. Cinematic tag (just one to avoid overly long queries)
    parts.append("cinematic")

    # 4. Style modifiers (max 1)
    if style_modifiers:
        parts.append(style_modifiers[0])

    # Build final query — stock APIs work best with 2-5 word queries
    query = " ".join(parts)

    # Trim to reasonable length for stock API (max ~8 words)
    words = query.split()
    if len(words) > 8:
        words = words[:8]
    query = " ".join(words)

    return query


def build_elite_search_query(
    scene: SceneSegment,
    style_modifiers: List[str] = None,
    pacing_context: str = "",
) -> str:
    """
    Build an ELITE search query combining:
    1. Semantic topic (what the scene is about)
    2. Emotional tag (mood modifier)
    3. Cinematic style tag (visual aesthetic)
    4. Pacing context (movement/speed descriptor)

    Example output: "moody cinematic businessman walking alone slow motion rain dramatic lighting"

    Returns a rich search string optimized for stock footage APIs.
    """
    parts = []

    # 1. Semantic topic (1-3 words)
    if scene.topic:
        parts.append(scene.topic)

    # 2. Emotion modifier — richer selection based on intensity
    emotion_mods = EMOTION_MODIFIERS.get(scene.emotion, EMOTION_MODIFIERS["dramatic"])
    mod_index = min(int(scene.intensity * len(emotion_mods)), len(emotion_mods) - 1)
    parts.append(emotion_mods[mod_index])

    # 3. Shot type visual hint
    shot_mod = SHOT_TYPE_MODIFIERS.get(scene.shot_type, "")
    if shot_mod:
        # Take just the first 2 words of the shot modifier
        shot_words = shot_mod.split()[:2]
        parts.append(" ".join(shot_words))

    # 4. Pacing context (movement style)
    if not pacing_context:
        pacing_context = PACING_CONTEXT_MODIFIERS.get(scene.narrative_role, "cinematic")
    # Take first word of pacing context
    pacing_word = pacing_context.split()[0] if pacing_context else ""
    if pacing_word and pacing_word not in " ".join(parts):
        parts.append(pacing_word)

    # 5. Style modifiers (max 1)
    if style_modifiers:
        parts.append(style_modifiers[0])

    # 6. Always add cinematic for quality
    if "cinematic" not in " ".join(parts):
        parts.append("cinematic")

    # Build and trim
    query = " ".join(parts)
    words = query.split()
    if len(words) > 8:
        words = words[:8]
    query = " ".join(words)

    return query


def build_all_search_queries(
    scenes: List[SceneSegment],
    video_style: str = "",
    use_elite: bool = True,
) -> List[SceneSegment]:
    """Build search queries for all scenes, incorporating style profile."""
    style_modifiers = []

    if video_style:
        try:
            from app.services.style_presets import get_visual_profile
            profile = get_visual_profile(video_style)
            if profile:
                style_modifiers = profile.get("search_modifiers", [])
        except (ImportError, AttributeError):
            pass

    for scene in scenes:
        if use_elite:
            scene.search_query = build_elite_search_query(scene, style_modifiers)
        else:
            scene.search_query = build_emotion_search_query(scene, style_modifiers)

    logger.info(f"built {len(scenes)} {'elite' if use_elite else 'emotion'} search queries")
    for s in scenes:
        logger.debug(f"  scene {s.scene_index}: [{s.emotion} {s.intensity:.1f}] → \"{s.search_query}\"")

    return scenes


# ── Multi-Candidate Re-Ranking ───────────────────────────────────────────────

def score_clip_for_scene(
    clip_data: dict,
    scene: SceneSegment,
    used_urls: set = None,
) -> float:
    """
    Score a candidate clip for how well it matches a scene.

    Scoring factors:
      - Resolution quality (0-3 points)
      - Duration appropriateness (0-2 points)
      - Novelty: not already used (0-2 points)
      - Emotion keyword overlap (0-3 points)

    Returns: float score (higher = better match)
    """
    score = 0.0

    # Resolution scoring
    width = clip_data.get("width", 0)
    height = clip_data.get("height", 0)
    if width >= 1920 or height >= 1920:
        score += 3.0  # 4K/Full HD
    elif width >= 1280 or height >= 1280:
        score += 2.0  # HD
    elif width >= 720 or height >= 720:
        score += 1.0  # SD
    # else: 0 points

    # Duration scoring
    duration = clip_data.get("duration", 0)
    if 3 <= duration <= 15:
        score += 2.0  # ideal range
    elif duration > 1:
        score += 1.0

    # Novelty scoring
    url = clip_data.get("url", "")
    if used_urls and url in used_urls:
        score -= 2.0  # penalize reuse
    else:
        score += 2.0

    # Quality score from API
    quality = clip_data.get("quality_score", 0)
    score += quality * 0.5

    return score


def rank_candidates(
    candidates: list,
    scene: SceneSegment,
    used_urls: set = None,
    top_k: int = 3,
) -> list:
    """
    Rank candidate clips and return the top-K best matches for a scene.
    """
    if not candidates:
        return []

    scored = []
    for clip in candidates:
        clip_score = score_clip_for_scene(clip, scene, used_urls)
        scored.append((clip_score, clip))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    results = [clip for _, clip in scored[:top_k]]
    logger.debug(
        f"scene {scene.scene_index}: ranked {len(candidates)} candidates, "
        f"top score={scored[0][0]:.1f}" if scored else "no candidates"
    )

    return results
