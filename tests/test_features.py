"""Unit tests for feature extraction with synthetic audio."""

import numpy as np
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import make_sine, make_noise, make_click_train, SR

from features import extract_features, compute_deltas, delta_magnitude


class TestExtractFeatures:
    def test_returns_all_keys(self, short_sine, sr):
        feat = extract_features(short_sine, sr)
        expected_keys = {
            'rms_mean', 'rms_std', 'centroid_mean', 'centroid_std',
            'onset_strength_mean', 'onset_density', 'tempo',
        }
        assert set(feat.keys()) == expected_keys

    def test_short_audio_returns_zeros(self, sr):
        tiny = np.zeros(int(sr * 0.05))  # 50ms, below 0.1s threshold
        feat = extract_features(tiny, sr)
        assert feat['rms_mean'] == 0.0
        assert feat['tempo'] == 0.0

    def test_louder_signal_higher_rms(self, sr):
        quiet = make_sine(440, 3.0, amplitude=0.1)
        loud = make_sine(440, 3.0, amplitude=0.8)
        f_quiet = extract_features(quiet, sr)
        f_loud = extract_features(loud, sr)
        assert f_loud['rms_mean'] > f_quiet['rms_mean']

    def test_higher_freq_higher_centroid(self, sr):
        low = make_sine(200, 3.0)
        high = make_sine(4000, 3.0)
        f_low = extract_features(low, sr)
        f_high = extract_features(high, sr)
        assert f_high['centroid_mean'] > f_low['centroid_mean']

    def test_click_train_has_onsets(self, sr):
        clicks = make_click_train(3.0, clicks_per_sec=8.0)
        feat = extract_features(clicks, sr)
        assert feat['onset_density'] > 0

    def test_noise_has_features(self, sr):
        noise = make_noise(3.0)
        feat = extract_features(noise, sr)
        assert feat['rms_mean'] > 0
        assert feat['centroid_mean'] > 0


class TestDeltas:
    def test_identical_signals_zero_deltas(self, sr):
        y = make_sine(440, 3.0)
        feat = extract_features(y, sr)
        deltas = compute_deltas(feat, feat)
        for v in deltas.values():
            assert abs(v) < 1e-6

    def test_louder_variant_positive_rms_delta(self, sr):
        quiet = make_sine(440, 3.0, amplitude=0.2)
        loud = make_sine(440, 3.0, amplitude=0.6)
        f_orig = extract_features(quiet, sr)
        f_var = extract_features(loud, sr)
        deltas = compute_deltas(f_orig, f_var)
        assert deltas['rms_mean'] > 0

    def test_quieter_variant_negative_rms_delta(self, sr):
        loud = make_sine(440, 3.0, amplitude=0.6)
        quiet = make_sine(440, 3.0, amplitude=0.2)
        f_orig = extract_features(loud, sr)
        f_var = extract_features(quiet, sr)
        deltas = compute_deltas(f_orig, f_var)
        assert deltas['rms_mean'] < 0


class TestDeltaMagnitude:
    def test_zero_deltas_zero_magnitude(self):
        deltas = {'a': 0.0, 'b': 0.0, 'c': 0.0}
        assert delta_magnitude(deltas) == 0.0

    def test_nonzero_deltas_positive_magnitude(self):
        deltas = {'a': 0.5, 'b': -0.3, 'c': 0.1}
        assert delta_magnitude(deltas) > 0

    def test_magnitude_is_l2_norm(self):
        deltas = {'a': 3.0, 'b': 4.0}
        assert abs(delta_magnitude(deltas) - 5.0) < 1e-6
