"""
Revenue-first metadata generator for upload layer.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from app.config import config
from app.services.monetization import _generate_title, _extract_seo_keywords, _generate_tags, _generate_hashtags
from app.services.revenue_orchestrator import build_funnel_slots, score_niche_for_revenue
from app.services.niche_intelligence import NICHE_DATABASE
from app.services.revenue_optimization import choose_offer_for_niche, build_buyer_intent_hook


@dataclass
class RevenueMetadata:
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    pinned_comment: str = ""
    cta_tag: str = ""
    affiliate_link_slot: str = ""
    lead_magnet_slot: str = ""
    monetization_link_used: str = ""
    seo_keywords: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    estimated_cpm: float = 0.0
    thumbnail_path: Optional[str] = None
    revenue_priority_score: float = 0.0
    offer_label: str = ""
    landing_page_slot: str = ""
    buyer_intent_hook: str = ""
    offer_code: str = ""
    offer_angle: str = ""


def generate_revenue_metadata(
    topic: str,
    niche: str,
    style: str = "",
    channel_name: str = "",
    affiliate_overrides: Optional[Dict[str, str]] = None,
    db: Any = None,
    channel_tier: str = "tier3_experiment",
) -> RevenueMetadata:
    style_key = style or niche or "dark_psychology"
    revenue_profile = score_niche_for_revenue(niche or style_key)
    funnel = build_funnel_slots(niche or style_key)
    seo_keywords = _extract_seo_keywords(topic, niche or style_key)
    tags = _generate_tags(topic, niche or style_key, seo_keywords)
    hashtags = _generate_hashtags(niche or style_key, seo_keywords[:5])

    selected_offer = choose_offer_for_niche(
        db,
        niche or style_key,
        explore_rate=float(config.app.get("offer_explore_rate", 0.2) or 0.2),
    ) if db is not None else {
        "code": "GEN_A",
        "label": "Primary Offer",
        "url": funnel["affiliate_link_slot"],
        "landing_slot": "[LANDING_DEFAULT]",
    }

    affiliate_slot = selected_offer.get("url", funnel["affiliate_link_slot"])
    if affiliate_overrides:
        affiliate_slot = affiliate_overrides.get("primary", affiliate_slot)
    lead_slot = affiliate_overrides.get("lead_magnet", funnel["lead_magnet_slot"]) if affiliate_overrides else funnel["lead_magnet_slot"]
    cta_tag = funnel["cta_tag"]
    buyer_hook = build_buyer_intent_hook(topic, niche or style_key)
    angle = _build_offer_angle(topic, niche or style_key, selected_offer.get("label", "this offer"))

    cpm = NICHE_DATABASE.get(niche or style_key, {}).get("cpm_range", [5, 15])
    estimated_cpm = float(cpm[0] + cpm[1]) / 2.0
    title = _generate_title(topic, style_key, __import__("random").Random(hash(topic) & 0xFFFFFFFF))

    description = _build_revenue_description(
        topic=topic,
        seo_keywords=seo_keywords,
        hashtags=hashtags,
        affiliate_slot=affiliate_slot,
        lead_slot=lead_slot,
        cta_tag=cta_tag,
        channel_name=channel_name,
        buyer_hook=buyer_hook,
        channel_tier=channel_tier,
        landing_page_slot=selected_offer.get("landing_slot", "[LANDING_DEFAULT]"),
        offer_angle=angle,
    )
    pinned_comment = (
        "Top resource from this video:\n"
        f"{affiliate_slot}\n\n"
        f"Type '{cta_tag}' if you want a deeper breakdown."
    )

    return RevenueMetadata(
        title=title,
        description=description,
        tags=tags,
        pinned_comment=pinned_comment,
        cta_tag=cta_tag,
        affiliate_link_slot=affiliate_slot,
        lead_magnet_slot=lead_slot,
        monetization_link_used=affiliate_slot,
        seo_keywords=seo_keywords,
        hashtags=hashtags,
        estimated_cpm=estimated_cpm,
        revenue_priority_score=revenue_profile.revenue_priority_score,
        offer_label=selected_offer.get("label", ""),
        landing_page_slot=selected_offer.get("landing_slot", "[LANDING_DEFAULT]"),
        buyer_intent_hook=buyer_hook,
        offer_code=selected_offer.get("code", "GEN_A"),
        offer_angle=angle,
    )


def _build_revenue_description(
    topic: str,
    seo_keywords: List[str],
    hashtags: List[str],
    affiliate_slot: str,
    lead_slot: str,
    cta_tag: str,
    channel_name: str,
    buyer_hook: str,
    channel_tier: str,
    landing_page_slot: str,
    offer_angle: str,
) -> str:
    tier_line = {
        "tier1_authority": "Tier 1 Strategy: Authority -> digital product + high-ticket affiliate",
        "tier2_traffic": "Tier 2 Strategy: Traffic -> lead magnet + email capture",
        "tier3_experiment": "Tier 3 Strategy: Experiment -> direct affiliate testing",
    }.get(channel_tier, "Tier Strategy: direct conversion optimization")

    lines = [
        buyer_hook,
        "",
        tier_line,
        "",
        "RESOURCES:",
        f"- Affiliate Offer: {affiliate_slot}",
        f"- Landing Page: {landing_page_slot}",
        f"- Free Lead Magnet: {lead_slot}",
        "",
        f"Authority framing: {offer_angle}",
        "Urgency: Offer terms may change soon, check before fees return.",
        "",
        "CTA:",
        "1) Subscribe for more monetization-ready content",
        "2) Use the affiliate resource above",
        "3) Download the lead magnet",
        f"4) Comment with: {cta_tag}",
        "",
    ]
    if seo_keywords:
        lines.append("Topics covered: " + ", ".join(seo_keywords[:12]))
        lines.append("")
    if hashtags:
        lines.append(" ".join(hashtags[:8]))
    if channel_name:
        lines.extend(["", f"© {channel_name}"])
    return "\n".join(lines)


def _build_offer_angle(topic: str, niche: str, offer_label: str) -> str:
    if niche == "finance":
        return f"After testing 12 finance tools, {offer_label} is the one I use to reduce hidden fees."
    if niche == "ai_technology":
        return f"After testing 12 AI workflows, {offer_label} saved the most time per week."
    if niche == "health":
        return f"After testing 12 health products, {offer_label} gave the best cost-to-result ratio."
    return f"After testing 12 options, {offer_label} was the most practical pick."
