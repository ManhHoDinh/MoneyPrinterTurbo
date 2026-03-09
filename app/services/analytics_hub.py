"""
Analytics Hub — Network-level performance aggregation.

Aggregates Content Genome data into actionable analytics:
  - Per-channel performance summaries
  - Per-tier comparisons
  - Network-wide KPIs
  - Trend detection (improving/declining channels)
  - Revenue projections based on CPM and view estimates

Usage:
    from app.services.analytics_hub import AnalyticsHub
    hub = AnalyticsHub()
    report = hub.network_report()
    channel_stats = hub.channel_report("us-t1-wealth")
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


@dataclass
class ChannelAnalytics:
    """Aggregated analytics for a single channel."""
    channel_id: str = ""
    channel_name: str = ""
    tier: int = 0
    niche: str = ""
    total_videos: int = 0
    quality_pass_rate: float = 0.0
    avg_viral_score: float = 0.0
    avg_retention_score: float = 0.0
    avg_hook_score: float = 0.0
    top_hook_type: str = ""
    top_archetype: str = ""
    trend: str = "stable"
    views_24h: int = 0
    views_7d: int = 0
    avg_ctr: float = 0.0
    avg_watch_time: float = 0.0
    estimated_revenue: float = 0.0
    health_status: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkReport:
    """Full network analytics report."""
    total_channels: int = 0
    total_videos: int = 0
    avg_viral_score: float = 0.0
    avg_retention_score: float = 0.0
    network_quality_rate: float = 0.0
    estimated_monthly_revenue: float = 0.0
    tier_breakdown: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    channels: List[ChannelAnalytics] = field(default_factory=list)
    top_performers: List[str] = field(default_factory=list)
    underperformers: List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["channels"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.channels]
        return d


class AnalyticsHub:

    def __init__(self):
        from app.services.content_genome import GenomeStore
        self.store = GenomeStore()

    def network_report(self) -> NetworkReport:
        """Generate a full network analytics report."""
        try:
            from app.services.network_config import NETWORK
        except ImportError:
            return NetworkReport()

        report = NetworkReport()
        all_channels = []
        tier_data: Dict[int, List[ChannelAnalytics]] = {}

        for key, config in NETWORK.items():
            ca = self._analyze_channel(config.channel_id, config)
            all_channels.append(ca)
            tier_data.setdefault(config.tier, []).append(ca)

        report.total_channels = len(all_channels)
        report.total_videos = sum(c.total_videos for c in all_channels)
        report.channels = all_channels

        # Network averages
        viral_scores = [c.avg_viral_score for c in all_channels if c.avg_viral_score > 0]
        ret_scores = [c.avg_retention_score for c in all_channels if c.avg_retention_score > 0]
        report.avg_viral_score = round(
            sum(viral_scores) / len(viral_scores), 1
        ) if viral_scores else 0
        report.avg_retention_score = round(
            sum(ret_scores) / len(ret_scores), 1
        ) if ret_scores else 0

        quality_rates = [c.quality_pass_rate for c in all_channels if c.total_videos > 0]
        report.network_quality_rate = round(
            sum(quality_rates) / len(quality_rates), 1
        ) if quality_rates else 0

        # Tier breakdown
        for tier, channels in tier_data.items():
            tier_viral = [c.avg_viral_score for c in channels if c.avg_viral_score > 0]
            tier_ret = [c.avg_retention_score for c in channels if c.avg_retention_score > 0]
            report.tier_breakdown[tier] = {
                "channels": len(channels),
                "total_videos": sum(c.total_videos for c in channels),
                "avg_viral": round(sum(tier_viral) / len(tier_viral), 1) if tier_viral else 0,
                "avg_retention": round(sum(tier_ret) / len(tier_ret), 1) if tier_ret else 0,
            }

        # Top/under performers
        scored = [(c, c.avg_viral_score) for c in all_channels if c.total_videos > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        report.top_performers = [c.channel_id for c, _ in scored[:2]]
        report.underperformers = [c.channel_id for c, _ in scored[-2:] if _[1] < 50]

        report.estimated_monthly_revenue = sum(c.estimated_revenue for c in all_channels)

        logger.info(
            f"[AnalyticsHub] Network report: {report.total_channels} channels, "
            f"{report.total_videos} videos, avg_viral={report.avg_viral_score}"
        )

        return report

    def channel_report(self, channel_id: str) -> ChannelAnalytics:
        """Get detailed analytics for a single channel."""
        # Try to find config
        config = None
        try:
            from app.services.network_config import NETWORK
            for key, cfg in NETWORK.items():
                if cfg.channel_id == channel_id:
                    config = cfg
                    break
        except ImportError:
            pass

        return self._analyze_channel(channel_id, config)

    def compare_tiers(self) -> Dict[str, Any]:
        """Compare performance across network tiers."""
        report = self.network_report()
        return {
            "tiers": report.tier_breakdown,
            "recommendation": self._tier_recommendation(report.tier_breakdown),
        }

    def _analyze_channel(self, channel_id: str, config=None) -> ChannelAnalytics:
        """Analyze a single channel from genome data."""
        genomes = self.store.query(channel_id=channel_id, limit=100, sort_by="created_at")

        ca = ChannelAnalytics(
            channel_id=channel_id,
            channel_name=config.name if config else channel_id,
            tier=config.tier if config else 0,
            niche=config.niche if config else "",
            total_videos=len(genomes),
        )

        if not genomes:
            ca.health_status = "no_data"
            return ca

        # Score averages
        viral = [g.viral_score for g in genomes if g.viral_score > 0]
        ret = [g.retention_score for g in genomes if g.retention_score > 0]
        hooks = [g.hook_score for g in genomes if g.hook_score > 0]
        passed = sum(1 for g in genomes if g.quality_passed)

        ca.avg_viral_score = round(sum(viral) / len(viral), 1) if viral else 0
        ca.avg_retention_score = round(sum(ret) / len(ret), 1) if ret else 0
        ca.avg_hook_score = round(sum(hooks) / len(hooks), 1) if hooks else 0
        ca.quality_pass_rate = round(passed / len(genomes) * 100, 1)

        # Top hook type
        hook_counts: Dict[str, int] = {}
        for g in genomes:
            if g.hook_type:
                hook_counts[g.hook_type] = hook_counts.get(g.hook_type, 0) + 1
        if hook_counts:
            ca.top_hook_type = max(hook_counts, key=hook_counts.get)

        # Top archetype
        arch_counts: Dict[str, int] = {}
        for g in genomes:
            if g.archetype:
                arch_counts[g.archetype] = arch_counts.get(g.archetype, 0) + 1
        if arch_counts:
            ca.top_archetype = max(arch_counts, key=arch_counts.get)

        # YouTube metrics
        ca.views_24h = sum(g.views_24h for g in genomes)
        ca.views_7d = sum(g.views_7d for g in genomes)
        ctrs = [g.ctr for g in genomes if g.ctr > 0]
        ca.avg_ctr = round(sum(ctrs) / len(ctrs), 2) if ctrs else 0
        watch_times = [g.avg_watch_time for g in genomes if g.avg_watch_time > 0]
        ca.avg_watch_time = round(sum(watch_times) / len(watch_times), 1) if watch_times else 0

        # Revenue estimate
        if config and config.target_cpm_range and ca.views_7d > 0:
            avg_cpm = sum(config.target_cpm_range) / 2
            ca.estimated_revenue = round(ca.views_7d / 1000 * avg_cpm * 4, 2)  # Monthly

        # Trend
        if len(genomes) >= 6:
            mid = len(genomes) // 2
            recent = [g.viral_score for g in genomes[:mid] if g.viral_score > 0]
            older = [g.viral_score for g in genomes[mid:] if g.viral_score > 0]
            if recent and older:
                r_avg = sum(recent) / len(recent)
                o_avg = sum(older) / len(older)
                ca.trend = "improving" if r_avg > o_avg * 1.1 else (
                    "declining" if r_avg < o_avg * 0.9 else "stable"
                )

        # Health
        score = ca.avg_viral_score * 0.4 + ca.avg_retention_score * 0.35 + ca.quality_pass_rate * 0.25
        ca.health_status = (
            "excellent" if score >= 75 else
            "good" if score >= 55 else
            "warning" if score >= 40 else
            "critical"
        )

        return ca

    def _tier_recommendation(self, tiers: Dict) -> str:
        """Generate recommendation based on tier comparison."""
        if not tiers:
            return "Insufficient data"

        t1 = tiers.get(1, {}).get("avg_viral", 0)
        t2 = tiers.get(2, {}).get("avg_viral", 0)
        t3 = tiers.get(3, {}).get("avg_viral", 0)

        if t3 > t1 and t3 > 60:
            return "Tier 3 experimental outperforming — consider promoting to Tier 2"
        if t1 < 45:
            return "Tier 1 authority channels underperforming — review content strategy"
        if t2 > t1:
            return "Tier 2 growth channels outperforming Tier 1 — rebalance resources"
        return "Network performing as expected — maintain current strategy"
