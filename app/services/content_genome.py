"""
Content Genome System — Persistent metadata store for content learning.

Each generated video gets a "genome" — a structured metadata record that
captures its complete DNA for future learning and optimization:

  - Hook type and strength
  - Emotion arc (per-segment emotion sequence)
  - Visual style
  - Niche classification
  - Retention prediction
  - Viral score breakdown
  - Mutation vector applied
  - Channel assignment

The genome store persists to JSON files, preparing the foundation for
future ML-powered optimization (reinforcement learning on content performance).

Usage:
    from app.services.content_genome import GenomeStore, ContentGenome
    store = GenomeStore()
    genome = ContentGenome(job_id="abc", topic="...", ...)
    store.save(genome)
    recent = store.query(niche="psychology", min_score=60, limit=50)
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


# ── Content Genome Record ────────────────────────────────────────────────────

@dataclass
class ContentGenome:
    """Complete metadata fingerprint for a single generated video."""
    # Identity
    job_id: str = ""
    channel_id: str = ""
    topic: str = ""
    niche: str = ""

    # Content DNA
    hook_type: str = ""           # "fear", "curiosity", "shock", "authority"
    hook_score: float = 0.0
    emotion_arc: List[str] = field(default_factory=list)   # per-segment emotions
    archetype: str = ""           # viral archetype used
    visual_style: str = ""
    style_preset: str = ""

    # Quality Metrics
    viral_score: float = 0.0
    viral_breakdown: Dict[str, float] = field(default_factory=dict)
    retention_score: float = 0.0
    retention_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Mutation
    mutation_vector: Dict[str, Any] = field(default_factory=dict)
    mutation_intensity: float = 0.0

    # Production
    video_path: str = ""
    duration_seconds: float = 0.0
    word_count: int = 0
    segment_count: int = 0

    # Upload
    youtube_video_id: str = ""
    upload_status: str = ""       # "uploaded", "scheduled", "rejected", "pending"
    scheduled_publish: str = ""

    # Performance (filled later from YouTube Analytics)
    views_24h: int = 0
    views_7d: int = 0
    ctr: float = 0.0             # Click-through rate
    avg_watch_time: float = 0.0
    avg_retention_pct: float = 0.0
    likes: int = 0
    comments: int = 0

    # Metadata
    created_at: float = field(default_factory=time.time)
    quality_passed: bool = True
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ContentGenome":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @property
    def performance_score(self) -> float:
        """Computed performance score from YouTube metrics (0-100)."""
        if not self.views_24h:
            return 0.0
        ctr_score = min(self.ctr * 10, 30)  # Max 30 from CTR
        retention_score = min(self.avg_retention_pct, 40)  # Max 40 from retention
        engagement = (self.likes + self.comments * 2) / max(self.views_24h, 1) * 100
        engagement_score = min(engagement * 3, 30)  # Max 30 from engagement
        return round(ctr_score + retention_score + engagement_score, 1)


# ── Genome Store ─────────────────────────────────────────────────────────────

class GenomeStore:
    """
    JSON-file-based genome persistence.

    Storage structure:
        storage/genomes/
            {job_id}.json
        storage/genomes/index.json   (lightweight index for queries)
    """

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            storage_dir = os.path.join(root, "storage", "genomes")
        os.makedirs(storage_dir, exist_ok=True)
        self.storage_dir = storage_dir
        self._index_path = os.path.join(storage_dir, "index.json")

    def save(self, genome: ContentGenome):
        """Persist a content genome and update the index."""
        filepath = os.path.join(self.storage_dir, f"{genome.job_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(genome.to_dict(), f, indent=2, ensure_ascii=False)

        # Update lightweight index
        self._update_index(genome)
        logger.debug(f"[Genome] Saved genome for job {genome.job_id[:8]}")

    def load(self, job_id: str) -> Optional[ContentGenome]:
        """Load a genome by job ID."""
        filepath = os.path.join(self.storage_dir, f"{job_id}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ContentGenome.from_dict(data)

    def query(
        self,
        niche: str = "",
        channel_id: str = "",
        min_score: float = 0.0,
        hook_type: str = "",
        limit: int = 50,
        sort_by: str = "created_at",
    ) -> List[ContentGenome]:
        """Query genomes from the index with optional filters."""
        index = self._load_index()

        results = []
        for entry in index:
            if niche and entry.get("niche") != niche:
                continue
            if channel_id and entry.get("channel_id") != channel_id:
                continue
            if min_score and entry.get("viral_score", 0) < min_score:
                continue
            if hook_type and entry.get("hook_type") != hook_type:
                continue
            results.append(entry)

        # Sort
        results.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
        results = results[:limit]

        # Load full genomes
        genomes = []
        for entry in results:
            genome = self.load(entry.get("job_id", ""))
            if genome:
                genomes.append(genome)

        return genomes

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics from the genome store."""
        index = self._load_index()
        if not index:
            return {"total": 0}

        niches: Dict[str, int] = {}
        hooks: Dict[str, int] = {}
        archetypes: Dict[str, int] = {}
        scores = []

        for entry in index:
            niche = entry.get("niche", "unknown")
            niches[niche] = niches.get(niche, 0) + 1

            hook = entry.get("hook_type", "unknown")
            hooks[hook] = hooks.get(hook, 0) + 1

            arch = entry.get("archetype", "unknown")
            archetypes[arch] = archetypes.get(arch, 0) + 1

            scores.append(entry.get("viral_score", 0))

        return {
            "total": len(index),
            "avg_viral_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "niches": niches,
            "hook_types": hooks,
            "archetypes": archetypes,
            "top_score": max(scores) if scores else 0,
        }

    def get_recent_topics(self, count: int = 20) -> List[str]:
        """Get recent topic strings for novelty deduplication."""
        index = self._load_index()
        index.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return [e.get("topic", "") for e in index[:count]]

    def update_performance(
        self,
        job_id: str,
        views_24h: int = 0,
        views_7d: int = 0,
        ctr: float = 0.0,
        avg_watch_time: float = 0.0,
        avg_retention_pct: float = 0.0,
        likes: int = 0,
        comments: int = 0,
    ):
        """Update a genome with YouTube performance data (for future learning)."""
        genome = self.load(job_id)
        if not genome:
            return
        genome.views_24h = views_24h
        genome.views_7d = views_7d
        genome.ctr = ctr
        genome.avg_watch_time = avg_watch_time
        genome.avg_retention_pct = avg_retention_pct
        genome.likes = likes
        genome.comments = comments
        self.save(genome)
        logger.info(f"[Genome] Updated performance for {job_id[:8]}: {genome.performance_score}")

    # ── Internal ─────────────────────────────────────────────────────────

    def _load_index(self) -> List[Dict]:
        if not os.path.exists(self._index_path):
            return []
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _update_index(self, genome: ContentGenome):
        index = self._load_index()

        # Remove existing entry if present
        index = [e for e in index if e.get("job_id") != genome.job_id]

        # Add new entry (lightweight — only index fields)
        index.append({
            "job_id": genome.job_id,
            "channel_id": genome.channel_id,
            "topic": genome.topic,
            "niche": genome.niche,
            "hook_type": genome.hook_type,
            "archetype": genome.archetype,
            "viral_score": genome.viral_score,
            "retention_score": genome.retention_score,
            "quality_passed": genome.quality_passed,
            "created_at": genome.created_at,
        })

        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)


# ── Factory Function ─────────────────────────────────────────────────────────

def create_genome_from_job(
    job_id: str,
    topic: str,
    channel_id: str = "",
    niche: str = "",
    style: str = "",
    script: str = "",
    video_path: str = "",
    **kwargs,
) -> ContentGenome:
    """
    Build a ContentGenome by running all intelligence systems on a job.

    This is the main integration point — it calls viral_score,
    retention_simulator, and trend_intelligence to populate the genome.
    """
    genome = ContentGenome(
        job_id=job_id,
        channel_id=channel_id,
        topic=topic,
        niche=niche,
        style_preset=style,
        video_path=video_path,
    )

    # Score topic
    try:
        from app.services.trend_intelligence import score_topic
        scored = score_topic(topic, niche=niche)
        genome.hook_type = scored.emotion_tags[0] if scored.emotion_tags else ""
        genome.archetype = scored.archetype
    except Exception:
        pass

    # Viral scoring (if script available)
    if script:
        try:
            from app.services.viral_score import compute_viral_score
            vr = compute_viral_score(script)
            genome.viral_score = vr.get("score", 0)
            genome.viral_breakdown = {
                k: v for k, v in vr.items() if k != "score" and k != "grade"
            }
        except Exception:
            pass

        # Retention simulation
        try:
            from app.services.retention_simulator import simulate_retention
            rr = simulate_retention(script, style=style)
            genome.retention_score = rr.overall_score
            genome.hook_score = rr.hook_score
            genome.retention_breakdown = rr.to_dict()
            genome.emotion_arc = [s.dominant_emotion for s in rr.segments]
            genome.segment_count = len(rr.segments)
            genome.quality_passed = rr.passed
            genome.rejection_reason = rr.rejection_reason
        except Exception:
            pass

        genome.word_count = len(script.split())

    # Apply extra kwargs
    for k, v in kwargs.items():
        if hasattr(genome, k):
            setattr(genome, k, v)

    return genome
