import ast
from abc import ABC, abstractmethod

from app.config import config
from app.models import const


# Base class for state management
class BaseState(ABC):
    @abstractmethod
    def update_task(self, task_id: str, state: int, progress: int = 0, **kwargs):
        pass

    @abstractmethod
    def get_task(self, task_id: str):
        pass

    @abstractmethod
    def get_all_tasks(self, page: int, page_size: int):
        pass


# Memory state management
class MemoryState(BaseState):
    def __init__(self):
        self._tasks = {}

    def get_all_tasks(self, page: int, page_size: int):
        start = (page - 1) * page_size
        end = start + page_size
        tasks = list(self._tasks.values())
        total = len(tasks)
        return tasks[start:end], total

    def update_task(
        self,
        task_id: str,
        state: int = const.TASK_STATE_PROCESSING,
        progress: int = 0,
        **kwargs,
    ):
        progress = int(progress)
        if progress > 100:
            progress = 100

        self._tasks[task_id] = {
            "task_id": task_id,
            "state": state,
            "progress": progress,
            **kwargs,
        }

    def get_task(self, task_id: str):
        return self._tasks.get(task_id, None)

    def delete_task(self, task_id: str):
        if task_id in self._tasks:
            del self._tasks[task_id]


# Redis state management
class RedisState(BaseState):
    def __init__(self, host="localhost", port=6379, db=0, password=None):
        import redis

        self._redis = redis.StrictRedis(host=host, port=port, db=db, password=password)

    def get_all_tasks(self, page: int, page_size: int):
        start = (page - 1) * page_size
        end = start + page_size
        tasks = []
        cursor = 0
        total = 0
        while True:
            cursor, keys = self._redis.scan(cursor, count=page_size)
            total += len(keys)
            if total > start:
                for key in keys[max(0, start - total):end - total]:
                    task_data = self._redis.hgetall(key)
                    task = {
                        k.decode("utf-8"): self._convert_to_original_type(v) for k, v in task_data.items()
                    }
                    tasks.append(task)
                    if len(tasks) >= page_size:
                        break
            if cursor == 0 or len(tasks) >= page_size:
                break
        return tasks, total

    def update_task(
        self,
        task_id: str,
        state: int = const.TASK_STATE_PROCESSING,
        progress: int = 0,
        **kwargs,
    ):
        progress = int(progress)
        if progress > 100:
            progress = 100

        fields = {
            "task_id": task_id,
            "state": state,
            "progress": progress,
            **kwargs,
        }

        for field, value in fields.items():
            self._redis.hset(task_id, field, str(value))

    def get_task(self, task_id: str):
        task_data = self._redis.hgetall(task_id)
        if not task_data:
            return None

        task = {
            key.decode("utf-8"): self._convert_to_original_type(value)
            for key, value in task_data.items()
        }
        return task

    def delete_task(self, task_id: str):
        self._redis.delete(task_id)

    @staticmethod
    def _convert_to_original_type(value):
        """
        Convert the value from byte string to its original data type.
        You can extend this method to handle other data types as needed.
        """
        value_str = value.decode("utf-8")

        try:
            # try to convert byte string array to list
            return ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            pass

        if value_str.isdigit():
            return int(value_str)
        # Add more conversions here if needed
        return value_str


# Global state
_enable_redis = config.app.get("enable_redis", False)
_redis_host = config.app.get("redis_host", "localhost")
_redis_port = config.app.get("redis_port", 6379)
_redis_db = config.app.get("redis_db", 0)
_redis_password = config.app.get("redis_password", None)

_inner_state = (
    RedisState(
        host=_redis_host, port=_redis_port, db=_redis_db, password=_redis_password
    )
    if _enable_redis
    else MemoryState()
)


# ── Logging State Proxy ──────────────────────────────────────────────────────
# Wraps the real state and emits job_log() on every update_task call
# so that all 20 video generation tasks stream logs in real-time.

_PROGRESS_STAGE_MAP = {
    5: "Starting pipeline",
    10: "Script generated",
    20: "Search terms ready",
    30: "Audio generated (TTS)",
    40: "Subtitles created",
    50: "Video materials downloaded",
    100: "Complete",
}

_STATE_NAME_MAP = {
    const.TASK_STATE_PROCESSING: "PROCESSING",
    const.TASK_STATE_COMPLETE: "COMPLETE",
    const.TASK_STATE_FAILED: "FAILED",
}


class _LoggingStateProxy:
    """Proxy that wraps the real state and emits job_log on updates."""

    def __init__(self, inner):
        self._inner = inner

    def update_task(self, task_id: str, state: int = const.TASK_STATE_PROCESSING, progress: int = 0, **kwargs):
        self._inner.update_task(task_id, state=state, progress=progress, **kwargs)

        # Emit log for streaming
        try:
            from app.services.job_logger import job_log

            progress = int(progress)
            state_name = _STATE_NAME_MAP.get(state, f"state={state}")

            # Determine stage description
            stage_desc = _PROGRESS_STAGE_MAP.get(progress, "")
            if not stage_desc and progress > 50:
                stage_desc = f"Rendering video ({progress}%)"

            if state == const.TASK_STATE_FAILED:
                job_log(task_id, f"❌ Task FAILED at {progress}%", level="ERROR", stage="failed")
            elif state == const.TASK_STATE_COMPLETE:
                job_log(task_id, f"✅ Task completed", stage="completed")
                if kwargs.get("videos"):
                    videos = kwargs["videos"]
                    job_log(task_id, f"Generated {len(videos)} video(s)", stage="completed")
                if kwargs.get("viral_score"):
                    job_log(task_id, f"Viral score: {kwargs['viral_score']}", stage="score")
            elif stage_desc:
                job_log(task_id, f"[{progress}%] {stage_desc}", stage=stage_desc.split()[0].lower())
            else:
                job_log(task_id, f"[{progress}%] Progress update", stage="progress")
        except Exception:
            pass  # Never let logging break the pipeline

    def get_task(self, task_id: str):
        return self._inner.get_task(task_id)

    def get_all_tasks(self, page: int, page_size: int):
        return self._inner.get_all_tasks(page, page_size)

    def delete_task(self, task_id: str):
        return self._inner.delete_task(task_id)


state = _LoggingStateProxy(_inner_state)


# ── Loguru Task Sink ─────────────────────────────────────────────────────────
# Captures logger.info/error/etc calls from task.py and routes them to job_log
# based on the current task context.

import threading

_current_task_id = threading.local()


def set_current_task(task_id: str):
    """Set the active task_id for log routing in this thread."""
    _current_task_id.value = task_id


def get_current_task() -> str:
    """Get the active task_id for this thread."""
    return getattr(_current_task_id, "value", "")


def _task_log_sink(message):
    """Loguru sink that routes logs to the active task's job_log buffer."""
    task_id = get_current_task()
    if not task_id:
        return

    record = message.record
    text = record["message"]

    # Skip very noisy or internal messages
    if any(skip in text for skip in ["[Genome]", "[JobLogger]", "[AnalyticsHub]"]):
        return

    try:
        from app.services.job_logger import job_log
        level = record["level"].name
        job_log(task_id, text, level=level, stage="pipeline")
    except Exception:
        pass


# Install the sink (only captures task-context logs, not ALL logs)
from loguru import logger as _logger
_logger.add(_task_log_sink, level="INFO", filter=lambda record: bool(get_current_task()))

