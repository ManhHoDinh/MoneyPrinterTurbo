"""
Retention Simulator — Predict audience retention curve and reject weak scripts.

Models a simplified attention curve based on:
  - Hook strength (first 3 seconds / sentences)
  - Scene pacing (visual change frequency)
  - Open loop density (curiosity gaps per 15s block)
  - Emotion arc shifts (variety of emotional tones)
  - Pattern interrupts (surprise elements that re-engage)

Return a predicted retention score (0-100) and a per-segment breakdown.
Scripts below the threshold are rejected before video generation.

Usage:
    from app.services.retention_simulator import simulate_retention
    result = simulate_retention(script="...", style="dark_psychology")
    if not result.passed:
        print(f"Rejected: {result.rejection_reason}")
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any

from loguru import logger


# ── Retention Constants ──────────────────────────────────────────────────────

DEFAULT_THRESHOLD = 55.0

# Attention decay per 15-second block (baseline without re-engagement)
BASE_DECAY_CURVE = [100, 88, 78, 70, 63, 58, 54, 50, 47, 44, 42, 40]

# Words that create pattern interrupts (re-engage attention)
INTERRUPT_WORDS = [
    "but wait", "here's the thing", "plot twist", "now here's where",
    "think about this", "let me explain", "the crazy part",
    "nobody expected", "suddenly", "but then", "the real question",
    "actually", "what most people miss", "the shocking part",
    "before I continue", "stay with me", "here's why",
]

# Words indicating emotional shift (maintain attention via variety)
EMOTION_SHIFT_WORDS = {
    "fear": ["dangerous", "terrifying", "nightmare", "warning", "deadly"],
    "curiosity": ["secret", "hidden", "discover", "reveals", "truth"],
    "anger": ["unfair", "outrageous", "disgusting", "corrupt", "rigged"],
    "hope": ["solution", "answer", "breakthrough", "finally", "possible"],
    "surprise": ["shocking", "unbelievable", "nobody", "impossible"],
}


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class SegmentAnalysis:
    """Analysis of a single 15-second script segment."""
    index: int = 0
    text: str = ""
    base_retention: float = 100.0
    interrupt_bonus: float = 0.0
    emotion_shift_bonus: float = 0.0
    open_loop_bonus: float = 0.0
    final_retention: float = 100.0
    dominant_emotion: str = "neutral"


@dataclass
class RetentionResult:
    """Full retention simulation result."""
    overall_score: float = 0.0
    hook_score: float = 0.0
    avg_retention: float = 0.0
    min_retention: float = 0.0
    dropoff_point: int = -1          # Segment index where retention drops below 40%
    passed: bool = True
    threshold: float = DEFAULT_THRESHOLD
    rejection_reason: str = ""
    segments: List[SegmentAnalysis] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "hook_score": self.hook_score,
            "avg_retention": self.avg_retention,
            "min_retention": self.min_retention,
            "dropoff_point": self.dropoff_point,
            "passed": self.passed,
            "threshold": self.threshold,
            "rejection_reason": self.rejection_reason,
            "segment_count": len(self.segments),
            "recommendations": self.recommendations,
        }


# ── Public API ───────────────────────────────────────────────────────────────

def simulate_retention(
    script: str,
    style: str = "",
    threshold: float = DEFAULT_THRESHOLD,
    words_per_15s: int = 40,
) -> RetentionResult:
    """
    Simulate audience retention for a given script.

    Args:
        script:        Full video script text
        style:         Style preset name (adjusts expectations)
        threshold:     Minimum overall score to pass (0-100)
        words_per_15s: Estimated words spoken per 15-second segment

    Returns:
        RetentionResult with scores, segment breakdown, and pass/fail.
    """
    if not script or not script.strip():
        return RetentionResult(
            overall_score=0,
            passed=False,
            rejection_reason="Empty script",
        )

    # Split script into ~15-second segments
    words = script.split()
    segments_text = []
    for i in range(0, len(words), words_per_15s):
        chunk = " ".join(words[i:i + words_per_15s])
        if chunk.strip():
            segments_text.append(chunk)

    if not segments_text:
        return RetentionResult(overall_score=0, passed=False, rejection_reason="No content")

    # Analyze each segment
    segments = []
    prev_emotion = ""
    for idx, text in enumerate(segments_text):
        seg = _analyze_segment(idx, text, prev_emotion)
        segments.append(seg)
        prev_emotion = seg.dominant_emotion

    # Calculate hook score (first segment)
    hook_score = _score_hook(segments_text[0]) if segments_text else 0

    # Compute overall metrics
    retentions = [s.final_retention for s in segments]
    avg_retention = sum(retentions) / len(retentions) if retentions else 0
    min_retention = min(retentions) if retentions else 0

    # Dropoff point: first segment below 40%
    dropoff = -1
    for i, r in enumerate(retentions):
        if r < 40:
            dropoff = i
            break

    # Overall score: weighted combination
    overall = (
        hook_score * 0.35
        + avg_retention * 0.40
        + min_retention * 0.25
    )

    # Style adjustments
    style_bonus = _style_adjustment(style, segments)
    overall += style_bonus

    overall = max(0.0, min(100.0, round(overall, 1)))

    # Generate recommendations
    recommendations = _generate_recommendations(
        hook_score, avg_retention, min_retention, dropoff, segments
    )

    # Pass/fail
    passed = overall >= threshold
    rejection_reason = ""
    if not passed:
        if hook_score < 40:
            rejection_reason = f"Weak hook ({hook_score:.0f}/100)"
        elif min_retention < 30:
            rejection_reason = f"Critical retention drop at segment {dropoff}"
        else:
            rejection_reason = f"Below threshold ({overall:.0f} < {threshold:.0f})"

    result = RetentionResult(
        overall_score=overall,
        hook_score=round(hook_score, 1),
        avg_retention=round(avg_retention, 1),
        min_retention=round(min_retention, 1),
        dropoff_point=dropoff,
        passed=passed,
        threshold=threshold,
        rejection_reason=rejection_reason,
        segments=segments,
        recommendations=recommendations,
    )

    level = "✅" if passed else "❌"
    logger.info(
        f"[RetentionSim] {level} score={overall:.0f} hook={hook_score:.0f} "
        f"avg={avg_retention:.0f} min={min_retention:.0f} "
        f"segments={len(segments)} style={style}"
    )

    return result


def batch_filter(
    scripts: List[Dict[str, str]],
    threshold: float = DEFAULT_THRESHOLD,
) -> Dict[str, Any]:
    """
    Filter a batch of scripts, returning only those that pass retention.

    Args:
        scripts: List of {"topic": "...", "script": "...", "style": "..."} dicts
        threshold: Minimum score to pass

    Returns:
        {"passed": [...], "rejected": [...], "stats": {...}}
    """
    passed = []
    rejected = []

    for item in scripts:
        result = simulate_retention(
            script=item.get("script", ""),
            style=item.get("style", ""),
            threshold=threshold,
        )
        entry = {
            "topic": item.get("topic", ""),
            "score": result.overall_score,
            "hook_score": result.hook_score,
            "reason": result.rejection_reason,
        }
        if result.passed:
            passed.append(entry)
        else:
            rejected.append(entry)

    return {
        "passed": passed,
        "rejected": rejected,
        "stats": {
            "total": len(scripts),
            "passed": len(passed),
            "rejected": len(rejected),
            "pass_rate": round(len(passed) / len(scripts) * 100, 1) if scripts else 0,
        },
    }


# ── Internal Analysis ────────────────────────────────────────────────────────

def _analyze_segment(idx: int, text: str, prev_emotion: str) -> SegmentAnalysis:
    """Analyze a single script segment for retention factors."""
    text_lower = text.lower()

    # Base retention from decay curve
    base = BASE_DECAY_CURVE[idx] if idx < len(BASE_DECAY_CURVE) else 38.0

    # Pattern interrupt bonus
    interrupt_bonus = 0.0
    for phrase in INTERRUPT_WORDS:
        if phrase in text_lower:
            interrupt_bonus += 6.0
    interrupt_bonus = min(interrupt_bonus, 18.0)

    # Emotion detection
    dominant = "neutral"
    max_hits = 0
    for emotion, keywords in EMOTION_SHIFT_WORDS.items():
        hits = sum(1 for k in keywords if k in text_lower)
        if hits > max_hits:
            max_hits = hits
            dominant = emotion

    # Emotion shift bonus (changing emotion re-engages)
    emotion_bonus = 0.0
    if prev_emotion and dominant != prev_emotion and dominant != "neutral":
        emotion_bonus = 8.0

    # Open loop bonus (questions, ellipses, "but...")
    open_loop_bonus = 0.0
    if "?" in text:
        open_loop_bonus += 5.0
    if "..." in text:
        open_loop_bonus += 3.0
    if text_lower.strip().endswith("but"):
        open_loop_bonus += 6.0
    if any(w in text_lower for w in ["but wait", "here's the thing", "the twist"]):
        open_loop_bonus += 7.0

    final = min(100.0, base + interrupt_bonus + emotion_bonus + open_loop_bonus)

    return SegmentAnalysis(
        index=idx,
        text=text[:100] + "..." if len(text) > 100 else text,
        base_retention=base,
        interrupt_bonus=round(interrupt_bonus, 1),
        emotion_shift_bonus=round(emotion_bonus, 1),
        open_loop_bonus=round(open_loop_bonus, 1),
        final_retention=round(final, 1),
        dominant_emotion=dominant,
    )


def _score_hook(first_segment: str) -> float:
    """Score the opening hook (first ~15 seconds)."""
    score = 50.0  # Base

    text = first_segment.lower()
    words = text.split()

    # Short, punchy opening (fewer words = better hook)
    if len(words) <= 15:
        score += 15
    elif len(words) <= 25:
        score += 8

    # Question hook
    if "?" in first_segment:
        score += 12

    # Direct address ("you")
    if "you" in words[:10]:
        score += 8

    # Power words in first sentence
    power_words = ["secret", "never", "always", "shocking", "truth", "nobody",
                   "dangerous", "hidden", "mistake", "stop", "warning", "urgent"]
    hook_power = sum(1 for w in power_words if w in text)
    score += hook_power * 6

    # Curse of knowledge breaker (simple language)
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 5
    if avg_word_len <= 5.0:
        score += 5  # Simple = accessible = better hook

    return max(0.0, min(100.0, score))


def _style_adjustment(style: str, segments: list) -> float:
    """Apply style-specific retention adjustments."""
    bonuses = {
        "dark_psychology": 3.0,     # Inherently attention-grabbing
        "high_energy": 2.0,         # Fast pacing helps retention
        "motivation": -2.0,         # Motivation fatigue is real
        "luxury_lifestyle": 1.0,
        "stoic_philosophy": -3.0,   # Slower, higher drop risk
        "minimal_calm": -5.0,       # Calm = lower retention baseline
        "viral_facts": 4.0,         # Facts = natural curiosity
    }
    return bonuses.get(style, 0.0)


def _generate_recommendations(
    hook_score: float,
    avg_retention: float,
    min_retention: float,
    dropoff: int,
    segments: list,
) -> List[str]:
    """Generate actionable improvement recommendations."""
    recs = []

    if hook_score < 50:
        recs.append("HOOK: Open with a bold question or shocking statement in first 3 seconds")
    if hook_score < 70:
        recs.append("HOOK: Add direct address ('you') in opening line")

    if avg_retention < 55:
        recs.append("PACING: Add more pattern interrupts ('but here's the thing', 'plot twist')")
    if avg_retention < 45:
        recs.append("PACING: Shorten scenes to 2-3 seconds maximum")

    if min_retention < 35:
        recs.append(f"DROPOUT: Critical drop at segment {dropoff} — add open loop before it")
    if min_retention < 25:
        recs.append("DROPOUT: Consider splitting into a shorter video")

    # Check for emotional flatness
    emotions = {s.dominant_emotion for s in segments}
    if len(emotions) <= 2:
        recs.append("EMOTION: Script is emotionally flat — introduce fear/surprise shifts")

    if dropoff >= 0 and dropoff < len(segments) - 2:
        recs.append(f"STRUCTURE: Move strongest content to segment {dropoff} to prevent dropoff")

    return recs
