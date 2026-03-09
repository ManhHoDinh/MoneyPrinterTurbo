"""
Revenue orchestration layer.

Keeps video engine untouched and focuses on monetization strategy:
  - Revenue-oriented niche scoring
  - Funnel slot templates (affiliate, lead magnet, CTA tag)
  - Production scaling recommendation per niche
"""

from dataclasses import dataclass
from typing import Dict, Any

from app.services.niche_intelligence import NICHE_DATABASE


PURCHASING_POWER_INDEX = {
    "finance": 95,
    "luxury_lifestyle": 92,
    "ai_technology": 85,
    "health": 80,
    "motivation": 72,
    "dark_psychology": 68,
    "stoic_philosophy": 64,
    "relationships": 62,
    "viral_facts": 45,
    "true_crime": 42,
}


@dataclass
class RevenueNicheScore:
    niche: str
    cpm_score: float
    affiliate_score: float
    purchasing_power_score: float
    revenue_priority_score: float
    production_multiplier: float
    tier: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "niche": self.niche,
            "cpm_score": round(self.cpm_score, 2),
            "affiliate_score": round(self.affiliate_score, 2),
            "purchasing_power_score": round(self.purchasing_power_score, 2),
            "revenue_priority_score": round(self.revenue_priority_score, 2),
            "production_multiplier": round(self.production_multiplier, 2),
            "tier": self.tier,
        }


def score_niche_for_revenue(niche: str) -> RevenueNicheScore:
    data = NICHE_DATABASE.get(niche, {})
    cpm_range = data.get("cpm_range", [5, 15])
    avg_cpm = float(cpm_range[0] + cpm_range[1]) / 2.0

    # Normalize to 0-100 using a practical CPM cap for shorts channels.
    cpm_score = min(100.0, max(0.0, (avg_cpm / 50.0) * 100.0))
    affiliate_score = min(100.0, float(len(data.get("affiliate_categories", []))) * 20.0)
    purchasing_power_score = float(PURCHASING_POWER_INDEX.get(niche, 60.0))

    revenue_score = (
        cpm_score * 0.45
        + affiliate_score * 0.25
        + purchasing_power_score * 0.30
    )

    if revenue_score >= 80:
        tier = "high"
        multiplier = 1.6
    elif revenue_score >= 65:
        tier = "mid_high"
        multiplier = 1.25
    elif revenue_score >= 50:
        tier = "mid"
        multiplier = 1.0
    else:
        tier = "low"
        multiplier = 0.65

    return RevenueNicheScore(
        niche=niche,
        cpm_score=cpm_score,
        affiliate_score=affiliate_score,
        purchasing_power_score=purchasing_power_score,
        revenue_priority_score=revenue_score,
        production_multiplier=multiplier,
        tier=tier,
    )


def recommend_videos_per_run(base_videos: int, niche: str, min_videos: int = 1, max_videos: int = 12) -> int:
    profile = score_niche_for_revenue(niche)
    target = int(round(float(base_videos) * profile.production_multiplier))
    if target < min_videos:
        target = min_videos
    if target > max_videos:
        target = max_videos
    return target


def build_funnel_slots(niche: str) -> Dict[str, str]:
    key = niche.strip().lower() if niche else "general"
    return {
        "affiliate_link_slot": f"[AFFILIATE_{key.upper()}_LINK]",
        "lead_magnet_slot": f"[LEADMAGNET_{key.upper()}_LINK]",
        "cta_tag": f"cta_{key}",
    }


def infer_channel_revenue_tier(channel: Any) -> str:
    """
    Tier 1 (Authority): low volume, high value
    Tier 2 (Traffic): medium volume, lead capture
    Tier 3 (Experiment): high volume, offer tests
    """
    try:
        daily_limit = int(getattr(channel, "daily_video_limit", 3) or 3)
    except Exception:
        daily_limit = 3

    if daily_limit <= 2:
        return "tier1_authority"
    if daily_limit <= 5:
        return "tier2_traffic"
    return "tier3_experiment"
