"""Audio loading, normalization, slicing, and auto-anchor generation."""

import re
import numpy as np
import librosa
import soundfile as sf


SAMPLE_RATE = 22050


def parse_timestamp(ts: str) -> float:
    """Parse 'M:SS' or 'M:SS.ms' or 'SS' to seconds."""
    ts = ts.strip()
    # M:SS or M:SS.ms
    m = re.match(r'^(\d+):(\d+(?:\.\d+)?)$', ts)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    # plain seconds
    try:
        return float(ts)
    except ValueError:
        raise ValueError(f"Cannot parse timestamp: '{ts}'")


def parse_bracket(bracket: str) -> tuple:
    """Parse '1:12-1:28' to (start_sec, end_sec)."""
    parts = bracket.split('-', 1)
    if len(parts) != 2:
        raise ValueError(f"Bracket must be 'START-END', got: '{bracket}'")
    return (parse_timestamp(parts[0]), parse_timestamp(parts[1]))


def load_audio(path: str, sr: int = SAMPLE_RATE) -> tuple:
    """Load audio file, convert to mono, resample."""
    y, sr_out = librosa.load(path, sr=sr, mono=True)
    return y, sr_out


def get_duration(y: np.ndarray, sr: int) -> float:
    """Get duration of audio in seconds."""
    return len(y) / sr


def slice_audio(y: np.ndarray, sr: int, start: float, end: float,
                pre_roll: float = 2.0, post_roll: float = 2.0) -> np.ndarray:
    """Extract audio slice with optional pre/post roll, clamped to bounds."""
    duration = get_duration(y, sr)
    actual_start = max(0.0, start - pre_roll)
    actual_end = min(duration, end + post_roll)
    start_sample = int(actual_start * sr)
    end_sample = int(actual_end * sr)
    return y[start_sample:end_sample]


def slice_audio_exact(y: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    """Extract audio slice without pre/post roll."""
    return slice_audio(y, sr, start, end, pre_roll=0.0, post_roll=0.0)


def save_slice(y: np.ndarray, sr: int, path: str):
    """Write audio slice to WAV file."""
    sf.write(path, y, sr)


def generate_auto_anchors(duration: float, brackets: list, n: int = 4,
                          window_len: float = 8.0) -> list:
    """Generate evenly-spaced anchor windows, avoiding bracket regions.

    Args:
        duration: Total track duration in seconds.
        brackets: List of (start, end) tuples for bracket regions.
        n: Target number of anchor windows.
        window_len: Length of each anchor window in seconds.

    Returns:
        List of (start, end) tuples for anchor windows.
    """
    if duration < window_len:
        return []

    buffer = 4.0  # stay 4s away from bracket edges
    candidates = []
    step = duration / (n + 1)

    for i in range(1, n + 1):
        center = step * i
        start = center - window_len / 2
        end = center + window_len / 2

        # Clamp to audio bounds
        start = max(0.0, start)
        end = min(duration, end)

        # Check overlap with bracket regions
        overlaps = False
        for b_start, b_end in brackets:
            if start < (b_end + buffer) and end > (b_start - buffer):
                overlaps = True
                break

        if not overlaps and (end - start) >= window_len * 0.5:
            candidates.append((round(start, 2), round(end, 2)))

    return candidates


def format_timestamp(seconds: float) -> str:
    """Convert seconds to M:SS format."""
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    if secs == int(secs):
        return f"{minutes}:{int(secs):02d}"
    return f"{minutes}:{secs:05.2f}"


def format_window(start: float, end: float) -> str:
    """Format a time window as 'M:SS-M:SS'."""
    return f"{format_timestamp(start)}-{format_timestamp(end)}"
