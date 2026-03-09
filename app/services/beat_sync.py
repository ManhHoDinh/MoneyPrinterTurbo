"""
Beat-Sync Editing Engine — Align scene cuts with music beats.

Detects beat intervals from background music and snaps scene cut
points to the nearest beat for rhythmically-aligned editing.
"""

import os
import struct
import wave
from typing import List, Tuple, Optional
from loguru import logger


# ── Beat Detection ───────────────────────────────────────────────────────────

def detect_beats(audio_path: str) -> List[float]:
    """
    Detect beat timestamps from an audio file.

    Tries librosa first (accurate), falls back to energy-based detection.
    Returns a sorted list of beat times in seconds.
    """
    if not audio_path or not os.path.exists(audio_path):
        logger.warning(f"beat detection: audio file not found: {audio_path}")
        return []

    # Try librosa first (best quality)
    try:
        return _detect_beats_librosa(audio_path)
    except ImportError:
        logger.info("librosa not available, using energy-based beat detection")
    except Exception as e:
        logger.warning(f"librosa beat detection failed: {e}")

    # Fallback: energy-based detection
    try:
        return _detect_beats_energy(audio_path)
    except Exception as e:
        logger.warning(f"energy-based beat detection failed: {e}")

    return []


def _detect_beats_librosa(audio_path: str) -> List[float]:
    """Use librosa for high-quality beat detection."""
    import librosa
    import numpy as np

    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    beats = sorted(beat_times.tolist())
    logger.info(f"librosa detected {len(beats)} beats, tempo={tempo:.0f} BPM")
    return beats


def _detect_beats_energy(audio_path: str) -> List[float]:
    """
    Simple energy-based beat detection fallback.

    Analyzes audio energy in windows and detects sudden peaks
    as beat positions. Less accurate than librosa but zero dependencies.
    """
    # For mp3 files, we need a different approach
    if audio_path.lower().endswith(".mp3"):
        return _detect_beats_from_mp3(audio_path)

    # WAV file processing
    try:
        with wave.open(audio_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            frames = wf.readframes(n_frames)
    except Exception as e:
        logger.warning(f"cannot read WAV: {e}")
        return []

    # Convert to samples
    if sample_width == 2:
        fmt = f"<{n_frames * n_channels}h"
        samples = list(struct.unpack(fmt, frames))
    else:
        return []

    # Mono-ify
    if n_channels > 1:
        samples = [samples[i] for i in range(0, len(samples), n_channels)]

    # Energy-based detection
    window_size = int(framerate * 0.05)  # 50ms windows
    hop_size = window_size // 2

    energies = []
    for i in range(0, len(samples) - window_size, hop_size):
        window = samples[i: i + window_size]
        energy = sum(s * s for s in window) / window_size
        energies.append(energy)

    if not energies:
        return []

    # Find peaks (beats)
    avg_energy = sum(energies) / len(energies)
    threshold = avg_energy * 1.5

    beats = []
    min_beat_gap = 0.25  # minimum 250ms between beats
    last_beat_time = -1.0

    for i, e in enumerate(energies):
        time_sec = (i * hop_size) / framerate
        if e > threshold and (time_sec - last_beat_time) > min_beat_gap:
            # Check if it's a local maximum
            if i > 0 and i < len(energies) - 1:
                if e >= energies[i - 1] and e >= energies[i + 1]:
                    beats.append(round(time_sec, 3))
                    last_beat_time = time_sec

    logger.info(f"energy detector found {len(beats)} beats")
    return beats


def _detect_beats_from_mp3(audio_path: str) -> List[float]:
    """
    Estimate beat times from MP3 using pydub if available,
    otherwise return evenly-spaced beats based on common BPM.
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        duration = len(audio) / 1000.0  # seconds

        # Use dBFS analysis for rough beat detection
        chunk_ms = 50  # 50ms chunks
        energies = []
        for i in range(0, len(audio), chunk_ms):
            chunk = audio[i: i + chunk_ms]
            energies.append(chunk.dBFS if chunk.dBFS > -float("inf") else -60)

        if not energies:
            return _generate_default_beats(duration)

        avg_energy = sum(energies) / len(energies)
        threshold = avg_energy + 3  # 3 dB above average

        beats = []
        min_gap = 0.25
        last_beat = -1.0

        for i, e in enumerate(energies):
            t = (i * chunk_ms) / 1000.0
            if e > threshold and (t - last_beat) > min_gap:
                beats.append(round(t, 3))
                last_beat = t

        if len(beats) < 5:
            return _generate_default_beats(duration)

        logger.info(f"pydub energy detector found {len(beats)} beats")
        return beats

    except ImportError:
        logger.info("pydub not available, using default beat estimation")
    except Exception as e:
        logger.warning(f"pydub beat detection failed: {e}")

    # Last resort: estimate duration and generate default beats
    return _generate_default_beats(60.0)  # default 60s


def _generate_default_beats(duration: float, bpm: float = 120.0) -> List[float]:
    """Generate evenly-spaced beats based on assumed BPM."""
    interval = 60.0 / bpm
    beats = []
    t = 0.0
    while t < duration:
        beats.append(round(t, 3))
        t += interval
    logger.info(f"generated {len(beats)} default beats at {bpm} BPM")
    return beats


# ── Beat Interval Analysis ──────────────────────────────────────────────────

def get_beat_intervals(beats: List[float]) -> dict:
    """
    Analyze beat intervals to extract tempo information.

    Returns:
        dict with:
        - bpm: estimated beats per minute
        - avg_interval: average time between beats (seconds)
        - intervals: list of intervals between consecutive beats
    """
    if len(beats) < 2:
        return {"bpm": 120.0, "avg_interval": 0.5, "intervals": []}

    intervals = [beats[i + 1] - beats[i] for i in range(len(beats) - 1)]
    avg_interval = sum(intervals) / len(intervals)
    bpm = 60.0 / avg_interval if avg_interval > 0 else 120.0

    return {
        "bpm": round(bpm, 1),
        "avg_interval": round(avg_interval, 3),
        "intervals": [round(iv, 3) for iv in intervals],
    }


# ── Cut Alignment ───────────────────────────────────────────────────────────

def align_cuts_to_beats(
    cut_timestamps: List[float],
    beat_timestamps: List[float],
    tolerance: float = 0.3,
) -> List[float]:
    """
    Snap scene cut timestamps to the nearest beat.

    For each cut, find the nearest beat within `tolerance` seconds.
    If a beat is close enough, snap the cut to that beat.
    Otherwise, keep the original cut time.

    Args:
        cut_timestamps: planned scene cut times (seconds)
        beat_timestamps: detected beat times (seconds)
        tolerance: maximum snap distance (seconds)

    Returns:
        adjusted cut timestamps aligned to beats
    """
    if not beat_timestamps:
        return cut_timestamps

    aligned = []
    used_beats = set()

    for cut_time in cut_timestamps:
        # Find nearest unused beat
        best_beat = None
        best_distance = float("inf")

        for beat in beat_timestamps:
            if beat in used_beats:
                continue
            distance = abs(cut_time - beat)
            if distance < best_distance:
                best_distance = distance
                best_beat = beat

        # Snap if within tolerance
        if best_beat is not None and best_distance <= tolerance:
            aligned.append(round(best_beat, 3))
            used_beats.add(best_beat)
            logger.debug(
                f"cut {cut_time:.2f}s snapped to beat {best_beat:.2f}s "
                f"(delta={best_distance:.3f}s)"
            )
        else:
            aligned.append(cut_time)

    snapped = sum(1 for a, c in zip(aligned, cut_timestamps) if a != c)
    logger.info(f"beat sync: {snapped}/{len(cut_timestamps)} cuts aligned to beats")
    return aligned


def compute_beat_aligned_durations(
    clip_durations: List[float],
    beat_timestamps: List[float],
    tolerance: float = 0.3,
) -> List[float]:
    """
    Adjust clip durations so that cut boundaries fall on beats.

    Converts durations to cumulative timestamps, aligns to beats,
    then converts back to durations.
    """
    if not beat_timestamps or not clip_durations:
        return clip_durations

    # Convert durations to cut timestamps
    cuts = []
    cumulative = 0.0
    for dur in clip_durations:
        cumulative += dur
        cuts.append(cumulative)

    # Align cuts to beats
    aligned_cuts = align_cuts_to_beats(cuts, beat_timestamps, tolerance)

    # Convert back to durations
    new_durations = []
    prev = 0.0
    for cut in aligned_cuts:
        dur = max(0.5, cut - prev)  # minimum 0.5s per clip
        new_durations.append(round(dur, 3))
        prev = cut

    return new_durations
