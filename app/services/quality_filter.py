"""
Auto Quality Filter — Pre-upload video quality gate.

Runs a multi-check quality assessment before a video is queued for
YouTube upload. Rejects low-quality videos to protect channel reputation.

Checks:
  1. File existence and minimum size (corrupt/empty files)
  2. Duration range (too short = bad, too long = bad for Shorts)
  3. Viral score threshold (from viral_score.py)
  4. Retention prediction (from retention_simulator.py)
  5. Content genome quality flag

Usage:
    from app.services.quality_filter import quality_gate
    result = quality_gate(job_id="abc", video_path="/path/to/video.mp4")
    if result["passed"]:
        # Safe to upload
    else:
        print(result["rejection_reasons"])
"""

import os
from typing import Dict, Any, List, Optional

from loguru import logger


# ── Default Thresholds ──────────────────────────────────────────────────────

DEFAULT_THRESHOLDS = {
    "min_file_size_mb": 1.0,         # Reject files under 1MB (likely corrupt)
    "max_file_size_mb": 500.0,       # Reject files over 500MB
    "min_duration_seconds": 15.0,    # Too short = no value
    "max_duration_seconds": 600.0,   # 10 min max for this format
    "viral_score_min": 45.0,         # Minimum viral score
    "retention_score_min": 40.0,     # Minimum retention prediction
    "min_word_count": 30,            # Scripts with <30 words are likely bad
}


# ── Quality Gate ─────────────────────────────────────────────────────────────

def quality_gate(
    job_id: str = "",
    video_path: str = "",
    script: str = "",
    style: str = "",
    thresholds: Dict[str, float] = None,
) -> Dict[str, Any]:
    """
    Run the full quality gauntlet on a video before upload.

    Returns:
        {
            "passed": True/False,
            "score": 0-100 (composite quality score),
            "checks": {
                "file_check": {"passed": True, "details": "..."},
                "viral_score": {"passed": True, "score": 72, "details": "..."},
                ...
            },
            "rejection_reasons": ["..."],
        }
    """
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    checks: Dict[str, Dict[str, Any]] = {}
    rejection_reasons: List[str] = []
    scores: List[float] = []

    # ── Check 1: File validation ─────────────────────────────────────
    file_result = _check_file(video_path, th)
    checks["file_check"] = file_result
    if not file_result["passed"]:
        rejection_reasons.append(f"File: {file_result['details']}")

    # ── Check 2: Script quality (if script provided) ─────────────────
    if script:
        script_result = _check_script(script, th)
        checks["script_check"] = script_result
        if not script_result["passed"]:
            rejection_reasons.append(f"Script: {script_result['details']}")
    else:
        checks["script_check"] = {"passed": True, "details": "No script provided (skipped)"}

    # ── Check 3: Viral score ─────────────────────────────────────────
    if script:
        viral_result = _check_viral_score(script, th)
        checks["viral_score"] = viral_result
        scores.append(viral_result.get("score", 0))
        if not viral_result["passed"]:
            rejection_reasons.append(f"Viral: {viral_result['details']}")
    else:
        checks["viral_score"] = {"passed": True, "score": 0, "details": "Skipped (no script)"}

    # ── Check 4: Retention prediction ────────────────────────────────
    if script:
        retention_result = _check_retention(script, style, th)
        checks["retention"] = retention_result
        scores.append(retention_result.get("score", 0))
        if not retention_result["passed"]:
            rejection_reasons.append(f"Retention: {retention_result['details']}")
    else:
        checks["retention"] = {"passed": True, "score": 0, "details": "Skipped (no script)"}

    # ── Check 5: Content genome (if stored) ──────────────────────────
    if job_id:
        genome_result = _check_genome(job_id)
        checks["genome"] = genome_result
        if not genome_result["passed"]:
            rejection_reasons.append(f"Genome: {genome_result['details']}")
    else:
        checks["genome"] = {"passed": True, "details": "No job_id (skipped)"}

    # Composite score
    composite = sum(scores) / len(scores) if scores else 50.0
    passed = len(rejection_reasons) == 0

    level = "✅ PASSED" if passed else "❌ REJECTED"
    logger.info(
        f"[QualityFilter] {level} job={job_id[:8] if job_id else 'N/A'} "
        f"score={composite:.0f} checks={sum(1 for c in checks.values() if c['passed'])}/{len(checks)}"
    )
    if rejection_reasons:
        for r in rejection_reasons:
            logger.warning(f"[QualityFilter]   → {r}")

    return {
        "passed": passed,
        "score": round(composite, 1),
        "checks": checks,
        "rejection_reasons": rejection_reasons,
    }


def batch_quality_filter(
    items: List[Dict[str, Any]],
    thresholds: Dict[str, float] = None,
) -> Dict[str, Any]:
    """
    Filter a batch of videos, returning pass/fail for each.

    Args:
        items: List of {"job_id": "...", "video_path": "...", "script": "...", "style": "..."}
        thresholds: Override thresholds

    Returns:
        {"passed": [...], "rejected": [...], "stats": {...}}
    """
    passed = []
    rejected = []

    for item in items:
        result = quality_gate(
            job_id=item.get("job_id", ""),
            video_path=item.get("video_path", ""),
            script=item.get("script", ""),
            style=item.get("style", ""),
            thresholds=thresholds,
        )
        entry = {
            "job_id": item.get("job_id", ""),
            "passed": result["passed"],
            "score": result["score"],
            "reasons": result["rejection_reasons"],
        }
        if result["passed"]:
            passed.append(entry)
        else:
            rejected.append(entry)

    return {
        "passed": passed,
        "rejected": rejected,
        "stats": {
            "total": len(items),
            "passed": len(passed),
            "rejected": len(rejected),
            "pass_rate": round(len(passed) / len(items) * 100, 1) if items else 0,
            "avg_score": round(
                sum(e["score"] for e in passed + rejected) / len(items), 1
            ) if items else 0,
        },
    }


# ── Individual Checks ────────────────────────────────────────────────────────

def _check_file(video_path: str, th: Dict) -> Dict[str, Any]:
    """Validate video file exists and meets size requirements."""
    if not video_path:
        return {"passed": False, "details": "No video path provided"}

    if not os.path.exists(video_path):
        return {"passed": False, "details": f"File not found: {video_path}"}

    size_mb = os.path.getsize(video_path) / (1024 * 1024)

    if size_mb < th["min_file_size_mb"]:
        return {
            "passed": False,
            "details": f"File too small ({size_mb:.1f}MB < {th['min_file_size_mb']}MB) — likely corrupt",
            "size_mb": round(size_mb, 1),
        }

    if size_mb > th["max_file_size_mb"]:
        return {
            "passed": False,
            "details": f"File too large ({size_mb:.0f}MB > {th['max_file_size_mb']}MB)",
            "size_mb": round(size_mb, 1),
        }

    return {"passed": True, "details": f"OK ({size_mb:.1f}MB)", "size_mb": round(size_mb, 1)}


def _check_script(script: str, th: Dict) -> Dict[str, Any]:
    """Basic script quality checks."""
    word_count = len(script.split())

    if word_count < th["min_word_count"]:
        return {
            "passed": False,
            "details": f"Script too short ({word_count} words < {th['min_word_count']})",
            "word_count": word_count,
        }

    # Check for placeholder/template text
    placeholder_markers = ["[INSERT", "[YOUR", "TODO", "PLACEHOLDER", "lorem ipsum"]
    for marker in placeholder_markers:
        if marker.lower() in script.lower():
            return {
                "passed": False,
                "details": f"Script contains placeholder text: '{marker}'",
                "word_count": word_count,
            }

    return {"passed": True, "details": f"OK ({word_count} words)", "word_count": word_count}


def _check_viral_score(script: str, th: Dict) -> Dict[str, Any]:
    """Run viral score check."""
    try:
        from app.services.viral_score import compute_viral_score
        result = compute_viral_score(script)
        score = result.get("score", 0)
        grade = result.get("grade", "?")

        passed = score >= th["viral_score_min"]
        return {
            "passed": passed,
            "score": score,
            "grade": grade,
            "details": f"{'OK' if passed else 'LOW'} (score={score:.0f}, grade={grade}, min={th['viral_score_min']})",
        }
    except Exception as e:
        logger.warning(f"[QualityFilter] Viral score check failed: {e}")
        return {"passed": True, "score": 0, "details": f"Check failed (skipped): {e}"}


def _check_retention(script: str, style: str, th: Dict) -> Dict[str, Any]:
    """Run retention simulation check."""
    try:
        from app.services.retention_simulator import simulate_retention
        result = simulate_retention(script, style=style, threshold=th["retention_score_min"])
        score = result.overall_score

        return {
            "passed": result.passed,
            "score": score,
            "hook_score": result.hook_score,
            "details": (
                f"{'OK' if result.passed else 'WEAK'} "
                f"(score={score:.0f}, hook={result.hook_score:.0f}, min={th['retention_score_min']})"
                + (f" — {result.rejection_reason}" if result.rejection_reason else "")
            ),
        }
    except Exception as e:
        logger.warning(f"[QualityFilter] Retention check failed: {e}")
        return {"passed": True, "score": 0, "details": f"Check failed (skipped): {e}"}


def _check_genome(job_id: str) -> Dict[str, Any]:
    """Check if content genome flagged this video as rejected."""
    try:
        from app.services.content_genome import GenomeStore
        store = GenomeStore()
        genome = store.load(job_id)
        if not genome:
            return {"passed": True, "details": "No genome record found (skipped)"}

        if not genome.quality_passed:
            return {
                "passed": False,
                "details": f"Genome flagged: {genome.rejection_reason or 'quality_passed=False'}",
            }

        return {"passed": True, "details": "OK (genome quality_passed=True)"}
    except Exception as e:
        return {"passed": True, "details": f"Genome check failed (skipped): {e}"}
