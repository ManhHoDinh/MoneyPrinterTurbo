"""
Celery application configuration.

Uses Redis as broker and backend, pulling config from config.toml.
"""

from celery import Celery
from kombu import Queue

from app.config import config

# Build Redis URL from existing config
_redis_host = config.app.get("redis_host", "localhost")
_redis_port = config.app.get("redis_port", 6379)
_redis_db = config.app.get("redis_db", 0)
_redis_password = config.app.get("redis_password", "")

if _redis_password:
    REDIS_URL = f"redis://:{_redis_password}@{_redis_host}:{_redis_port}/{_redis_db}"
else:
    REDIS_URL = f"redis://{_redis_host}:{_redis_port}/{_redis_db}"

celery_app = Celery(
    "contentfarm",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker.tasks"],
)

_render_queue = str(config.app.get("render_queue_name", "render") or "render")
_upload_queue = str(config.app.get("upload_queue_name", "upload") or "upload")
_control_queue = str(config.app.get("control_queue_name", "control") or "control")

_enable_autopilot = bool(config.app.get("enable_autopilot", False))
_beat_schedule = {
    "check-schedules-every-minute": {
        "task": "check_all_schedules",
        "schedule": 60.0,
    },
    "health-check-every-5-minutes": {
        "task": "health_check_task",
        "schedule": 300.0,
    },
}
if _enable_autopilot:
    _beat_schedule["autopilot-cycle-every-hour"] = {
        "task": "run_autopilot_cycle",
        "schedule": 3600.0,
    }

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue=_render_queue,
    task_queues=(
        Queue(_render_queue),
        Queue(_upload_queue),
        Queue(_control_queue),
    ),
    task_routes={
        "generate_video_task": {"queue": _render_queue},
        "upload_video_task": {"queue": _upload_queue},
        "run_scheduled_batch": {"queue": _control_queue},
        "check_all_schedules": {"queue": _control_queue},
        "run_autopilot_cycle": {"queue": _control_queue},
        "health_check_task": {"queue": _control_queue},
    },
    worker_prefetch_multiplier=int(config.app.get("worker_prefetch_multiplier", 1) or 1),
    worker_max_tasks_per_child=int(config.app.get("worker_max_tasks_per_child", 1) or 1),
    broker_transport_options={"visibility_timeout": int(config.app.get("broker_visibility_timeout", 14400) or 14400)},
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Result expiry
    result_expires=3600 * 24,  # 24 hours
    # Static beat schedule to poll dynamic DB configs
    beat_schedule=_beat_schedule,
)
