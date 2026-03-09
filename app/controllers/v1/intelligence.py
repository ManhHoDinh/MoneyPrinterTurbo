"""
Intelligence Controller — API endpoints for EXTREME MODE intelligence systems.

Exposes:
  - Topic intelligence (scoring, pool generation)
  - Retention simulation
  - Content genome queries
  - Quality filter checks
"""

from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Query, Body, Depends
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.db.engine import get_db
from app.db.models import Channel, UploadHistory, RevenueTag

router = APIRouter(
    prefix="/api/v1/intelligence",
    tags=["Intelligence"],
)


# ── Trend Intelligence ───────────────────────────────────────────────────────

@router.post("/topics/generate")
def generate_topics(
    niche: str = Body("psychology"),
    count: int = Body(20),
    min_score: float = Body(40.0),
):
    """Generate a scored topic pool with multi-signal ranking."""
    from app.services.trend_intelligence import generate_scored_topics
    topics = generate_scored_topics(niche=niche, count=count, min_score=min_score)
    return {
        "count": len(topics),
        "topics": [t.to_dict() for t in topics],
    }


@router.post("/topics/score")
def score_single_topic(topic: str = Body(...), niche: str = Body("")):
    """Score a single topic across novelty, emotion, and curiosity."""
    from app.services.trend_intelligence import score_topic
    result = score_topic(topic, niche=niche)
    return result.to_dict()


@router.post("/topics/distribute")
def distribute_topics(
    niche: str = Body("psychology"),
    count: int = Body(20),
    channel_ids: List[str] = Body(...),
):
    """Generate topics and distribute across channels."""
    from app.services.trend_intelligence import generate_scored_topics, distribute_to_channels
    topics = generate_scored_topics(niche=niche, count=count)
    assignment = distribute_to_channels(topics, channel_ids)
    return {
        channel_id: [t.to_dict() for t in assigned]
        for channel_id, assigned in assignment.items()
    }


# ── Retention Simulator ──────────────────────────────────────────────────────

@router.post("/retention/simulate")
def simulate_retention_endpoint(
    script: str = Body(...),
    style: str = Body(""),
    threshold: float = Body(55.0),
):
    """Predict audience retention curve for a script."""
    from app.services.retention_simulator import simulate_retention
    result = simulate_retention(script, style=style, threshold=threshold)
    return result.to_dict()


@router.post("/retention/batch-filter")
def batch_filter_scripts(
    scripts: List[Dict[str, str]] = Body(...),
    threshold: float = Body(55.0),
):
    """Filter a batch of scripts, returning only those that pass retention."""
    from app.services.retention_simulator import batch_filter
    return batch_filter(scripts, threshold=threshold)


# ── Content Genome ───────────────────────────────────────────────────────────

@router.get("/genome/stats")
def genome_stats():
    """Get aggregate statistics from the content genome store."""
    from app.services.content_genome import GenomeStore
    store = GenomeStore()
    return store.get_stats()


@router.get("/genome/{job_id}")
def get_genome(job_id: str):
    """Get the full content genome for a specific job."""
    from app.services.content_genome import GenomeStore
    store = GenomeStore()
    genome = store.load(job_id)
    if not genome:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Genome not found")
    return genome.to_dict()


@router.get("/genome")
def query_genomes(
    niche: str = Query(""),
    channel_id: str = Query(""),
    min_score: float = Query(0.0),
    limit: int = Query(50),
):
    """Query content genomes with filters."""
    from app.services.content_genome import GenomeStore
    store = GenomeStore()
    genomes = store.query(niche=niche, channel_id=channel_id, min_score=min_score, limit=limit)
    return {
        "count": len(genomes),
        "genomes": [g.to_dict() for g in genomes],
    }


# ── Quality Filter ───────────────────────────────────────────────────────────

@router.post("/quality/check")
def quality_check(
    job_id: str = Body(""),
    video_path: str = Body(""),
    script: str = Body(""),
    style: str = Body(""),
):
    """Run the full quality gate on a video before upload."""
    from app.services.quality_filter import quality_gate
    return quality_gate(job_id=job_id, video_path=video_path, script=script, style=style)


# ── Style Mutation Preview ───────────────────────────────────────────────────

@router.get("/mutation/preview")
def preview_mutations(
    style: str = Query("dark_psychology"),
    intensity: float = Query(None),
):
    """Preview style mutations for a given style."""
    from app.services.style_mutation import preview_mutation
    return preview_mutation(style=style, intensity=intensity)


# ── Niche Intelligence ───────────────────────────────────────────────────────

@router.get("/niches/discover")
def discover_niches(
    count: int = Query(10),
    min_score: float = Query(0.0),
    sort_by: str = Query("composite_score"),
):
    """Discover and rank niches by business viability."""
    from app.services.niche_intelligence import discover_niches as _discover
    niches = _discover(count=count, min_score=min_score, sort_by=sort_by)
    return {"count": len(niches), "niches": [n.to_dict() for n in niches]}


@router.get("/niches/score/{niche_key}")
def score_niche_endpoint(niche_key: str):
    """Score a specific niche across viral, monetization, and emotion."""
    from app.services.niche_intelligence import score_niche
    return score_niche(niche_key).to_dict()


@router.get("/niches/portfolio")
def recommend_portfolio(
    channel_count: int = Query(3),
    strategy: str = Query("balanced"),
):
    """Recommend a multi-channel portfolio strategy."""
    from app.services.niche_intelligence import recommend_channel_portfolio
    return {"strategy": strategy, "portfolio": recommend_channel_portfolio(channel_count, strategy)}


# ── Monetization ─────────────────────────────────────────────────────────────

@router.post("/monetization/generate")
def generate_monetization(
    topic: str = Body(...),
    niche: str = Body("dark_psychology"),
    style: str = Body(""),
    channel_name: str = Body(""),
):
    """Generate monetization-optimized upload metadata for a video."""
    from app.services.monetization import generate_monetization_metadata
    meta = generate_monetization_metadata(
        topic=topic, niche=niche, style=style, channel_name=channel_name
    )
    return meta.to_dict()


@router.post("/monetization/batch")
def batch_monetization(items: List[Dict[str, str]] = Body(...)):
    """Generate metadata for a batch of videos."""
    from app.services.monetization import batch_generate_metadata
    return {"results": batch_generate_metadata(items)}


@router.post("/revenue/update")
def update_revenue_metrics(
    tag_id: str = Body(""),
    job_id: str = Body(""),
    youtube_video_id: str = Body(""),
    clicks: int = Body(0),
    conversions: int = Body(0),
    views: int = Body(0),
    revenue_generated: float = Body(0.0),
    db: Session = Depends(get_db),
):
    """
    Update per-video revenue tagging metrics.
    Stores: topic, niche, offer_used, click_count, revenue_generated, EPMV.
    """
    from app.services.revenue_optimization import update_video_revenue_metrics
    return update_video_revenue_metrics(
        db=db,
        tag_id=tag_id,
        job_id=job_id,
        youtube_video_id=youtube_video_id,
        clicks=clicks,
        conversions=conversions,
        views=views,
        revenue_generated=revenue_generated,
    )


@router.get("/revenue/epmv")
def get_epmv(days: int = Query(60), db: Session = Depends(get_db)):
    """Get overall EPMV summary."""
    from app.services.revenue_optimization import compute_epmv_summary
    return compute_epmv_summary(db, days=days)


@router.get("/revenue/niches")
def get_revenue_niche_profitability(days: int = Query(60), db: Session = Depends(get_db)):
    """Rank niches by EPMV (profitability)."""
    from app.services.revenue_optimization import niche_profitability
    rows = niche_profitability(db, days=days)
    return {"count": len(rows), "items": rows}


@router.get("/revenue/offers")
def get_offer_profitability(days: int = Query(60), db: Session = Depends(get_db)):
    """Rank offers by revenue efficiency."""
    from app.services.revenue_optimization import offer_profitability
    rows = offer_profitability(db, days=days)
    return {"count": len(rows), "items": rows}


@router.get("/revenue/dashboard")
def get_revenue_dashboard(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """Dashboard snapshot from actual upload and revenue records."""
    since = datetime.utcnow() - timedelta(days=max(1, int(days)))

    channels = db.query(Channel).all()
    uploads = db.query(UploadHistory).filter(UploadHistory.uploaded_at >= since).all()
    revenue_tags = db.query(RevenueTag).filter(RevenueTag.created_at >= since).all()

    uploads_by_channel: Dict[str, List[UploadHistory]] = {}
    for row in uploads:
        uploads_by_channel.setdefault(row.channel_id, []).append(row)

    revenue_by_channel: Dict[str, List[RevenueTag]] = {}
    for row in revenue_tags:
        revenue_by_channel.setdefault(row.channel_id, []).append(row)

    channel_rows: List[Dict[str, Any]] = []
    total_revenue = 0.0
    total_views = 0
    total_clicks = 0
    total_conversions = 0
    total_uploads = 0
    total_platform_uploads = {"youtube": 0, "tiktok": 0, "instagram": 0, "facebook": 0}
    total_platform_uploads_all: Dict[str, int] = {}

    for ch in channels:
        ch_uploads = uploads_by_channel.get(ch.id, [])
        ch_tags = revenue_by_channel.get(ch.id, [])

        views = sum(int(x.views_count or 0) for x in ch_tags)
        revenue = sum(float(x.revenue_generated or 0.0) for x in ch_tags)
        clicks = sum(int(x.click_count or 0) for x in ch_tags)
        conversions = sum(int(x.conversion_count or 0) for x in ch_tags)
        youtube_uploads = sum(1 for x in ch_uploads if x.youtube_video_id)
        tiktok_uploads = sum(1 for x in ch_uploads if x.tiktok_video_id)
        instagram_uploads = sum(1 for x in ch_uploads if x.ig_video_id)
        facebook_uploads = sum(1 for x in ch_uploads if x.fb_video_id)
        extra_platform_uploads: Dict[str, int] = {}
        for x in ch_uploads:
            raw = getattr(x, "platform_results_json", "") or ""
            if not raw:
                continue
            try:
                results = json.loads(raw)
            except Exception:
                continue
            if not isinstance(results, dict):
                continue
            for platform, info in results.items():
                if isinstance(info, dict) and not info.get("success", False):
                    continue
                p = str(platform or "").strip().lower()
                if not p:
                    continue
                extra_platform_uploads[p] = extra_platform_uploads.get(p, 0) + 1
        upload_count = len(ch_uploads)

        epmv = (revenue / views) * 1000.0 if views > 0 else 0.0
        ctr = (clicks / views) if views > 0 else 0.0
        conversion_rate = (conversions / clicks) if clicks > 0 else 0.0
        monthly_projection = (revenue / float(days)) * 30.0

        total_revenue += revenue
        total_views += views
        total_clicks += clicks
        total_conversions += conversions
        total_uploads += upload_count
        total_platform_uploads["youtube"] += youtube_uploads
        total_platform_uploads["tiktok"] += tiktok_uploads
        total_platform_uploads["instagram"] += instagram_uploads
        total_platform_uploads["facebook"] += facebook_uploads
        for p, c in extra_platform_uploads.items():
            total_platform_uploads_all[p] = total_platform_uploads_all.get(p, 0) + int(c)

        channel_rows.append({
            "channel_id": ch.id,
            "channel_name": ch.name,
            "niche": ch.niche_type,
            "is_active": bool(ch.is_active),
            "uploads": upload_count,
            "youtube_uploads": youtube_uploads,
            "tiktok_uploads": tiktok_uploads,
            "instagram_uploads": instagram_uploads,
            "facebook_uploads": facebook_uploads,
            "platform_uploads_all": extra_platform_uploads,
            "views": views,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": round(revenue, 4),
            "epmv": round(epmv, 4),
            "ctr": round(ctr, 4),
            "conversion_rate": round(conversion_rate, 4),
            "monthly_projection": round(monthly_projection, 2),
        })

    channel_rows.sort(key=lambda item: item.get("revenue", 0.0), reverse=True)

    return {
        "days": int(days),
        "summary": {
            "channels_total": len(channels),
            "channels_active": sum(1 for ch in channels if ch.is_active),
            "revenue_events_total": len(revenue_tags),
            "revenue_tagged_channels": len({row.channel_id for row in revenue_tags if row.channel_id}),
            "uploads_total": total_uploads,
            "views_total": total_views,
            "clicks_total": total_clicks,
            "conversions_total": total_conversions,
            "revenue_total": round(total_revenue, 4),
            "epmv": round((total_revenue / total_views) * 1000.0, 4) if total_views > 0 else 0.0,
            "ctr": round((total_clicks / total_views), 4) if total_views > 0 else 0.0,
            "conversion_rate": round((total_conversions / total_clicks), 4) if total_clicks > 0 else 0.0,
            "monthly_projection": round((total_revenue / float(days)) * 30.0, 2),
            "platform_uploads": total_platform_uploads,
            "platform_uploads_all": total_platform_uploads_all,
        },
        "channels": channel_rows,
    }


@router.get("/revenue/winner")
def get_offer_winner(
    niche: str = Query("finance"),
    min_impressions: Optional[int] = Query(None),
    min_lift_ratio: Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    """Get auto-promote winner decision for a niche."""
    from app.services.revenue_optimization import detect_offer_winner
    return detect_offer_winner(
        db=db,
        niche=niche,
        min_impressions=min_impressions,
        min_lift_ratio=min_lift_ratio,
    )


@router.get("/revenue/offer-map")
def get_offer_map(niche: str = Query("default")):
    """Show mapped affiliate offers for a niche."""
    from app.services.revenue_optimization import OFFER_CATALOG
    return {
        "niche": niche,
        "offers": OFFER_CATALOG.get(niche, OFFER_CATALOG.get("default", [])),
    }


@router.post("/revenue/intent-score")
def score_intent(topic: str = Body(...), niche: str = Body("finance")):
    """Score buyer intent for a topic."""
    from app.services.revenue_optimization import score_topic_intent, build_buyer_intent_hook
    return {
        "topic": topic,
        "niche": niche,
        "intent_score": score_topic_intent(topic, niche),
        "buyer_intent_hook": build_buyer_intent_hook(topic, niche),
    }


# ── Evolution Engine ─────────────────────────────────────────────────────────

@router.get("/evolution/run")
def run_evolution(channel_id: str = Query(""), niche: str = Query("")):
    """Run a full evolution cycle and get optimization insights."""
    from app.services.evolution_engine import EvolutionEngine
    engine = EvolutionEngine()
    state = engine.evolve(channel_id=channel_id, niche=niche)
    return state.to_dict()


@router.get("/evolution/topic-bias")
def get_topic_bias(channel_id: str = Query(""), niche: str = Query("")):
    """Get topic selection bias from past performance."""
    from app.services.evolution_engine import EvolutionEngine
    engine = EvolutionEngine()
    return engine.get_topic_bias(niche=niche, channel_id=channel_id)


@router.get("/evolution/hook-preference")
def get_hook_preference(channel_id: str = Query("")):
    """Get preferred hook type distribution from genome data."""
    from app.services.evolution_engine import EvolutionEngine
    engine = EvolutionEngine()
    return engine.get_hook_preference(channel_id=channel_id)


# ── Resource Optimizer ───────────────────────────────────────────────────────

@router.post("/resources/allocate")
def allocate_resources(
    channel_ids: List[str] = Body(...),
    total_slots: int = Body(20),
):
    """Allocate worker slots across channels based on performance."""
    from app.services.resource_optimizer import ResourceOptimizer
    optimizer = ResourceOptimizer()
    plan = optimizer.allocate(channel_ids=channel_ids, total_slots=total_slots)
    return plan.to_dict()


@router.post("/resources/priority")
def channel_priority(channel_ids: List[str] = Body(...)):
    """Rank channels by generation priority."""
    from app.services.resource_optimizer import ResourceOptimizer
    optimizer = ResourceOptimizer()
    return {"priority": optimizer.get_channel_priority(channel_ids)}


# ── Channel Autopilot ────────────────────────────────────────────────────────

@router.post("/autopilot/create-channel")
def auto_create_channel(niche: str = Body(""), force_name: str = Body("")):
    """Auto-generate a channel identity for a niche."""
    from app.services.channel_autopilot import ChannelAutopilot
    pilot = ChannelAutopilot()
    identity = pilot.auto_create_channel(niche=niche, force_name=force_name)
    return identity.to_dict()


@router.post("/autopilot/create-fleet")
def auto_create_fleet(count: int = Body(3), strategy: str = Body("balanced")):
    """Create a fleet of differentiated channels."""
    from app.services.channel_autopilot import ChannelAutopilot
    pilot = ChannelAutopilot()
    fleet = pilot.auto_create_fleet(count=count, strategy=strategy)
    return {"count": len(fleet), "channels": [i.to_dict() for i in fleet]}


@router.post("/autopilot/health-check")
def fleet_health_check(channel_ids: List[str] = Body(...)):
    """Assess health of all channels in the fleet."""
    from app.services.channel_autopilot import ChannelAutopilot
    pilot = ChannelAutopilot()
    results = pilot.health_check(channel_ids)
    return {"channels": [h.to_dict() for h in results]}


@router.post("/autopilot/auto-kill")
def auto_kill_channels(channel_ids: List[str] = Body(...)):
    """Evaluate channels and take lifecycle actions (boost/maintain/reduce/kill)."""
    from app.services.channel_autopilot import ChannelAutopilot
    pilot = ChannelAutopilot()
    actions = pilot.auto_kill(channel_ids)
    return {"actions": [a.to_dict() for a in actions]}


@router.get("/autopilot/opportunities")
def detect_opportunities(count: int = Query(5)):
    """Detect emerging niche opportunities."""
    from app.services.channel_autopilot import ChannelAutopilot
    pilot = ChannelAutopilot()
    return {"opportunities": pilot.detect_opportunities(count)}


# ── Network Config ───────────────────────────────────────────────────────────

@router.get("/network/summary")
def network_summary():
    """Get US HIGH CPM network configuration summary."""
    from app.services.network_config import get_network_summary
    return get_network_summary()


@router.get("/network/tier/{tier}")
def get_network_tier(tier: int):
    """Get channels in a specific tier."""
    from app.services.network_config import get_tier
    channels = get_tier(tier)
    return {"tier": tier, "channels": [c.to_dict() for c in channels]}


@router.get("/network/quota")
def get_quota():
    """Get daily video production quota across the network."""
    from app.services.network_config import get_daily_quota
    return get_daily_quota()


# ── Analytics Hub ────────────────────────────────────────────────────────────

@router.get("/analytics/network")
def analytics_network():
    """Full network analytics report."""
    from app.services.analytics_hub import AnalyticsHub
    hub = AnalyticsHub()
    return hub.network_report().to_dict()


@router.get("/analytics/channel/{channel_id}")
def analytics_channel(channel_id: str):
    """Analytics for a single channel."""
    from app.services.analytics_hub import AnalyticsHub
    hub = AnalyticsHub()
    return hub.channel_report(channel_id).to_dict()


@router.get("/analytics/tiers")
def analytics_tiers():
    """Compare performance across network tiers."""
    from app.services.analytics_hub import AnalyticsHub
    hub = AnalyticsHub()
    return hub.compare_tiers()


# ── Master Orchestrator ──────────────────────────────────────────────────────

@router.post("/orchestrator/run-cycle")
def run_full_cycle():
    """Run a full production cycle for the entire network."""
    from app.services.orchestrator import Orchestrator
    orch = Orchestrator()
    report = orch.run_cycle()
    return report.to_dict()


@router.post("/orchestrator/run-channel")
def run_channel_pipeline(
    channel_id: str = Body("default"),
    niche: str = Body("dark_psychology"),
    style: str = Body("dark_psychology"),
    count: int = Body(3),
):
    """Run the pipeline for a single channel."""
    from app.services.orchestrator import Orchestrator
    orch = Orchestrator()
    items = orch.run_channel(channel_id=channel_id, niche=niche, style=style, count=count)
    return {
        "channel_id": channel_id,
        "count": len(items),
        "completed": sum(1 for i in items if i.stage == "complete"),
        "rejected": sum(1 for i in items if i.stage == "rejected"),
        "items": [i.to_dict() for i in items],
    }


@router.post("/orchestrator/dry-run")
def orchestrator_dry_run(
    niche: str = Body("dark_psychology"),
    count: int = Body(5),
):
    """Dry run — preview what would be generated without running the pipeline."""
    from app.services.orchestrator import Orchestrator
    orch = Orchestrator(dry_run_mode=True)
    preview = orch.dry_run(niche=niche, count=count)
    return {"count": len(preview), "preview": preview}


# ── System Health ────────────────────────────────────────────────────────────

@router.get("/health")
def system_health_status(db: Session = Depends(get_db)):
    """Get content farm system health and queue metrics."""
    from app.db.models import VideoJob, Channel
    from app.worker.celery_app import celery_app
    
    # DB Stats
    stats = {
        "channels": db.query(Channel).filter(Channel.is_active == True).count(),
        "jobs_pending": db.query(VideoJob).filter(VideoJob.status == "pending").count(),
        "jobs_active": db.query(VideoJob).filter(VideoJob.status.in_(["generating", "rendering", "uploading"])).count(),
        "jobs_completed": db.query(VideoJob).filter(VideoJob.status == "completed").count(),
        "jobs_failed": db.query(VideoJob).filter(VideoJob.status == "failed").count(),
    }
    
    # Minimal worker status (avoids blocking too long)
    worker_status = "unknown"
    try:
        i = celery_app.control.inspect()
        active = i.active()
        worker_status = "online" if active else "offline"
    except Exception:
        pass
        
    return {
        "status": "ok",
        "worker_status": worker_status,
        "metrics": stats
    }
