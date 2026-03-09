"""
Persistence for monetization performance tracking.
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.db.models import MonetizationEvent, VideoJob, RevenueTag
from app.services.revenue_optimization import record_offer_impression


def record_monetization_event(
    db: Session,
    job: VideoJob,
    upload_result: Dict[str, Any],
    monetization_meta: Any,
    revenue_profile: Dict[str, Any],
) -> MonetizationEvent:
    affiliate_link = ""
    lead_magnet_link = ""
    cta_tag = ""

    if monetization_meta is not None:
        affiliate_link = str(getattr(monetization_meta, "monetization_link_used", "") or "")
        lead_magnet_link = str(getattr(monetization_meta, "lead_magnet_slot", "") or "")
        cta_tag = str(getattr(monetization_meta, "cta_tag", "") or "")

    youtube_video_id = str(upload_result.get("video_id", "") or "")
    event = MonetizationEvent(
        job_id=job.id,
        channel_id=job.channel_id,
        niche=(job.channel.niche_type if job.channel else ""),
        video_topic=job.topic or "",
        youtube_video_id=youtube_video_id,
        monetization_link_used=affiliate_link,
        lead_magnet_link=lead_magnet_link,
        cta_tag=cta_tag,
        uploaded_at=datetime.utcnow(),
        revenue_priority_score=float(revenue_profile.get("revenue_priority_score", 0.0) or 0.0),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    revenue_tag = db.query(RevenueTag).filter(RevenueTag.job_id == job.id).first()
    if not revenue_tag:
        revenue_tag = RevenueTag(
            job_id=job.id,
            channel_id=job.channel_id,
            niche=(job.channel.niche_type if job.channel else ""),
            topic=job.topic or "",
            youtube_video_id=youtube_video_id,
            offer_id=str(getattr(monetization_meta, "offer_code", "") or ""),
            offer_used=affiliate_link,
            offer_url=affiliate_link,
            click_count=0,
            views_count=0,
            revenue_generated=0.0,
            epmv=0.0,
            upload_time=datetime.utcnow(),
        )
        db.add(revenue_tag)
    else:
        revenue_tag.youtube_video_id = youtube_video_id
        revenue_tag.offer_id = str(getattr(monetization_meta, "offer_code", "") or "")
        revenue_tag.offer_used = affiliate_link
        revenue_tag.offer_url = affiliate_link
        revenue_tag.upload_time = datetime.utcnow()
    db.commit()

    record_offer_impression(
        db,
        niche=(job.channel.niche_type if job.channel else "default"),
        offer={
            "code": str(getattr(monetization_meta, "offer_code", "GEN_A") or "GEN_A"),
            "label": str(getattr(monetization_meta, "offer_label", "Offer") or "Offer"),
            "url": affiliate_link or "[AFFILIATE_LINK]",
        },
    )

    return event
