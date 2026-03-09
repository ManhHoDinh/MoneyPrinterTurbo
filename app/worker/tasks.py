"""
Celery worker tasks for the Content Farm Platform.

Tasks:
  - generate_video_task: Run the full video generation pipeline for a job
  - upload_video_task:   Upload a completed video to YouTube
  - run_scheduled_batch: Auto-generate a batch of videos for a channel
"""

import json
import os
import resource
import subprocess
import shutil
import time
import uuid
from datetime import datetime

from celery import states
from loguru import logger
import redis

from app.worker.celery_app import celery_app
from app.config import config
from app.db.engine import SessionLocal
from app.db.models import VideoJob, Channel, ScheduleConfig


def _capture_process_metrics() -> dict:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "cpu_seconds": float(usage.ru_utime + usage.ru_stime),
        "max_rss_mb": float(usage.ru_maxrss) / 1024.0,
    }


def _read_current_rss_mb() -> float:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return float(parts[1]) / 1024.0
    except Exception:
        pass
    return 0.0


def _queue_depth_metrics() -> dict:
    redis_host = config.app.get("redis_host", "localhost")
    redis_port = int(config.app.get("redis_port", 6379) or 6379)
    redis_db = int(config.app.get("redis_db", 0) or 0)
    redis_password = config.app.get("redis_password", "")
    queues = [
        str(config.app.get("render_queue_name", "render") or "render"),
        str(config.app.get("upload_queue_name", "upload") or "upload"),
        str(config.app.get("control_queue_name", "control") or "control"),
    ]
    metrics = {}
    try:
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password if redis_password else None,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=False,
        )
        for q in queues:
            metrics[f"queue_{q}_depth"] = int(client.llen(q))
        client.close()
    except Exception as e:
        logger.warning(f"[Health] queue depth read failed: {e}")
    return metrics


def _count_active_jobs_for_channel(db, channel_id: str) -> int:
    return db.query(VideoJob).filter(
        VideoJob.channel_id == channel_id,
        VideoJob.status.in_(["pending", "generating", "rendering", "uploading"]),
    ).count()


def _video_has_audio_stream(video_path: str) -> bool:
    if not video_path or not os.path.exists(video_path):
        return False
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return "audio" in (proc.stdout or "").lower()
    except Exception as e:
        logger.warning(f"[Worker] ffprobe audio validation failed: {e}")
        return False


def _clear_job_run_data(job: VideoJob) -> None:
    """
    Remove temporary task artifacts to free disk after successful upload.
    """
    task_folder = os.path.join("/MoneyPrinterTurbo/storage/tasks", job.id)
    try:
        if os.path.isdir(task_folder):
            shutil.rmtree(task_folder, ignore_errors=True)
    except Exception as e:
        logger.warning(f"[Worker] Failed to remove task folder {task_folder}: {e}")

    # Clear file references after cleanup
    job.video_path = ""
    job.task_id = ""

    # Clear in-memory/redis task state when available
    try:
        from app.services import state as sm
        sm.state.delete_task(job.id)
    except Exception:
        pass


def _cleanup_cache_videos(active_render_jobs: int) -> dict:
    """
    Cleanup storage/cache_videos by age and total size.
    Skips cleanup while rendering jobs are active.
    """
    result = {
        "enabled": bool(config.app.get("enable_cache_cleanup", True)),
        "skipped": False,
        "deleted_files": 0,
        "freed_bytes": 0,
    }
    if not result["enabled"]:
        result["skipped"] = True
        return result

    if active_render_jobs > 0:
        result["skipped"] = True
        return result

    cache_dir = "/MoneyPrinterTurbo/storage/cache_videos"
    if not os.path.isdir(cache_dir):
        result["skipped"] = True
        return result

    now_ts = datetime.utcnow().timestamp()
    max_age_days = int(config.app.get("cache_cleanup_days", 7) or 7)
    max_size_gb = float(config.app.get("cache_max_size_gb", 8) or 8)
    max_age_seconds = max_age_days * 24 * 3600
    size_limit_bytes = int(max_size_gb * (1024 ** 3))

    files = []
    total_size = 0
    for name in os.listdir(cache_dir):
        if not name.lower().endswith(".mp4"):
            continue
        file_path = os.path.join(cache_dir, name)
        try:
            st = os.stat(file_path)
            files.append((file_path, st.st_mtime, st.st_size))
            total_size += st.st_size
        except Exception:
            continue

    # 1) Remove files older than max_age_days
    for file_path, mtime, size in files:
        if now_ts - mtime > max_age_seconds:
            try:
                os.remove(file_path)
                result["deleted_files"] += 1
                result["freed_bytes"] += size
                total_size -= size
            except Exception:
                continue

    # Refresh list after age-based cleanup
    remaining = []
    for name in os.listdir(cache_dir):
        if not name.lower().endswith(".mp4"):
            continue
        file_path = os.path.join(cache_dir, name)
        try:
            st = os.stat(file_path)
            remaining.append((file_path, st.st_mtime, st.st_size))
        except Exception:
            continue

    # 2) If still above size cap, remove oldest files first
    if total_size > size_limit_bytes:
        remaining.sort(key=lambda x: x[1])  # oldest first
        for file_path, _mtime, size in remaining:
            if total_size <= size_limit_bytes:
                break
            try:
                os.remove(file_path)
                result["deleted_files"] += 1
                result["freed_bytes"] += size
                total_size -= size
            except Exception:
                continue

    return result


@celery_app.task(bind=True, name="generate_video_task", max_retries=3)
def generate_video_task(self, job_id: str):
    """
    Run the existing video generation pipeline for a specific job.

    Delegates to generator_wrapper â€” the existing pipeline is never touched.
    Updates job status through: generating â†’ rendering â†’ completed/failed
    """
    db = SessionLocal()
    start_wall = time.perf_counter()
    start_metrics = _capture_process_metrics()
    try:
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"status": "error", "message": "Job not found"}

        # Update to generating
        job.status = "generating"
        job.started_at = datetime.utcnow()
        job.task_id = self.request.id or str(uuid.uuid4())
        db.commit()

        from app.services.job_logger import job_log
        job_log(job_id, f"Job started â€” topic: {job.topic}", stage="init")
        logger.info(f"[Worker] Starting video generation for job [{job_id[:8]}]: {job.topic}")

        # â”€â”€ Use the black-box generator wrapper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from app.services.generator_wrapper import generate_video, GeneratorInput

        cfg = GeneratorInput(
            job_id=job_id,
            topic=job.topic,
            style=job.style or "",
            channel_id=job.channel_id,
            language=getattr(job, "language", "en"),
        )

        # Update to rendering before the heavy pipeline work
        job.status = "rendering"
        db.commit()
        job_log(job_id, "Pipeline configured â€” starting video render", stage="rendering")

        result = generate_video(cfg)

        if result.success:
            if not _video_has_audio_stream(result.video_path):
                job.status = "failed"
                job.error_message = "Generated video has no audio stream"
                job.completed_at = datetime.utcnow()
                job_log(job_id, "Generated video missing audio stream", level="ERROR", stage="failed")
                db.commit()
                return {"status": job.status, "video_path": ""}

            # â”€â”€ Inject Sponsorship â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if bool(config.app.get("enable_sponsorship", False)):
                try:
                    from app.services.sponsor_injector import inject_sponsorship
                    sponsored_path = inject_sponsorship(result.video_path, job.topic)
                    if sponsored_path:
                        result.video_path = sponsored_path
                        job_log(job_id, "Sponsorship watermark injected", stage="sponsored")
                except Exception as e:
                    logger.warning(f"Sponsorship injection failed: {e}")

            job.video_path = result.video_path
            job.status = "completed"
            job.error_message = ""
            job.completed_at = datetime.utcnow()
            job_log(job_id, f"âœ… Video generated in {result.duration_seconds}s", stage="completed")
            elapsed = round(time.perf_counter() - start_wall, 2)
            end_metrics = _capture_process_metrics()
            cpu_used = round(end_metrics["cpu_seconds"] - start_metrics["cpu_seconds"], 2)
            peak_rss_mb = round(max(start_metrics["max_rss_mb"], end_metrics["max_rss_mb"]), 2)
            job_log(job_id, f"perf: wall={elapsed}s cpu={cpu_used}s peak_rss={peak_rss_mb}MB", stage="metrics")
            job_log(job_id, f"Output: {result.video_path}", stage="completed")
            logger.info(f"[Worker] Video generated in {result.duration_seconds}s: {result.video_path}")
            logger.info(f"[Worker][Metrics] job={job_id[:8]} wall={elapsed}s cpu={cpu_used}s peak_rss={peak_rss_mb}MB")
            
            # Auto-upload
            if job.channel and job.channel.encrypted_oauth_credentials and job.channel.is_active:
                logger.info(f"[Worker] Queueing auto-upload for job [{job_id[:8]}]")
                upload_video_task.apply_async(args=[job_id], countdown=2)
                
        else:
            job.status = "failed"
            job.error_message = result.error
            job.completed_at = datetime.utcnow()
            job_log(job_id, f"âŒ Generation failed: {result.error}", level="ERROR", stage="failed")

        db.commit()
        return {"status": job.status, "video_path": job.video_path}

    except Exception as e:
        try:
            from app.services.job_logger import job_log as _jl
            _jl(job_id, f"âŒ Fatal error: {e}", level="ERROR", stage="error")
        except Exception:
            pass
        logger.error(f"[Worker] Video generation failed for job [{job_id[:8]}]: {e}")
        try:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)[:500]
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


@celery_app.task(bind=True, name="upload_video_task", max_retries=3)
def upload_video_task(self, job_id: str):
    """
    Upload a completed video to YouTube with monetization-optimized metadata.

    Auto-generates: SEO title, revenue description, tags, CTA, pinned comment.
    """
    db = SessionLocal()
    start_wall = time.perf_counter()
    start_metrics = _capture_process_metrics()
    try:
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}

        if not job.video_path:
            return {"status": "error", "message": "Job not ready for upload"}
        # Allow retry upload from `failed` state if render already exists.
        if job.status not in ("completed", "failed"):
            return {"status": "error", "message": f"Job status '{job.status}' is not uploadable"}

        job.status = "uploading"
        db.commit()

        from app.services.job_logger import job_log
        job_log(job_id, "Preparing upload with monetization metadata...", stage="uploading")

        # â”€â”€ Generate monetization metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        try:
            from app.services.revenue_metadata import generate_revenue_metadata
            from app.services.revenue_orchestrator import infer_channel_revenue_tier
            from app.services.llm import translate_content
            
            channel_name = job.channel.name if job.channel else ""
            niche = job.channel.niche_type if job.channel else "dark_psychology"
            
            # Translate topic to generate native metadata if not English
            job_lang = getattr(job, "language", "en")
            native_topic = job.topic
            if job_lang and job_lang != "en":
                native_topic = translate_content(job.topic, job_lang)
                job_log(job_id, f"Translated topic for metadata: {native_topic[:50]}...", stage="monetization")

            meta = generate_revenue_metadata(
                topic=native_topic,
                niche=niche,
                style=job.style or "",
                channel_name=channel_name,
                db=db,
                channel_tier=infer_channel_revenue_tier(job.channel),
            )
            job_log(job_id, f"Monetization metadata generated: title='{meta.title[:50]}â€¦'", stage="monetization")
            job_log(job_id, f"Tags: {len(meta.tags)}, SEO keywords: {len(meta.seo_keywords)}", stage="monetization")
            job_log(
                job_id,
                f"Offer selected: {getattr(meta, 'offer_code', '')} | {getattr(meta, 'offer_label', '')}",
                stage="monetization",
            )

            # â”€â”€ Generate Thumbnail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            from app.services.thumbnail_generator import generate_thumbnail
            from app.utils.utils import resource_dir
            import os
            
            thumb_dir = os.path.join(resource_dir(), 'thumbnails')
            try:
                # Use native_topic so the AI Thumbnail Generator writes localized text
                thumb_path = generate_thumbnail(native_topic, job.style, thumb_dir)
                if thumb_path:
                    meta.thumbnail_path = thumb_path
                    job_log(job_id, f"Generated AI thumbnail: {os.path.basename(thumb_path)}", stage="thumbnail")
            except Exception as e:
                logger.warning(f"[Worker] Thumbnail generation failed: {e}")
                job_log(job_id, f"âš ï¸ Thumbnail generation failed: {e}", level="WARNING", stage="thumbnail")
        except Exception as e:
            logger.warning(f"[Worker] Monetization metadata failed: {e}")
            meta = None
            job_log(job_id, f"âš ï¸ Monetization fallback: {e}", level="WARNING", stage="monetization")

        # â”€â”€ Upload using YouTube service â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from app.services.youtube_service import upload_video
        result = upload_video(db, job, monetization_meta=meta)

        if result.get("success"):
            job.status = "completed"
            job.error_message = ""
            job_log(job_id, f"âœ… Uploaded to YouTube: {result.get('video_id')}", stage="uploaded")
            logger.info(f"[Worker] Uploaded job [{job_id[:8]}]: yt={result.get('video_id')}")

            # â”€â”€ Multi-Platform Upload â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            try:
                from app.services.multi_uploader import multi_platform_upload
                from app.db.models import UploadHistory
                mp_results = multi_platform_upload(
                    job.video_path,
                    meta,
                    target_platforms=getattr(job.channel, "target_platforms", "youtube"),
                    platform_settings_json=getattr(job.channel, "platform_settings_json", ""),
                    max_workers=int(config.app.get("multi_platform_upload_workers", 3) or 3),
                )
                history = db.query(UploadHistory).filter(UploadHistory.job_id == job_id).order_by(UploadHistory.uploaded_at.desc()).first()
                if history:
                    try:
                        external_ids = json.loads(history.external_ids_json or "{}")
                    except Exception:
                        external_ids = {}
                    try:
                        platform_results = json.loads(history.platform_results_json or "{}")
                    except Exception:
                        platform_results = {}
                    for platform, result_item in (mp_results or {}).items():
                        if not isinstance(result_item, dict):
                            continue
                        if not result_item.get("success"):
                            continue
                        platform_video_id = str(result_item.get("video_id", "") or "").strip()
                        if not platform_video_id:
                            continue
                        external_ids[platform] = platform_video_id
                        if platform == "tiktok":
                            history.tiktok_video_id = platform_video_id
                        elif platform == "instagram":
                            history.ig_video_id = platform_video_id
                        elif platform == "facebook":
                            history.fb_video_id = platform_video_id
                    platform_results.update(mp_results)
                    history.external_ids_json = json.dumps(external_ids)
                    history.platform_results_json = json.dumps(platform_results)
                    job_log(job_id, f"âœ… Multi-platform upload finalized", stage="multi_uploaded")
            except Exception as e:
                logger.warning(f"Multi-platform upload failed: {e}")

            # â”€â”€ Save content genome for feedback loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _save_genome_on_upload(job, result, meta)
            try:
                from app.services.revenue_orchestrator import score_niche_for_revenue
                from app.services.revenue_tracking import record_monetization_event

                score = score_niche_for_revenue(niche).to_dict()
                record_monetization_event(
                    db=db,
                    job=job,
                    upload_result=result,
                    monetization_meta=meta,
                    revenue_profile=score,
                )
                job_log(
                    job_id,
                    f"Revenue tracked: cta={getattr(meta, 'cta_tag', '')} "
                    f"link={getattr(meta, 'monetization_link_used', '')}",
                    stage="monetization",
                )
            except Exception as e:
                logger.warning(f"[Revenue] tracking failed: {e}")

            # â”€â”€ Clear Run Data (optional) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if bool(config.app.get("clear_run_data_after_upload", True)):
                _clear_job_run_data(job)
                job_log(job_id, "Run data cleared after successful upload", stage="cleanup")

            elapsed = round(time.perf_counter() - start_wall, 2)
            end_metrics = _capture_process_metrics()
            cpu_used = round(end_metrics["cpu_seconds"] - start_metrics["cpu_seconds"], 2)
            peak_rss_mb = round(max(start_metrics["max_rss_mb"], end_metrics["max_rss_mb"]), 2)
            job_log(job_id, f"upload perf: wall={elapsed}s cpu={cpu_used}s peak_rss={peak_rss_mb}MB", stage="metrics")
            logger.info(f"[Worker][Metrics] upload job={job_id[:8]} wall={elapsed}s cpu={cpu_used}s peak_rss={peak_rss_mb}MB")
        else:
            job.status = "failed"
            job.error_message = result.get("error", "Upload failed")
            job_log(job_id, f"âŒ Upload failed: {job.error_message}", level="ERROR", stage="upload_failed")

        db.commit()
        return result

    except Exception as e:
        logger.error(f"[Worker] Upload failed for job [{job_id[:8]}]: {e}")
        try:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = f"Upload error: {str(e)[:400]}"
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))
    finally:
        db.close()


@celery_app.task(name="run_scheduled_batch")
def run_scheduled_batch(channel_id: str):
    """
    INTELLIGENT batch generation for a scheduled channel.

    Uses the full intelligence pipeline instead of basic fallback:
      1. Trend-scored topic generation
      2. Duplicate avoidance via content genome
      3. Evolution bias (prefer historically performing styles/topics)
      4. Retention filtering on generated scripts
      5. Auto-queue for generation + upload
    """
    db = SessionLocal()
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel or not channel.is_active:
            logger.warning(f"[AutoPilot] Channel {channel_id} not found or inactive")
            return {"status": "skipped"}

        schedule = db.query(ScheduleConfig).filter(
            ScheduleConfig.channel_id == channel_id
        ).first()

        base_videos_to_create = schedule.videos_per_run if schedule else channel.daily_video_limit
        niche = channel.niche_type or "dark_psychology"
        style = channel.style_preset or "dark_psychology"
        try:
            from app.services.revenue_orchestrator import score_niche_for_revenue, recommend_videos_per_run

            revenue_profile = score_niche_for_revenue(niche)
            videos_to_create = recommend_videos_per_run(
                base_videos=int(base_videos_to_create),
                niche=niche,
                min_videos=1,
                max_videos=int(config.app.get("max_videos_per_run", 12) or 12),
            )
            logger.info(
                f"[Revenue] niche={niche} score={revenue_profile.revenue_priority_score:.1f} "
                f"tier={revenue_profile.tier} videos_per_run={base_videos_to_create}->{videos_to_create}"
            )
        except Exception as e:
            logger.warning(f"[Revenue] production strategy fallback: {e}")
            videos_to_create = int(base_videos_to_create)
        
        # Parse target languages (default to "en" if missing)
        target_languages_str = getattr(channel, 'target_languages', 'en')
        languages = [l.strip() for l in target_languages_str.split(',') if l.strip()]
        if not languages:
            languages = ['en']

        active_jobs = _count_active_jobs_for_channel(db, channel_id)
        max_pending_jobs = max(1, int(getattr(channel, "max_pending_jobs", 6) or 6))
        available_slots = max(0, max_pending_jobs - active_jobs)
        requested_jobs = videos_to_create * len(languages)
        if available_slots <= 0:
            logger.info(
                f"[AutoPilot] [{channel.name}] pending cap reached "
                f"({active_jobs}/{max_pending_jobs}), skipping new jobs"
            )
            return {
                "status": "skipped",
                "reason": "pending_cap_reached",
                "active_jobs": active_jobs,
                "max_pending_jobs": max_pending_jobs,
            }
        if requested_jobs > available_slots:
            logger.info(
                f"[AutoPilot] [{channel.name}] throttling batch "
                f"{requested_jobs}->{available_slots} because pending cap={max_pending_jobs}"
            )

        logger.info(f"[AutoPilot] ðŸš€ Smart batch for [{channel.name}]: {videos_to_create} videos, niche={niche}, langs={languages}")

        # â”€â”€ Stage 1: Score and select topics via intelligence â”€â”€â”€â”€
        scored_topics = _generate_smart_topics(niche, style, videos_to_create * 2, channel_id)
        _base_topics = list(scored_topics)
        try:
            from app.services.revenue_optimization import prioritize_topics_by_intent
            scored_topics = prioritize_topics_by_intent(
                scored_topics,
                niche=niche,
                min_intent=float(config.app.get("intent_min_score", 30) or 30),
            )[:videos_to_create]
            if not scored_topics:
                scored_topics = _base_topics[:videos_to_create]
            logger.info(f"[Revenue] buyer-intent filtered topics: {len(scored_topics)} selected")
        except Exception as e:
            logger.warning(f"[Revenue] intent filter fallback: {e}")
            scored_topics = _base_topics[:videos_to_create]

        # â”€â”€ Stage 2: Create jobs and queue generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from app.services.job_service import create_job
        from app.models.job_schemas import JobCreate

        queued_jobs = []
        remaining_slots = min(len(scored_topics) * len(languages), available_slots)
        for topic_info in scored_topics:
            topic_en = topic_info["topic"]
            
            # Spawn a job for EACH target language
            for lang in languages:
                if remaining_slots <= 0:
                    break
                try:
                    # Optional: We could translate the topic here, or let the generator_wrapper handle it.
                    # For now, we pass the English topic and the target language; wrapper will handle translation.
                    payload = JobCreate(
                        channel_id=channel_id,
                        topic=topic_en,
                        style=topic_info.get("style", style),
                    )
                    job = create_job(db, payload)
                    job.viral_score = topic_info.get("score", 0.0)
                    job.language = lang
                    db.commit()

                    generate_video_task.delay(job.id)
                    queued_jobs.append(job.id)
                    remaining_slots -= 1
                except Exception as e:
                    logger.warning(f"[AutoPilot] Topic skipped for lang {lang}: {e}")
            if remaining_slots <= 0:
                break

        # Update schedule tracking
        if schedule:
            schedule.last_run_at = datetime.utcnow()
            db.commit()

        logger.info(f"[AutoPilot] âœ… Queued {len(queued_jobs)} intelligent jobs for [{channel.name}]")
        return {"status": "success", "jobs_created": len(queued_jobs), "topics": [t["topic"][:50] for t in scored_topics]}

    except Exception as e:
        logger.error(f"[AutoPilot] Smart batch failed for channel {channel_id}: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="run_autopilot_cycle")
def run_autopilot_cycle():
    """
    Run a full network-wide autopilot cycle.

    Checks all active channels, determines daily quotas,
    and triggers intelligent batch generation for each.
    """
    db = SessionLocal()
    try:
        logger.info("[AutoPilot] â•â•â• Starting full network cycle â•â•â•")
        active_channels = db.query(Channel).filter(Channel.is_active == True).all()

        results = {}
        for channel in active_channels:
            schedule = db.query(ScheduleConfig).filter(
                ScheduleConfig.channel_id == channel.id,
                ScheduleConfig.is_active == True,
            ).first()

            if not schedule:
                continue

            try:
                # Check if channel already has pending/generating jobs today
                today_jobs = db.query(VideoJob).filter(
                    VideoJob.channel_id == channel.id,
                    VideoJob.status.in_(["pending", "generating", "rendering", "uploading"]),
                ).count()

                channel_cap = max(
                    int(schedule.videos_per_run or channel.daily_video_limit or 1),
                    int(getattr(channel, "max_pending_jobs", 6) or 6),
                )
                if today_jobs >= channel_cap:
                    logger.info(f"[AutoPilot] [{channel.name}] already has {today_jobs} active jobs, skipping")
                    results[channel.name] = {"status": "skipped", "active_jobs": today_jobs}
                    continue

                run_scheduled_batch.delay(channel.id)
                results[channel.name] = {"status": "triggered"}
            except Exception as e:
                results[channel.name] = {"status": "error", "error": str(e)}

        logger.info(f"[AutoPilot] â•â•â• Network cycle complete: {len(results)} channels processed â•â•â•")
        return {"status": "success", "channels": results}
    except Exception as e:
        logger.error(f"[AutoPilot] Network cycle failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="check_all_schedules")
def check_all_schedules():
    """
    Periodically check all active schedules and trigger runs if the
    cron expression indicates it's time.

    Called by Celery Beat every 60 seconds.
    """
    db = SessionLocal()
    try:
        from app.services import scheduler
        from croniter import croniter

        active_schedules = scheduler.get_active_schedules(db)
        now = datetime.utcnow()
        triggered_count = 0

        for schedule in active_schedules:
            if not schedule.next_run_at:
                try:
                    iter = croniter(schedule.cron_expression, now)
                    schedule.next_run_at = iter.get_next(datetime)
                    db.commit()
                except Exception as e:
                    logger.warning(f"[Scheduler] Invalid cron for {schedule.channel_id}: {e}")
                    continue

            if now >= schedule.next_run_at:
                logger.info(f"[Scheduler] CRON match for {schedule.channel_id}, kicking off smart batch.")
                run_scheduled_batch.delay(schedule.channel_id)

                try:
                    iter = croniter(schedule.cron_expression, now)
                    schedule.next_run_at = iter.get_next(datetime)
                    db.commit()
                except Exception as e:
                    logger.error(f"[Scheduler] Error shifting next_run_at for {schedule.channel_id}: {e}")

                triggered_count += 1

        return {"status": "success", "triggered_channels": triggered_count}
    except Exception as e:
        logger.error(f"[Scheduler] Periodic check failed: {e}")
        return {"status": "error"}
    finally:
        db.close()


@celery_app.task(name="health_check_task")
def health_check_task():
    """
    Auto-health monitor â€” runs every 5 minutes.

    - Auto-retries stuck jobs (generating > 30 min â†’ mark failed â†’ retry)
    - Cleans up orphaned jobs
    - Reports system health metrics
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        stuck_threshold = now - __import__("datetime").timedelta(minutes=30)

        # Find stuck jobs (generating/rendering for > 30 min)
        stuck_jobs = db.query(VideoJob).filter(
            VideoJob.status.in_(["generating", "rendering"]),
            VideoJob.started_at < stuck_threshold,
        ).all()

        retried = 0
        for job in stuck_jobs:
            if job.retry_count < 3:
                job.status = "pending"
                job.error_message = f"Auto-retried: stuck in {job.status} for >30min"
                job.retry_count += 1
                db.commit()
                generate_video_task.delay(job.id)
                retried += 1
                logger.info(f"[Health] Auto-retried stuck job [{job.id[:8]}] (attempt {job.retry_count})")
            else:
                job.status = "failed"
                job.error_message = "Max retries reached after being stuck"
                job.completed_at = now
                db.commit()
                logger.warning(f"[Health] Abandoned stuck job [{job.id[:8]}] after {job.retry_count} retries")

        # Count stats
        active_jobs = db.query(VideoJob).filter(VideoJob.status.in_(["generating", "rendering"])).count()
        cache_cleanup = _cleanup_cache_videos(active_render_jobs=active_jobs)
        if cache_cleanup.get("deleted_files", 0) > 0:
            logger.info(
                f"[Health] cache cleanup: deleted={cache_cleanup['deleted_files']}, "
                f"freed={cache_cleanup['freed_bytes'] / (1024 * 1024):.1f}MB"
            )

        load_1m, _load_5m, _load_15m = os.getloadavg()
        proc_metrics = _capture_process_metrics()
        stats = {
            "total_jobs": db.query(VideoJob).count(),
            "pending": db.query(VideoJob).filter(VideoJob.status == "pending").count(),
            "generating": active_jobs,
            "completed": db.query(VideoJob).filter(VideoJob.status == "completed").count(),
            "failed": db.query(VideoJob).filter(VideoJob.status == "failed").count(),
            "stuck_retried": retried,
            "active_channels": db.query(Channel).filter(Channel.is_active == True).count(),
            "cache_cleanup_deleted_files": cache_cleanup.get("deleted_files", 0),
            "cache_cleanup_freed_mb": round(cache_cleanup.get("freed_bytes", 0) / (1024 * 1024), 2),
            "cache_cleanup_skipped": cache_cleanup.get("skipped", False),
            "worker_load_1m": round(float(load_1m), 2),
            "worker_cpu_seconds_total": round(proc_metrics["cpu_seconds"], 2),
            "worker_current_rss_mb": round(_read_current_rss_mb(), 2),
            "worker_peak_rss_mb": round(proc_metrics["max_rss_mb"], 2),
        }
        stats.update(_queue_depth_metrics())

        if retried:
            logger.info(f"[Health] Auto-retried {retried} stuck jobs")

        return {"status": "ok", **stats}
    except Exception as e:
        logger.error(f"[Health] Check failed: {e}")
        return {"status": "error"}
    finally:
        db.close()


# â”€â”€ Intelligence Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _generate_smart_topics(niche: str, style: str, count: int, channel_id: str) -> list:
    """
    Generate intelligence-scored topics with full pipeline:
      1. Trend scoring â†’ rank topics by virality potential
      2. Duplicate check â†’ skip recently used topics
      3. Evolution bias â†’ prefer historically successful patterns
    """
    topics = []

    # â”€â”€ Step 1: Generate scored topics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        from app.services.trend_intelligence import score_topic, generate_trending_topics
        raw_topics = generate_trending_topics(niche=niche, count=count * 3)  # Over-generate for filtering

        scored = []
        for t in raw_topics:
            try:
                result = score_topic(t, niche=niche)
                scored.append({
                    "topic": t,
                    "score": result.final_score,
                    "style": style,
                    "archetype": result.archetype,
                })
            except Exception:
                scored.append({"topic": t, "score": 50.0, "style": style})

        scored.sort(key=lambda x: x["score"], reverse=True)
        topics = scored
    except Exception as e:
        logger.warning(f"[AutoPilot] Trend scoring failed, using fallback: {e}")
        topics = [{"topic": f"{niche} topic #{i+1}", "score": 50.0, "style": style} for i in range(count)]

    # â”€â”€ Step 2: Duplicate avoidance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        from app.services.content_genome import GenomeStore
        store = GenomeStore()
        recent = store.get_recent_topics(count=50)
        if recent:
            recent_lower = {t.lower() for t in recent}
            topics = [t for t in topics if t["topic"].lower() not in recent_lower]
    except Exception:
        pass

    # â”€â”€ Step 3: Evolution bias â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        from app.services.evolution_engine import get_topic_bias
        biased = get_topic_bias(topics, channel_id=channel_id, niche=niche)
        if biased:
            topics = biased
    except Exception:
        pass

    # Return top N
    return topics[:count]


def _save_genome_on_upload(job, upload_result: dict, meta=None):
    """Save content genome after successful upload for the feedback loop."""
    try:
        from app.services.content_genome import GenomeStore, ContentGenome
        store = GenomeStore()

        genome = ContentGenome(
            job_id=job.id,
            channel_id=job.channel_id,
            topic=job.topic,
            niche=job.channel.niche_type if job.channel else "",
            style_preset=job.style or "",
            video_path=job.video_path or "",
            viral_score=job.viral_score or 0.0,
            youtube_video_id=upload_result.get("video_id", ""),
            upload_status="uploaded",
            quality_passed=True,
        )
        store.save(genome)
        logger.info(f"[Genome] Saved post-upload genome for job [{job.id[:8]}]")
    except Exception as e:
        logger.warning(f"[Genome] Post-upload save failed: {e}")



