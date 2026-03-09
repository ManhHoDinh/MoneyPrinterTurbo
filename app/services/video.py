import glob
import os
import random
import shutil
import subprocess
import tempfile
from typing import List
from PIL import ImageFont
from loguru import logger
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    afx,
    concatenate_videoclips,
)
from moviepy.video.tools.subtitles import SubtitlesClip

from app.config import config
from app.models.schema import VideoAspect
from app.utils import utils


def get_bgm_file(bgm_name: str = "random"):
    if not bgm_name:
        return ""
    if bgm_name == "random":
        suffix = "*.mp3"
        song_dir = utils.song_dir()
        files = glob.glob(os.path.join(song_dir, suffix))
        return random.choice(files)

    file = os.path.join(utils.song_dir(), bgm_name)
    if os.path.exists(file):
        return file
    return ""


def combine_videos(combined_video_path: str,
                   video_paths: List[str],
                   audio_file: str,
                   video_aspect: VideoAspect = VideoAspect.portrait,
                   max_clip_duration: int = 5,
                   threads: int = 1,
                   ) -> str:
    if not video_paths:
        raise ValueError("no video paths provided for combine_videos")

    logger.info(f"combining {len(video_paths)} videos into one file: {combined_video_path}")
    audio_clip = AudioFileClip(audio_file)
    max_duration = audio_clip.duration
    logger.info(f"max duration of audio: {max_duration} seconds")
    # Required duration of each clip
    req_dur = max_duration / len(video_paths)
    logger.info(f"each clip will be maximum {req_dur} seconds long")

    aspect = VideoAspect(video_aspect)
    video_width, video_height = aspect.to_resolution()

    # Build segment plan first, then render in small chunks to prevent OOM.
    segment_plan = []
    duration_cache = {}
    tot_dur = 0.0
    path_index = 0
    while tot_dur < max_duration:
        video_path = video_paths[path_index % len(video_paths)]
        path_index += 1
        source_duration = duration_cache.get(video_path)
        if source_duration is None:
            probe_clip = VideoFileClip(video_path)
            source_duration = probe_clip.duration
            probe_clip.close()
            duration_cache[video_path] = source_duration

        clip_seconds = min(source_duration, req_dur, max_clip_duration, max_duration - tot_dur)
        if clip_seconds <= 0:
            break
        segment_plan.append((video_path, clip_seconds))
        tot_dur += clip_seconds

    chunk_paths = []
    chunk_size = 6
    encode_opts = _get_ffmpeg_encode_options()

    for start in range(0, len(segment_plan), chunk_size):
        chunk = segment_plan[start:start + chunk_size]
        chunk_clips = []

        for video_path, clip_seconds in chunk:
            clip = VideoFileClip(video_path).without_audio().subclipped(0, clip_seconds)
            if clip.w != video_width or clip.h != video_height:
                clip_ratio = clip.w / clip.h
                video_ratio = video_width / video_height

                if clip_ratio == video_ratio:
                    clip = clip.resized(new_size=(video_width, video_height))
                else:
                    if clip_ratio > video_ratio:
                        scale_factor = video_height / clip.h
                    else:
                        scale_factor = video_width / clip.w

                    new_width = int(clip.w * scale_factor)
                    new_height = int(clip.h * scale_factor)

                    from moviepy import ColorClip
                    background = ColorClip(
                        size=(video_width, video_height), color=(0, 0, 0)
                    ).with_duration(clip.duration)
                    clip_resized = clip.resized(new_size=(new_width, new_height)).with_position("center")
                    clip = CompositeVideoClip([background, clip_resized])

            chunk_clips.append(clip)

        chunk_clip = concatenate_videoclips(chunk_clips, method="chain")
        chunk_path = f"{combined_video_path}.chunk-{len(chunk_paths)}.mp4"
        chunk_clip.write_videofile(
            chunk_path,
            threads=max(1, int(threads or 1)),
            fps=30,
            audio=False,
            preset=encode_opts["preset"],
            bitrate=encode_opts["video_bitrate"],
            ffmpeg_params=encode_opts["ffmpeg_params"],
            logger=None,
        )
        chunk_clip.close()
        for clip in chunk_clips:
            try:
                clip.close()
            except Exception:
                pass
        chunk_paths.append(chunk_path)

    if not chunk_paths:
        audio_clip.close()
        raise ValueError("failed to render combined chunks")

    if len(chunk_paths) == 1:
        shutil.move(chunk_paths[0], combined_video_path)
    else:
        if not _concat_chunks_stream_copy(chunk_paths, combined_video_path):
            final_clips = [VideoFileClip(p).without_audio() for p in chunk_paths]
            final_clip = concatenate_videoclips(final_clips, method="chain")
            logger.info("writing")
            final_clip.write_videofile(
                combined_video_path,
                threads=max(1, int(threads or 1)),
                fps=30,
                audio=False,
                preset=encode_opts["preset"],
                bitrate=encode_opts["video_bitrate"],
                ffmpeg_params=encode_opts["ffmpeg_params"],
                logger=None,
            )
            final_clip.close()
            for clip in final_clips:
                try:
                    clip.close()
                except Exception:
                    pass

    for chunk_path in chunk_paths:
        try:
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
        except Exception:
            pass

    audio_clip.close()
    logger.success("completed")
    return combined_video_path


def wrap_text(text, max_width, font='Arial', fontsize=60):
    font = ImageFont.truetype(font, fontsize)

    def get_text_size(inner_text):
        left, top, right, bottom = font.getbbox(inner_text)
        return right - left, bottom - top

    width, height = get_text_size(text)
    if width <= max_width:
        return text

    logger.warning(f"wrapping text, max_width: {max_width}, text_width: {width}, text: {text}")
    
    _wrapped_lines_ = []

    # If text contains spaces, wrap by words. Otherwise, wrap by characters (for CJK languages).
    has_space = ' ' in text
    words = text.split(' ') if has_space else list(text)
    
    _txt_ = ''
    for word in words:
        if not word and has_space:
            # Preserve multiple spaces if needed, but usually we just collapse them. 
            # In this simple logic, let's keep it clean
            continue
            
        test_line = _txt_ + (' ' if _txt_ and has_space else '') + word
        _width, _height = get_text_size(test_line)
        if _width <= max_width:
            _txt_ = test_line
        else:
            if _txt_:
                _wrapped_lines_.append(_txt_)
                _txt_ = word
            else:
                _wrapped_lines_.append(word)
                _txt_ = ''
                
    if _txt_:
        _wrapped_lines_.append(_txt_)
        
    return '\n'.join(_wrapped_lines_)


def generate_video(video_path: str,
                   audio_path: str,
                   subtitle_path: str,
                   output_file: str,
                   video_aspect: VideoAspect = VideoAspect.portrait,

                   threads: int = 2,

                   font_name: str = "",
                   fontsize: int = 60,
                   stroke_color: str = "#000000",
                   stroke_width: float = 1.5,
                   text_fore_color: str = "white",
                   text_background_color: str = "transparent",

                   bgm_file: str = "",

                   subtitle_mode: str = "dynamic",
                   sub_maker=None,
                   ):
    """
    Generate the final video with audio, subtitles, and optional BGM.

    Args:
        subtitle_mode: "dynamic" for word-by-word Hormozi-style highlighting,
                       "static" for traditional SubtitlesClip rendering.
        sub_maker: voice.SubMaker object with word-level timestamps.
                   Required for dynamic mode; falls back to SRT if absent.
    """
    aspect = VideoAspect(video_aspect)
    video_width, video_height = aspect.to_resolution()

    logger.info(f"start, video size: {video_width} x {video_height}")
    logger.info(f"  â‘  video: {video_path}")
    logger.info(f"  â‘¡ audio: {audio_path}")
    logger.info(f"  â‘¢ subtitle: {subtitle_path}")
    logger.info(f"  â‘£ output: {output_file}")
    logger.info(f"  â‘¤ subtitle_mode: {subtitle_mode}")

    output_dir = os.path.dirname(output_file)

    if not font_name:
        font_name = "STHeitiMedium.ttc"
    font_path = os.path.join(utils.font_dir(), font_name)
    if os.name == "nt":
        font_path = font_path.replace("\\", "/")
    logger.info(f"using font: {font_path}")

    video_clip = VideoFileClip(video_path).without_audio()
    audio_clip = AudioFileClip(audio_path)
    bgm_clip = None
    clips = [video_clip]


    # â”€â”€ Subtitle Rendering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    subtitle_added = False

    if subtitle_mode == "dynamic":
        try:
            from app.services.dynamic_subtitle import (
                create_subtitle_clip_from_submaker,
                create_subtitle_clip_from_srt,
            )

            dynamic_clip = None

            # Priority 1: Use SubMaker word-level timings (best quality)
            if sub_maker is not None:
                logger.info("dynamic subtitles: using SubMaker word timings")
                dynamic_clip = create_subtitle_clip_from_submaker(
                    sub_maker=sub_maker,
                    video_width=video_width,
                    video_height=video_height,
                    font_path=font_path,
                    font_size=fontsize,
                    normal_color=text_fore_color if text_fore_color != "white" else "#FFFFFF",
                    active_color="#FFD700",
                    stroke_color=stroke_color,
                    stroke_width=int(stroke_width),
                )

            # Priority 2: Fall back to SRT-based approximation
            if dynamic_clip is None and subtitle_path and os.path.exists(subtitle_path):
                logger.info("dynamic subtitles: falling back to SRT-based timings")
                dynamic_clip = create_subtitle_clip_from_srt(
                    srt_path=subtitle_path,
                    video_width=video_width,
                    video_height=video_height,
                    font_path=font_path,
                    font_size=fontsize,
                    normal_color=text_fore_color if text_fore_color != "white" else "#FFFFFF",
                    active_color="#FFD700",
                    stroke_color=stroke_color,
                    stroke_width=int(stroke_width),
                )

            if dynamic_clip is not None:
                clips.append(dynamic_clip)
                subtitle_added = True
                logger.success("dynamic subtitle clip added successfully")

        except Exception as e:
            logger.warning(f"dynamic subtitle failed, falling back to static: {e}")

    # Fallback: Static subtitles (original behavior)
    if not subtitle_added and subtitle_path and os.path.exists(subtitle_path):
        logger.info("using static subtitle rendering (SubtitlesClip)")

        def generator(txt):
            wrapped_txt = wrap_text(txt, max_width=video_width - 100,
                                    font=font_path,
                                    fontsize=fontsize)
            _bg_color = text_background_color if text_background_color and text_background_color != "transparent" else None
            return TextClip(
                text=wrapped_txt,
                font=font_path,
                font_size=int(fontsize),
                color=text_fore_color,
                bg_color=_bg_color,
                stroke_color=stroke_color,
                stroke_width=int(stroke_width),
            )

        position_height = video_height - 200
        if video_aspect == VideoAspect.landscape:
            position_height = video_height - 100

        subtitles = SubtitlesClip(subtitle_path, make_textclip=generator, encoding="utf-8")
        clips.append(subtitles.with_position(lambda _t: ('center', position_height)))

    # Build the composed video timeline before post-processing/effects.
    result = CompositeVideoClip(clips).with_audio(audio_clip)

    # â”€â”€ Anti-Fingerprinting (Micro-Mutations) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Apply imperceptible changes to the video to ensure a unique MD5 hash
    try:
        if hasattr(result, "fx"):
            from moviepy import vfx
            gamma_shift = random.uniform(0.99, 1.01)
            result = result.fx(vfx.GammaCorrection, gamma=gamma_shift)
            logger.info(f"Applied anti-fingerprinting mutations: gamma={gamma_shift:.3f}")
        else:
            logger.debug("anti-fingerprinting skipped: clip.fx not available")
    except Exception as e:
        logger.warning(f"Anti-fingerprinting failed: {e}")

    if bgm_file:
        try:
            logger.info(f"adding background music: {bgm_file}")
            bgm_clip = AudioFileClip(bgm_file).with_effects([
                afx.MultiplyVolume(0.2),
                afx.AudioFadeOut(3),
                afx.AudioLoop(duration=result.duration),
            ])
            result = result.with_audio(CompositeAudioClip([audio_clip, bgm_clip]))
        except Exception as e:
            logger.error(f"failed to add bgm: {str(e)}")

    logger.info(f"encoding audio codec to aac")
    encode_opts = _get_ffmpeg_encode_options()
    temp_audio_file = os.path.join(
        output_dir, f".{os.path.basename(output_file)}.temp-audio.m4a"
    )
    result.write_videofile(
        output_file,
        audio_codec="aac",
        temp_audiofile=temp_audio_file,
        remove_temp=True,
        threads=threads or 2,
        preset=encode_opts["preset"],
        bitrate=encode_opts["video_bitrate"],
        audio_bitrate=encode_opts["audio_bitrate"],
        ffmpeg_params=encode_opts["ffmpeg_params"],
        logger=None,
        fps=30,
    )
    result.close()
    video_clip.close()
    audio_clip.close()
    if bgm_clip is not None:
        try:
            bgm_clip.close()
        except Exception:
            pass
    del result
    logger.success(f"completed")


def _get_ffmpeg_encode_options() -> dict:
    preset = str(config.app.get("ffmpeg_preset", "veryfast") or "veryfast")
    video_bitrate = str(config.app.get("ffmpeg_video_bitrate", "3000k") or "3000k")
    audio_bitrate = str(config.app.get("ffmpeg_audio_bitrate", "128k") or "128k")
    crf = config.app.get("ffmpeg_crf", 24)

    ffmpeg_params = ["-movflags", "+faststart"]
    try:
        if crf is not None:
            ffmpeg_params.extend(["-crf", str(int(crf))])
    except Exception:
        pass

    return {
        "preset": preset,
        "video_bitrate": video_bitrate,
        "audio_bitrate": audio_bitrate,
        "ffmpeg_params": ffmpeg_params,
    }


def _concat_chunks_stream_copy(chunk_paths: List[str], output_path: str) -> bool:
    """
    Join homogeneous chunk files with ffmpeg stream copy to avoid an extra re-encode.
    """
    if len(chunk_paths) < 2:
        return False

    list_file = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            list_file = tmp.name
            for path in chunk_paths:
                escaped = path.replace("'", "'\\''")
                tmp.write(f"file '{escaped}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and os.path.exists(output_path):
            logger.info("merged chunk videos using ffmpeg stream copy")
            return True
        logger.warning(f"ffmpeg stream-copy concat failed, fallback to moviepy: {proc.stderr[-400:]}")
        return False
    except Exception as e:
        logger.warning(f"ffmpeg stream-copy concat exception: {e}")
        return False
    finally:
        if list_file and os.path.exists(list_file):
            try:
                os.remove(list_file)
            except Exception:
                pass
