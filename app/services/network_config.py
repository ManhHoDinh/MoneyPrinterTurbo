"""
US High CPM Content Network — 3-tier channel configuration.

Defines the specific channel fleet targeting US audience with high CPM niches:

  Tier 1 (Authority):    Wealth Psychology, Business Discipline
  Tier 2 (Growth):       Dark Psychology, AI Automation
  Tier 3 (Experimental): Rotating test niches

Each channel has full identity: hook archetype, visual tone, pacing,
subtitle style, emotion bias, CPM target, and content strategy.

Usage:
    from app.services.network_config import NETWORK, get_tier, get_all_channels
    tier1 = get_tier(1)
    all_channels = get_all_channels()
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


@dataclass
class ChannelConfig:
    """Full channel identity for the US HIGH CPM network."""
    channel_id: str = ""
    name: str = ""
    tier: int = 1
    niche: str = ""
    description: str = ""

    # Identity
    hook_archetype: str = ""
    visual_tone: str = ""
    pacing_style: str = ""
    subtitle_style: str = ""
    emotion_bias: List[str] = field(default_factory=list)

    # Content Strategy
    topics_per_day: int = 1
    style_preset: str = ""
    target_duration_seconds: int = 60
    script_tone: str = ""

    # Monetization
    target_cpm_range: List[int] = field(default_factory=list)
    affiliate_categories: List[str] = field(default_factory=list)
    cta_style: str = ""

    # Scheduling
    upload_hour_utc: int = 14        # ~9-10 AM EST peak
    upload_days: List[str] = field(default_factory=lambda: [
        "mon", "tue", "wed", "thu", "fri", "sat", "sun"
    ])

    # Performance Thresholds
    min_retention_score: float = 55.0
    min_viral_score: float = 50.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Network Definition ───────────────────────────────────────────────────────

NETWORK: Dict[str, ChannelConfig] = {

    # ━━━ TIER 1: AUTHORITY CHANNELS (Highest CPM) ━━━━━━━━━━━━━━━━━━━━━━━━━━

    "wealth-psychology": ChannelConfig(
        channel_id="us-t1-wealth",
        name="Wealth Psychology",
        tier=1,
        niche="finance",
        description="Psychology of money, wealth building, financial behavior",
        hook_archetype="authority",
        visual_tone="corporate_dark",
        pacing_style="analytical",
        subtitle_style="clean_data",
        emotion_bias=["aspiration", "fear", "curiosity"],
        topics_per_day=2,
        style_preset="luxury_lifestyle",
        target_duration_seconds=60,
        script_tone="authoritative, data-driven, contrarian",
        target_cpm_range=[18, 55],
        affiliate_categories=["brokerages", "courses", "finance_tools", "credit_cards"],
        cta_style="professional",
        upload_hour_utc=14,
        min_retention_score=60.0,
        min_viral_score=55.0,
    ),

    "business-discipline": ChannelConfig(
        channel_id="us-t1-discipline",
        name="Business Discipline",
        tier=1,
        niche="motivation",
        description="Productivity systems, business psychology, elite performance",
        hook_archetype="aspiration",
        visual_tone="warm_motivational",
        pacing_style="steady_build",
        subtitle_style="clean_centered",
        emotion_bias=["aspiration", "anger", "determination"],
        topics_per_day=2,
        style_preset="motivation",
        target_duration_seconds=55,
        script_tone="intense, direct, no-nonsense",
        target_cpm_range=[10, 28],
        affiliate_categories=["courses", "books", "coaching", "productivity_tools"],
        cta_style="motivational",
        upload_hour_utc=13,
        min_retention_score=55.0,
        min_viral_score=50.0,
    ),

    # ━━━ TIER 2: GROWTH CHANNELS (High Viral + Good CPM) ━━━━━━━━━━━━━━━━━━━

    "dark-psychology": ChannelConfig(
        channel_id="us-t2-darkpsych",
        name="Dark Psychology Decoded",
        tier=2,
        niche="dark_psychology",
        description="Manipulation tactics, cognitive biases, behavioral psychology",
        hook_archetype="fear",
        visual_tone="dark_cinematic",
        pacing_style="accelerating",
        subtitle_style="bold_highlight",
        emotion_bias=["fear", "curiosity", "surprise"],
        topics_per_day=3,
        style_preset="dark_psychology",
        target_duration_seconds=50,
        script_tone="ominous, revealing, urgent",
        target_cpm_range=[8, 22],
        affiliate_categories=["books", "courses", "self-improvement"],
        cta_style="fear_driven",
        upload_hour_utc=15,
        min_retention_score=50.0,
        min_viral_score=45.0,
    ),

    "ai-automation": ChannelConfig(
        channel_id="us-t2-ai",
        name="AI Future Lab",
        tier=2,
        niche="ai_technology",
        description="AI disruption, automation trends, future of work",
        hook_archetype="curiosity",
        visual_tone="tech_neon",
        pacing_style="rapid_fire",
        subtitle_style="monospace_tech",
        emotion_bias=["curiosity", "fear", "aspiration"],
        topics_per_day=2,
        style_preset="viral_facts",
        target_duration_seconds=45,
        script_tone="futuristic, provocative, breaking-news",
        target_cpm_range=[12, 40],
        affiliate_categories=["tools", "courses", "software", "hosting"],
        cta_style="tech_forward",
        upload_hour_utc=16,
        min_retention_score=50.0,
        min_viral_score=45.0,
    ),

    # ━━━ TIER 3: EXPERIMENTAL CHANNELS (Test & Scale) ━━━━━━━━━━━━━━━━━━━━━━

    "experiment-alpha": ChannelConfig(
        channel_id="us-t3-alpha",
        name="Mind Unlocked",
        tier=3,
        niche="relationships",
        description="Relationship psychology, attraction science, social dynamics",
        hook_archetype="shock",
        visual_tone="intimate_dark",
        pacing_style="conversational",
        subtitle_style="bold_highlight",
        emotion_bias=["curiosity", "anger", "surprise"],
        topics_per_day=1,
        style_preset="dark_psychology",
        target_duration_seconds=55,
        script_tone="raw, unfiltered, confrontational",
        target_cpm_range=[6, 20],
        affiliate_categories=["books", "courses", "dating_apps"],
        cta_style="emotional",
        upload_hour_utc=17,
        min_retention_score=45.0,
        min_viral_score=40.0,
    ),

    "experiment-beta": ChannelConfig(
        channel_id="us-t3-beta",
        name="Health Decoded",
        tier=3,
        niche="health",
        description="Biohacking, health myths, supplement science",
        hook_archetype="curiosity",
        visual_tone="bright_energetic",
        pacing_style="rapid_fire",
        subtitle_style="animated_pop",
        emotion_bias=["curiosity", "fear", "hope"],
        topics_per_day=1,
        style_preset="viral_facts",
        target_duration_seconds=50,
        script_tone="scientific, myth-busting, urgent",
        target_cpm_range=[10, 35],
        affiliate_categories=["supplements", "equipment", "courses", "apps"],
        cta_style="health_conscious",
        upload_hour_utc=15,
        min_retention_score=45.0,
        min_viral_score=40.0,
    ),
}


# ── Query Functions ──────────────────────────────────────────────────────────

def get_all_channels() -> List[ChannelConfig]:
    """Get all channels in the network."""
    return list(NETWORK.values())


def get_tier(tier: int) -> List[ChannelConfig]:
    """Get all channels in a specific tier."""
    return [c for c in NETWORK.values() if c.tier == tier]


def get_channel(channel_key: str) -> Optional[ChannelConfig]:
    """Get a specific channel by key."""
    return NETWORK.get(channel_key)


def get_daily_quota() -> Dict[str, int]:
    """Get total daily video quota across the network."""
    return {
        "tier_1": sum(c.topics_per_day for c in get_tier(1)),
        "tier_2": sum(c.topics_per_day for c in get_tier(2)),
        "tier_3": sum(c.topics_per_day for c in get_tier(3)),
        "total": sum(c.topics_per_day for c in NETWORK.values()),
    }


def get_network_summary() -> Dict[str, Any]:
    """Get a summary of the entire network."""
    channels = get_all_channels()
    quota = get_daily_quota()

    # Revenue estimate
    all_cpms = []
    for c in channels:
        if c.target_cpm_range:
            all_cpms.append(sum(c.target_cpm_range) / 2)

    avg_cpm = sum(all_cpms) / len(all_cpms) if all_cpms else 10
    daily_videos = quota["total"]
    # Assume 50k avg views per video at maturity
    monthly_ad_low = avg_cpm * 50 * daily_videos * 30 / 1000
    monthly_ad_high = monthly_ad_low * 2

    return {
        "total_channels": len(channels),
        "tiers": {
            "authority": len(get_tier(1)),
            "growth": len(get_tier(2)),
            "experimental": len(get_tier(3)),
        },
        "daily_video_quota": quota,
        "avg_network_cpm": round(avg_cpm, 1),
        "channels": [
            {
                "name": c.name,
                "tier": c.tier,
                "niche": c.niche,
                "videos_per_day": c.topics_per_day,
                "cpm_range": c.target_cpm_range,
            }
            for c in channels
        ],
        "estimated_monthly_revenue": f"${monthly_ad_low:,.0f}-${monthly_ad_high:,.0f} (ad revenue at 50k views/video)",
    }
