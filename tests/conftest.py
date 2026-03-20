"""Shared fixtures: synthetic audio generators with controllable properties."""

import numpy as np
import pytest
import sys
import os

# Add project root to path so we can import modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from audio_utils import SAMPLE_RATE

SR = SAMPLE_RATE  # 22050


def make_sine(freq=440.0, duration=5.0, amplitude=0.5, sr=SR):
    """Generate a pure sine wave."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def make_noise(duration=5.0, amplitude=0.3, sr=SR):
    """Generate white noise."""
    rng = np.random.default_rng(42)
    return (amplitude * rng.standard_normal(int(sr * duration))).astype(np.float32)


def make_click_train(duration=5.0, clicks_per_sec=4.0, amplitude=0.8, sr=SR):
    """Generate a click train (sharp transients at regular intervals)."""
    n_samples = int(sr * duration)
    y = np.zeros(n_samples, dtype=np.float32)
    click_len = int(sr * 0.005)  # 5ms click
    interval = int(sr / clicks_per_sec)
    for i in range(0, n_samples, interval):
        end = min(i + click_len, n_samples)
        y[i:end] = amplitude
    return y


def make_test_track(duration=30.0, sr=SR, base_freq=220.0,
                    base_amplitude=0.3, noise_level=0.05):
    """Generate a composite test track: sine + harmonics + light noise.

    This simulates a simple musical signal with controllable properties.
    """
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = base_amplitude * np.sin(2 * np.pi * base_freq * t)
    y += (base_amplitude * 0.5) * np.sin(2 * np.pi * base_freq * 2 * t)
    y += (base_amplitude * 0.25) * np.sin(2 * np.pi * base_freq * 3 * t)
    rng = np.random.default_rng(42)
    y += noise_level * rng.standard_normal(len(y))
    return y.astype(np.float32)


def apply_region_boost(y, sr, start, end, loudness_boost=1.0,
                       brightness_boost=0.0, onset_injection=0.0):
    """Modify a specific region of audio with controllable changes.

    Args:
        y: Input audio signal (will be copied).
        sr: Sample rate.
        start: Region start in seconds.
        end: Region end in seconds.
        loudness_boost: Multiplier for amplitude in region (1.0 = no change).
        brightness_boost: Amount of high-freq noise to add (0.0 = none).
        onset_injection: Clicks per second to inject (0.0 = none).
    """
    y_out = y.copy()
    s = int(start * sr)
    e = min(int(end * sr), len(y))

    # Loudness
    if loudness_boost != 1.0:
        y_out[s:e] *= loudness_boost

    # Brightness (add high-freq content)
    if brightness_boost > 0:
        region_len = e - s
        t = np.linspace(0, (e - s) / sr, region_len, endpoint=False)
        hf = brightness_boost * np.sin(2 * np.pi * 8000 * t)
        y_out[s:e] += hf.astype(np.float32)

    # Onset injection (add clicks)
    if onset_injection > 0:
        region_len = e - s
        click_len = int(sr * 0.003)
        interval = int(sr / onset_injection)
        for i in range(0, region_len, interval):
            ce = min(i + click_len, region_len)
            y_out[s + i:s + ce] += 0.5

    return np.clip(y_out, -1.0, 1.0).astype(np.float32)


@pytest.fixture
def sr():
    return SR


@pytest.fixture
def short_sine():
    """5-second 440Hz sine wave."""
    return make_sine(440.0, 5.0)


@pytest.fixture
def test_track_30s():
    """30-second composite test track."""
    return make_test_track(30.0)


@pytest.fixture
def track_pair_louder_bracket():
    """Original + variant where bracket region [10-20s] is 2x louder.

    Non-bracket regions are identical → drift should be LOW.
    """
    orig = make_test_track(30.0)
    variant = apply_region_boost(orig, SR, 10.0, 20.0, loudness_boost=2.0)
    return orig, variant


@pytest.fixture
def track_pair_brighter_bracket():
    """Original + variant where bracket region [10-20s] is brighter.

    High-frequency content added in bracket only.
    """
    orig = make_test_track(30.0)
    variant = apply_region_boost(orig, SR, 10.0, 20.0, brightness_boost=0.3)
    return orig, variant


@pytest.fixture
def track_pair_busier_bracket():
    """Original + variant where bracket region [10-20s] has more onsets."""
    orig = make_test_track(30.0)
    variant = apply_region_boost(orig, SR, 10.0, 20.0, onset_injection=8.0)
    return orig, variant


@pytest.fixture
def track_pair_global_drift():
    """Original + variant where EVERYTHING changes (high drift expected).

    Uses a 120s track so auto-anchors have room outside the bracket.
    """
    orig = make_test_track(120.0)
    variant = apply_region_boost(orig, SR, 0.0, 120.0,
                                 loudness_boost=3.0, brightness_boost=0.5,
                                 onset_injection=12.0)
    return orig, variant


@pytest.fixture
def tmp_bank(tmp_path):
    """Temporary snippet bank directory."""
    bank = tmp_path / 'snippet_bank'
    bank.mkdir()
    return str(bank)


@pytest.fixture
def tmp_out(tmp_path):
    """Temporary output directory."""
    out = tmp_path / 'lab_out'
    out.mkdir()
    return str(out)
