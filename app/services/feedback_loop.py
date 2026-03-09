"""
Self-Learning Feedback Loop — GOD MODE Performance Learning.

Stores performance signals (watch time, drop-off, comment rate, like velocity)
and adjusts hook types, pacing, and emotion preferences based on historical
performance data. System improves over time.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from loguru import logger


# ── Feedback Signal ──────────────────────────────────────────────────────────

@dataclass
class FeedbackSignal:
    """Performance data for a completed video."""
    video_id: str = ""
    task_id: str = ""
    topic: str = ""
    style: str = ""
    hook_variant_id: int = -1
    hook_psych_type: str = ""
    pacing_speed: float = 1.0         # BLACK OPS: store pacing data
    channel_profile: str = ""         # BLACK OPS: store channel profile
    # Performance metrics
    watch_time: float = 0.0           # average watch time in seconds
    drop_off_point: float = 0.0       # timestamp where most viewers drop off
    completion_rate: float = 0.0      # % of viewers who watched to the end
    comment_rate: float = 0.0         # comments per 1000 views
    like_velocity: float = 0.0        # likes per hour in first 24h
    share_count: int = 0
    view_count: int = 0
    # Context
    emotion_profile: List[str] = field(default_factory=list)
    topic_score: float = 0.0
    timestamp: float = field(default_factory=time.time)


# ── Feedback Store ───────────────────────────────────────────────────────────

class FeedbackStore:
    """
    Stores and retrieves feedback signals for performance learning.
    Uses JSON files per video in a feedback directory.
    """

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            storage_dir = os.path.join(root_dir, "storage", "feedback")
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def record(self, signal: FeedbackSignal) -> str:
        """Record a feedback signal. Returns the storage path."""
        video_id = signal.video_id or f"video_{int(signal.timestamp)}"
        file_path = os.path.join(self.storage_dir, f"{video_id}.json")

        data = asdict(signal)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"feedback recorded for video '{video_id}'")
        return file_path

    def load(self, video_id: str) -> Optional[FeedbackSignal]:
        """Load a specific feedback signal."""
        file_path = os.path.join(self.storage_dir, f"{video_id}.json")
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return FeedbackSignal(**{k: v for k, v in data.items()
                                if k in FeedbackSignal.__dataclass_fields__})

    def load_all(self, limit: int = 100) -> List[FeedbackSignal]:
        """Load all feedback signals, most recent first."""
        signals = []
        if not os.path.exists(self.storage_dir):
            return signals

        files = sorted(
            [f for f in os.listdir(self.storage_dir) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(self.storage_dir, f)),
            reverse=True,
        )

        for filename in files[:limit]:
            try:
                file_path = os.path.join(self.storage_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                signal = FeedbackSignal(**{k: v for k, v in data.items()
                                          if k in FeedbackSignal.__dataclass_fields__})
                signals.append(signal)
            except Exception as e:
                logger.warning(f"failed to load feedback {filename}: {e}")

        return signals

    def load_by_style(self, style: str, limit: int = 50) -> List[FeedbackSignal]:
        """Load feedback signals filtered by video style."""
        all_signals = self.load_all(limit=limit * 3)
        return [s for s in all_signals if s.style == style][:limit]


# ── Performance Analysis ─────────────────────────────────────────────────────

_store: Optional[FeedbackStore] = None


def _get_store() -> FeedbackStore:
    """Get or create the global feedback store."""
    global _store
    if _store is None:
        _store = FeedbackStore()
    return _store


def record_feedback(signal: FeedbackSignal) -> str:
    """Record performance feedback for a video."""
    return _get_store().record(signal)


def get_performance_summary(
    style: str = "",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Aggregate recent feedback by style/hook_type/topic.

    Returns:
        {
            "total_videos": 25,
            "avg_watch_time": 18.5,
            "avg_completion_rate": 0.62,
            "avg_comment_rate": 3.2,
            "hook_performance": {"fear": 0.8, "curiosity": 1.2, ...},
            "top_emotions": ["curiosity", "tension"],
            "avg_drop_off_point": 12.5,
        }
    """
    store = _get_store()
    if style:
        signals = store.load_by_style(style, limit)
    else:
        signals = store.load_all(limit)

    if not signals:
        return {"total_videos": 0, "message": "no feedback data available"}

    total = len(signals)
    avg_watch_time = sum(s.watch_time for s in signals) / total
    avg_completion = sum(s.completion_rate for s in signals) / total
    avg_comment_rate = sum(s.comment_rate for s in signals) / total
    avg_drop_off = sum(s.drop_off_point for s in signals) / total

    # Hook performance: average completion rate per hook type
    hook_perf: Dict[str, List[float]] = {}
    for s in signals:
        if s.hook_psych_type:
            hook_perf.setdefault(s.hook_psych_type, []).append(s.completion_rate)

    hook_weights = {}
    for hook_type, rates in hook_perf.items():
        hook_weights[hook_type] = sum(rates) / len(rates) if rates else 0.5

    # Top emotions: rank by frequency in high-performing videos
    high_performers = [s for s in signals if s.completion_rate > avg_completion]
    emotion_counts: Dict[str, int] = {}
    for s in high_performers:
        for em in s.emotion_profile:
            emotion_counts[em] = emotion_counts.get(em, 0) + 1

    top_emotions = sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)
    top_emotions = [e for e, _ in top_emotions[:5]]

    return {
        "total_videos": total,
        "avg_watch_time": round(avg_watch_time, 1),
        "avg_completion_rate": round(avg_completion, 3),
        "avg_comment_rate": round(avg_comment_rate, 1),
        "avg_drop_off_point": round(avg_drop_off, 1),
        "hook_performance": hook_weights,
        "top_emotions": top_emotions,
    }


def adjust_hook_weights(limit: int = 50) -> Dict[str, float]:
    """
    Compute hook type weights based on performance data.

    Higher weight = this hook type correlates with better watch time.
    Returns: {"fear": 0.8, "curiosity": 1.2, "shock": 1.0, ...}

    Default weight is 1.0 when no data is available.
    """
    store = _get_store()
    signals = store.load_all(limit)

    if not signals:
        return {}

    # Group by hook type → average watch_time
    hook_data: Dict[str, List[float]] = {}
    for s in signals:
        if s.hook_psych_type and s.watch_time > 0:
            hook_data.setdefault(s.hook_psych_type, []).append(s.watch_time)

    if not hook_data:
        return {}

    # Calculate average watch time per hook type
    avg_per_type = {
        ht: sum(times) / len(times) for ht, times in hook_data.items()
    }

    # Normalize to weights (1.0 = average)
    global_avg = sum(avg_per_type.values()) / len(avg_per_type)
    if global_avg == 0:
        return {ht: 1.0 for ht in avg_per_type}

    weights = {ht: round(avg / global_avg, 2) for ht, avg in avg_per_type.items()}
    logger.info(f"hook weights adjusted from feedback: {weights}")
    return weights


def adjust_pacing_preferences(limit: int = 50) -> Dict[str, Any]:
    """
    Determine pacing preferences from drop-off patterns.

    If viewers drop off early → need faster pacing / more pattern interrupts.
    If completion is high → current pacing is good.

    Returns:
        {
            "recommended_clip_duration": 2.5,
            "needs_faster_pacing": True,
            "early_drop_off_detected": True,
            "avg_drop_off_ratio": 0.35,
        }
    """
    store = _get_store()
    signals = store.load_all(limit)

    if not signals:
        return {"recommended_clip_duration": 3.0, "needs_faster_pacing": False,
                "early_drop_off_detected": False, "avg_drop_off_ratio": 0.5}

    # Calculate drop-off ratio (where in the video viewers leave)
    drop_off_ratios = []
    for s in signals:
        if s.watch_time > 0 and s.drop_off_point > 0:
            ratio = s.drop_off_point / max(s.watch_time, 1)
            drop_off_ratios.append(min(ratio, 1.0))

    if not drop_off_ratios:
        return {"recommended_clip_duration": 3.0, "needs_faster_pacing": False,
                "early_drop_off_detected": False, "avg_drop_off_ratio": 0.5}

    avg_ratio = sum(drop_off_ratios) / len(drop_off_ratios)

    # Early drop-off = before 40% of video
    early_drop_off = avg_ratio < 0.4
    needs_faster = avg_ratio < 0.5

    # Recommend clip duration based on engagement
    if early_drop_off:
        clip_duration = 2.0  # fast cuts to recover attention
    elif needs_faster:
        clip_duration = 2.5
    else:
        clip_duration = 3.0

    return {
        "recommended_clip_duration": clip_duration,
        "needs_faster_pacing": needs_faster,
        "early_drop_off_detected": early_drop_off,
        "avg_drop_off_ratio": round(avg_ratio, 2),
    }


def get_preferred_emotions(limit: int = 50) -> List[str]:
    """
    Rank emotions by engagement correlation across recent videos.
    Returns emotions sorted by performance (best first).
    """
    store = _get_store()
    signals = store.load_all(limit)

    if not signals:
        return ["curiosity", "tension", "shock"]

    # Score each emotion by the average completion rate of videos that used it
    emotion_scores: Dict[str, List[float]] = {}
    for s in signals:
        for em in s.emotion_profile:
            emotion_scores.setdefault(em, []).append(s.completion_rate)

    avg_scores = {
        em: sum(rates) / len(rates)
        for em, rates in emotion_scores.items()
        if rates
    }

    ranked = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
    result = [em for em, _ in ranked]

    if result:
        logger.info(f"preferred emotions from feedback: {result[:5]}")

    return result if result else ["curiosity", "tension", "shock"]


# ── Genome-Aware Learning ────────────────────────────────────────────────────

def prioritize_genome_patterns(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Return top genomes ranked by average performance across feedback data.
    Correlates genome_id from feedback signals with genome store data.
    """
    store = _get_store()
    signals = store.load_all(limit)

    if not signals:
        return []

    # Group performance by task_id (proxy for genome)
    task_perf: Dict[str, Dict] = {}
    for s in signals:
        tid = s.task_id or s.video_id
        if not tid:
            continue
        if tid not in task_perf:
            task_perf[tid] = {
                "task_id": tid,
                "style": s.style,
                "hook_type": s.hook_psych_type,
                "watch_times": [],
                "completion_rates": [],
                "comment_rates": [],
            }
        task_perf[tid]["watch_times"].append(s.watch_time)
        task_perf[tid]["completion_rates"].append(s.completion_rate)
        task_perf[tid]["comment_rates"].append(s.comment_rate)

    # Compute composite score per genome
    ranked = []
    for tid, data in task_perf.items():
        avg_watch = sum(data["watch_times"]) / max(len(data["watch_times"]), 1)
        avg_completion = sum(data["completion_rates"]) / max(len(data["completion_rates"]), 1)
        avg_comment = sum(data["comment_rates"]) / max(len(data["comment_rates"]), 1)

        composite = (avg_watch * 0.4) + (avg_completion * 40) + (avg_comment * 0.2)
        ranked.append({
            "task_id": tid,
            "style": data["style"],
            "hook_type": data["hook_type"],
            "avg_watch_time": round(avg_watch, 1),
            "avg_completion_rate": round(avg_completion, 3),
            "avg_comment_rate": round(avg_comment, 1),
            "composite_score": round(composite, 2),
        })

    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    logger.info(f"prioritized {len(ranked)} genome patterns by performance")
    return ranked[:limit]


def get_weak_genomes(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Return genomes with consistently low performance.
    These patterns should be avoided in future generation.
    """
    all_patterns = prioritize_genome_patterns(limit=100)
    if not all_patterns:
        return []

    # Bottom 30% by composite score
    cutoff = max(1, int(len(all_patterns) * 0.3))
    weak = all_patterns[-cutoff:]

    logger.info(f"identified {len(weak)} weak genome patterns to avoid")
    return weak[:limit]


def auto_adjust_pacing_rules() -> Dict[str, Any]:
    """
    Auto-adjust pacing configuration based on completion rate data.
    Combines drop-off analysis with hook/pacing performance correlation.
    """
    pacing_prefs = adjust_pacing_preferences()
    hook_weights = adjust_hook_weights()
    preferred_emotions = get_preferred_emotions()

    adjustments = {
        "pacing": pacing_prefs,
        "hook_weights": hook_weights,
        "preferred_emotions": preferred_emotions[:3],
        "rules": {},
    }

    # Derive specific rule adjustments
    if pacing_prefs.get("early_drop_off_detected"):
        adjustments["rules"]["max_static_duration"] = 3.0
        adjustments["rules"]["hook_max_duration"] = 1.5
        adjustments["rules"]["pattern_interrupt_interval"] = 6.0
    elif pacing_prefs.get("needs_faster_pacing"):
        adjustments["rules"]["max_static_duration"] = 4.0
        adjustments["rules"]["hook_max_duration"] = 2.0
        adjustments["rules"]["pattern_interrupt_interval"] = 8.0
    else:
        adjustments["rules"]["max_static_duration"] = 5.0
        adjustments["rules"]["hook_max_duration"] = 2.5
        adjustments["rules"]["pattern_interrupt_interval"] = 10.0

    logger.info(f"auto-adjusted pacing rules: {adjustments['rules']}")
    return adjustments


def get_evolution_recommendations() -> Dict[str, Any]:
    """
    Suggest genome mutations based on top performers.
    Recommends what to keep, what to change, and what to avoid.
    """
    top = prioritize_genome_patterns(limit=10)
    weak = get_weak_genomes(limit=10)
    preferred_emotions = get_preferred_emotions()

    recommendations = {
        "keep": [],
        "change": [],
        "avoid": [],
    }

    # What to keep: traits from top performers
    top_hooks = set()
    top_styles = set()
    for t in top[:5]:
        if t.get("hook_type"):
            top_hooks.add(t["hook_type"])
        if t.get("style"):
            top_styles.add(t["style"])

    if top_hooks:
        recommendations["keep"].append(f"Hook types: {', '.join(top_hooks)}")
    if top_styles:
        recommendations["keep"].append(f"Styles: {', '.join(top_styles)}")
    if preferred_emotions:
        recommendations["keep"].append(f"Emotions: {', '.join(preferred_emotions[:3])}")

    # What to avoid: traits from weak performers
    weak_hooks = set()
    weak_styles = set()
    for w in weak[:5]:
        if w.get("hook_type") and w["hook_type"] not in top_hooks:
            weak_hooks.add(w["hook_type"])
        if w.get("style") and w["style"] not in top_styles:
            weak_styles.add(w["style"])

    if weak_hooks:
        recommendations["avoid"].append(f"Hook types: {', '.join(weak_hooks)}")
    if weak_styles:
        recommendations["avoid"].append(f"Styles: {', '.join(weak_styles)}")

    # What to change: experiment with
    recommendations["change"].append("Try new archetype rotations")
    recommendations["change"].append("Vary controversy levels within 0.3-0.7 range")

    logger.info(f"evolution recommendations: keep={len(recommendations['keep'])}, avoid={len(recommendations['avoid'])}")
    return recommendations
