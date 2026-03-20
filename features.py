"""Feature extraction from audio slices using librosa."""

import numpy as np
import librosa


def extract_features(y: np.ndarray, sr: int) -> dict:
    """Compute audio features for a slice.

    Returns dict with:
        rms_mean, rms_std: loudness/dynamics
        centroid_mean, centroid_std: brightness proxy
        onset_strength_mean: overall onset energy
        onset_density: onsets per second
        tempo: estimated BPM (rough)
    """
    duration = len(y) / sr
    if duration < 0.1:
        return _empty_features()

    # RMS loudness
    rms = librosa.feature.rms(y=y)[0]
    rms_mean = float(np.mean(rms))
    rms_std = float(np.std(rms))

    # Spectral centroid (brightness)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = float(np.mean(centroid))
    centroid_std = float(np.std(centroid))

    # Onset strength
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_strength_mean = float(np.mean(onset_env))

    # Onset density (onsets per second)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time')
    onset_density = len(onsets) / max(duration, 0.01)

    # Tempo estimate
    tempo_arr = librosa.beat.tempo(y=y, sr=sr)
    tempo = float(tempo_arr[0]) if len(tempo_arr) > 0 else 0.0

    return {
        'rms_mean': round(rms_mean, 6),
        'rms_std': round(rms_std, 6),
        'centroid_mean': round(centroid_mean, 2),
        'centroid_std': round(centroid_std, 2),
        'onset_strength_mean': round(onset_strength_mean, 4),
        'onset_density': round(onset_density, 2),
        'tempo': round(tempo, 1),
    }


def _empty_features() -> dict:
    """Return zeroed feature dict for very short slices."""
    return {
        'rms_mean': 0.0,
        'rms_std': 0.0,
        'centroid_mean': 0.0,
        'centroid_std': 0.0,
        'onset_strength_mean': 0.0,
        'onset_density': 0.0,
        'tempo': 0.0,
    }


def compute_deltas(orig: dict, variant: dict, eps: float = 1e-8) -> dict:
    """Compute normalized deltas: (variant - original) / (|original| + eps).

    Positive delta = feature increased in variant.
    Negative delta = feature decreased in variant.
    """
    deltas = {}
    for key in orig:
        o = orig[key]
        v = variant[key]
        deltas[key] = round((v - o) / (abs(o) + eps), 4)
    return deltas


def delta_magnitude(deltas: dict) -> float:
    """L2 norm of all deltas — overall change magnitude."""
    vals = list(deltas.values())
    return float(np.linalg.norm(vals))
