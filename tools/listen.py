#!/usr/bin/env python3
"""Listen — extract audio features from a single file or time region.

Claude Code uses this to "hear" what's in an audio file without needing
actual audio playback. Returns a JSON feature profile.

Usage:
    python -m tools.listen track.mp3
    python -m tools.listen track.mp3 --region "0:30-1:00"
    python -m tools.listen track.mp3 --region "0:00-0:30" --region "1:00-1:30"
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from audio_utils import load_audio, get_duration, parse_bracket, slice_audio_exact, format_window, SAMPLE_RATE
from features import extract_features


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Extract audio features from a file')
    p.add_argument('audio', help='Path to audio file (MP3/WAV)')
    p.add_argument('--region', action='append', default=None,
                   help='Time region to analyze, e.g. "0:30-1:00" (repeatable). '
                        'If omitted, analyzes the full track.')
    return p.parse_args(argv)


def listen(audio_path, regions=None):
    """Extract features from an audio file, optionally for specific regions.

    Returns a dict with:
        file, duration, and either full_track features or per-region features.
    """
    y, sr = load_audio(audio_path)
    duration = get_duration(y, sr)

    result = {
        'file': os.path.abspath(audio_path),
        'duration': round(duration, 2),
        'sample_rate': sr,
    }

    if regions:
        parsed = [parse_bracket(r) for r in regions]
        region_results = []
        for start, end in parsed:
            segment = slice_audio_exact(y, sr, start, end)
            feats = extract_features(segment, sr)
            region_results.append({
                'window': format_window(start, end),
                'start': start,
                'end': end,
                'features': feats,
            })
        result['regions'] = region_results
    else:
        result['features'] = extract_features(y, sr)

    return result


def main(argv=None):
    args = parse_args(argv)
    result = listen(args.audio, args.region)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
