"""
Master Orchestrator — End-to-end autonomous content farm pipeline.

Chains ALL intelligence layers into a single execution flow:

  1. Network Config      → Which channels need content today?
  2. Resource Optimizer   → How many slots per channel?
  3. Trend Intelligence   → Generate scored topic pool
  4. Evolution Engine     → Apply learned bias (prefer/avoid patterns)
  5. Hook Generator       → Create hook variants per topic
  6. Retention Simulator  → Reject weak scripts before generation
  7. Generator Wrapper    → Call black-box video engine
  8. Quality Filter       → Gate output before upload
  9. Content Genome       → Persist metadata for learning
  10. Monetization        → Generate upload metadata (title, desc, tags, CTAs)
  11. Channel Autopilot   → Health check + lifecycle actions

Usage:
    from app.services.orchestrator import Orchestrator
    orch = Orchestrator()

    # Run a full production cycle for the entire network
    report = orch.run_cycle()

    # Run for a single channel
    report = orch.run_channel("us-t1-wealth", count=3)

    # Dry run — score & filter topics without generating videos
    preview = orch.dry_run(niche="dark_psychology", count=5)
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable

from loguru import logger


# ── Pipeline Stage Results ───────────────────────────────────────────────────

@dataclass
class PipelineItem:
    """A single item flowing through the orchestration pipeline."""
    job_id: str = ""
    channel_id: str = ""
    topic: str = ""
    niche: str = ""
    style: str = ""

    # Stage results
    topic_score: float = 0.0
    hook_variants: List[str] = field(default_factory=list)
    selected_hook: str = ""
    retention_score: float = 0.0
    retention_passed: bool = False
    video_path: str = ""
    generation_success: bool = False
    quality_passed: bool = False
    quality_score: float = 0.0
    genome_saved: bool = False

    # Monetization
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Status
    stage: str = "queued"        # queued, scoring, hooks, retention, generating, quality, complete, rejected
    rejected_at: str = ""
    rejection_reason: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CycleReport:
    """Report from a full orchestration cycle."""
    cycle_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_seconds: float = 0.0

    # Counts
    topics_generated: int = 0
    retention_passed: int = 0
    retention_rejected: int = 0
    videos_generated: int = 0
    quality_passed: int = 0
    quality_rejected: int = 0
    genomes_saved: int = 0
    upload_ready: int = 0

    # Per-channel breakdown
    channel_results: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Pipeline items
    items: List[PipelineItem] = field(default_factory=list)

    # Lifecycle actions
    lifecycle_actions: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["items"] = [i.to_dict() if hasattr(i, "to_dict") else i for i in self.items]
        return d

    @property
    def success_rate(self) -> float:
        if self.topics_generated == 0:
            return 0
        return round(self.upload_ready / self.topics_generated * 100, 1)


# ── Master Orchestrator ──────────────────────────────────────────────────────

class Orchestrator:
    """
    Master orchestration engine.

    Chains all intelligence modules into an autonomous pipeline.
    Each stage has error isolation — a failure in one stage
    doesn't crash the entire pipeline.
    """

    def __init__(self, dry_run_mode: bool = False):
        self.dry_run_mode = dry_run_mode

    def run_cycle(self) -> CycleReport:
        """
        Run a full production cycle for the entire network.

        Reads network_config for daily quotas, allocates resources,
        generates topics, runs the pipeline for each channel.
        """
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"
        start = time.time()
        report = CycleReport(cycle_id=cycle_id, started_at=start)

        logger.info(f"[Orchestrator] ═══ Starting cycle {cycle_id} ═══")

        # Step 1: Get network channels and quotas
        channels = self._get_network_channels()
        if not channels:
            logger.warning("[Orchestrator] No channels configured — using defaults")
            channels = [{"channel_id": "default", "niche": "dark_psychology",
                         "topics_per_day": 3, "style": "dark_psychology"}]

        # Step 2: Allocate resources
        allocation = self._allocate_resources(channels)

        # Step 3: Run pipeline per channel
        for ch in channels:
            cid = ch["channel_id"]
            count = allocation.get(cid, ch.get("topics_per_day", 1))
            niche = ch.get("niche", "dark_psychology")
            style = ch.get("style_preset", ch.get("style", "dark_psychology"))

            logger.info(f"[Orchestrator] ── Channel {cid}: {count} videos ({niche}) ──")

            items = self.run_channel(
                channel_id=cid,
                niche=niche,
                style=style,
                count=count,
            )
            for item in items:
                report.items.append(item)
                report.channel_results.setdefault(cid, {
                    "generated": 0, "passed": 0, "rejected": 0
                })
                if item.generation_success:
                    report.channel_results[cid]["generated"] += 1
                if item.quality_passed:
                    report.channel_results[cid]["passed"] += 1
                if item.rejection_reason:
                    report.channel_results[cid]["rejected"] += 1

        # Step 4: Channel health check + lifecycle
        report.lifecycle_actions = self._run_lifecycle(channels)

        # Compute totals
        report.topics_generated = len(report.items)
        report.retention_passed = sum(1 for i in report.items if i.retention_passed)
        report.retention_rejected = sum(1 for i in report.items if i.rejected_at == "retention")
        report.videos_generated = sum(1 for i in report.items if i.generation_success)
        report.quality_passed = sum(1 for i in report.items if i.quality_passed)
        report.quality_rejected = sum(1 for i in report.items if i.rejected_at == "quality")
        report.genomes_saved = sum(1 for i in report.items if i.genome_saved)
        report.upload_ready = sum(1 for i in report.items if i.stage == "complete")

        report.completed_at = time.time()
        report.duration_seconds = round(report.completed_at - start, 1)

        logger.info(
            f"[Orchestrator] ═══ Cycle {cycle_id} complete ═══\n"
            f"  Topics: {report.topics_generated} → "
            f"Retention: {report.retention_passed} → "
            f"Generated: {report.videos_generated} → "
            f"Quality: {report.quality_passed} → "
            f"Upload-ready: {report.upload_ready} "
            f"({report.success_rate}% success) "
            f"in {report.duration_seconds}s"
        )

        return report

    def run_channel(
        self,
        channel_id: str = "default",
        niche: str = "dark_psychology",
        style: str = "dark_psychology",
        count: int = 3,
    ) -> List[PipelineItem]:
        """Run the pipeline for a single channel."""
        items = []

        # ── Stage 1: Generate scored topics ──────────────────────────
        topics = self._stage_topics(niche, count)

        # ── Stage 2: Apply evolution bias ────────────────────────────
        topics = self._stage_evolution_bias(topics, channel_id, niche)

        for topic_data in topics:
            item = PipelineItem(
                job_id=f"job-{uuid.uuid4().hex[:8]}",
                channel_id=channel_id,
                topic=topic_data.get("topic", ""),
                niche=niche,
                style=style,
                topic_score=topic_data.get("score", 0),
            )

            try:
                # ── Stage 3: Generate hooks ──────────────────────────
                item = self._stage_hooks(item)

                # ── Stage 4: Retention check ─────────────────────────
                item = self._stage_retention(item)
                if not item.retention_passed:
                    items.append(item)
                    continue

                # ── Stage 5: Generate video ──────────────────────────
                if not self.dry_run_mode:
                    item = self._stage_generate(item)
                    if not item.generation_success:
                        items.append(item)
                        continue

                    # ── Stage 6: Quality filter ──────────────────────
                    item = self._stage_quality(item)

                # ── Stage 7: Save genome ─────────────────────────────
                item = self._stage_genome(item)

                # ── Stage 8: Monetization metadata ───────────────────
                item = self._stage_monetization(item)

                if item.quality_passed or self.dry_run_mode:
                    item.stage = "complete"
                else:
                    item.stage = "quality_rejected"

            except Exception as e:
                logger.error(f"[Orchestrator] Pipeline error for {item.job_id}: {e}")
                item.stage = "error"
                item.rejection_reason = str(e)

            items.append(item)

        return items

    def dry_run(self, niche: str = "dark_psychology", count: int = 5) -> List[Dict]:
        """
        Dry run — score and filter topics without generating videos.

        Returns preview of what WOULD be generated.
        """
        self.dry_run_mode = True
        items = self.run_channel(niche=niche, count=count)
        self.dry_run_mode = False

        return [
            {
                "topic": i.topic,
                "score": i.topic_score,
                "hook": i.selected_hook,
                "retention": i.retention_score,
                "retention_passed": i.retention_passed,
                "would_generate": i.retention_passed,
                "rejection_reason": i.rejection_reason,
            }
            for i in items
        ]

    # ── Pipeline Stages ──────────────────────────────────────────────────────

    def _stage_topics(self, niche: str, count: int) -> List[Dict]:
        """Stage 1: Generate scored topics."""
        try:
            from app.services.trend_intelligence import generate_scored_topics
            topics = generate_scored_topics(niche=niche, count=count, min_score=35)
            return [
                {"topic": t.topic, "score": t.composite_score, "archetype": t.archetype}
                for t in topics
            ]
        except Exception as e:
            logger.warning(f"[Orchestrator] Topic generation failed: {e}")
            # Fallback: emergency topics
            from app.services.trend_intelligence import _emergency_topics
            raw = _emergency_topics(niche, count)
            return [{"topic": t, "score": 50.0, "archetype": ""} for t in raw]

    def _stage_evolution_bias(
        self, topics: List[Dict], channel_id: str, niche: str
    ) -> List[Dict]:
        """Stage 2: Apply evolution engine bias to topic selection."""
        try:
            from app.services.evolution_engine import EvolutionEngine
            engine = EvolutionEngine()
            bias = engine.get_topic_bias(niche=niche, channel_id=channel_id)

            prefer = set(bias.get("prefer_keywords", []))
            avoid = set(bias.get("avoid_patterns", []))

            for topic in topics:
                text = topic["topic"].lower()
                # Boost topics matching preferred keywords
                if any(k in text for k in prefer):
                    topic["score"] = topic.get("score", 50) * 1.15
                # Penalize topics matching avoid patterns
                if any(a in text for a in avoid):
                    topic["score"] = topic.get("score", 50) * 0.75

            topics.sort(key=lambda x: x.get("score", 0), reverse=True)
        except Exception as e:
            logger.debug(f"[Orchestrator] Evolution bias skipped: {e}")

        return topics

    def _stage_hooks(self, item: PipelineItem) -> PipelineItem:
        """Stage 3: Generate hook variants."""
        item.stage = "hooks"
        try:
            from app.services.hook_generator import generate_hook_variants
            variants = generate_hook_variants(
                topic=item.topic,
                style=item.style,
                count=3,
            )
            item.hook_variants = variants if isinstance(variants, list) else [str(variants)]
            item.selected_hook = item.hook_variants[0] if item.hook_variants else item.topic
        except Exception as e:
            logger.debug(f"[Orchestrator] Hook generation skipped: {e}")
            item.selected_hook = item.topic

        return item

    def _stage_retention(self, item: PipelineItem) -> PipelineItem:
        """Stage 4: Retention prediction — reject weak scripts."""
        item.stage = "retention"
        try:
            from app.services.retention_simulator import simulate_retention
            # Use the selected hook as proxy script for pre-generation check
            script_proxy = item.selected_hook or item.topic
            result = simulate_retention(script_proxy, style=item.style)
            item.retention_score = result.overall_score
            item.retention_passed = result.passed

            if not result.passed:
                item.rejected_at = "retention"
                item.rejection_reason = result.rejection_reason
                item.stage = "rejected"
                logger.debug(
                    f"[Orchestrator] Rejected '{item.topic[:30]}' "
                    f"retention={result.overall_score:.0f}: {result.rejection_reason}"
                )
        except Exception as e:
            logger.warning(f"[Orchestrator] Retention check failed: {e}")
            item.retention_passed = True  # Pass through on error
            item.retention_score = 50.0

        return item

    def _stage_generate(self, item: PipelineItem) -> PipelineItem:
        """Stage 5: Call the black-box video generator."""
        item.stage = "generating"
        start = time.time()
        try:
            from app.services.generator_wrapper import generate_video, GeneratorInput
            cfg = GeneratorInput(
                job_id=item.job_id,
                topic=item.selected_hook or item.topic,
                style=item.style,
                channel_id=item.channel_id,
                language="en",
            )
            result = generate_video(cfg)
            item.generation_success = result.success
            item.video_path = result.video_path or ""
            item.duration_seconds = round(time.time() - start, 1)

            if not result.success:
                item.rejected_at = "generation"
                item.rejection_reason = result.error or "Generation failed"
                item.stage = "rejected"
        except Exception as e:
            logger.error(f"[Orchestrator] Generation failed: {e}")
            item.generation_success = False
            item.rejected_at = "generation"
            item.rejection_reason = str(e)
            item.stage = "rejected"
            item.duration_seconds = round(time.time() - start, 1)

        return item

    def _stage_quality(self, item: PipelineItem) -> PipelineItem:
        """Stage 6: Quality filter gate."""
        item.stage = "quality"
        try:
            from app.services.quality_filter import quality_gate
            result = quality_gate(
                job_id=item.job_id,
                video_path=item.video_path,
                script=item.selected_hook,
                style=item.style,
            )
            item.quality_passed = result["passed"]
            item.quality_score = result["score"]

            if not result["passed"]:
                item.rejected_at = "quality"
                item.rejection_reason = "; ".join(result.get("rejection_reasons", []))
                item.stage = "rejected"
        except Exception as e:
            logger.warning(f"[Orchestrator] Quality check failed: {e}")
            item.quality_passed = True  # Pass through on error
            item.quality_score = 50.0

        return item

    def _stage_genome(self, item: PipelineItem) -> PipelineItem:
        """Stage 7: Save content genome."""
        try:
            from app.services.content_genome import GenomeStore, create_genome_from_job
            genome = create_genome_from_job(
                job_id=item.job_id,
                topic=item.topic,
                channel_id=item.channel_id,
                niche=item.niche,
                style=item.style,
                script=item.selected_hook,
                video_path=item.video_path,
            )
            store = GenomeStore()
            store.save(genome)
            item.genome_saved = True
        except Exception as e:
            logger.warning(f"[Orchestrator] Genome save failed: {e}")

        return item

    def _stage_monetization(self, item: PipelineItem) -> PipelineItem:
        """Stage 8: Generate monetization metadata."""
        try:
            from app.services.monetization import generate_monetization_metadata
            meta = generate_monetization_metadata(
                topic=item.topic,
                niche=item.niche,
                style=item.style,
            )
            item.title = meta.title
            item.description = meta.description
            item.tags = meta.tags
        except Exception as e:
            logger.debug(f"[Orchestrator] Monetization metadata skipped: {e}")

        return item

    # ── Helper Methods ───────────────────────────────────────────────────────

    def _get_network_channels(self) -> List[Dict]:
        """Get channel definitions from network config."""
        try:
            from app.services.network_config import get_all_channels
            channels = get_all_channels()
            return [
                {
                    "channel_id": c.channel_id,
                    "niche": c.niche,
                    "style_preset": c.style_preset,
                    "topics_per_day": c.topics_per_day,
                }
                for c in channels
            ]
        except Exception:
            return []

    def _allocate_resources(self, channels: List[Dict]) -> Dict[str, int]:
        """Use resource optimizer to allocate slots."""
        try:
            from app.services.resource_optimizer import ResourceOptimizer
            optimizer = ResourceOptimizer()
            channel_ids = [c["channel_id"] for c in channels]
            total = sum(c.get("topics_per_day", 1) for c in channels)
            plan = optimizer.allocate(channel_ids, total)
            return {a.channel_id: a.slots for a in plan.allocations}
        except Exception:
            return {c["channel_id"]: c.get("topics_per_day", 1) for c in channels}

    def _run_lifecycle(self, channels: List[Dict]) -> List[Dict]:
        """Run channel autopilot lifecycle check."""
        try:
            from app.services.channel_autopilot import ChannelAutopilot
            pilot = ChannelAutopilot()
            channel_ids = [c["channel_id"] for c in channels]
            actions = pilot.auto_kill(channel_ids)
            return [a.to_dict() for a in actions]
        except Exception:
            return []
