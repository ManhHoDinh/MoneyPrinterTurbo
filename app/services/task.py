import math
import os
import os.path
import random
import re
from os import path

from loguru import logger

from app.config import config
from app.models import const
from app.models.schema import VideoConcatMode, VideoParams
from app.services import llm, material, subtitle, video, voice, engagement, style_presets
from app.services import state as sm
from app.services import scene_analyzer, cinematic_flow
from app.services.cinematic_flow import build_visual_arc, enforce_emotional_arc
from app.services import hook_generator, viral_story, retention_optimizer
from app.services import feedback_loop
# GOD ELITE COS imports
from app.services import content_genome, duplicate_avoidance, loop_addiction
from app.services import channel_dna as channel_dna_module
from app.services import viral_score as viral_score_module
from app.services import anti_fingerprint, viral_archetypes
from app.utils import utils


def _resolve_bgm_file(params) -> str:
    """
    Resolve the BGM file path from request params.

    Priority:
      1) explicit `bgm_file` if provided
      2) `bgm_type` (e.g. "random")
    """
    explicit = (getattr(params, "bgm_file", "") or "").strip()
    bgm_type = (getattr(params, "bgm_type", "random") or "random").strip()
    requested = explicit or bgm_type
    if not requested:
        return ""
    return video.get_bgm_file(requested)


def _fallback_script_from_subject(subject: str) -> str:
    clean_subject = (subject or "this behavior").strip()
    return (
        f"You think {clean_subject} is your choice. "
        "It is often social pressure in disguise. "
        "Your brain copies the group to feel safe. "
        "That is useful for survival, but dangerous for decisions. "
        "You buy what feels popular, not always what is right. "
        "Notice the pattern in your last choice. "
        "Did you choose for yourself, or for approval? "
        "Comment your answer below."
    )


def generate_script(task_id, params):
    logger.info("\n\n## generating video script")
    video_script = params.video_script.strip()
    if not video_script:
        video_script = llm.generate_script(
            video_subject=params.video_subject,
            language=params.video_language,
            paragraph_number=params.paragraph_number,
            video_style=params.video_style or "",
        )
    if video_script and "Error: " in video_script:
        logger.warning("LLM script generation failed, using deterministic fallback script")
        video_script = _fallback_script_from_subject(params.video_subject)
    else:
        logger.debug(f"video script: \n{video_script}")

    if not video_script:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("failed to generate video script.")
        return None

    # Post-process with engagement optimizer
    video_script = engagement.optimize_script(video_script, params.video_style)

    # GOD MODE: Elite script structure enforcement
    try:
        video_script = viral_story.enforce_script_structure(
            video_script, params.video_style or ""
        )
        logger.info("elite script psychology structure enforced")
    except Exception as e:
        logger.warning(f"script structure enforcement failed: {e}")

    # Elite: Viral story rewrite (open loops + pattern interrupts + comment bait)
    if getattr(params, 'enable_viral_rewrite', True):
        try:
            video_script = viral_story.rewrite_for_virality(
                video_script, params.video_style or ""
            )
            logger.info("viral story rewrite applied")
        except Exception as e:
            logger.warning(f"viral story rewrite failed: {e}")

    # GOD ELITE: Loop addiction design (callbacks + unresolved endings + moral tension)
    try:
        video_script = loop_addiction.apply_loop_addiction(
            video_script, style=params.video_style or ""
        )
        logger.info("loop addiction design applied")
    except Exception as e:
        logger.warning(f"loop addiction failed: {e}")

    # GOD MODE: Engagement trifecta (polarizing + question + incomplete conclusion)
    try:
        video_script = engagement.ensure_engagement_trifecta(
            video_script,
            video_subject=params.video_subject,
            style_name=params.video_style,
        )
        logger.info("engagement trifecta enforced")
    except Exception as e:
        logger.warning(f"engagement trifecta failed: {e}")

    # GOD MODE: Hook A/B variant generation + selection
    if getattr(params, 'enable_ab_hooks', False):
        try:
            variants = hook_generator.generate_hook_variants(
                video_subject=params.video_subject,
                video_style=params.video_style or "",
                variant_count=5,
            )
            # Use feedback weights if available
            feedback_weights = feedback_loop.adjust_hook_weights()
            best_hook = hook_generator.select_best_hook(
                variants, feedback_weights=feedback_weights
            )
            if best_hook and best_hook.get("hook_text"):
                # Prepend the selected hook to the script
                video_script = best_hook["hook_text"] + "\n\n" + video_script
                logger.info(
                    f"A/B hook selected: type={best_hook['psych_type']}, "
                    f"text='{best_hook['hook_text'][:50]}...'"
                )
        except Exception as e:
            logger.warning(f"A/B hook generation failed: {e}")

    return video_script


def generate_terms(task_id, params, video_script):
    logger.info("\n\n## generating video terms")
    video_terms = params.video_terms
    if not video_terms:
        video_terms = llm.generate_terms(
            video_subject=params.video_subject, video_script=video_script, amount=5
        )

    if isinstance(video_terms, str):
        normalized = (
            video_terms.replace("\r", "\n")
            .replace("，", ",")
            .replace(";", ",")
            .replace("|", ",")
        )
        parts = re.split(r"[\n,]+", normalized)
        video_terms = [p.strip(" -\"'") for p in parts if p and p.strip(" -\"'")]
    elif isinstance(video_terms, list):
        video_terms = [str(term).strip() for term in video_terms if str(term).strip()]
    else:
        raise ValueError("video_terms must be a string or a list of strings.")

    video_terms = video_terms[:5]

    # If LLM returned an error blob/string, fall back to deterministic keywords.
    if video_terms:
        first_term = str(video_terms[0]).strip().lower()
        if first_term.startswith("error:") or first_term.startswith("http") or first_term.startswith("{"):
            fallback_terms = [
                params.video_subject,
                "crowd behavior",
                "social influence",
                "decision making",
                "human psychology",
            ]
            video_terms = [t.strip() for t in fallback_terms if t and t.strip()][:5]
            logger.warning(f"video terms fallback activated: {utils.to_json(video_terms)}")
    logger.debug(f"video terms: {utils.to_json(video_terms)}")

    if not video_terms:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("failed to generate video terms.")
        return None

    return video_terms


def analyze_script_scenes(task_id, params, video_script):
    """Analyze script into emotion-tagged scenes for cinematic visual matching."""
    if not params.video_style:
        return None

    logger.info("\n\n## analyzing script scenes (emotion-aware)")
    try:
        scenes = scene_analyzer.analyze_scenes(
            script=video_script,
            video_subject=params.video_subject,
            video_style=params.video_style or "",
        )
        if scenes:
            logger.success(f"analyzed {len(scenes)} emotion-tagged scenes")
            # Apply visual story arc to smooth intensity progression
            scenes = build_visual_arc(scenes)
            # Elite: Enforce complete emotional arc
            scenes = enforce_emotional_arc(scenes)
            # Elite: Enhance hook visuals
            if getattr(params, 'enable_hook_generator', True):
                try:
                    scenes = hook_generator.enhance_hook_visuals(scenes)
                except Exception as e:
                    logger.warning(f"hook visual enhancement failed: {e}")
            for s in scenes:
                logger.info(f"  scene {s.scene_index}: [{s.emotion} {s.intensity:.1f}] role={s.narrative_role} shot={s.shot_type} → '{s.search_query}'")
            return scenes
    except Exception as e:
        logger.error(f"scene analysis failed: {e}")

    logger.warning("scene analysis failed, falling back to standard term generation")
    return None


def save_script_data(task_id, video_script, video_terms, params):
    script_file = path.join(utils.task_dir(task_id), "script.json")
    script_data = {
        "script": video_script,
        "search_terms": video_terms,
        "params": params,
    }

    with open(script_file, "w", encoding="utf-8") as f:
        f.write(utils.to_json(script_data))


def generate_audio(task_id, params, video_script):
    '''
    Generate audio for the video script.
    If a custom audio file is provided, it will be used directly.
    There will be no subtitle maker object returned in this case.
    Otherwise, TTS will be used to generate the audio.
    Returns:
        - audio_file: path to the generated or provided audio file
        - audio_duration: duration of the audio in seconds
        - sub_maker: subtitle maker object if TTS is used, None otherwise
    '''
    logger.info("\n\n## generating audio")
    custom_audio_file = params.custom_audio_file
    if not custom_audio_file or not os.path.exists(custom_audio_file):
        if custom_audio_file:
            logger.warning(
                f"custom audio file not found: {custom_audio_file}, using TTS to generate audio."
            )
        else:
            logger.info("no custom audio file provided, using TTS to generate audio.")
        audio_file = path.join(utils.task_dir(task_id), "audio.mp3")
        sub_maker = voice.tts(
            text=video_script,
            voice_name=voice.parse_voice_name(params.voice_name),
            voice_rate=params.voice_rate,
            voice_file=audio_file,
        )
        if sub_maker is None:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                """failed to generate audio:
1. check if the language of the voice matches the language of the video script.
2. check if the network is available. If you are in China, it is recommended to use a VPN and enable the global traffic mode.
            """.strip()
            )
            return None, None, None
        audio_duration = math.ceil(voice.get_audio_duration(sub_maker))
        if audio_duration == 0:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("failed to get audio duration.")
            return None, None, None
        return audio_file, audio_duration, sub_maker
    else:
        logger.info(f"using custom audio file: {custom_audio_file}")
        audio_duration = voice.get_audio_duration(custom_audio_file)
        if audio_duration == 0:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("failed to get audio duration from custom audio file.")
            return None, None, None
        return custom_audio_file, audio_duration, None

def generate_subtitle(task_id, params, video_script, sub_maker, audio_file):
    '''
    Generate subtitle for the video script.
    If subtitle generation is disabled or no subtitle maker is provided, it will return an empty string.
    Otherwise, it will generate the subtitle using the specified provider.
    Returns:
        - subtitle_path: path to the generated subtitle file
    '''
    logger.info("\n\n## generating subtitle")
    if not params.subtitle_enabled or sub_maker is None:
        return ""

    subtitle_path = path.join(utils.task_dir(task_id), "subtitle.srt")
    subtitle_provider = config.app.get("subtitle_provider", "edge").strip().lower()
    whisper_fallback_enabled = bool(config.app.get("subtitle_whisper_fallback", False))
    logger.info(f"\n\n## generating subtitle, provider: {subtitle_provider}")

    subtitle_fallback = False
    if subtitle_provider == "edge":
        voice.create_subtitle(
            text=video_script, sub_maker=sub_maker, subtitle_file=subtitle_path
        )
        if not os.path.exists(subtitle_path):
            if whisper_fallback_enabled:
                subtitle_fallback = True
                logger.warning("subtitle file not found, fallback to whisper")
            else:
                logger.warning(
                    "subtitle file not found; skipping subtitles (whisper fallback disabled)"
                )

    if subtitle_provider == "whisper" or subtitle_fallback:
        subtitle.create(audio_file=audio_file, subtitle_file=subtitle_path)
        if os.path.exists(subtitle_path):
            logger.info("\n\n## correcting subtitle")
            subtitle.correct(subtitle_file=subtitle_path, video_script=video_script)
        else:
            logger.warning("whisper subtitle generation failed, continuing without subtitles")
            return ""

    subtitle_lines = subtitle.file_to_subtitles(subtitle_path)
    if not subtitle_lines:
        logger.warning(f"subtitle file is invalid: {subtitle_path}")
        return ""

    return subtitle_path


def get_video_materials(task_id, params, video_terms, audio_duration, scenes=None):
    def _fallback_cached_videos():
        cache_dir = utils.storage_dir("cache_videos")
        if not os.path.isdir(cache_dir):
            return []
        candidates = [
            os.path.join(cache_dir, f)
            for f in os.listdir(cache_dir)
            if f.lower().endswith(".mp4")
        ]
        if not candidates:
            return []
        random.shuffle(candidates)
        # Use a small pool for stability and speed.
        return candidates[:12]

    if params.video_source == "local":
        logger.info("\n\n## preprocess local materials")
        materials = video.preprocess_video(
            materials=params.video_materials, clip_duration=params.video_clip_duration
        )
        if not materials:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                "no valid materials found, please check the materials and try again."
            )
            return None
        return [material_info.url for material_info in materials]
    else:
        # Use emotion-aware per-scene search when scenes are available
        if scenes:
            logger.info(f"\n\n## downloading videos with EMOTION-AWARE search ({len(scenes)} scenes)")
            downloaded_videos = material.download_videos_for_scenes(
                task_id=task_id,
                scenes=scenes,
                source=params.video_source,
                video_aspect=params.video_aspect,
                audio_duration=audio_duration * params.video_count,
                max_clip_duration=params.video_clip_duration,
            )
        else:
            logger.info(f"\n\n## downloading videos from {params.video_source}")
            downloaded_videos = material.download_videos(
                task_id=task_id,
                search_terms=video_terms,
                source=params.video_source,
                video_aspect=params.video_aspect,
                video_contact_mode=params.video_concat_mode,
                audio_duration=audio_duration * params.video_count,
                max_clip_duration=params.video_clip_duration,
            )

        if not downloaded_videos:
            fallback_videos = _fallback_cached_videos()
            if fallback_videos:
                logger.warning(
                    f"video source download failed, using cached fallback videos: {len(fallback_videos)} clips"
                )
                return fallback_videos
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error(
                "failed to download videos, maybe the network is not available. if you are in China, please use a VPN."
            )
            return None
        return downloaded_videos


def generate_final_videos(
    task_id, params, downloaded_videos, audio_file, subtitle_path, scenes=None,
    sub_maker=None,
):
    final_video_paths = []
    combined_video_paths = []
    video_concat_mode = (
        params.video_concat_mode if params.video_count == 1 else VideoConcatMode.random
    )
    video_transition_mode = params.video_transition_mode

    # Get pacing config from style preset
    hook_clip_count = 0
    hook_cut_duration = 0
    if params.video_style:
        channel_profile = getattr(params, 'channel_profile', None)
        pacing = style_presets.get_pacing(params.video_style, channel_profile=channel_profile)
        hook_clip_count = 3  # first 3 clips are hook section
        hook_cut_duration = pacing.get("hook_cut_duration", 2)
        logger.info(f"viral pacing enabled: hook={hook_cut_duration}s for first {hook_clip_count} clips")

    # Elite: Beat-sync editing (align cuts to BGM beats)
    beat_timestamps = []
    if getattr(params, 'enable_beat_sync', False) and audio_file:
        try:
            from app.services import beat_sync
            bgm_file = _resolve_bgm_file(params)
            if bgm_file:
                beat_timestamps = beat_sync.detect_beats(bgm_file)
                if beat_timestamps:
                    beat_info = beat_sync.get_beat_intervals(beat_timestamps)
                    logger.info(f"beat sync: detected {len(beat_timestamps)} beats, {beat_info['bpm']:.0f} BPM")
        except Exception as e:
            logger.warning(f"beat sync failed: {e}")

    _progress = 50
    thread_cap = max(1, int(config.app.get("max_render_threads_per_job", 1) or 1))
    render_threads = max(1, min(int(params.n_threads or 1), thread_cap))
    if render_threads != int(params.n_threads or 1):
        logger.info(f"capped render threads to {render_threads} for stability")
    for i in range(params.video_count):
        index = i + 1
        combined_video_path = path.join(
            utils.task_dir(task_id), f"combined-{index}.mp4"
        )
        logger.info(f"\n\n## combining video: {index} => {combined_video_path}")
        video.combine_videos(
            combined_video_path=combined_video_path,
            video_paths=downloaded_videos,
            audio_file=audio_file,
            video_aspect=params.video_aspect,
            max_clip_duration=params.video_clip_duration,
            threads=render_threads,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_path = path.join(utils.task_dir(task_id), f"final-{index}.mp4")

        logger.info(f"\n\n## generating video: {index} => {final_video_path}")
        video.generate_video(
            video_path=combined_video_path,
            audio_path=audio_file,
            subtitle_path=subtitle_path,
            output_file=final_video_path,
            video_aspect=params.video_aspect,
            threads=render_threads,
            font_name=params.font_name,
            fontsize=params.font_size,
            stroke_color=params.stroke_color,
            stroke_width=params.stroke_width,
            text_fore_color=params.text_fore_color,
            text_background_color=params.text_background_color,
            bgm_file=getattr(params, "bgm_file", ""),
            subtitle_mode=getattr(params, "subtitle_mode", "dynamic"),
            sub_maker=sub_maker,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_paths.append(final_video_path)
        combined_video_paths.append(combined_video_path)

    return final_video_paths, combined_video_paths


def start(task_id, params: VideoParams, stop_at: str = "video"):
    logger.info(f"start task: {task_id}, stop_at: {stop_at}")

    # Route all loguru messages from this thread to the task's log buffer
    from app.services.state import set_current_task
    set_current_task(task_id)

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=5)

    if type(params.video_concat_mode) is str:
        params.video_concat_mode = VideoConcatMode(params.video_concat_mode)

    # GOD ELITE: Apply channel DNA if channel_profile is set
    selected_hook_type = ""
    selected_archetype = ""
    try:
        channel_id = getattr(params, 'channel_profile', None)
        if channel_id:
            channel_dna_module.apply_channel_dna(params, channel_id)
            logger.info(f"channel DNA applied: {channel_id}")
    except Exception as e:
        logger.warning(f"channel DNA application failed: {e}")

    # GOD ELITE: Select viral archetype for content structure
    try:
        from app.services.llm import translate_content
        # Translate topic if language is not English
        if params.video_language and params.video_language != "en":
            params.video_subject = translate_content(params.video_subject, params.video_language)
            logger.info(f"translated topic into {params.video_language}: {params.video_subject}")
            
        selected_archetype = viral_archetypes.select_archetype(
            niche=getattr(params, 'video_subject', ''),
        )
        archetype_data = viral_archetypes.apply_archetype(
            selected_archetype,
            topic=getattr(params, 'video_subject', ''),
        )
        selected_hook_type = archetype_data.get('recommended_hook_type', '')
        logger.info(f"viral archetype selected: {selected_archetype}")
    except Exception as e:
        logger.warning(f"archetype selection failed: {e}")

    # 1. Generate script & 2a. analyze with Auto-Fail Filter Loop
    max_retries = 3
    for attempt in range(max_retries):
        video_script = generate_script(task_id, params)
        if not video_script or "Error: " in video_script:
            if attempt == max_retries - 1:
                sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
                return
            continue

        sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=10)

        if stop_at == "script":
            sm.state.update_task(
                task_id, state=const.TASK_STATE_COMPLETE, progress=100, script=video_script
            )
            return {"script": video_script}

        # 2a. Emotion-aware scene analysis (when style is set)
        scenes = analyze_script_scenes(task_id, params, video_script)

        # 2a-bis. Apply viral style learning if reference tags provided
        if scenes and params.reference_style_tags:
            try:
                from app.services.viral_style_learning import create_style_from_tags, apply_learned_style
                style_profile = create_style_from_tags(params.reference_style_tags)
                scenes = apply_learned_style(style_profile, scenes)
                logger.info(f"viral style learning applied: {params.reference_style_tags}")
            except Exception as e:
                logger.warning(f"viral style learning failed: {e}")

        # BLACK OPS: Quality Filter Check
        from app.services.stealth import QualityFilter
        quality = QualityFilter.evaluate_video_quality(params, video_script, scenes)
        if quality["passed"]:
            break
        elif attempt == max_retries - 1:
            logger.error(f"auto-fail forced task rejection: {quality['reason']}")
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            return
        else:
            logger.warning(f"generation rejected ({quality['reason']}), retrying... ({attempt+1}/{max_retries})")
            continue

    # 2b. Generate terms (use scene queries if available, else standard generation)
    video_terms = ""
    if params.video_source != "local":
        if scenes:
            # Extract search terms from scene queries for backward compat
            video_terms = [s.search_query for s in scenes if s.search_query]
            logger.info(f"using {len(video_terms)} emotion-enriched search queries")
        else:
            video_terms = generate_terms(task_id, params, video_script)
            if not video_terms:
                sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
                return

    save_script_data(task_id, video_script, video_terms, params)

    if stop_at == "terms":
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100, terms=video_terms
        )
        return {"script": video_script, "terms": video_terms}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=20)

    # 3. Generate audio
    audio_file, audio_duration, sub_maker = generate_audio(
        task_id, params, video_script
    )
    if not audio_file:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=30)

    if stop_at == "audio":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            audio_file=audio_file,
        )
        return {"audio_file": audio_file, "audio_duration": audio_duration}

    # 4. Generate subtitle
    subtitle_path = generate_subtitle(
        task_id, params, video_script, sub_maker, audio_file
    )

    if stop_at == "subtitle":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            subtitle_path=subtitle_path,
        )
        return {"subtitle_path": subtitle_path}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=40)

    # 5. Get video materials (emotion-aware when scenes available)
    downloaded_videos = get_video_materials(
        task_id, params, video_terms, audio_duration, scenes=scenes
    )
    if not downloaded_videos:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    if stop_at == "materials":
        sm.state.update_task(
            task_id,
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            materials=downloaded_videos,
        )
        return {"materials": downloaded_videos}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=50)

    # Resolve BGM once before rendering so dashboard/web runs always have music when enabled.
    resolved_bgm = _resolve_bgm_file(params)
    if resolved_bgm:
        params.bgm_file = resolved_bgm
        logger.info(f"background music selected: {resolved_bgm}")
    else:
        params.bgm_file = ""
        logger.warning("no background music selected, rendering voice-only audio")

    # 6. Generate final videos
    final_video_paths, combined_video_paths = generate_final_videos(
        task_id, params, downloaded_videos, audio_file, subtitle_path, scenes=scenes,
        sub_maker=sub_maker,
    )

    if not final_video_paths:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    logger.success(
        f"task {task_id} finished, generated {len(final_video_paths)} videos."
    )

    # GOD ELITE: Compute viral score and gate for export
    viral_result = {"viral_score": 0, "grade": "?"}
    try:
        viral_result = viral_score_module.compute_viral_score(
            script=video_script, scenes=scenes
        )
        threshold = getattr(params, 'viral_score_threshold', 0) or 0
        if threshold > 0 and not viral_score_module.gate_for_export(viral_result['viral_score'], threshold):
            logger.warning(f"video below viral threshold ({viral_result['viral_score']:.1f} < {threshold}), marking for review")
        logger.info(f"viral score: {viral_result['viral_score']:.1f} (grade={viral_result['grade']})")
    except Exception as e:
        logger.warning(f"viral score computation failed: {e}")

    # GOD ELITE: Extract and store content genome
    try:
        genome = content_genome.extract_genome(
            task_id=task_id,
            params=params,
            script=video_script,
            scenes=scenes,
            hook_type=selected_hook_type,
            archetype=selected_archetype,
        )
        genome.viral_score = viral_result.get('viral_score', 0)
        store = content_genome._get_store()
        store.save(genome)
        logger.info(f"content genome stored: {genome.genome_id}")
    except Exception as e:
        logger.warning(f"genome storage failed: {e}")

    # GOD ELITE: Record archetype usage
    try:
        if selected_archetype:
            viral_archetypes.record_archetype_usage(
                selected_archetype,
                viral_score=viral_result.get('viral_score', 0),
            )
    except Exception as e:
        logger.warning(f"archetype recording failed: {e}")

    if bool(config.app.get("cleanup_task_intermediates", True)):
        task_root = os.path.abspath(utils.task_dir(task_id))
        removable_paths = list(combined_video_paths)
        removable_paths.extend([audio_file, subtitle_path])
        removed_count = 0
        for file_path in removable_paths:
            if not file_path or not os.path.exists(file_path):
                continue
            abs_path = os.path.abspath(file_path)
            if not abs_path.startswith(task_root):
                continue
            try:
                os.remove(abs_path)
                removed_count += 1
            except Exception as e:
                logger.warning(f"failed to cleanup intermediate file: {abs_path}, {e}")
        if removed_count:
            logger.info(f"cleaned {removed_count} intermediate files for task {task_id}")
        combined_video_paths = []

    kwargs = {
        "videos": final_video_paths,
        "combined_videos": combined_video_paths,
        "script": video_script,
        "terms": video_terms,
        "audio_file": audio_file,
        "audio_duration": audio_duration,
        "subtitle_path": subtitle_path,
        "materials": downloaded_videos,
        "viral_score": viral_result.get('viral_score', 0),
        "viral_grade": viral_result.get('grade', '?'),
    }
    sm.state.update_task(
        task_id, state=const.TASK_STATE_COMPLETE, progress=100, **kwargs
    )
    return kwargs


if __name__ == "__main__":
    task_id = "task_id"
    params = VideoParams(
        video_subject="金钱的作用",
        voice_name="zh-CN-XiaoyiNeural-Female",
        voice_rate=1.0,
    )
    start(task_id, params, stop_at="video")
