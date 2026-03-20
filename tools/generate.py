#!/usr/bin/env python3
"""Generate — send a prompt to Suno and download the result.

Wraps the Suno API client for single-track generation. Claude Code
calls this to create audio, then uses listen/analyze to evaluate it.

Usage:
    python -m tools.generate \
        --prompt "Lo-fi hip hop beat, mellow piano, dusty drums, 85 BPM" \
        --out-dir ./audio

    # With bracket modification
    python -m tools.generate \
        --prompt "Lo-fi hip hop beat, mellow piano, dusty drums, 85 BPM" \
        --bracket-inject "0:30-0:45" \
        --intent "add more percussion, busier hi-hats" \
        --out-dir ./audio

    # Dry run
    python -m tools.generate --prompt "..." --dry-run

Environment:
    SUNO_API_KEY  — Suno API key (required unless --dry-run)
    SUNO_API_BASE — API base URL (default: https://api.suno.ai/v1)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from eval_suno import SunoClient, build_variant_prompt
from audio_utils import parse_bracket


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Generate audio via Suno API')
    p.add_argument('--prompt', required=True, help='Generation prompt')
    p.add_argument('--bracket-inject', default=None,
                   help='Bracket window to inject into prompt, e.g. "0:30-0:45"')
    p.add_argument('--intent', default=None,
                   help='Intent for bracket injection')
    p.add_argument('--filename', default=None,
                   help='Output filename (default: auto-generated)')
    p.add_argument('--out-dir', default='./audio', help='Output directory')
    p.add_argument('--api-key', default=None, help='Suno API key')
    p.add_argument('--api-base', default=None, help='Suno API base URL')
    p.add_argument('--dry-run', action='store_true',
                   help='Show prompt without calling API')
    return p.parse_args(argv)


def generate(prompt, bracket_inject=None, intent=None, filename=None,
             out_dir='./audio', api_key=None, api_base=None, dry_run=False):
    """Generate a single track via Suno API.

    Returns dict with: file, prompt, duration (if available), dry_run status.
    """
    # Build final prompt
    final_prompt = prompt
    if bracket_inject and intent:
        bracket_strs = [bracket_inject]
        brackets = [parse_bracket(bracket_inject)]
        final_prompt = build_variant_prompt(prompt, brackets, intent, bracket_strs)

    if dry_run:
        return {
            'dry_run': True,
            'prompt': final_prompt,
            'file': None,
        }

    os.makedirs(out_dir, exist_ok=True)

    suno = SunoClient(api_key=api_key, api_base=api_base)
    result = suno.generate(final_prompt)

    fname = filename or f"suno_{result.get('id', 'track')}.mp3"
    out_path = os.path.join(out_dir, fname)
    audio_url = result.get('audio_url') or result.get('output_url', '')
    suno.download(audio_url, out_path)

    return {
        'dry_run': False,
        'prompt': final_prompt,
        'file': os.path.abspath(out_path),
        'suno_id': result.get('id'),
        'duration': result.get('duration'),
    }


def main(argv=None):
    args = parse_args(argv)
    result = generate(
        args.prompt,
        bracket_inject=args.bracket_inject,
        intent=args.intent,
        filename=args.filename,
        out_dir=args.out_dir,
        api_key=args.api_key,
        api_base=args.api_base,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
