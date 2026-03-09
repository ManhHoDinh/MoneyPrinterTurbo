#!/usr/bin/env python3
"""
Backfill revenue_tags from existing jobs and upload history.

This connects older uploads to the revenue dashboard even before
external click/conversion data is ingested.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.db.engine import SessionLocal, init_db
from app.db.models import RevenueTag, UploadHistory, VideoJob


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        jobs = db.query(VideoJob).all()
        uploads = db.query(UploadHistory).all()
        uploads_by_job = {u.job_id: u for u in uploads}

        created = 0
        updated = 0

        for job in jobs:
            existing = db.query(RevenueTag).filter(RevenueTag.job_id == job.id).first()
            upload = uploads_by_job.get(job.id)
            niche = job.channel.niche_type if job.channel else ""

            if not existing:
                tag = RevenueTag(
                    job_id=job.id,
                    channel_id=job.channel_id,
                    niche=niche,
                    topic=job.topic or "",
                    youtube_video_id=(upload.youtube_video_id if upload else ""),
                    offer_id="",
                    offer_used="",
                    offer_url="",
                    click_count=0,
                    conversion_count=0,
                    conversion_rate=0.0,
                    views_count=0,
                    revenue_generated=0.0,
                    estimated_revenue=0.0,
                    epmv=0.0,
                    upload_time=(upload.uploaded_at if upload else None),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(tag)
                created += 1
            else:
                changed = False
                if upload and not existing.youtube_video_id:
                    existing.youtube_video_id = upload.youtube_video_id or ""
                    changed = True
                if upload and not existing.upload_time:
                    existing.upload_time = upload.uploaded_at
                    changed = True
                if not existing.niche:
                    existing.niche = niche
                    changed = True
                if changed:
                    existing.updated_at = datetime.utcnow()
                    updated += 1

        db.commit()
        print(json.dumps({
            "success": True,
            "jobs": len(jobs),
            "uploads": len(uploads),
            "created": created,
            "updated": updated,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
