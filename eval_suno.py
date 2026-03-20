#!/usr/bin/env python3
"""Tier 2 Eval Harness — Generate Suno tracks and evaluate bracket compliance.

This script automates the full Suno → Bracket Lab evaluation loop:
  1. Generate an original track via Suno API
  2. Generate variant(s) with bracket modifications
  3. Run bracket lab analysis on each pair
  4. Print a summary table for human review

Usage:
    # Basic evaluation
    python eval_suno.py \
        --prompt "Lo-fi hip hop beat, mellow piano, dusty drums, 85 BPM" \
        --bracket "0:30-0:45" \
        --intent "add more percussion, busier hi-hats" \
        --num-variants 3

    # With existing original (skip generation)
    python eval_suno.py \
        --original path/to/original.mp3 \
        --prompt "Lo-fi hip hop beat" \
        --bracket "0:30-0:45" \
        --intent "louder drums, punchy kick" \
        --num-variants 2

    # Dry run (show what would be generated, don't call API)
    python eval_suno.py \
        --prompt "..." --bracket "0:30-0:45" --intent "..." --dry-run

Environment:
    SUNO_API_KEY    — Your Suno API key (required unless --dry-run)
    SUNO_API_BASE   — API base URL (default: https://api.suno.ai/v1)

Notes:
    - This is NOT for automated tests. It's a manual evaluation tool.
    - Suno generation is non-deterministic — results vary per run.
    - Review the output table + reports to validate scoring quality.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from audio_utils import (
    load_audio, get_duration, parse_bracket, slice_audio_exact,
    generate_auto_anchors, format_window, SAMPLE_RATE,
)
from features import extract_features, compute_deltas
from scoring import score_compliance, score_drift
from notes import generate_notes
from snippet_bank import create_run_id, save_run, append_index
from report import print_console_summary, write_report_md, write_report_json


# ── Suno API Client ───────────────────────────────────────────────

class SunoClient:
    """Minimal Suno API client for generating tracks.

    Override or extend this class to match the actual Suno API contract
    as it evolves. The interface is intentionally minimal.
    """

    def __init__(self, api_key=None, api_base=None):
        self.api_key = api_key or os.environ.get('SUNO_API_KEY', '')
        self.api_base = (api_base or os.environ.get('SUNO_API_BASE', '')
                         or 'https://api.suno.ai/v1')
        if not self.api_key:
            raise EnvironmentError(
                'SUNO_API_KEY not set. Export it or pass --api-key.'
            )

        # Import here to fail fast if not installed
        try:
            import requests
            self._requests = requests
        except ImportError:
            raise ImportError(
                'requests is required for Suno API calls. '
                'Install with: pip install requests'
            )

    def generate(self, prompt, duration_sec=None, tags=None, wait=True,
                 poll_interval=10, timeout=300):
        """Generate a track from a text prompt.

        Args:
            prompt: The full generation prompt.
            duration_sec: Target duration in seconds (if API supports it).
            tags: Optional list of style tags.
            wait: If True, poll until generation completes.
            poll_interval: Seconds between status polls.
            timeout: Max seconds to wait for generation.

        Returns:
            dict with keys: id, audio_url, duration, status, metadata
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        payload = {'prompt': prompt}
        if duration_sec:
            payload['duration'] = duration_sec
        if tags:
            payload['tags'] = tags

        resp = self._requests.post(
            f'{self.api_base}/generate',
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        job = resp.json()
        job_id = job.get('id') or job.get('job_id')

        if not wait:
            return job

        # Poll for completion
        start = time.time()
        while time.time() - start < timeout:
            status = self._get_status(job_id, headers)
            if status.get('status') in ('complete', 'completed', 'succeeded'):
                return status
            if status.get('status') in ('failed', 'error'):
                raise RuntimeError(f'Suno generation failed: {status}')
            time.sleep(poll_interval)

        raise TimeoutError(f'Suno generation timed out after {timeout}s')

    def _get_status(self, job_id, headers):
        resp = self._requests.get(
            f'{self.api_base}/status/{job_id}',
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def download(self, audio_url, dest_path):
        """Download a generated audio file."""
        resp = self._requests.get(audio_url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest_path


# ── Pipeline Runner ────────────────────────────────────────────────

def run_eval(original_path, variant_path, brackets, intent, out_dir, bank_dir):
    """Run the full bracket lab pipeline on a pair of audio files."""
    y_orig, sr = load_audio(original_path)
    y_var, _ = load_audio(variant_path)
    duration = min(get_duration(y_orig, sr), get_duration(y_var, sr))

    anchors = generate_auto_anchors(duration, brackets)

    bracket_results = []
    for bstart, bend in brackets:
        exact_orig = slice_audio_exact(y_orig, sr, bstart, bend)
        exact_var = slice_audio_exact(y_var, sr, bstart, bend)
        feat_orig = extract_features(exact_orig, sr)
        feat_var = extract_features(exact_var, sr)
        deltas = compute_deltas(feat_orig, feat_var)
        compliance = score_compliance(deltas, intent)
        window_notes = generate_notes(
            bstart, bend, feat_orig, feat_var, deltas, intent, compliance,
        )
        bracket_results.append({
            'window': format_window(bstart, bend),
            'start': bstart, 'end': bend,
            'original_features': feat_orig,
            'variant_features': feat_var,
            'deltas': deltas,
            'compliance': compliance,
            'notes': window_notes,
        })

    anchor_deltas = []
    for astart, aend in anchors:
        exact_orig = slice_audio_exact(y_orig, sr, astart, aend)
        exact_var = slice_audio_exact(y_var, sr, astart, aend)
        feat_orig = extract_features(exact_orig, sr)
        feat_var = extract_features(exact_var, sr)
        deltas = compute_deltas(feat_orig, feat_var)
        anchor_deltas.append(deltas)

    drift = score_drift(anchor_deltas)

    run_id = create_run_id()
    run_data = {
        'run_id': run_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'original_path': os.path.abspath(original_path),
        'variant_path': os.path.abspath(variant_path),
        'prompt_text': '',
        'intent': intent,
        'brackets': [{'start': s, 'end': e} for s, e in brackets],
        'anchors': [{'start': s, 'end': e} for s, e in anchors],
        'bracket_results': bracket_results,
        'drift': drift,
        'slice_files': [],
        'bank_dir': bank_dir,
    }

    save_run(run_id, run_data, bank_dir)
    summary = {
        'timestamp': run_data['timestamp'],
        'intent': intent,
        'brackets': [format_window(s, e) for s, e in brackets],
        'compliance_verdict': bracket_results[0]['compliance']['verdict'],
        'compliance_score': bracket_results[0]['compliance']['score'],
        'drift_verdict': drift['verdict'],
        'drift_score': drift['overall_drift'],
        'original': original_path,
        'variant': variant_path,
    }
    append_index(run_id, summary, bank_dir)

    os.makedirs(out_dir, exist_ok=True)
    run_out = os.path.join(out_dir, run_id)
    os.makedirs(run_out, exist_ok=True)
    write_report_md(run_data, os.path.join(run_out, 'report.md'))
    write_report_json(run_data, os.path.join(run_out, 'report.json'))

    return run_data


# ── Summary Table ──────────────────────────────────────────────────

def print_summary_table(results):
    """Print a compact comparison table across all variants."""
    print()
    print('=' * 78)
    print('  SUNO EVAL HARNESS — Summary Table')
    print('=' * 78)
    print(f'  {"Variant":<12} {"Compliance":<12} {"Score":<8} '
          f'{"Drift":<8} {"Drift Score":<12} {"Run ID"}')
    print('-' * 78)

    for i, rd in enumerate(results):
        br = rd['bracket_results'][0]
        c = br['compliance']
        d = rd['drift']
        print(f'  variant_{i:<4} {c["verdict"]:<12} {c["score"]:<8.3f} '
              f'{d["verdict"]:<8} {d["overall_drift"]:<12.4f} {rd["run_id"]}')

    print('-' * 78)

    # Aggregate stats
    pass_count = sum(1 for r in results
                     if r['bracket_results'][0]['compliance']['verdict'] == 'PASS')
    low_drift = sum(1 for r in results if r['drift']['verdict'] == 'LOW')
    print(f'  Pass rate: {pass_count}/{len(results)} | '
          f'Low drift: {low_drift}/{len(results)}')
    print('=' * 78)
    print()


# ── CLI ────────────────────────────────────────────────────────────

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description='Suno Eval Harness — generate and evaluate bracket experiments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('--prompt', required=True,
                   help='Generation prompt for the original track')
    p.add_argument('--bracket', required=True, action='append',
                   help='Bracket window e.g. "0:30-0:45" (repeatable)')
    p.add_argument('--intent', required=True,
                   help='Intent description for the bracket modification')
    p.add_argument('--variant-prompt', default=None,
                   help='Custom prompt for variants. If not set, appends '
                        'bracket+intent to the base prompt.')
    p.add_argument('--original', default=None,
                   help='Path to existing original audio (skip generation)')
    p.add_argument('--num-variants', type=int, default=3,
                   help='Number of variants to generate (default: 3)')
    p.add_argument('--out-dir', default='./eval_out',
                   help='Output directory (default: ./eval_out)')
    p.add_argument('--bank-dir', default='./snippet_bank',
                   help='Snippet bank directory (default: ./snippet_bank)')
    p.add_argument('--api-key', default=None,
                   help='Suno API key (or set SUNO_API_KEY env var)')
    p.add_argument('--api-base', default=None,
                   help='Suno API base URL (or set SUNO_API_BASE env var)')
    p.add_argument('--dry-run', action='store_true',
                   help='Show what would be generated without calling API')
    return p.parse_args(argv)


def build_variant_prompt(base_prompt, brackets, intent, bracket_strs):
    """Build the variant generation prompt by injecting bracket instructions."""
    bracket_block = '\n'.join(
        f'[{bs}] {intent}' for bs in bracket_strs
    )
    return f'{base_prompt}\n\n--- BRACKET MODIFICATION ---\n{bracket_block}'


def main(argv=None):
    args = parse_args(argv)

    bracket_strs = args.bracket
    brackets = [parse_bracket(b) for b in bracket_strs]

    variant_prompt = args.variant_prompt or build_variant_prompt(
        args.prompt, brackets, args.intent, bracket_strs,
    )

    # ── Dry run ────────────────────────────────────────────────────
    if args.dry_run:
        print('DRY RUN — no API calls will be made.\n')
        print(f'Original prompt:\n  {args.prompt}\n')
        print(f'Variant prompt:\n  {variant_prompt}\n')
        print(f'Brackets: {bracket_strs}')
        print(f'Intent: {args.intent}')
        print(f'Num variants: {args.num_variants}')
        return

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(args.bank_dir, exist_ok=True)

    # ── Suno client ────────────────────────────────────────────────
    if args.api_key:
        os.environ['SUNO_API_KEY'] = args.api_key
    if args.api_base:
        os.environ['SUNO_API_BASE'] = args.api_base

    suno = SunoClient()

    # ── Generate or load original ──────────────────────────────────
    if args.original:
        original_path = args.original
        print(f'Using existing original: {original_path}')
    else:
        print(f'Generating original track...')
        result = suno.generate(args.prompt)
        original_path = os.path.join(args.out_dir, 'original.mp3')
        audio_url = result.get('audio_url') or result.get('output_url', '')
        suno.download(audio_url, original_path)
        print(f'  Saved: {original_path}')

    # ── Generate variants ──────────────────────────────────────────
    variant_paths = []
    for i in range(args.num_variants):
        print(f'Generating variant {i + 1}/{args.num_variants}...')
        result = suno.generate(variant_prompt)
        vpath = os.path.join(args.out_dir, f'variant_{i}.mp3')
        audio_url = result.get('audio_url') or result.get('output_url', '')
        suno.download(audio_url, vpath)
        variant_paths.append(vpath)
        print(f'  Saved: {vpath}')

    # ── Run evaluations ────────────────────────────────────────────
    print(f'\nRunning bracket lab evaluation on {len(variant_paths)} variant(s)...\n')
    results = []
    for i, vpath in enumerate(variant_paths):
        print(f'── Evaluating variant {i} ──')
        try:
            run_data = run_eval(
                original_path, vpath, brackets, args.intent,
                args.out_dir, args.bank_dir,
            )
            results.append(run_data)
            print_console_summary(run_data)
        except Exception as e:
            print(f'  ERROR evaluating variant {i}: {e}')

    # ── Summary ────────────────────────────────────────────────────
    if results:
        print_summary_table(results)
        print(f'Reports written to: {args.out_dir}/')
        print(f'Snippet bank: {args.bank_dir}/')
    else:
        print('No successful evaluations.')


if __name__ == '__main__':
    main()
