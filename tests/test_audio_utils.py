"""Unit tests for audio_utils: parsing, slicing, and auto-anchor generation."""

import numpy as np
import pytest
from audio_utils import (
    parse_timestamp, parse_bracket, get_duration, slice_audio,
    slice_audio_exact, generate_auto_anchors, format_timestamp,
    format_window, SAMPLE_RATE,
)


# ── Timestamp Parsing ──────────────────────────────────────────────

class TestParseTimestamp:
    def test_minutes_seconds(self):
        assert parse_timestamp('1:12') == 72.0

    def test_minutes_seconds_decimal(self):
        assert parse_timestamp('1:12.50') == 72.5

    def test_zero_minutes(self):
        assert parse_timestamp('0:42') == 42.0

    def test_plain_seconds(self):
        assert parse_timestamp('42') == 42.0

    def test_plain_seconds_float(self):
        assert parse_timestamp('42.5') == 42.5

    def test_whitespace_stripped(self):
        assert parse_timestamp('  1:12  ') == 72.0

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_timestamp('not_a_time')

    def test_large_minutes(self):
        assert parse_timestamp('10:00') == 600.0


# ── Bracket Parsing ────────────────────────────────────────────────

class TestParseBracket:
    def test_basic(self):
        assert parse_bracket('1:12-1:28') == (72.0, 88.0)

    def test_seconds_only(self):
        assert parse_bracket('10-20') == (10.0, 20.0)

    def test_invalid_no_dash(self):
        with pytest.raises(ValueError):
            parse_bracket('1:12')


# ── Duration & Slicing ─────────────────────────────────────────────

class TestSlicing:
    def test_get_duration(self, sr):
        y = np.zeros(sr * 10)  # 10 seconds
        assert get_duration(y, sr) == 10.0

    def test_slice_exact(self, test_track_30s, sr):
        sliced = slice_audio_exact(test_track_30s, sr, 5.0, 10.0)
        expected_len = int(5.0 * sr)
        assert len(sliced) == expected_len

    def test_slice_with_preroll(self, test_track_30s, sr):
        sliced = slice_audio(test_track_30s, sr, 5.0, 10.0,
                             pre_roll=2.0, post_roll=2.0)
        # Should span 3.0 to 12.0 = 9 seconds
        expected_len = int(9.0 * sr)
        assert len(sliced) == expected_len

    def test_slice_clamped_to_start(self, test_track_30s, sr):
        sliced = slice_audio(test_track_30s, sr, 0.5, 2.0,
                             pre_roll=5.0, post_roll=0.0)
        # pre_roll would go to -4.5, clamped to 0.0 → span 0-2s
        expected_len = int(2.0 * sr)
        assert len(sliced) == expected_len

    def test_slice_clamped_to_end(self, test_track_30s, sr):
        sliced = slice_audio(test_track_30s, sr, 28.0, 29.5,
                             pre_roll=0.0, post_roll=5.0)
        # post_roll would go to 34.5, clamped to 30.0 → span 28-30s
        expected_len = int(2.0 * sr)
        assert len(sliced) == expected_len


# ── Auto Anchors ───────────────────────────────────────────────────

class TestAutoAnchors:
    def test_generates_anchors(self):
        anchors = generate_auto_anchors(120.0, [(50.0, 60.0)], n=4)
        assert len(anchors) > 0
        for start, end in anchors:
            assert start >= 0
            assert end <= 120.0
            assert end > start

    def test_avoids_bracket_region(self):
        bracket = (50.0, 60.0)
        buffer = 4.0
        anchors = generate_auto_anchors(120.0, [bracket], n=4)
        for start, end in anchors:
            # No anchor should overlap bracket +/- buffer
            assert not (start < bracket[1] + buffer and end > bracket[0] - buffer)

    def test_short_audio_returns_empty(self):
        assert generate_auto_anchors(3.0, [(1.0, 2.0)]) == []

    def test_multiple_brackets(self):
        brackets = [(20.0, 30.0), (80.0, 90.0)]
        anchors = generate_auto_anchors(200.0, brackets, n=6)
        assert len(anchors) > 0
        for s, e in anchors:
            for bs, be in brackets:
                assert not (s < be + 4.0 and e > bs - 4.0)


# ── Formatting ─────────────────────────────────────────────────────

class TestFormatting:
    def test_format_timestamp(self):
        assert format_timestamp(72.0) == '1:12'
        assert format_timestamp(0.0) == '0:00'
        assert format_timestamp(600.0) == '10:00'

    def test_format_window(self):
        assert format_window(72.0, 88.0) == '1:12-1:28'
