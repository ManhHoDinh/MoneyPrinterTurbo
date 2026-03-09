"""
Revenue Optimization 2.0 service layer.

Scope:
  - Buyer-intent topic scoring
  - Offer rotation (A/B/N) by niche
  - Revenue tagging updates (clicks/views/revenue)
  - EPMV analytics and niche profitability ranking
"""

from datetime import datetime, timedelta
import os
import random
from typing import Dict, List, Any

from sqlalchemy.orm import Session

from app.config import config
from app.db.models import RevenueTag, OfferRotationStat


BUYER_INTENT_TERMS = {
    "finance": ["debt", "credit card", "invest", "retirement", "savings", "fees", "tax", "budget"],
    "health": ["symptoms", "treatment", "supplement", "weight loss", "blood sugar", "sleep"],
    "ai_technology": ["tool", "automation", "workflow", "save time", "productivity"],
    "general": ["how to", "mistakes", "avoid", "why", "best", "cost", "problem", "fix"],
}


OFFER_CATALOG = {
    "finance": [
        {"code": "FIN_A", "label": "Broker Bonus", "url": "[AFFILIATE_FINANCE_A]", "landing_slot": "[LANDING_FINANCE_A]"},
        {"code": "FIN_B", "label": "Card Points Offer", "url": "[AFFILIATE_FINANCE_B]", "landing_slot": "[LANDING_FINANCE_B]"},
        {"code": "FIN_C", "label": "Budgeting App", "url": "[AFFILIATE_FINANCE_C]", "landing_slot": "[LANDING_FINANCE_C]"},
    ],
    "health": [
        {"code": "HLT_A", "label": "Supplement Stack", "url": "[AFFILIATE_HEALTH_A]", "landing_slot": "[LANDING_HEALTH_A]"},
        {"code": "HLT_B", "label": "Fitness App", "url": "[AFFILIATE_HEALTH_B]", "landing_slot": "[LANDING_HEALTH_B]"},
        {"code": "HLT_C", "label": "Meal Planner", "url": "[AFFILIATE_HEALTH_C]", "landing_slot": "[LANDING_HEALTH_C]"},
    ],
    "ai_technology": [
        {"code": "AI_A", "label": "AI Toolkit", "url": "[AFFILIATE_AI_A]", "landing_slot": "[LANDING_AI_A]"},
        {"code": "AI_B", "label": "Automation Course", "url": "[AFFILIATE_AI_B]", "landing_slot": "[LANDING_AI_B]"},
        {"code": "AI_C", "label": "Productivity SaaS", "url": "[AFFILIATE_AI_C]", "landing_slot": "[LANDING_AI_C]"},
    ],
    "default": [
        {"code": "GEN_A", "label": "Primary Offer", "url": "[AFFILIATE_GENERAL_A]", "landing_slot": "[LANDING_GENERAL_A]"},
        {"code": "GEN_B", "label": "Secondary Offer", "url": "[AFFILIATE_GENERAL_B]", "landing_slot": "[LANDING_GENERAL_B]"},
    ],
}


def _resolve_offer_runtime_values(offer: Dict[str, str]) -> Dict[str, str]:
    """
    Replace placeholder offer URLs with configured runtime values from config/env.
    """
    resolved = dict(offer or {})
    code = str(resolved.get("code", "") or "").strip().upper()
    if not code:
        return resolved

    url_overrides = config.app.get("offer_url_overrides", {}) or {}
    landing_overrides = config.app.get("offer_landing_overrides", {}) or {}

    env_url = os.environ.get(f"OFFER_URL_{code}", "").strip()
    env_landing = os.environ.get(f"OFFER_LANDING_{code}", "").strip()

    cfg_url = str(url_overrides.get(code, "") or "").strip() if isinstance(url_overrides, dict) else ""
    cfg_landing = str(landing_overrides.get(code, "") or "").strip() if isinstance(landing_overrides, dict) else ""

    if env_url:
        resolved["url"] = env_url
    elif cfg_url:
        resolved["url"] = cfg_url

    if env_landing:
        resolved["landing_slot"] = env_landing
    elif cfg_landing:
        resolved["landing_slot"] = cfg_landing

    return resolved


def _winner_runtime_config(
    min_impressions: int | None = None,
    min_lift_ratio: float | None = None,
    promote_share: float | None = None,
) -> Dict[str, float]:
    cfg_impressions = int(config.app.get("offer_winner_min_impressions", 50) or 50)
    cfg_lift_ratio = float(config.app.get("offer_winner_min_lift_ratio", 0.15) or 0.15)
    cfg_promote_share = float(config.app.get("offer_winner_promote_share", 0.75) or 0.75)

    final_impressions = int(min_impressions) if min_impressions is not None else cfg_impressions
    final_lift_ratio = float(min_lift_ratio) if min_lift_ratio is not None else cfg_lift_ratio
    final_promote_share = float(promote_share) if promote_share is not None else cfg_promote_share

    final_impressions = max(1, final_impressions)
    final_lift_ratio = max(0.0, final_lift_ratio)
    final_promote_share = max(0.0, min(1.0, final_promote_share))

    return {
        "min_impressions": final_impressions,
        "min_lift_ratio": final_lift_ratio,
        "promote_share": final_promote_share,
    }


def detect_offer_winner(
    db: Session,
    niche: str,
    min_impressions: int | None = None,
    min_lift_ratio: float | None = None,
) -> Dict[str, Any]:
    """
    Detect the best offer in a niche and require clear statistical lift.
    """
    runtime_cfg = _winner_runtime_config(
        min_impressions=min_impressions,
        min_lift_ratio=min_lift_ratio,
    )
    min_impressions = int(runtime_cfg["min_impressions"])
    min_lift_ratio = float(runtime_cfg["min_lift_ratio"])

    rows = db.query(OfferRotationStat).filter(OfferRotationStat.niche == niche).all()
    if len(rows) < 2:
        # Fallback from revenue tags when rotation stats are sparse/incomplete
        fallback = {}
        tag_rows = db.query(RevenueTag).filter(RevenueTag.niche == niche).all()
        for t in tag_rows:
            code = t.offer_id or t.offer_used
            if not code:
                continue
            x = fallback.setdefault(
                code,
                {
                    "offer_code": code,
                    "offer_label": code,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "revenue_generated": 0.0,
                    "conversion_rate": 0.0,
                },
            )
            x["impressions"] += 1
            x["clicks"] += int(t.click_count or 0)
            x["conversions"] += int(t.conversion_count or 0)
            x["revenue_generated"] += float(t.revenue_generated or 0.0)
        rows = []
        for code, x in fallback.items():
            row = OfferRotationStat(
                niche=niche,
                offer_code=code,
                offer_label=x["offer_label"],
                impressions=x["impressions"],
                clicks=x["clicks"],
                conversions=x["conversions"],
                conversion_rate=(x["conversions"] / x["clicks"]) if x["clicks"] > 0 else 0.0,
                revenue_generated=x["revenue_generated"],
            )
            rows.append(row)
        if len(rows) < 2:
            return {"has_winner": False, "reason": "not_enough_offers"}

    scored = []
    for r in rows:
        impressions = int(r.impressions or 0)
        if impressions <= 0:
            continue
        ctr = float(r.clicks or 0) / float(impressions)
        cvr = float(r.conversion_rate or 0.0)
        rpi = float(r.revenue_generated or 0.0) / float(impressions)
        score = ctr * 0.25 + cvr * 0.35 + rpi * 0.40
        scored.append(
            {
                "offer_code": r.offer_code,
                "offer_label": r.offer_label,
                "impressions": impressions,
                "score": score,
            }
        )

    if len(scored) < 2:
        return {"has_winner": False, "reason": "insufficient_valid_stats"}

    scored.sort(key=lambda x: x["score"], reverse=True)
    best = scored[0]
    second = scored[1]
    if best["impressions"] < min_impressions:
        return {"has_winner": False, "reason": "not_enough_impressions", "leader": best}

    base = max(second["score"], 1e-9)
    lift = (best["score"] - second["score"]) / base
    if lift < min_lift_ratio:
        return {"has_winner": False, "reason": "lift_too_small", "leader": best, "runner_up": second}

    return {
        "has_winner": True,
        "winner": best,
        "runner_up": second,
        "lift_ratio": lift,
    }


def score_topic_intent(topic: str, niche: str) -> float:
    t = (topic or "").lower()
    if not t:
        return 0.0

    niche_terms = BUYER_INTENT_TERMS.get(niche, []) + BUYER_INTENT_TERMS["general"]
    score = 0.0
    for term in niche_terms:
        if term in t:
            score += 8.0

    if any(x in t for x in ["why", "how to", "mistake", "avoid", "stuck", "debt"]):
        score += 15.0
    if any(x in t for x in ["quote", "motivation", "inspiration"]):
        score -= 12.0
    if len(t.split()) >= 7:
        score += 6.0

    return max(0.0, min(100.0, score))


def prioritize_topics_by_intent(scored_topics: List[Dict[str, Any]], niche: str, min_intent: float = 30.0) -> List[Dict[str, Any]]:
    ranked = []
    for item in scored_topics:
        topic = item.get("topic", "")
        intent = score_topic_intent(topic, niche)
        combined = float(item.get("score", 50.0)) * 0.55 + intent * 0.45
        if intent < min_intent:
            continue
        x = dict(item)
        x["intent_score"] = round(intent, 2)
        x["revenue_topic_score"] = round(combined, 2)
        ranked.append(x)
    ranked.sort(key=lambda i: i.get("revenue_topic_score", 0.0), reverse=True)
    return ranked


def build_buyer_intent_hook(topic: str, niche: str) -> str:
    if niche == "finance":
        return f"If you're trying to build wealth in your 20s, this is for you: {topic}"
    if niche == "health":
        return f"If you're trying to improve your health without wasting money, watch this: {topic}"
    if niche == "ai_technology":
        return f"If you want to save hours every week using AI, start here: {topic}"
    return f"If you're trying to solve this fast, watch: {topic}"


def choose_offer_for_niche(db: Session, niche: str, explore_rate: float = 0.2) -> Dict[str, str]:
    offers = OFFER_CATALOG.get(niche, OFFER_CATALOG["default"])
    runtime_cfg = _winner_runtime_config()

    winner_eval = detect_offer_winner(
        db=db,
        niche=niche,
        min_impressions=int(runtime_cfg["min_impressions"]),
        min_lift_ratio=float(runtime_cfg["min_lift_ratio"]),
    )
    if winner_eval.get("has_winner"):
        winner_code = winner_eval["winner"]["offer_code"]
        winner_offer = next((o for o in offers if o["code"] == winner_code), None)
        if winner_offer and random.random() < float(runtime_cfg["promote_share"]):
            return _resolve_offer_runtime_values(winner_offer)

    # Explore randomly sometimes
    if random.random() < explore_rate:
        return _resolve_offer_runtime_values(random.choice(offers))

    scored = []
    for offer in offers:
        stat = db.query(OfferRotationStat).filter(
            OfferRotationStat.niche == niche,
            OfferRotationStat.offer_code == offer["code"],
        ).first()
        if not stat or stat.impressions < 10:
            # cold-start preference
            score = 1.0
        else:
            ctr = float(stat.clicks) / float(stat.impressions or 1)
            cvr = float(stat.conversion_rate or 0.0)
            rpi = float(stat.revenue_generated) / float(stat.impressions or 1)
            score = ctr * 0.25 + cvr * 0.35 + rpi * 0.40
        scored.append((score, offer))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[0][1] if scored else random.choice(offers)
    return _resolve_offer_runtime_values(selected)


def record_offer_impression(db: Session, niche: str, offer: Dict[str, str]) -> None:
    row = db.query(OfferRotationStat).filter(
        OfferRotationStat.niche == niche,
        OfferRotationStat.offer_code == offer["code"],
    ).first()
    if not row:
        row = OfferRotationStat(
            niche=niche,
            offer_code=offer["code"],
            offer_label=offer.get("label", ""),
            impressions=1,
        )
        db.add(row)
    else:
        row.impressions = int(row.impressions or 0) + 1
    db.commit()


def update_video_revenue_metrics(
    db: Session,
    tag_id: str = "",
    job_id: str = "",
    youtube_video_id: str = "",
    clicks: int = 0,
    conversions: int = 0,
    views: int = 0,
    revenue_generated: float = 0.0,
) -> Dict[str, Any]:
    query = db.query(RevenueTag)
    if tag_id:
        tag = query.filter(RevenueTag.id == tag_id).first()
    elif job_id:
        tag = query.filter(RevenueTag.job_id == job_id).first()
    elif youtube_video_id:
        tag = query.filter(RevenueTag.youtube_video_id == youtube_video_id).first()
    else:
        return {"success": False, "message": "No selector provided"}

    if not tag:
        return {"success": False, "message": "Revenue tag not found"}

    old_clicks = int(tag.click_count or 0)
    old_revenue = float(tag.revenue_generated or 0.0)

    tag.click_count = max(0, int(clicks))
    tag.conversion_count = max(0, int(conversions))
    tag.views_count = max(0, int(views))
    tag.revenue_generated = max(0.0, float(revenue_generated))
    tag.estimated_revenue = tag.revenue_generated
    tag.conversion_rate = (float(tag.conversion_count) / float(tag.click_count)) if tag.click_count > 0 else 0.0
    tag.epmv = (tag.revenue_generated / max(tag.views_count, 1)) * 1000.0 if tag.views_count > 0 else 0.0
    tag.updated_at = datetime.utcnow()
    db.commit()

    delta_clicks = int(tag.click_count - old_clicks)
    delta_revenue = float(tag.revenue_generated - old_revenue)

    stat = db.query(OfferRotationStat).filter(
        OfferRotationStat.niche == tag.niche,
        OfferRotationStat.offer_code == (tag.offer_id or tag.offer_used),
    ).first()
    if stat:
        stat.clicks = max(0, int(stat.clicks or 0) + delta_clicks)
        stat.conversions = max(0, int(stat.conversions or 0) + int(conversions))
        stat.revenue_generated = max(0.0, float(stat.revenue_generated or 0.0) + delta_revenue)
        stat.conversion_rate = (float(stat.conversions) / float(stat.clicks)) if stat.clicks > 0 else 0.0
        stat.updated_at = datetime.utcnow()
        db.commit()

    return {
        "success": True,
        "tag_id": tag.id,
        "epmv": round(float(tag.epmv or 0.0), 4),
        "click_count": int(tag.click_count or 0),
        "conversion_count": int(tag.conversion_count or 0),
        "conversion_rate": round(float(tag.conversion_rate or 0.0), 4),
        "views_count": int(tag.views_count or 0),
        "revenue_generated": round(float(tag.revenue_generated or 0.0), 4),
    }


def compute_epmv_summary(db: Session, days: int = 60) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=max(1, int(days)))
    rows = db.query(RevenueTag).filter(RevenueTag.created_at >= since).all()
    total_views = sum(int(r.views_count or 0) for r in rows)
    total_revenue = sum(float(r.revenue_generated or 0.0) for r in rows)
    epmv = (total_revenue / total_views) * 1000.0 if total_views > 0 else 0.0
    return {
        "days": int(days),
        "videos": len(rows),
        "total_views": total_views,
        "total_revenue": round(total_revenue, 4),
        "epmv": round(epmv, 4),
    }


def niche_profitability(db: Session, days: int = 60) -> List[Dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=max(1, int(days)))
    rows = db.query(RevenueTag).filter(RevenueTag.created_at >= since).all()
    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = r.niche or "unknown"
        x = agg.setdefault(k, {"niche": k, "videos": 0, "views": 0, "revenue": 0.0})
        x["videos"] += 1
        x["views"] += int(r.views_count or 0)
        x["revenue"] += float(r.revenue_generated or 0.0)
    result = []
    for k, x in agg.items():
        epmv = (x["revenue"] / x["views"]) * 1000.0 if x["views"] > 0 else 0.0
        item = dict(x)
        item["revenue"] = round(item["revenue"], 4)
        item["epmv"] = round(epmv, 4)
        result.append(item)
    result.sort(key=lambda i: i["epmv"], reverse=True)
    return result


def offer_profitability(db: Session, days: int = 60) -> List[Dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=max(1, int(days)))
    rows = db.query(RevenueTag).filter(RevenueTag.created_at >= since).all()
    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = r.offer_id or r.offer_used or "unknown_offer"
        x = agg.setdefault(
            k,
            {
                "offer_id": k,
                "videos": 0,
                "clicks": 0,
                "conversions": 0,
                "views": 0,
                "revenue": 0.0,
            },
        )
        x["videos"] += 1
        x["clicks"] += int(r.click_count or 0)
        x["conversions"] += int(r.conversion_count or 0)
        x["views"] += int(r.views_count or 0)
        x["revenue"] += float(r.revenue_generated or 0.0)

    result = []
    for _, x in agg.items():
        ctr = (x["clicks"] / x["views"]) if x["views"] > 0 else 0.0
        cvr = (x["conversions"] / x["clicks"]) if x["clicks"] > 0 else 0.0
        epmv = (x["revenue"] / x["views"]) * 1000.0 if x["views"] > 0 else 0.0
        item = dict(x)
        item["ctr"] = round(ctr, 4)
        item["conversion_rate"] = round(cvr, 4)
        item["epmv"] = round(epmv, 4)
        item["revenue"] = round(item["revenue"], 4)
        result.append(item)
    result.sort(key=lambda i: i["epmv"], reverse=True)
    return result
