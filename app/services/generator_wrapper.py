"""
Video Generator Wrapper — Black-box interface to the existing video pipeline.

This wrapper NEVER modifies the underlying generator logic. It acts as a clean
adapter that:
  1. Accepts a GeneratorInput config
  2. Translates it into VideoParams
  3. Calls the existing `task.start()` as an opaque subprocess
  4. Locates the rendered output and returns a GeneratorResult

Usage:
    from app.services.generator_wrapper import generate_video
    result = generate_video(GeneratorInput(
        job_id="abc-123",
        topic="5 Dark Psychology Tricks",
        style="dark_psychology",
        channel_id="ch-xyz",
        language="en",
    ))
    if result.success:
        print(result.video_path)
"""

import glob
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from loguru import logger


# ── Input / Output Contracts ─────────────────────────────────────────────────

@dataclass
class GeneratorInput:
    """Configuration accepted by the wrapper. All the outside world needs."""
    job_id: str
    topic: str
    style: str = ""
    channel_id: str = ""
    language: str = "en"
    video_aspect: str = "9:16"       # portrait by default (Shorts/Reels)
    video_count: int = 1
    video_clip_duration: int = 3
    voice_name: str = "en-US-EricNeural-Male"
    voice_rate: float = 1.0
    bgm_type: str = "random"
    subtitle_enabled: bool = True
    subtitle_position: str = "bottom"
    enable_hook_generator: bool = False
    enable_viral_rewrite: bool = False
    apply_style_mutation: bool = False
    apply_channel_dna: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratorResult:
    """What the wrapper returns — no internals leak out."""
    success: bool
    video_path: str = ""
    task_id: str = ""
    duration_seconds: float = 0.0
    error: str = ""


# ── Wrapper Implementation ───────────────────────────────────────────────────

def generate_video(cfg: GeneratorInput) -> GeneratorResult:
    """
    Run the full video generation pipeline as a black-box operation.

    Steps:
      1. Build VideoParams from GeneratorInput
      2. Apply style preset (tone, pacing, visuals)
      3. Apply channel DNA (differentiation layer)
      4. Invoke the existing generator: task.start()
      5. Locate output video files
      6. Return GeneratorResult

    The existing generator is NEVER modified — only called.
    """
    start_time = time.time()
    task_id = cfg.job_id
    from app.services.job_logger import job_log

    try:
        # ── Step 1: Build VideoParams ────────────────────────────────
        from app.models.schema import VideoParams

        # Resolve voice_name — ensure we never send empty string to TTS
        resolved_voice = cfg.voice_name or _resolve_default_voice(cfg.language)

        params = VideoParams(
            video_subject=cfg.topic,
            video_language=cfg.language,
            video_aspect=cfg.video_aspect,
            video_count=cfg.video_count,
            video_clip_duration=cfg.video_clip_duration,
            voice_name=resolved_voice,
            voice_rate=cfg.voice_rate,
            bgm_type=cfg.bgm_type,
            subtitle_enabled=cfg.subtitle_enabled,
            subtitle_position=cfg.subtitle_position,
            subtitle_mode="static",
            font_name="MicrosoftYaHeiBold.ttc",
            font_size=30,
            enable_hook_generator=cfg.enable_hook_generator,
            enable_viral_rewrite=cfg.enable_viral_rewrite,
            video_style=cfg.style or None,
        )
        job_log(task_id, f"Voice: {resolved_voice}", stage="config")

        # Apply any extra overrides from the caller
        for key, val in cfg.extra_params.items():
            if hasattr(params, key):
                setattr(params, key, val)

        # ── Step 2: Apply style preset ───────────────────────────────
        _apply_style_preset(params, cfg.style)
        job_log(task_id, f"Style preset applied: {cfg.style}", stage="style")

        if cfg.apply_channel_dna and cfg.channel_id:
            _apply_channel_dna(params, cfg.channel_id)
            job_log(task_id, f"Channel DNA applied: {cfg.channel_id[:12]}", stage="channel_dna")

        job_log(task_id, f"Starting pipeline: topic='{cfg.topic[:60]}'", stage="pipeline")
        logger.info(
            f"[GeneratorWrapper] Starting pipeline "
            f"task={task_id} topic='{cfg.topic[:60]}' style={cfg.style}"
        )

        # ── Step 3.5: Apply style mutations (controlled variation) ───
        if cfg.apply_style_mutation:
            _apply_style_mutations(params, cfg.job_id, cfg.style, cfg.channel_id)
            job_log(task_id, "Style mutations applied", stage="mutations")

        # ── Step 4: Call the existing generator ──────────────────────
        job_log(task_id, "Invoking video generator engine...", stage="generating")
        from app.services import task as task_service
        result_dict = task_service.start(task_id=task_id, params=params)

        duration = round(time.time() - start_time, 1)

        if not result_dict:
            # task_service.start() returns None or falsy when it aborts early
            logger.warning(f"[GeneratorWrapper] Pipeline aborted internally for {task_id}")
            return GeneratorResult(
                success=False,
                task_id=task_id,
                duration_seconds=duration,
                error="Pipeline aborted internally (likely quality filter, LLM error, or material download failed)",
            )

        # ── Step 5: Locate output ────────────────────────────────────
        from app.utils import utils
        task_dir = os.path.join(utils.task_dir(), task_id)

        finals = sorted(glob.glob(os.path.join(task_dir, "final-*.mp4")))
        combined = sorted(glob.glob(os.path.join(task_dir, "combined-*.mp4")))
        output_files = finals or combined

        if output_files:
            video_path = output_files[0]
            job_log(task_id, f"✅ Video ready: {os.path.basename(video_path)} ({duration}s)", stage="completed")
            logger.info(
                f"[GeneratorWrapper] ✅ Video ready: {video_path} ({duration}s)"
            )
            return GeneratorResult(
                success=True,
                video_path=video_path,
                task_id=task_id,
                duration_seconds=duration,
            )
        else:
            job_log(task_id, f"⚠️ No output files found in {task_dir}", level="WARNING", stage="failed")
            logger.warning(f"[GeneratorWrapper] No output files in {task_dir} despite pipeline success")
            return GeneratorResult(
                success=False,
                task_id=task_id,
                duration_seconds=duration,
                error="No output video files found after generation",
            )

    except Exception as e:
        duration = round(time.time() - start_time, 1)
        logger.error(f"[GeneratorWrapper] ❌ Pipeline failed ({duration}s): {e}")
        return GeneratorResult(
            success=False,
            task_id=task_id,
            duration_seconds=duration,
            error=str(e)[:500],
        )


# ── Internal Helpers (never exposed) ─────────────────────────────────────────

def _apply_style_preset(params, style: str):
    """Inject style preset tone into the video subject for LLM processing."""
    if not style:
        return
    try:
        from app.services.style_presets import get_preset, get_pacing, get_visual_profile

        preset = get_preset(style)
        if not preset:
            return

        # Inject script tone
        tone = preset.get("script_tone", "")
        if tone:
            params.video_subject = f"[{tone[:250]}] {params.video_subject}"

        # Apply pacing overrides
        pacing = get_pacing(style)
        if pacing:
            if pacing.get("max_scene_duration"):
                params.video_clip_duration = int(pacing["max_scene_duration"])
            if pacing.get("transition_style") == "hard_cut":
                params.video_transition_mode = None
            elif pacing.get("transition_style") == "fade":
                from app.models.schema import VideoTransitionMode
                params.video_transition_mode = VideoTransitionMode.fade_in

        # Apply visual profile
        vis = get_visual_profile(style)
        if vis and vis.get("search_modifiers"):
            # Feed search modifiers to video terms for better stock footage
            existing = params.video_terms or []
            if isinstance(existing, str):
                existing = [existing]
            params.video_terms = existing + vis["search_modifiers"][:3]

        logger.debug(f"[GeneratorWrapper] Applied style preset: {style}")

    except Exception as e:
        logger.warning(f"[GeneratorWrapper] Style preset '{style}' apply failed: {e}")


def _apply_channel_dna(params, channel_id: str):
    """Apply channel-specific differentiation overrides."""
    try:
        from app.services.channel_dna import apply_channel_dna
        apply_channel_dna(params, channel_id)
        logger.debug(f"[GeneratorWrapper] Applied channel DNA: {channel_id[:8]}")
    except Exception as e:
        logger.warning(f"[GeneratorWrapper] Channel DNA apply failed: {e}")


def _apply_style_mutations(params, job_id: str, style: str, channel_id: str):
    """Apply controlled random mutations for content uniqueness."""
    try:
        from app.services.style_mutation import mutate_params
        vector = mutate_params(
            params,
            job_id=job_id,
            style=style,
            channel_id=channel_id,
        )
        if vector.mutations:
            logger.info(f"[GeneratorWrapper] Mutations: {vector.summary()}")
    except Exception as e:
        logger.warning(f"[GeneratorWrapper] Style mutation failed: {e}")


def _resolve_default_voice(language: str) -> str:
    """
    Resolve a default TTS voice based on language.

    Prevents the 'Invalid voice' error that occurs when voice_name is empty.
    """
    voice_map = {
        "en": "en-US-EricNeural-Male",
        "zh": "zh-CN-XiaoxiaoNeural-Female",
        "vi": "vi-VN-HoaiMyNeural-Female",
        "ja": "ja-JP-NanamiNeural-Female",
        "ko": "ko-KR-SunHiNeural-Female",
        "fr": "fr-FR-DeniseNeural-Female",
        "de": "de-DE-KatjaNeural-Female",
        "es": "es-ES-ElviraNeural-Female",
        "pt": "pt-BR-FranciscaNeural-Female",
        "id": "id-ID-GadisNeural-Female",
        "th": "th-TH-PremwadeeNeural-Female",
    }
    # Match by prefix (e.g., "en" from "en-US")
    lang_prefix = language.split("-")[0].lower() if language else "en"
    return voice_map.get(lang_prefix, "en-US-EricNeural-Male")
