"""
Niche Intelligence Engine — Score niches by business viability.

Evaluates candidate niches across three dimensions:
  - Viral Potential:        Shareability, controversy, emotional trigger density
  - Monetization Potential: Affiliate opportunity, CPM range, product-market fit
  - Emotional Intensity:    Psychological hook strength, obsession factor

Returns ranked niches with full scoring breakdown and recommended
style presets, archetypes, and channel DNA profiles.

Usage:
    from app.services.niche_intelligence import score_niche, discover_niches
    result = score_niche("dark psychology")
    top_niches = discover_niches(count=10)
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


# ── Niche Knowledge Base ─────────────────────────────────────────────────────

NICHE_DATABASE: Dict[str, Dict[str, Any]] = {
    "dark_psychology": {
        "display_name": "Dark Psychology",
        "viral_base": 88,
        "monetization_base": 72,
        "emotion_base": 92,
        "cpm_range": [8, 22],
        "affiliate_categories": ["books", "courses", "self-improvement"],
        "audience_obsession": 0.9,
        "controversy_level": 0.7,
        "best_archetypes": ["dark_psychological_revelation", "forbidden_knowledge"],
        "recommended_styles": ["dark_psychology"],
        "audience_size": "large",
        "saturation": "medium",
        "evergreen": True,
    },
    "motivation": {
        "display_name": "Motivation & Self-Improvement",
        "viral_base": 75,
        "monetization_base": 80,
        "emotion_base": 70,
        "cpm_range": [10, 28],
        "affiliate_categories": ["courses", "books", "coaching", "supplements"],
        "audience_obsession": 0.65,
        "controversy_level": 0.3,
        "best_archetypes": ["success_myth_destruction", "identity_challenge"],
        "recommended_styles": ["motivation"],
        "audience_size": "very_large",
        "saturation": "high",
        "evergreen": True,
    },
    "stoic_philosophy": {
        "display_name": "Stoic Philosophy",
        "viral_base": 68,
        "monetization_base": 65,
        "emotion_base": 60,
        "cpm_range": [6, 18],
        "affiliate_categories": ["books", "journals", "meditation"],
        "audience_obsession": 0.7,
        "controversy_level": 0.2,
        "best_archetypes": ["secret_rule_explanation", "counterintuitive_truth"],
        "recommended_styles": ["stoic_philosophy"],
        "audience_size": "medium",
        "saturation": "low",
        "evergreen": True,
    },
    "luxury_lifestyle": {
        "display_name": "Luxury Lifestyle & Wealth",
        "viral_base": 82,
        "monetization_base": 90,
        "emotion_base": 75,
        "cpm_range": [15, 45],
        "affiliate_categories": ["finance", "investing", "luxury_goods", "real_estate"],
        "audience_obsession": 0.8,
        "controversy_level": 0.5,
        "best_archetypes": ["success_myth_destruction", "hidden_danger_warning"],
        "recommended_styles": ["luxury_lifestyle"],
        "audience_size": "large",
        "saturation": "high",
        "evergreen": True,
    },
    "viral_facts": {
        "display_name": "Viral Facts & Science",
        "viral_base": 90,
        "monetization_base": 55,
        "emotion_base": 65,
        "cpm_range": [4, 14],
        "affiliate_categories": ["books", "education", "gadgets"],
        "audience_obsession": 0.5,
        "controversy_level": 0.3,
        "best_archetypes": ["counterintuitive_truth", "forbidden_knowledge"],
        "recommended_styles": ["viral_facts"],
        "audience_size": "very_large",
        "saturation": "medium",
        "evergreen": True,
    },
    "finance": {
        "display_name": "Personal Finance & Investing",
        "viral_base": 70,
        "monetization_base": 95,
        "emotion_base": 72,
        "cpm_range": [18, 55],
        "affiliate_categories": ["brokerages", "credit_cards", "courses", "tools"],
        "audience_obsession": 0.75,
        "controversy_level": 0.4,
        "best_archetypes": ["secret_rule_explanation", "hidden_danger_warning"],
        "recommended_styles": ["dark_psychology", "motivation"],
        "audience_size": "large",
        "saturation": "high",
        "evergreen": True,
    },
    "relationships": {
        "display_name": "Relationships & Dating",
        "viral_base": 85,
        "monetization_base": 68,
        "emotion_base": 88,
        "cpm_range": [6, 20],
        "affiliate_categories": ["books", "courses", "dating_apps"],
        "audience_obsession": 0.85,
        "controversy_level": 0.6,
        "best_archetypes": ["dark_psychological_revelation", "identity_challenge"],
        "recommended_styles": ["dark_psychology"],
        "audience_size": "very_large",
        "saturation": "medium",
        "evergreen": True,
    },
    "health": {
        "display_name": "Health & Biohacking",
        "viral_base": 78,
        "monetization_base": 85,
        "emotion_base": 70,
        "cpm_range": [10, 35],
        "affiliate_categories": ["supplements", "equipment", "courses", "apps"],
        "audience_obsession": 0.7,
        "controversy_level": 0.5,
        "best_archetypes": ["hidden_danger_warning", "counterintuitive_truth"],
        "recommended_styles": ["viral_facts", "dark_psychology"],
        "audience_size": "large",
        "saturation": "medium",
        "evergreen": True,
    },
    "ai_technology": {
        "display_name": "AI & Technology",
        "viral_base": 85,
        "monetization_base": 78,
        "emotion_base": 68,
        "cpm_range": [12, 40],
        "affiliate_categories": ["tools", "courses", "software", "hosting"],
        "audience_obsession": 0.75,
        "controversy_level": 0.4,
        "best_archetypes": ["forbidden_knowledge", "hidden_danger_warning"],
        "recommended_styles": ["viral_facts"],
        "audience_size": "large",
        "saturation": "low",
        "evergreen": False,
    },
    "true_crime": {
        "display_name": "True Crime & Mystery",
        "viral_base": 92,
        "monetization_base": 60,
        "emotion_base": 95,
        "cpm_range": [5, 16],
        "affiliate_categories": ["books", "streaming", "podcasts"],
        "audience_obsession": 0.95,
        "controversy_level": 0.6,
        "best_archetypes": ["dark_psychological_revelation", "forbidden_knowledge"],
        "recommended_styles": ["dark_psychology"],
        "audience_size": "very_large",
        "saturation": "medium",
        "evergreen": True,
    },
}

# Scoring weights
NICHE_WEIGHTS = {
    "viral_potential": 0.35,
    "monetization_potential": 0.35,
    "emotional_intensity": 0.30,
}


# ── Scored Niche ─────────────────────────────────────────────────────────────

@dataclass
class ScoredNiche:
    """A niche with full business viability scoring."""
    niche_key: str = ""
    display_name: str = ""
    viral_potential: float = 0.0
    monetization_potential: float = 0.0
    emotional_intensity: float = 0.0
    composite_score: float = 0.0
    cpm_range: List[int] = field(default_factory=list)
    affiliate_categories: List[str] = field(default_factory=list)
    recommended_styles: List[str] = field(default_factory=list)
    best_archetypes: List[str] = field(default_factory=list)
    audience_size: str = ""
    saturation: str = ""
    evergreen: bool = True
    estimated_monthly_revenue: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Public API ───────────────────────────────────────────────────────────────

def score_niche(niche_key: str) -> ScoredNiche:
    """Score a single niche across all business dimensions."""
    data = NICHE_DATABASE.get(niche_key)
    if not data:
        # Score unknown niche with conservative defaults
        return ScoredNiche(
            niche_key=niche_key,
            display_name=niche_key.replace("_", " ").title(),
            viral_potential=50,
            monetization_potential=50,
            emotional_intensity=50,
            composite_score=50,
        )

    viral = _compute_viral_potential(data)
    monetization = _compute_monetization(data)
    emotion = _compute_emotional_intensity(data)

    composite = (
        viral * NICHE_WEIGHTS["viral_potential"]
        + monetization * NICHE_WEIGHTS["monetization_potential"]
        + emotion * NICHE_WEIGHTS["emotional_intensity"]
    )

    # Revenue estimate
    avg_cpm = sum(data.get("cpm_range", [5, 15])) / 2
    # Assume 100k views/month at start (conservative)
    monthly_ad = avg_cpm * 100  # 100k views / 1000 * avg_cpm
    revenue_str = f"${monthly_ad:.0f}-${monthly_ad * 3:.0f}/mo (ads) + affiliate"

    return ScoredNiche(
        niche_key=niche_key,
        display_name=data.get("display_name", niche_key),
        viral_potential=round(viral, 1),
        monetization_potential=round(monetization, 1),
        emotional_intensity=round(emotion, 1),
        composite_score=round(composite, 1),
        cpm_range=data.get("cpm_range", []),
        affiliate_categories=data.get("affiliate_categories", []),
        recommended_styles=data.get("recommended_styles", []),
        best_archetypes=data.get("best_archetypes", []),
        audience_size=data.get("audience_size", ""),
        saturation=data.get("saturation", ""),
        evergreen=data.get("evergreen", True),
        estimated_monthly_revenue=revenue_str,
    )


def discover_niches(
    count: int = 10,
    min_score: float = 0.0,
    sort_by: str = "composite_score",
) -> List[ScoredNiche]:
    """
    Score all known niches and return ranked by business viability.

    Args:
        count:    Maximum niches to return
        min_score: Minimum composite score threshold
        sort_by:  Sort field (composite_score, viral_potential, monetization_potential)
    """
    scored = []
    for key in NICHE_DATABASE:
        sn = score_niche(key)
        if sn.composite_score >= min_score:
            scored.append(sn)

    scored.sort(key=lambda x: getattr(x, sort_by, 0), reverse=True)

    result = scored[:count]
    logger.info(
        f"[NicheIntel] Discovered {len(result)} niches "
        f"(min={min_score}, top={result[0].display_name if result else 'N/A'}: "
        f"{result[0].composite_score if result else 0})"
    )
    return result


def recommend_channel_portfolio(
    channel_count: int = 3,
    strategy: str = "balanced",
) -> List[Dict[str, Any]]:
    """
    Recommend a multi-channel portfolio strategy.

    Strategies:
      - "balanced":     Mix of high-viral + high-monetization niches
      - "monetization": Focus on highest CPM niches
      - "growth":       Focus on highest viral potential niches
    """
    all_niches = discover_niches(count=len(NICHE_DATABASE))

    if strategy == "monetization":
        all_niches.sort(key=lambda x: x.monetization_potential, reverse=True)
    elif strategy == "growth":
        all_niches.sort(key=lambda x: x.viral_potential, reverse=True)
    else:
        # Balanced — already sorted by composite
        pass

    portfolio = []
    used_styles = set()

    for niche in all_niches:
        if len(portfolio) >= channel_count:
            break
        # Avoid overlapping styles for differentiation
        styles = set(niche.recommended_styles)
        if styles & used_styles and len(portfolio) > 0:
            continue
        used_styles |= styles

        portfolio.append({
            "niche": niche.niche_key,
            "display_name": niche.display_name,
            "score": niche.composite_score,
            "cpm_range": niche.cpm_range,
            "styles": niche.recommended_styles,
            "archetypes": niche.best_archetypes,
            "revenue_estimate": niche.estimated_monthly_revenue,
        })

    return portfolio


# ── Internal Scoring Functions ───────────────────────────────────────────────

def _compute_viral_potential(data: Dict) -> float:
    """Score viral potential (0-100)."""
    score = data.get("viral_base", 50)

    # Controversy boosts virality
    score += data.get("controversy_level", 0.5) * 10

    # Large audience = more share surface
    audience_bonus = {"very_large": 8, "large": 5, "medium": 2, "small": 0}
    score += audience_bonus.get(data.get("audience_size", "medium"), 0)

    # Low saturation = easier to break through
    sat_bonus = {"low": 8, "medium": 3, "high": -3}
    score += sat_bonus.get(data.get("saturation", "medium"), 0)

    return max(0, min(100, score))


def _compute_monetization(data: Dict) -> float:
    """Score monetization potential (0-100)."""
    score = data.get("monetization_base", 50)

    # CPM range affects ad revenue
    cpm = data.get("cpm_range", [5, 15])
    avg_cpm = sum(cpm) / 2
    if avg_cpm >= 25:
        score += 10
    elif avg_cpm >= 15:
        score += 5

    # More affiliate categories = more monetization paths
    affiliates = len(data.get("affiliate_categories", []))
    score += min(affiliates * 3, 12)

    # Evergreen = sustained revenue
    if data.get("evergreen", True):
        score += 5

    return max(0, min(100, score))


def _compute_emotional_intensity(data: Dict) -> float:
    """Score emotional intensity / psychological hook strength (0-100)."""
    score = data.get("emotion_base", 50)

    # Obsession factor — how addicted the audience gets
    score += data.get("audience_obsession", 0.5) * 15

    # Controversy adds emotional charge
    score += data.get("controversy_level", 0.5) * 8

    return max(0, min(100, score))
