#!/usr/bin/env python3
"""
Auto-Agent audit loop for MoneyPrinterTurbo.

What it does:
1) Runs lightweight code-quality scans.
2) Reads production metrics from SQLite DB.
3) Scores system health + monetization readiness.
4) Emits prioritized action items.

Usage:
    python scripts/auto_agent.py
    python scripts/auto_agent.py --hours 72 --output storage/auto_agent_report.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "storage" / "contentfarm.db"
DEFAULT_OUTPUT = ROOT / "storage" / "auto_agent_report.md"


@dataclass
class AuditFinding:
    level: str  # critical, high, medium, low
    title: str
    detail: str
    action: str


def _run_rg_count(pattern: str, globs: Optional[List[str]] = None) -> int:
    cmd = ["rg", "-n", pattern, "app"]
    if globs:
        for g in globs:
            cmd.extend(["-g", g])
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
        if out.returncode not in (0, 1):
            return 0
        return len([ln for ln in out.stdout.splitlines() if ln.strip()])
    except Exception:
        return 0


def _iso_to_dt(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _fetchone(conn: sqlite3.Connection, sql: str, params: Tuple = ()) -> Tuple:
    row = conn.execute(sql, params).fetchone()
    return row if row is not None else tuple()


def collect_metrics(db_path: Path, hours: int) -> dict:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    from_dt = now - dt.timedelta(hours=hours)
    from_sql = from_dt.strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "jobs_total": 0,
        "jobs_failed": 0,
        "jobs_completed": 0,
        "jobs_rendering": 0,
        "jobs_pending": 0,
        "uploads_total": 0,
        "uploads_recent": 0,
        "top_errors": [],
        "stuck_jobs": [],
        "has_db": db_path.exists(),
    }

    if not db_path.exists():
        return data

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if _table_exists(conn, "video_jobs"):
            data["jobs_total"] = _fetchone(conn, "SELECT COUNT(*) FROM video_jobs")[0]
            data["jobs_failed"] = _fetchone(
                conn, "SELECT COUNT(*) FROM video_jobs WHERE status='failed'"
            )[0]
            data["jobs_completed"] = _fetchone(
                conn, "SELECT COUNT(*) FROM video_jobs WHERE status='completed'"
            )[0]
            data["jobs_rendering"] = _fetchone(
                conn, "SELECT COUNT(*) FROM video_jobs WHERE status='rendering'"
            )[0]
            data["jobs_pending"] = _fetchone(
                conn, "SELECT COUNT(*) FROM video_jobs WHERE status='pending'"
            )[0]

            rows = conn.execute(
                """
                SELECT id, topic, status, started_at, created_at
                FROM video_jobs
                WHERE status IN ('pending','generating','rendering','uploading')
                ORDER BY created_at ASC
                LIMIT 300
                """
            ).fetchall()
            stuck = []
            for r in rows:
                started = _iso_to_dt(r["started_at"]) or _iso_to_dt(r["created_at"])
                if not started:
                    continue
                age_min = (now - started).total_seconds() / 60.0
                if age_min >= 45:
                    stuck.append(
                        {
                            "id": r["id"],
                            "status": r["status"],
                            "age_min": int(age_min),
                            "topic": (r["topic"] or "")[:80],
                        }
                    )
            data["stuck_jobs"] = stuck[:20]

            err_rows = conn.execute(
                """
                SELECT error_message, COUNT(*) AS c
                FROM video_jobs
                WHERE status='failed' AND error_message IS NOT NULL AND TRIM(error_message) != ''
                GROUP BY error_message
                ORDER BY c DESC
                LIMIT 6
                """
            ).fetchall()
            data["top_errors"] = [
                {"count": int(r["c"]), "error": (r["error_message"] or "")[:220]} for r in err_rows
            ]

        if _table_exists(conn, "upload_history"):
            data["uploads_total"] = _fetchone(conn, "SELECT COUNT(*) FROM upload_history")[0]
            data["uploads_recent"] = _fetchone(
                conn,
                "SELECT COUNT(*) FROM upload_history WHERE datetime(uploaded_at) >= datetime(?)",
                (from_sql,),
            )[0]
    finally:
        conn.close()

    return data


def collect_code_scan() -> dict:
    return {
        "broad_except": _run_rg_count(r"except\s+Exception\s+as\s+\w+:"),
        "bare_except": _run_rg_count(r"except\s*:"),
        "todo_count": _run_rg_count(r"\bTODO\b|\bFIXME\b"),
        "pass_count": _run_rg_count(r"^\s*pass\s*$"),
    }


def score_and_findings(metrics: dict, scan: dict) -> Tuple[int, int, List[AuditFinding]]:
    health = 100
    money = 100
    findings: List[AuditFinding] = []

    failed = int(metrics["jobs_failed"])
    completed = int(metrics["jobs_completed"])
    total = max(failed + completed, 1)
    fail_rate = failed / total

    if fail_rate > 0.35:
        health -= 25
        money -= 15
        findings.append(
            AuditFinding(
                "critical",
                "Job fail rate is high",
                f"Failed/completed ratio in DB is {failed}/{completed} ({fail_rate:.1%}).",
                "Stabilize top failure class first (upload metadata, provider timeouts, queue retries).",
            )
        )

    stuck = len(metrics["stuck_jobs"])
    if stuck >= 5:
        health -= 20
        money -= 10
        findings.append(
            AuditFinding(
                "high",
                "Queue has stuck jobs",
                f"{stuck} jobs are running/pending for >45 minutes.",
                "Add stuck-job watchdog + auto-requeue with bounded retries and alert.",
            )
        )

    if metrics["top_errors"]:
        top = metrics["top_errors"][0]
        if "invalid video description" in top["error"].lower():
            health -= 15
            money -= 20
            findings.append(
                AuditFinding(
                    "critical",
                    "YouTube upload metadata still rejected",
                    "Top failure is invalidDescription from YouTube API.",
                    "Add strict fallback path that bypasses AI metadata entirely per retry and log final payload hash.",
                )
            )

    if scan["broad_except"] > 120:
        health -= 10
        findings.append(
            AuditFinding(
                "medium",
                "Too many broad exception handlers",
                f"Found {scan['broad_except']} 'except Exception as ...' blocks.",
                "Replace high-volume hotspots with typed exceptions in upload, LLM, and I/O boundaries.",
            )
        )

    if scan["bare_except"] > 0:
        health -= 8
        findings.append(
            AuditFinding(
                "high",
                "Bare except blocks detected",
                f"Found {scan['bare_except']} bare except blocks.",
                "Remove bare except usage; always capture and log exception class/message.",
            )
        )

    if metrics["uploads_recent"] == 0:
        money -= 12
        findings.append(
            AuditFinding(
                "high",
                "No recent upload throughput",
                "No uploads were recorded in selected window.",
                "Prioritize stable upload path + fallback metadata + alerting to unblock revenue.",
            )
        )

    health = max(0, min(100, health))
    money = max(0, min(100, money))
    findings.sort(key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.level, 9))
    return health, money, findings


def render_report(metrics: dict, scan: dict, health: int, money: int, findings: List[AuditFinding], hours: int) -> str:
    lines = []
    lines.append(f"# Auto-Agent Report ({dt.datetime.now(dt.UTC).isoformat()})")
    lines.append("")
    lines.append("## Scores")
    lines.append(f"- Health score: **{health}/100**")
    lines.append(f"- Monetization score: **{money}/100**")
    lines.append("")
    lines.append(f"## Pipeline Metrics (last {hours}h window for recent uploads)")
    lines.append(f"- Jobs total: {metrics['jobs_total']}")
    lines.append(f"- Jobs completed: {metrics['jobs_completed']}")
    lines.append(f"- Jobs failed: {metrics['jobs_failed']}")
    lines.append(f"- Jobs pending: {metrics['jobs_pending']}")
    lines.append(f"- Jobs rendering: {metrics['jobs_rendering']}")
    lines.append(f"- Uploads total: {metrics['uploads_total']}")
    lines.append(f"- Uploads in window: {metrics['uploads_recent']}")
    lines.append("")
    lines.append("## Code Scan")
    lines.append(f"- broad except handlers: {scan['broad_except']}")
    lines.append(f"- bare except handlers: {scan['bare_except']}")
    lines.append(f"- TODO/FIXME markers: {scan['todo_count']}")
    lines.append(f"- bare pass statements: {scan['pass_count']}")
    lines.append("")

    lines.append("## Top Failure Buckets")
    if metrics["top_errors"]:
        for item in metrics["top_errors"]:
            lines.append(f"- ({item['count']}x) {item['error']}")
    else:
        lines.append("- No failure buckets detected.")
    lines.append("")

    lines.append("## Stuck Jobs (>45m)")
    if metrics["stuck_jobs"]:
        for item in metrics["stuck_jobs"][:10]:
            lines.append(
                f"- {item['id']} | {item['status']} | {item['age_min']}m | {item['topic']}"
            )
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("## Priority Actions")
    if findings:
        for idx, f in enumerate(findings, start=1):
            lines.append(f"{idx}. [{f.level.upper()}] {f.title}")
            lines.append(f"   - Signal: {f.detail}")
            lines.append(f"   - Action: {f.action}")
    else:
        lines.append("1. No critical issues detected. Continue monitoring.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run auto-agent audit loop.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite DB")
    parser.add_argument("--hours", type=int, default=24, help="Recent window in hours")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown report path")
    args = parser.parse_args()

    # Ensure the SQLite schema exists before we audit it.
    try:
        from app.db.engine import init_db
        init_db()
    except Exception:
        pass

    db_path = Path(args.db)
    out_path = Path(args.output)

    metrics = collect_metrics(db_path=db_path, hours=args.hours)
    scan = collect_code_scan()
    health, money, findings = score_and_findings(metrics, scan)
    report = render_report(metrics, scan, health, money, findings, args.hours)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    payload = {
        "health_score": health,
        "monetization_score": money,
        "report_path": str(out_path),
        "top_findings": [f"{f.level}:{f.title}" for f in findings[:5]],
        "metrics": metrics,
        "scan": scan,
        "actions": [
            {
                "level": f.level,
                "title": f.title,
                "detail": f.detail,
                "action": f.action,
            }
            for f in findings
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
