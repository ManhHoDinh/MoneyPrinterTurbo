"""
Job Logger — Per-job log capture and streaming.

Captures loguru log messages tagged with a job_id and stores them in a
thread-safe ring buffer. Supports:
  - Real-time SSE (Server-Sent Events) streaming
  - Historical log retrieval
  - Automatic cleanup of old logs

Usage (in worker/tasks.py or generator_wrapper.py):
    from app.services.job_logger import job_log, get_job_logs, stream_job_logs

    # Write a log entry for a specific job
    job_log(job_id, "Starting video generation...")
    job_log(job_id, "Applying style mutations", level="DEBUG")
    job_log(job_id, "Generation failed: timeout", level="ERROR")

    # Get historical logs
    logs = get_job_logs(job_id)

    # Stream logs via SSE (used by the API endpoint)
    async for event in stream_job_logs(job_id):
        yield event
"""

import asyncio
import time
import threading
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, AsyncGenerator

from loguru import logger


# ── Configuration ────────────────────────────────────────────────────────────

MAX_LOGS_PER_JOB = 500          # Ring buffer size per job
LOG_TTL_SECONDS = 3600          # Auto-cleanup after 1 hour of inactivity
STREAM_POLL_INTERVAL = 0.5      # SSE poll interval in seconds
STREAM_TIMEOUT = 300            # SSE stream timeout (5 minutes)


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class LogEntry:
    """A single log entry for a job."""
    timestamp: float
    level: str
    message: str
    stage: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "time": time.strftime("%H:%M:%S", time.localtime(self.timestamp)),
            "level": self.level,
            "message": self.message,
            "stage": self.stage,
        }

    def to_sse(self) -> str:
        """Format as SSE data line."""
        import json
        return f"data: {json.dumps(self.to_dict())}\n\n"


class JobLogBuffer:
    """Thread-safe ring buffer for per-job logs."""

    def __init__(self, max_size: int = MAX_LOGS_PER_JOB):
        self.entries: deque = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.last_access = time.time()
        self.seq = 0                # Monotonic sequence number
        self._event = asyncio.Event() if _has_running_loop() else None

    def append(self, entry: LogEntry):
        with self.lock:
            self.seq += 1
            self.entries.append(entry)
            self.last_access = time.time()
        # Notify any SSE listeners
        if self._event:
            self._event.set()

    def get_all(self) -> List[LogEntry]:
        with self.lock:
            self.last_access = time.time()
            return list(self.entries)

    def get_since(self, after_seq: int) -> tuple:
        """Get entries added after a given sequence number."""
        with self.lock:
            self.last_access = time.time()
            current_seq = self.seq
            count = current_seq - after_seq
            if count <= 0:
                return [], current_seq
            entries = list(self.entries)[-count:]
            return entries, current_seq

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_access) > LOG_TTL_SECONDS


def _has_running_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


# ── Global Log Store ─────────────────────────────────────────────────────────

_buffers: Dict[str, JobLogBuffer] = {}
_buffers_lock = threading.Lock()


def _get_buffer(job_id: str) -> JobLogBuffer:
    """Get or create a log buffer for a job."""
    with _buffers_lock:
        if job_id not in _buffers:
            _buffers[job_id] = JobLogBuffer()
        return _buffers[job_id]


def _cleanup_expired():
    """Remove expired buffers."""
    with _buffers_lock:
        expired = [jid for jid, buf in _buffers.items() if buf.is_expired]
        for jid in expired:
            del _buffers[jid]
        if expired:
            logger.debug(f"[JobLogger] Cleaned up {len(expired)} expired log buffers")


# ── Public API ───────────────────────────────────────────────────────────────

def job_log(
    job_id: str,
    message: str,
    level: str = "INFO",
    stage: str = "",
):
    """
    Write a log entry for a specific job.

    Call this from worker tasks, generator_wrapper, or any pipeline stage.
    """
    entry = LogEntry(
        timestamp=time.time(),
        level=level.upper(),
        message=message,
        stage=stage,
    )
    buf = _get_buffer(job_id)
    buf.append(entry)


def get_job_logs(job_id: str) -> List[dict]:
    """Get all log entries for a job."""
    buf = _get_buffer(job_id)
    return [e.to_dict() for e in buf.get_all()]


def get_active_jobs() -> List[dict]:
    """Get list of jobs that have active log buffers."""
    with _buffers_lock:
        return [
            {
                "job_id": jid,
                "log_count": len(buf.entries),
                "last_active": buf.last_access,
                "last_active_ago": round(time.time() - buf.last_access, 1),
            }
            for jid, buf in _buffers.items()
            if not buf.is_expired
        ]


async def stream_job_logs(job_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator for SSE streaming of job logs.

    Yields SSE-formatted events as new log entries arrive.
    """
    buf = _get_buffer(job_id)
    last_seq = 0
    start = time.time()

    # First, send all existing logs
    entries = buf.get_all()
    for entry in entries:
        yield entry.to_sse()
    last_seq = buf.seq

    # Then stream new entries
    while (time.time() - start) < STREAM_TIMEOUT:
        new_entries, new_seq = buf.get_since(last_seq)
        if new_entries:
            for entry in new_entries:
                yield entry.to_sse()
            last_seq = new_seq
        else:
            await asyncio.sleep(STREAM_POLL_INTERVAL)

        # Check if job is done
        if _is_job_finished(job_id):
            # Send any remaining entries
            final_entries, _ = buf.get_since(last_seq)
            for entry in final_entries:
                yield entry.to_sse()
            yield "data: {\"type\": \"done\", \"message\": \"Job completed\"}\n\n"
            break

    # Cleanup old buffers periodically
    _cleanup_expired()


def _is_job_finished(job_id: str) -> bool:
    """Check if a job has reached a terminal state."""
    try:
        from app.db.engine import SessionLocal
        from app.db.models import VideoJob
        db = SessionLocal()
        try:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job and job.status in ("completed", "failed"):
                return True
        finally:
            db.close()
    except Exception:
        pass
    return False
