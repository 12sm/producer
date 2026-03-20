"""Unit tests for producer note generation."""

import pytest
from notes import generate_notes


def _make_features(**overrides):
    base = {
        'rms_mean': 0.1, 'rms_std': 0.02, 'centroid_mean': 2000.0,
        'centroid_std': 500.0, 'onset_strength_mean': 1.0,
        'onset_density': 4.0, 'tempo': 120.0,
    }
    base.update(overrides)
    return base


class TestGenerateNotes:
    def test_returns_required_keys(self):
        orig = _make_features()
        var = _make_features()
        deltas = {k: 0.0 for k in orig}
        compliance = {'verdict': 'MIXED', 'matched_rules': [], 'score': 0.5}
        notes = generate_notes(10.0, 20.0, orig, var, deltas, 'louder', compliance)
        assert 'window' in notes
        assert 'what_changed' in notes
        assert 'what_improved' in notes
        assert 'what_got_worse' in notes
        assert 'suggested_tweak' in notes

    def test_louder_change_detected(self):
        orig = _make_features(rms_mean=0.1)
        var = _make_features(rms_mean=0.3)
        deltas = {'rms_mean': 1.0, 'rms_std': 0.0, 'centroid_mean': 0.0,
                  'centroid_std': 0.0, 'onset_strength_mean': 0.0,
                  'onset_density': 0.0, 'tempo': 0.0}
        compliance = {'verdict': 'PASS', 'matched_rules': [], 'score': 1.0}
        notes = generate_notes(10.0, 20.0, orig, var, deltas, 'louder', compliance)
        assert 'louder' in notes['what_changed'].lower()

    def test_no_change_noted(self):
        orig = _make_features()
        var = _make_features()
        deltas = {k: 0.0 for k in orig}
        compliance = {'verdict': 'MIXED', 'matched_rules': [], 'score': 0.5}
        notes = generate_notes(10.0, 20.0, orig, var, deltas, 'test', compliance)
        assert 'no significant' in notes['what_changed'].lower()

    def test_pass_verdict_locks_tweak(self):
        orig = _make_features()
        var = _make_features()
        deltas = {k: 0.0 for k in orig}
        compliance = {'verdict': 'PASS', 'matched_rules': [], 'score': 1.0}
        notes = generate_notes(10.0, 20.0, orig, var, deltas, 'louder', compliance)
        assert 'working well' in notes['suggested_tweak'].lower()

    def test_window_formatted(self):
        orig = _make_features()
        var = _make_features()
        deltas = {k: 0.0 for k in orig}
        compliance = {'verdict': 'MIXED', 'matched_rules': [], 'score': 0.5}
        notes = generate_notes(72.0, 88.0, orig, var, deltas, 'test', compliance)
        assert notes['window'] == '1:12-1:28'
