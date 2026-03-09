#!/usr/bin/env python3
"""
Apply safe, deterministic source-code fix recipes.

This script is idempotent: it only patches known legacy patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ReplaceRecipe:
    name: str
    file_path: Path
    old: str
    new: str


def _apply_replace(recipe: ReplaceRecipe) -> dict:
    if not recipe.file_path.exists():
        return {"name": recipe.name, "status": "missing_file"}

    content = recipe.file_path.read_text(encoding="utf-8")
    if recipe.new in content:
        return {"name": recipe.name, "status": "already_fixed"}
    if recipe.old not in content:
        return {"name": recipe.name, "status": "pattern_not_found"}

    updated = content.replace(recipe.old, recipe.new)
    recipe.file_path.write_text(updated, encoding="utf-8")
    return {"name": recipe.name, "status": "patched"}


def main() -> int:
    recipes = [
        ReplaceRecipe(
            name="worker_upload_retry_from_failed",
            file_path=ROOT / "app" / "worker" / "tasks.py",
            old=(
                "        if job.status != \"completed\" or not job.video_path:\n"
                "            return {\"status\": \"error\", \"message\": \"Job not ready for upload\"}\n"
            ),
            new=(
                "        if not job.video_path:\n"
                "            return {\"status\": \"error\", \"message\": \"Job not ready for upload\"}\n"
                "        # Allow retry upload from `failed` state if render already exists.\n"
                "        if job.status not in (\"completed\", \"failed\"):\n"
                "            return {\"status\": \"error\", \"message\": f\"Job status '{job.status}' is not uploadable\"}\n"
            ),
        ),
        ReplaceRecipe(
            name="task_bgm_signature_fix",
            file_path=ROOT / "app" / "services" / "task.py",
            old="            bgm_file = video.get_bgm_file(params.bgm_type, params.bgm_file)\n",
            new="            bgm_file = _resolve_bgm_file(params)\n",
        ),
        ReplaceRecipe(
            name="auto_agent_recent_uploads_sql_fix",
            file_path=ROOT / "scripts" / "auto_agent.py",
            old=(
                "            data[\"uploads_recent\"] = _fetchone(\n"
                "                conn, \"SELECT COUNT(*) FROM upload_history WHERE uploaded_at >= ?\",\n"
                "                (from_iso,),\n"
                "            )[0]\n"
            ),
            new=(
                "            data[\"uploads_recent\"] = _fetchone(\n"
                "                conn,\n"
                "                \"SELECT COUNT(*) FROM upload_history WHERE datetime(uploaded_at) >= datetime(?)\",\n"
                "                (from_sql,),\n"
                "            )[0]\n"
            ),
        ),
    ]

    results = [_apply_replace(r) for r in recipes]
    patched = sum(1 for r in results if r["status"] == "patched")
    print(json.dumps({"patched": patched, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
