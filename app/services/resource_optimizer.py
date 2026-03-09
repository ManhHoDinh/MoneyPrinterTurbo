"""
Resource Optimizer — Performance-based worker allocation.

Allocates video generation capacity across channels based on:
  - Historical viral score performance
  - Retention prediction scores
  - Content genome quality pass rate
  - Channel upload schedule density

High-performing channels get proportionally more worker slots in each
batch cycle. Low performers get minimum baseline allocation.

Usage:
    from app.services.resource_optimizer import ResourceOptimizer
    optimizer = ResourceOptimizer()
    allocation = optimizer.allocate(
        channel_ids=["ch-01", "ch-02", "ch-03"],
        total_slots=20,
    )
    # {"ch-01": 10, "ch-02": 7, "ch-03": 3}
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


# ── Configuration ────────────────────────────────────────────────────────────

MIN_SLOTS_PER_CHANNEL = 1          # Every channel gets at least 1 slot
MAX_SHARE = 0.60                    # No channel gets more than 60% of total
PERFORMANCE_LOOKBACK = 50           # Genomes to consider per channel
DEFAULT_SCORE = 50.0                # Score for channels with no history


@dataclass
class ChannelAllocation:
    """Worker allocation for a single channel."""
    channel_id: str = ""
    slots: int = 1
    share_pct: float = 0.0
    performance_score: float = 0.0
    quality_pass_rate: float = 0.0
    avg_viral_score: float = 0.0
    avg_retention_score: float = 0.0
    genome_count: int = 0
    reason: str = ""


@dataclass
class AllocationPlan:
    """Complete allocation plan across all channels."""
    total_slots: int = 0
    allocations: List[ChannelAllocation] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_slots": self.total_slots,
            "timestamp": self.timestamp,
            "allocations": [asdict(a) for a in self.allocations],
            "summary": {a.channel_id: a.slots for a in self.allocations},
        }


# ── Resource Optimizer ───────────────────────────────────────────────────────

class ResourceOptimizer:

    def __init__(self):
        from app.services.content_genome import GenomeStore
        self.store = GenomeStore()

    def allocate(
        self,
        channel_ids: List[str],
        total_slots: int = 20,
    ) -> AllocationPlan:
        """
        Allocate worker slots across channels proportional to performance.

        Steps:
          1. Score each channel from genome history
          2. Normalize scores to shares
          3. Apply min/max constraints
          4. Distribute remaining slots by score ranking
        """
        if not channel_ids:
            return AllocationPlan(total_slots=total_slots)

        # Score each channel
        scores: List[ChannelAllocation] = []
        for cid in channel_ids:
            alloc = self._score_channel(cid)
            scores.append(alloc)

        # Normalize to shares
        total_perf = sum(a.performance_score for a in scores) or 1.0
        for a in scores:
            a.share_pct = round(a.performance_score / total_perf * 100, 1)

        # Allocate slots
        remaining = total_slots
        max_slots = int(total_slots * MAX_SHARE)

        # Phase 1: Give everyone minimum
        for a in scores:
            a.slots = MIN_SLOTS_PER_CHANNEL
            remaining -= MIN_SLOTS_PER_CHANNEL

        # Phase 2: Distribute remaining proportionally
        if remaining > 0:
            scores_sorted = sorted(scores, key=lambda x: x.performance_score, reverse=True)
            for a in scores_sorted:
                fair_share = max(0, int(remaining * (a.performance_score / total_perf)))
                fair_share = min(fair_share, max_slots - a.slots)
                a.slots += fair_share
                remaining -= fair_share

            # Phase 3: Give any leftover to top performer
            if remaining > 0:
                top = scores_sorted[0]
                add = min(remaining, max_slots - top.slots)
                top.slots += add
                remaining -= add

            # Phase 4: Distribute any remaining round-robin
            idx = 0
            while remaining > 0:
                a = scores_sorted[idx % len(scores_sorted)]
                if a.slots < max_slots:
                    a.slots += 1
                    remaining -= 1
                idx += 1
                if idx > len(scores_sorted) * max_slots:
                    break  # Safety exit

        # Set reasons
        for a in scores:
            if a.genome_count == 0:
                a.reason = "No history — baseline allocation"
            elif a.performance_score >= 70:
                a.reason = "High performer — boosted allocation"
            elif a.performance_score >= 50:
                a.reason = "Moderate performer — standard allocation"
            else:
                a.reason = "Low performer — minimum allocation"

        plan = AllocationPlan(total_slots=total_slots, allocations=scores)

        logger.info(
            f"[ResourceOpt] Allocated {total_slots} slots across "
            f"{len(channel_ids)} channels: "
            + ", ".join(f"{a.channel_id[:8]}={a.slots}" for a in scores)
        )

        return plan

    def get_channel_priority(self, channel_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Rank channels by priority for next generation cycle.
        Returns ordered list with scores and recommendations.
        """
        scored = []
        for cid in channel_ids:
            alloc = self._score_channel(cid)
            scored.append({
                "channel_id": cid,
                "priority_score": alloc.performance_score,
                "quality_pass_rate": alloc.quality_pass_rate,
                "avg_viral": alloc.avg_viral_score,
                "avg_retention": alloc.avg_retention_score,
                "genomes": alloc.genome_count,
            })

        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored

    def _score_channel(self, channel_id: str) -> ChannelAllocation:
        """Score a channel's performance from genome history."""
        genomes = self.store.query(
            channel_id=channel_id,
            limit=PERFORMANCE_LOOKBACK,
            sort_by="created_at",
        )

        if not genomes:
            return ChannelAllocation(
                channel_id=channel_id,
                performance_score=DEFAULT_SCORE,
                genome_count=0,
            )

        viral_scores = [g.viral_score for g in genomes if g.viral_score > 0]
        ret_scores = [g.retention_score for g in genomes if g.retention_score > 0]
        quality_passed = sum(1 for g in genomes if g.quality_passed)

        avg_viral = sum(viral_scores) / len(viral_scores) if viral_scores else 50.0
        avg_retention = sum(ret_scores) / len(ret_scores) if ret_scores else 50.0
        pass_rate = quality_passed / len(genomes) * 100 if genomes else 100.0

        # Composite performance: 40% viral + 35% retention + 25% quality
        perf = avg_viral * 0.40 + avg_retention * 0.35 + pass_rate * 0.25

        return ChannelAllocation(
            channel_id=channel_id,
            performance_score=round(perf, 1),
            quality_pass_rate=round(pass_rate, 1),
            avg_viral_score=round(avg_viral, 1),
            avg_retention_score=round(avg_retention, 1),
            genome_count=len(genomes),
        )
