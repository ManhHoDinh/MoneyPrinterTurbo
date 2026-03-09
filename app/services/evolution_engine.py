"""
Evolution Engine — Self-evolving learning loop for autonomous optimization.

Closes the feedback loop between Content Genome performance data and
future content decisions. Learns from past video performance to:

  1. Bias topic selection toward historically high-performing patterns
  2. Prefer hook types that achieve better retention
  3. Adjust mutation intensity per channel based on outcomes
  4. Recommend archetype rotations based on engagement data
  5. Avoid topic patterns that consistently underperform

This is NOT ML — it's a deterministic feedback system using
weighted moving averages over the genome store. Designed to
improve autonomously over time without manual tuning.

Usage:
    from app.services.evolution_engine import EvolutionEngine
    engine = EvolutionEngine()
    bias = engine.get_topic_bias(niche="dark_psychology")
    hook_pref = engine.get_hook_preference(channel_id="ch-001")
    intensity = engine.get_optimal_mutation_intensity(channel_id="ch-001")
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple

from loguru import logger


# ── Evolution Config ─────────────────────────────────────────────────────────

MIN_SAMPLES = 5            # Minimum genomes before evolution kicks in
RECENCY_WINDOW = 100       # Only consider last N genomes for calculations
PERFORMANCE_ALPHA = 0.3    # EMA smoothing factor (higher = faster adaptation)


@dataclass
class EvolutionInsight:
    """Actionable insight from the evolution engine."""
    category: str = ""      # "topic", "hook", "archetype", "mutation", "style"
    signal: str = ""        # What was observed
    action: str = ""        # What to do about it
    confidence: float = 0.0  # 0-1, how confident the recommendation is
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionState:
    """Current evolution state for a channel or globally."""
    total_genomes: int = 0
    avg_viral_score: float = 0.0
    avg_retention_score: float = 0.0
    top_hook_type: str = ""
    top_archetype: str = ""
    optimal_mutation_intensity: float = 0.5
    insights: List[EvolutionInsight] = field(default_factory=list)
    topic_bias_keywords: List[str] = field(default_factory=list)
    avoid_patterns: List[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["insights"] = [asdict(i) for i in self.insights]
        return d


# ── Evolution Engine ─────────────────────────────────────────────────────────

class EvolutionEngine:
    """
    Self-evolving feedback loop that reads Content Genome performance
    data and outputs optimization recommendations.
    """

    def __init__(self):
        from app.services.content_genome import GenomeStore
        self.store = GenomeStore()

    def evolve(self, channel_id: str = "", niche: str = "") -> EvolutionState:
        """
        Run a full evolution cycle for a channel or globally.

        Returns an EvolutionState with insights and adjusted parameters.
        """
        genomes = self._load_relevant_genomes(channel_id, niche)

        if len(genomes) < MIN_SAMPLES:
            logger.info(
                f"[Evolution] Insufficient data ({len(genomes)}/{MIN_SAMPLES}) — "
                "using defaults"
            )
            return EvolutionState(
                total_genomes=len(genomes),
                insights=[EvolutionInsight(
                    category="system",
                    signal=f"Only {len(genomes)} genomes available",
                    action="Continue generating content to build learning dataset",
                    confidence=1.0,
                )],
            )

        state = EvolutionState(total_genomes=len(genomes))
        insights = []

        # ── Analyze hook performance ─────────────────────────────────
        hook_perf = self._analyze_hooks(genomes)
        state.top_hook_type = hook_perf.get("best", "")
        if hook_perf.get("best"):
            insights.append(EvolutionInsight(
                category="hook",
                signal=f"'{hook_perf['best']}' hooks avg {hook_perf['best_score']:.0f} retention",
                action=f"Increase '{hook_perf['best']}' hook frequency to 40%",
                confidence=min(len(genomes) / 20, 1.0),
                data=hook_perf,
            ))
        if hook_perf.get("worst") and hook_perf.get("worst_score", 100) < 45:
            insights.append(EvolutionInsight(
                category="hook",
                signal=f"'{hook_perf['worst']}' hooks avg only {hook_perf['worst_score']:.0f}",
                action=f"Reduce '{hook_perf['worst']}' hook usage",
                confidence=min(len(genomes) / 20, 1.0),
                data=hook_perf,
            ))

        # ── Analyze archetype performance ────────────────────────────
        arch_perf = self._analyze_archetypes(genomes)
        state.top_archetype = arch_perf.get("best", "")
        if arch_perf.get("best"):
            insights.append(EvolutionInsight(
                category="archetype",
                signal=f"'{arch_perf['best']}' archetype performs best",
                action=f"Weight '{arch_perf['best']}' at 2x in rotation",
                confidence=min(len(genomes) / 30, 1.0),
                data=arch_perf,
            ))

        # ── Optimal mutation intensity ───────────────────────────────
        opt_intensity = self._find_optimal_mutation(genomes)
        state.optimal_mutation_intensity = opt_intensity
        insights.append(EvolutionInsight(
            category="mutation",
            signal=f"Best mutation intensity: {opt_intensity:.2f}",
            action=f"Set mutation intensity to {opt_intensity:.2f}",
            confidence=min(len(genomes) / 25, 1.0),
            data={"optimal": opt_intensity},
        ))

        # ── Topic bias from high performers ──────────────────────────
        bias_keywords = self._extract_topic_bias(genomes)
        state.topic_bias_keywords = bias_keywords
        if bias_keywords:
            insights.append(EvolutionInsight(
                category="topic",
                signal=f"High-performing keywords: {', '.join(bias_keywords[:5])}",
                action="Bias topic generation toward these keywords",
                confidence=min(len(genomes) / 15, 1.0),
                data={"keywords": bias_keywords},
            ))

        # ── Avoid patterns from low performers ──────────────────────
        avoid = self._extract_avoid_patterns(genomes)
        state.avoid_patterns = avoid
        if avoid:
            insights.append(EvolutionInsight(
                category="topic",
                signal=f"Underperforming patterns: {', '.join(avoid[:3])}",
                action="Filter out topics containing these patterns",
                confidence=min(len(genomes) / 15, 1.0),
                data={"avoid": avoid},
            ))

        # ── Score trends ─────────────────────────────────────────────
        scores = [g.viral_score for g in genomes if g.viral_score > 0]
        state.avg_viral_score = round(sum(scores) / len(scores), 1) if scores else 0

        ret_scores = [g.retention_score for g in genomes if g.retention_score > 0]
        state.avg_retention_score = round(
            sum(ret_scores) / len(ret_scores), 1
        ) if ret_scores else 0

        state.insights = insights

        logger.info(
            f"[Evolution] Cycle complete: {len(genomes)} genomes → "
            f"{len(insights)} insights, top_hook={state.top_hook_type}, "
            f"mutation={state.optimal_mutation_intensity:.2f}"
        )

        return state

    # ── Convenience Getters ──────────────────────────────────────────────

    def get_topic_bias(self, niche: str = "", channel_id: str = "") -> Dict[str, Any]:
        """Get topic selection bias from past performance."""
        state = self.evolve(channel_id=channel_id, niche=niche)
        return {
            "prefer_keywords": state.topic_bias_keywords,
            "avoid_patterns": state.avoid_patterns,
            "top_hook_type": state.top_hook_type,
            "top_archetype": state.top_archetype,
        }

    def get_hook_preference(self, channel_id: str = "") -> Dict[str, Any]:
        """Get preferred hook distribution from past performance."""
        genomes = self._load_relevant_genomes(channel_id)
        return self._analyze_hooks(genomes)

    def get_optimal_mutation_intensity(self, channel_id: str = "") -> float:
        """Get optimal mutation intensity from past performance."""
        genomes = self._load_relevant_genomes(channel_id)
        return self._find_optimal_mutation(genomes)

    # ── Analysis Methods ─────────────────────────────────────────────────

    def _load_relevant_genomes(self, channel_id: str = "", niche: str = ""):
        """Load recent genomes for analysis."""
        genomes = self.store.query(
            channel_id=channel_id,
            niche=niche,
            limit=RECENCY_WINDOW,
            sort_by="created_at",
        )
        return genomes

    def _analyze_hooks(self, genomes) -> Dict[str, Any]:
        """Analyze hook type performance."""
        hook_scores: Dict[str, List[float]] = {}
        for g in genomes:
            if not g.hook_type or g.retention_score <= 0:
                continue
            hook_scores.setdefault(g.hook_type, []).append(g.retention_score)

        if not hook_scores:
            return {}

        avg_by_hook = {
            hook: round(sum(scores) / len(scores), 1)
            for hook, scores in hook_scores.items()
            if len(scores) >= 2
        }

        if not avg_by_hook:
            return {}

        best = max(avg_by_hook, key=avg_by_hook.get)
        worst = min(avg_by_hook, key=avg_by_hook.get)

        return {
            "best": best,
            "best_score": avg_by_hook[best],
            "worst": worst,
            "worst_score": avg_by_hook[worst],
            "all": avg_by_hook,
            "sample_sizes": {h: len(s) for h, s in hook_scores.items()},
        }

    def _analyze_archetypes(self, genomes) -> Dict[str, Any]:
        """Analyze archetype performance."""
        arch_scores: Dict[str, List[float]] = {}
        for g in genomes:
            if not g.archetype or g.viral_score <= 0:
                continue
            arch_scores.setdefault(g.archetype, []).append(g.viral_score)

        if not arch_scores:
            return {}

        avg_by_arch = {
            arch: round(sum(scores) / len(scores), 1)
            for arch, scores in arch_scores.items()
            if len(scores) >= 2
        }

        if not avg_by_arch:
            return {}

        best = max(avg_by_arch, key=avg_by_arch.get)
        return {
            "best": best,
            "best_score": avg_by_arch[best],
            "all": avg_by_arch,
        }

    def _find_optimal_mutation(self, genomes) -> float:
        """Find mutation intensity correlated with best retention."""
        if len(genomes) < MIN_SAMPLES:
            return 0.5

        # Group by mutation intensity buckets (0.1 increments)
        buckets: Dict[float, List[float]] = {}
        for g in genomes:
            if g.retention_score <= 0:
                continue
            bucket = round(g.mutation_intensity * 10) / 10  # snap to 0.1
            bucket = max(0.0, min(1.0, bucket))
            buckets.setdefault(bucket, []).append(g.retention_score)

        if not buckets:
            return 0.5

        avg_by_bucket = {
            b: sum(scores) / len(scores)
            for b, scores in buckets.items()
            if len(scores) >= 2
        }

        if not avg_by_bucket:
            return 0.5

        return max(avg_by_bucket, key=avg_by_bucket.get)

    def _extract_topic_bias(self, genomes) -> List[str]:
        """Extract keywords from top-performing topics."""
        # Get top 20% by retention score
        scored = [(g, g.retention_score) for g in genomes if g.retention_score > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:max(len(scored) // 5, 3)]

        # Extract common words
        stop = {"the", "a", "an", "is", "are", "of", "in", "to", "for",
                "and", "or", "but", "that", "this", "it", "you", "your"}
        word_counts: Dict[str, int] = {}
        for g, _ in top:
            words = g.topic.lower().split()
            for w in words:
                w = w.strip(".,!?\"'")
                if w not in stop and len(w) > 3:
                    word_counts[w] = word_counts.get(w, 0) + 1

        # Return words appearing in multiple top performers
        return [w for w, c in sorted(word_counts.items(), key=lambda x: -x[1]) if c >= 2][:10]

    def _extract_avoid_patterns(self, genomes) -> List[str]:
        """Extract patterns from consistently underperforming topics."""
        scored = [(g, g.retention_score) for g in genomes if g.retention_score > 0]
        scored.sort(key=lambda x: x[1])
        bottom = scored[:max(len(scored) // 5, 3)]

        stop = {"the", "a", "an", "is", "are", "of", "in", "to", "for",
                "and", "or", "but", "that", "this", "it", "you", "your"}
        word_counts: Dict[str, int] = {}
        for g, _ in bottom:
            words = g.topic.lower().split()
            for w in words:
                w = w.strip(".,!?\"'")
                if w not in stop and len(w) > 3:
                    word_counts[w] = word_counts.get(w, 0) + 1

        return [w for w, c in sorted(word_counts.items(), key=lambda x: -x[1]) if c >= 2][:5]
