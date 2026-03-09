"""
Production Priority Score — Viral Score Engine.

Centralized scoring formula for publish/reject decisions:

ViralScore = (HookScore × 0.3) + (EmotionVariance × 0.2)
           + (CuriosityDensity × 0.2) + (VisualDiversity × 0.15)
           + (ControversyFactor × 0.15)

Only export videos above threshold. Regenerate others.
"""

import re
from typing import Dict, List, Optional, Any
from loguru import logger


# ── Component Scoring ────────────────────────────────────────────────────────

HOOK_POWER_WORDS = {
    "stop", "wait", "warning", "never", "always", "secret", "hidden",
    "truth", "lie", "dark", "shocking", "nobody", "everything", "wrong",
    "dangerous", "powerful", "mistake", "illegal", "banned", "exposed",
    "you", "your", "right now", "immediately",
}

CURIOSITY_INDICATORS = [
    "?", "but wait", "here's the thing", "what if", "you won't believe",
    "the truth is", "most people don't know", "nobody tells you",
    "the real reason", "but first", "keep watching", "stay tuned",
    "before I tell you", "the part most people miss",
]

CONTROVERSY_MARKERS = [
    "unpopular opinion", "most people", "nobody agrees", "controversial",
    "they don't want you to know", "the truth they hide", "uncomfortable truth",
    "you'll hate this", "this will offend", "not everyone can handle",
    "debate", "polarizing", "divided", "outrage",
]


def compute_hook_score(script: str) -> float:
    """
    Score the first 3 sentences for hook strength (0-100).

    Factors:
    - Power word density
    - Question/exclamation presence
    - Sentence shortness
    - Pattern interrupt detection
    """
    if not script:
        return 0.0

    # Extract first 3 sentences
    sentences = re.split(r'[.!?]+', script)
    hook_text = " ".join(sentences[:3]).lower().strip()

    if not hook_text:
        return 0.0

    score = 0.0

    # Power word density (0-40 points)
    words = hook_text.split()
    power_count = sum(1 for w in words if w.strip(".,;:'\"!?") in HOOK_POWER_WORDS)
    word_density = power_count / max(len(words), 1)
    score += min(40.0, word_density * 200)

    # Question/exclamation (0-20 points)
    if "?" in hook_text:
        score += 15.0
    if "!" in hook_text:
        score += 5.0

    # Short punchy sentences (0-20 points)
    avg_words = len(words) / max(len(sentences[:3]), 1)
    if avg_words <= 8:
        score += 20.0
    elif avg_words <= 12:
        score += 15.0
    elif avg_words <= 16:
        score += 10.0
    else:
        score += 5.0

    # Pattern interrupt (0-20 points)
    pattern_interrupts = ["stop", "wait", "hold on", "pause", "listen"]
    if any(pi in hook_text for pi in pattern_interrupts):
        score += 20.0
    elif hook_text.startswith(("you ", "your ")):
        score += 10.0

    return min(100.0, round(score, 1))


def compute_emotion_variance(scenes: list = None) -> float:
    """
    Score emotion diversity across scenes (0-100).
    More diverse emotions = higher score.
    """
    if not scenes:
        return 50.0  # neutral if no scenes

    emotions = [getattr(s, "emotion", "neutral") for s in scenes if getattr(s, "emotion", None)]

    if not emotions:
        return 30.0

    unique = len(set(emotions))
    total = len(emotions)

    # Diversity ratio
    diversity = unique / max(total, 1)

    # Bonus for emotion transitions (changes between adjacent scenes)
    transitions = sum(1 for i in range(1, len(emotions)) if emotions[i] != emotions[i-1])
    transition_ratio = transitions / max(total - 1, 1)

    score = (diversity * 60) + (transition_ratio * 40)
    return min(100.0, round(score, 1))


def compute_curiosity_density(script: str) -> float:
    """
    Score open loops / curiosity gaps per sentence ratio (0-100).
    """
    if not script:
        return 0.0

    script_lower = script.lower()
    sentences = re.split(r'[.!?]+', script)
    sentence_count = max(len([s for s in sentences if s.strip()]), 1)

    curiosity_count = sum(1 for indicator in CURIOSITY_INDICATORS if indicator in script_lower)

    # Also count questions
    question_count = script.count("?")

    total_curiosity = curiosity_count + question_count
    density = total_curiosity / sentence_count

    # Scale to 0-100 (ideal: 1 curiosity element per 3-4 sentences)
    if density >= 0.4:
        score = 100.0
    elif density >= 0.25:
        score = 80.0
    elif density >= 0.15:
        score = 60.0
    elif density >= 0.08:
        score = 40.0
    else:
        score = density * 250  # linear scale for low density

    return min(100.0, round(score, 1))


def compute_visual_diversity(scenes: list = None) -> float:
    """
    Score unique shot types / total shots (0-100).
    """
    if not scenes:
        return 50.0

    shot_types = [getattr(s, "shot_type", "medium") for s in scenes]
    if not shot_types:
        return 50.0

    unique = len(set(shot_types))
    total = len(shot_types)

    diversity = unique / max(total, 1)

    # Scale to 0-100
    score = diversity * 100

    # Bonus for no consecutive same shots
    consecutive_repeats = sum(1 for i in range(1, len(shot_types)) if shot_types[i] == shot_types[i-1])
    if consecutive_repeats == 0 and total > 1:
        score = min(100, score + 15)

    return min(100.0, round(score, 1))


def compute_controversy_factor(script: str) -> float:
    """
    Score polarizing statement density (0-100).
    Some controversy drives engagement, too much risks penalties.
    """
    if not script:
        return 0.0

    script_lower = script.lower()
    controversy_hits = sum(1 for marker in CONTROVERSY_MARKERS if marker in script_lower)

    sentences = re.split(r'[.!?]+', script)
    sentence_count = max(len([s for s in sentences if s.strip()]), 1)

    density = controversy_hits / sentence_count

    # Sweet spot: 0.1 - 0.5 density
    if 0.1 <= density <= 0.5:
        score = 80 + (density * 30)  # bonus for sweet spot
    elif density > 0.5:
        score = max(30, 95 - (density - 0.5) * 40)  # soft penalty for excess
    else:
        score = density * 600  # low controversy

    return max(0.0, min(100.0, round(score, 1)))


# ── Master Viral Score ───────────────────────────────────────────────────────

VIRAL_WEIGHTS = {
    "hook_score": 0.30,
    "emotion_variance": 0.20,
    "curiosity_density": 0.20,
    "visual_diversity": 0.15,
    "controversy_factor": 0.15,
}


def compute_viral_score(
    script: str,
    scenes: list = None,
    weights: Dict[str, float] = None,
) -> Dict[str, Any]:
    """
    Compute the production priority viral score.

    ViralScore = (HookScore × 0.3) + (EmotionVariance × 0.2)
               + (CuriosityDensity × 0.2) + (VisualDiversity × 0.15)
               + (ControversyFactor × 0.15)

    Returns:
        {
            "viral_score": 75.5,
            "hook_score": 80.0,
            "emotion_variance": 65.0,
            "curiosity_density": 70.0,
            "visual_diversity": 85.0,
            "controversy_factor": 60.0,
            "grade": "A",
        }
    """
    w = weights or VIRAL_WEIGHTS

    components = {
        "hook_score": compute_hook_score(script),
        "emotion_variance": compute_emotion_variance(scenes),
        "curiosity_density": compute_curiosity_density(script),
        "visual_diversity": compute_visual_diversity(scenes),
        "controversy_factor": compute_controversy_factor(script),
    }

    viral_score = sum(
        components[key] * w.get(key, 0.2)
        for key in components
    )
    viral_score = round(viral_score, 1)

    # Grade assignment
    if viral_score >= 85:
        grade = "S"
    elif viral_score >= 75:
        grade = "A"
    elif viral_score >= 60:
        grade = "B"
    elif viral_score >= 45:
        grade = "C"
    else:
        grade = "D"

    result = {
        "viral_score": viral_score,
        **components,
        "grade": grade,
    }

    logger.info(f"viral score: {viral_score} (grade={grade}) — hook={components['hook_score']}, "
                f"emotion={components['emotion_variance']}, curiosity={components['curiosity_density']}")
    return result


# ── Threshold Gating ─────────────────────────────────────────────────────────

def gate_for_export(
    score: float,
    threshold: float = 60.0,
) -> bool:
    """
    Determine if a video passes the quality gate for export.
    Returns True if score >= threshold.
    """
    passed = score >= threshold
    if not passed:
        logger.warning(f"video REJECTED: score {score:.1f} < threshold {threshold:.1f}")
    else:
        logger.success(f"video APPROVED: score {score:.1f} >= threshold {threshold:.1f}")
    return passed


def recommend_improvements(score_breakdown: Dict[str, Any]) -> List[str]:
    """
    Based on component scores, recommend specific improvements.
    """
    recommendations = []
    threshold_low = 50.0

    if score_breakdown.get("hook_score", 0) < threshold_low:
        recommendations.append("Strengthen hook: add power words, pattern interrupt, or direct question")

    if score_breakdown.get("emotion_variance", 0) < threshold_low:
        recommendations.append("Increase emotion diversity: vary emotional tone across scenes")

    if score_breakdown.get("curiosity_density", 0) < threshold_low:
        recommendations.append("Add more open loops: inject curiosity gaps every 4-5 sentences")

    if score_breakdown.get("visual_diversity", 0) < threshold_low:
        recommendations.append("Diversify visuals: mix shot types (wide, close, detail, motion)")

    if score_breakdown.get("controversy_factor", 0) < threshold_low:
        recommendations.append("Add polarizing element: include a debatable statement or challenge")

    return recommendations
