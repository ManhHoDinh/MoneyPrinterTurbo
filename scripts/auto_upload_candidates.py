#!/usr/bin/env python3
"""
Lightweight uploader for already-rendered jobs.

It does NOT generate new videos to avoid RAM pressure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Any, Dict, List, Tuple

import requests


def _parse_dt(value: Any) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _contains_money_signal(job: Dict[str, Any]) -> bool:
    payload = " ".join(
        [
            str(job.get("topic") or ""),
            str(job.get("title") or ""),
            str(job.get("description") or ""),
            str(job.get("niche") or ""),
            str(job.get("category") or ""),
        ]
    ).lower()
    keywords = (
        "review",
        "best",
        "top ",
        "deal",
        "discount",
        "affiliate",
        "buy",
        "price",
        "vs ",
        "comparison",
        "tool",
        "software",
    )
    return any(k in payload for k in keywords)


def _has_revenue_metadata(job: Dict[str, Any]) -> bool:
    fields = [
        "affiliate_link",
        "affiliate_links",
        "sponsor",
        "sponsor_link",
        "cta",
        "revenue_tag",
        "revenue_tags",
        "monetization",
        "monetization_ready",
    ]
    for f in fields:
        value = job.get(f)
        if value:
            return True
    return False


def _has_placeholder_text(job: Dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("description") or ""),
            str(job.get("topic") or ""),
        ]
    ).upper()
    return any(marker in text for marker in ("[YOUR_", "[AFFILIATE_", "[LANDING_"))


def _candidate_score(job: Dict[str, Any]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    status = (job.get("status") or "").lower()
    if status == "completed":
        score += 200
        reasons.append("status=completed")
    elif status == "failed":
        score += 40
        reasons.append("status=failed(retry)")

    if _has_revenue_metadata(job):
        score += 80
        reasons.append("has_revenue_metadata")

    if _contains_money_signal(job):
        score += 50
        reasons.append("money_keyword_match")

    if _has_placeholder_text(job):
        score -= 120
        reasons.append("placeholder_penalty")

    retry_count = int(job.get("upload_retry_count") or 0)
    if retry_count > 0:
        score -= min(45, retry_count * 15)
        reasons.append(f"retry_penalty={retry_count}")

    created_at = _parse_dt(job.get("created_at"))
    if created_at:
        age_hours = max(0, (dt.datetime.now() - created_at).total_seconds() / 3600.0)
        age_bonus = min(25, int(age_hours // 6))
        if age_bonus > 0:
            score += age_bonus
            reasons.append(f"age_bonus={age_bonus}")

    return score, reasons


def _fetch_jobs(base: str, limit: int, timeout: int) -> List[Dict[str, Any]]:
    resp = requests.get(f"{base}/api/v1/jobs?skip=0&limit={limit}", timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--max", type=int, default=2, dest="max_uploads")
    parser.add_argument("--limit", type=int, default=200, help="jobs to scan")
    parser.add_argument(
        "--prefer-completed-only",
        action="store_true",
        help="Only upload jobs with status=completed",
    )
    parser.add_argument("--request-timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument(
        "--require-money-signal",
        action="store_true",
        help="Only keep candidates with monetization metadata or money keyword signal",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=-9999,
        help="Drop candidates below this score",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    jobs = _fetch_jobs(base=base, limit=args.limit, timeout=args.request_timeout)

    candidates = []
    for j in jobs:
        if j.get("youtube_video_id"):
            continue
        if not j.get("video_path"):
            continue
        status = (j.get("status") or "").lower()
        if status not in ("completed", "failed"):
            continue
        if args.prefer_completed_only and status != "completed":
            continue
        score, reasons = _candidate_score(j)
        has_money_signal = _has_revenue_metadata(j) or _contains_money_signal(j)
        if args.require_money_signal and not has_money_signal:
            continue
        if score < args.min_score:
            continue
        j["_upload_score"] = score
        j["_upload_reasons"] = reasons
        candidates.append(j)

    candidates = sorted(
        candidates,
        key=lambda job: (
            int(job.get("_upload_score", 0)),
            1 if (job.get("status") or "").lower() == "completed" else 0,
            int(job.get("id") or 0),
        ),
        reverse=True,
    )

    triggered = []
    for j in candidates[: args.max_uploads]:
        job_id = j.get("id")
        try:
            r = requests.post(f"{base}/api/v1/youtube/upload/{job_id}", timeout=args.request_timeout)
            ok = r.status_code == 200
            triggered.append(
                {
                    "job_id": job_id,
                    "status_code": r.status_code,
                    "ok": ok,
                    "score": int(j.get("_upload_score", 0)),
                    "reasons": j.get("_upload_reasons", []),
                    "response": r.text[:300],
                }
            )
        except Exception as e:
            triggered.append(
                {
                    "job_id": job_id,
                    "ok": False,
                    "score": int(j.get("_upload_score", 0)),
                    "reasons": j.get("_upload_reasons", []),
                    "error": str(e),
                }
            )

    print(
        json.dumps(
            {
                "scanned": len(jobs),
                "candidates": len(candidates),
                "triggered": len(triggered),
                "selected": [
                    {
                        "job_id": c.get("id"),
                        "status": c.get("status"),
                        "score": int(c.get("_upload_score", 0)),
                        "reasons": c.get("_upload_reasons", []),
                    }
                    for c in candidates[: args.max_uploads]
                ],
                "details": triggered,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
