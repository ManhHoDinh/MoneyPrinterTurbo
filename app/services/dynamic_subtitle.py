"""
Dynamic Subtitle Engine — Hormozi-Style Word-by-Word Highlighting

Renders word-level highlighted subtitles as MoviePy VideoClips using Pillow
for pixel-perfect per-word control (multi-color, multi-size text in a single frame).

Architecture:
  1. Extract word-level timings from SubMaker or SRT
  2. Group words into display chunks (3-5 words)
  3. Render each frame with Pillow: active word highlighted, others normal
  4. Return a compositable MoviePy VideoClip
"""

import math
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from moviepy import VideoClip

from app.utils import utils


# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class WordTiming:
    """A single word with its exact spoken time range."""
    word: str
    start: float   # seconds
    end: float     # seconds


@dataclass
class WordGroup:
    """A display group of words shown on screen simultaneously."""
    words: List[WordTiming]
    start: float   # earliest word start
    end: float     # latest word end


@dataclass
class DynamicSubtitleConfig:
    """Configuration for the dynamic subtitle renderer."""
    # Layout
    max_words_per_group: int = 4
    video_width: int = 1080
    video_height: int = 1920
    position_y_ratio: float = 0.75  # vertical position (0=top, 1=bottom)

    # Typography
    font_path: str = ""
    font_size: int = 70
    active_scale: float = 1.15       # scale factor for the active word
    word_spacing: int = 18           # horizontal gap between words (pixels)
    line_spacing: int = 12           # vertical gap between lines (pixels)

    # Colors (RGBA)
    normal_color: str = "#FFFFFF"
    active_color: str = "#FFD700"     # Gold / Yellow
    stroke_color: str = "#000000"
    stroke_width: int = 4

    # Shadow
    shadow_offset: Tuple[int, int] = (3, 3)
    shadow_color: str = "#000000"
    shadow_opacity: int = 160        # 0-255

    def __post_init__(self):
        if not self.font_path:
            # Default to Montserrat Black, fallback to BeVietnamPro-Bold
            montserrat = os.path.join(utils.font_dir(), "Montserrat-Black.ttf")
            bevietnam = os.path.join(utils.font_dir(), "BeVietnamPro-Bold.ttf")
            if os.path.exists(montserrat):
                self.font_path = montserrat
            elif os.path.exists(bevietnam):
                self.font_path = bevietnam
            else:
                # Last resort: use any available TTF
                font_dir = utils.font_dir()
                for f in os.listdir(font_dir):
                    if f.endswith((".ttf", ".ttc")):
                        self.font_path = os.path.join(font_dir, f)
                        break


# ── Word Timing Extraction ───────────────────────────────────────────────────


def extract_word_timings_from_submaker(sub_maker) -> List[WordTiming]:
    """
    Extract word-level timings from a voice.SubMaker object.

    SubMaker stores:
      - subs: list of word/fragment strings
      - offset: list of (start_time, end_time) tuples in 100-nanosecond units

    Returns a list of WordTiming with times converted to seconds.
    """
    if not sub_maker or not hasattr(sub_maker, "subs") or not sub_maker.subs:
        logger.warning("SubMaker has no word data")
        return []

    words = []
    for i, (offset, sub_text) in enumerate(zip(sub_maker.offset, sub_maker.subs)):
        start_ns, end_ns = offset
        # Convert from 100-nanosecond units to seconds
        start_s = start_ns / 1e7
        end_s = end_ns / 1e7

        # Clean the word text
        word = sub_text.strip()
        if not word:
            continue

        words.append(WordTiming(word=word, start=start_s, end=end_s))

    logger.info(f"extracted {len(words)} word timings from SubMaker")
    return words


def extract_word_timings_from_srt(srt_path: str) -> List[WordTiming]:
    """
    Extract word-level timings from an SRT file.
    Each SRT block is treated as one "word group" — we approximate
    per-word timing by evenly dividing the block's time range.
    """
    if not srt_path or not os.path.exists(srt_path):
        logger.warning(f"SRT file not found: {srt_path}")
        return []

    words = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        # Parse timestamp line: 00:00:01,000 --> 00:00:03,500
        time_line = lines[1]
        time_match = re.findall(r"(\d+):(\d+):(\d+),(\d+)", time_line)
        if len(time_match) < 2:
            continue

        def _parse_ts(parts):
            h, m, s, ms = [int(x) for x in parts]
            return h * 3600 + m * 60 + s + ms / 1000.0

        block_start = _parse_ts(time_match[0])
        block_end = _parse_ts(time_match[1])

        # Get the text (may be multi-line)
        text = " ".join(lines[2:]).strip()
        text_words = text.split()
        if not text_words:
            continue

        # Distribute time evenly across words
        duration_per_word = (block_end - block_start) / len(text_words)
        for j, w in enumerate(text_words):
            ws = block_start + j * duration_per_word
            we = ws + duration_per_word
            words.append(WordTiming(word=w, start=ws, end=we))

    logger.info(f"extracted {len(words)} word timings from SRT: {srt_path}")
    return words


# ── Word Grouping ────────────────────────────────────────────────────────────


def group_words(words: List[WordTiming], max_words: int = 4) -> List[WordGroup]:
    """
    Chunk a list of WordTimings into display groups.

    Each group contains up to `max_words` words. Groups inherit
    the start time of the first word and the end time of the last.
    """
    if not words:
        return []

    groups = []
    for i in range(0, len(words), max_words):
        chunk = words[i : i + max_words]
        group = WordGroup(
            words=chunk,
            start=chunk[0].start,
            end=chunk[-1].end,
        )
        groups.append(group)

    logger.info(f"created {len(groups)} word groups (max {max_words} words each)")
    return groups


# ── Frame Rendering ──────────────────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert '#RRGGBB' to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Convert '#RRGGBB' to (R, G, B, A) tuple."""
    r, g, b = _hex_to_rgb(hex_color)
    return (r, g, b, alpha)


def _measure_word(word: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """Measure the bounding box of a word."""
    bbox = font.getbbox(word)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    position: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple,
    stroke_color: Tuple,
    stroke_width: int,
    shadow_offset: Tuple[int, int] = None,
    shadow_color: Tuple = None,
):
    """Draw text with stroke outline and optional drop shadow."""
    x, y = position

    # Draw shadow first (behind everything)
    if shadow_offset and shadow_color:
        sx, sy = shadow_offset
        draw.text(
            (x + sx, y + sy), text, font=font, fill=shadow_color,
        )

    # Draw stroke (outline) by drawing text offset in 8 directions
    if stroke_width > 0:
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx == 0 and dy == 0:
                    continue
                if abs(dx) + abs(dy) > stroke_width * 1.5:
                    continue  # Skip corners for smoother stroke
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)

    # Draw the main text
    draw.text((x, y), text, font=font, fill=fill)


def render_word_group_frame(
    group: WordGroup,
    current_time: float,
    config: DynamicSubtitleConfig,
) -> np.ndarray:
    """
    Render a single subtitle frame for a word group at `current_time`.

    Returns an RGBA numpy array of size (video_height, video_width, 4).
    Only the subtitle area is non-transparent.
    """
    # Create transparent RGBA image
    img = Image.new("RGBA", (config.video_width, config.video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        base_font = ImageFont.truetype(config.font_path, config.font_size)
        active_font_size = int(config.font_size * config.active_scale)
        active_font = ImageFont.truetype(config.font_path, active_font_size)
    except Exception as e:
        logger.error(f"failed to load font {config.font_path}: {e}")
        return np.array(img)

    normal_color = _hex_to_rgba(config.normal_color)
    active_color = _hex_to_rgba(config.active_color)
    stroke_color = _hex_to_rgba(config.stroke_color)
    shadow_color = _hex_to_rgba(config.shadow_color, config.shadow_opacity)

    # Determine which word is currently active
    active_idx = -1
    for i, wt in enumerate(group.words):
        if wt.start <= current_time < wt.end:
            active_idx = i
            break
    # If no word is exactly active, find the closest one that has started
    if active_idx == -1:
        for i, wt in enumerate(group.words):
            if current_time >= wt.start:
                active_idx = i

    # --- Layout Phase: Calculate positions ---
    # We may need to wrap words across multiple lines
    max_line_width = int(config.video_width * 0.85)

    # Build layout: list of lines, each line is a list of (word_idx, word, font, is_active)
    lines = []
    current_line = []
    current_line_width = 0

    for i, wt in enumerate(group.words):
        is_active = (i == active_idx)
        font = active_font if is_active else base_font
        w, h = _measure_word(wt.word, font)

        test_width = current_line_width + w
        if current_line:
            test_width += config.word_spacing

        if test_width > max_line_width and current_line:
            lines.append(current_line)
            current_line = []
            current_line_width = 0

        current_line.append((i, wt.word, font, is_active, w, h))
        current_line_width += w + (config.word_spacing if current_line_width > 0 else 0)

    if current_line:
        lines.append(current_line)

    # Calculate total text block height
    line_heights = []
    for line in lines:
        max_h = max(item[5] for item in line)
        line_heights.append(max_h)

    total_height = sum(line_heights) + config.line_spacing * (len(lines) - 1)
    start_y = int(config.video_height * config.position_y_ratio) - total_height // 2

    # --- Draw Phase ---
    y_cursor = start_y
    for line_idx, line in enumerate(lines):
        # Calculate line width for centering
        line_width = sum(item[4] for item in line) + config.word_spacing * (len(line) - 1)
        x_cursor = (config.video_width - line_width) // 2

        line_h = line_heights[line_idx]

        for item_idx, (word_idx, word, font, is_active, w, h) in enumerate(line):
            color = active_color if is_active else normal_color

            # Vertically center each word within the line
            y_offset = y_cursor + (line_h - h) // 2

            _draw_text_with_stroke(
                draw=draw,
                position=(x_cursor, y_offset),
                text=word,
                font=font,
                fill=color,
                stroke_color=stroke_color,
                stroke_width=config.stroke_width,
                shadow_offset=config.shadow_offset,
                shadow_color=shadow_color,
            )

            x_cursor += w + config.word_spacing

        y_cursor += line_h + config.line_spacing

    return np.array(img)


# ── VideoClip Factory ────────────────────────────────────────────────────────


def create_dynamic_subtitle_clip(
    word_timings: List[WordTiming],
    video_width: int = 1080,
    video_height: int = 1920,
    config: Optional[DynamicSubtitleConfig] = None,
) -> Optional[VideoClip]:
    """
    Create a full MoviePy VideoClip with dynamic word-by-word highlighting.

    This is the main entry point. It:
      1. Groups words into display chunks
      2. Creates a frame-generating function
      3. Returns a transparent-background VideoClip for compositing

    Args:
        word_timings: List of WordTiming objects with exact per-word timing
        video_width: Target video width in pixels
        video_height: Target video height in pixels
        config: Optional rendering configuration

    Returns:
        A MoviePy VideoClip with RGBA frames, or None if no timings
    """
    if not word_timings:
        logger.warning("no word timings provided, skipping dynamic subtitle")
        return None

    if config is None:
        config = DynamicSubtitleConfig()

    config.video_width = video_width
    config.video_height = video_height

    # Group words
    groups = group_words(word_timings, max_words=config.max_words_per_group)
    if not groups:
        return None

    total_duration = max(g.end for g in groups)

    # Pre-compute: map each time point to its active group
    # This avoids searching through all groups every frame
    def _find_group(t: float) -> Optional[WordGroup]:
        for g in groups:
            if g.start <= t < g.end:
                return g
        # If past all groups, show the last group briefly
        if t >= groups[-1].end and t < groups[-1].end + 0.3:
            return groups[-1]
        return None

    # Cache for rendered frames (keyed by group index + active word index)
    _frame_cache = {}

    def make_frame(t):
        """Generate a single RGBA frame at time t."""
        group = _find_group(t)
        if group is None:
            # Return transparent frame
            return np.zeros((video_height, video_width, 4), dtype=np.uint8)

        # Determine active word index for caching
        active_idx = -1
        for i, wt in enumerate(group.words):
            if wt.start <= t < wt.end:
                active_idx = i
                break
        if active_idx == -1:
            for i, wt in enumerate(group.words):
                if t >= wt.start:
                    active_idx = i

        # Cache key: group start + active word index
        cache_key = (group.start, active_idx)
        if cache_key not in _frame_cache:
            _frame_cache[cache_key] = render_word_group_frame(group, t, config)

        return _frame_cache[cache_key]

    # Create the VideoClip
    clip = VideoClip(
        frame_function=make_frame,
        duration=total_duration,
    )

    logger.success(
        f"dynamic subtitle clip created: {len(groups)} groups, "
        f"{len(word_timings)} words, {total_duration:.1f}s duration"
    )

    return clip


# ── Convenience: End-to-End from SubMaker ────────────────────────────────────


def create_subtitle_clip_from_submaker(
    sub_maker,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str = "",
    font_size: int = 70,
    normal_color: str = "#FFFFFF",
    active_color: str = "#FFD700",
    stroke_color: str = "#000000",
    stroke_width: int = 4,
    max_words: int = 4,
    position_y_ratio: float = 0.75,
) -> Optional[VideoClip]:
    """
    High-level convenience function: SubMaker -> Dynamic Subtitle VideoClip.

    This is the function called from video.py's generate_video().
    """
    word_timings = extract_word_timings_from_submaker(sub_maker)
    if not word_timings:
        logger.warning("no word timings from SubMaker, falling back to SRT if available")
        return None

    config = DynamicSubtitleConfig(
        font_path=font_path,
        font_size=font_size,
        normal_color=normal_color,
        active_color=active_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        max_words_per_group=max_words,
        video_width=video_width,
        video_height=video_height,
        position_y_ratio=position_y_ratio,
    )

    return create_dynamic_subtitle_clip(
        word_timings=word_timings,
        video_width=video_width,
        video_height=video_height,
        config=config,
    )


def create_subtitle_clip_from_srt(
    srt_path: str,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str = "",
    font_size: int = 70,
    normal_color: str = "#FFFFFF",
    active_color: str = "#FFD700",
    stroke_color: str = "#000000",
    stroke_width: int = 4,
    max_words: int = 4,
    position_y_ratio: float = 0.75,
) -> Optional[VideoClip]:
    """
    Fallback: Create dynamic subtitle clip from an SRT file.
    Word timings are approximated by evenly dividing each SRT block.
    """
    word_timings = extract_word_timings_from_srt(srt_path)
    if not word_timings:
        return None

    config = DynamicSubtitleConfig(
        font_path=font_path,
        font_size=font_size,
        normal_color=normal_color,
        active_color=active_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        max_words_per_group=max_words,
        video_width=video_width,
        video_height=video_height,
        position_y_ratio=position_y_ratio,
    )

    return create_dynamic_subtitle_clip(
        word_timings=word_timings,
        video_width=video_width,
        video_height=video_height,
        config=config,
    )
