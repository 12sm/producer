#!/usr/bin/env python3
"""Bracket Prompt Lab — CLI tool for evaluating Suno bracket prompt experiments.

Compare an original track to a variant/cover track, focusing on specific
bracketed time regions. Score compliance and drift, generate producer-style
notes, and save results to a searchable snippet bank.

Usage:
    python bracket_lab.py \\
        --original path/to/original.mp3 \\
        --variant path/to/variant.mp3 \\
        --bracket "1:12-1:28" \\
        --intent "Chorus 2 drum entry: tight 2-step, no crash, swung hats, less EDM riser" \\
        --prompt_file prompt.txt \\
        --out_dir ./lab_out
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from audio_utils import (
    load_audio, get_duration, parse_bracket,
    slice_audio, slice_audio_exact, save_slice,
    generate_auto_anchors, format_window,
)
from features import extract_features, compute_deltas
from scoring import score_compliance, score_drift
from notes import generate_notes
from snippet_bank import create_run_id, save_run, get_slices_dir, append_index
from report import print_console_summary, write_report_md, write_report_json


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Bracket Prompt Lab — evaluate Suno bracket prompt experiments',
    )
    parser.add_argument('--original', required=True,
                        help='Path to original audio file (MP3/WAV)')
    parser.add_argument('--variant', required=True,
                        help='Path to variant/cover audio file (MP3/WAV)')
    parser.add_argument('--bracket', action='append', required=True,
                        help='Bracket time window, e.g. "1:12-1:28". Can be specified multiple times.')
    parser.add_argument('--intent', required=True,
                        help='Intent description for the bracket modification')
    parser.add_argument('--prompt_file', default=None,
                        help='Path to the full prompt text file')
    parser.add_argument('--anchors', nargs='*', default=None,
                        help='Anchor windows for drift checking, e.g. "0:10-0:25" "0:55-1:05"')
    parser.add_argument('--out_dir', default='./lab_out',
                        help='Output directory (default: ./lab_out)')
    parser.add_argument('--bank_dir', default='./snippet_bank',
                        help='Snippet bank directory (default: ./snippet_bank)')
    parser.add_argument('--pre_roll', type=float, default=2.0,
                        help='Pre-roll seconds for bracket slices (default: 2.0)')
    parser.add_argument('--post_roll', type=float, default=2.0,
                        help='Post-roll seconds for bracket slices (default: 2.0)')
    parser.add_argument('--search', default=None,
                        help='Search the snippet bank instead of running analysis')
    return parser.parse_args(argv)


def run_search(query, bank_dir):
    """Search the snippet bank and print results."""
    from snippet_bank import search_bank
    results = search_bank(query, bank_dir)
    if not results:
        print(f"No results found for '{query}'")
        return
    print(f"Found {len(results)} result(s) for '{query}':\n")
    for r in results:
        print(f"  [{r.get('run_id', '?')}] {r.get('intent', '')} "
              f"— {r.get('compliance_verdict', '?')} / drift: {r.get('drift_verdict', '?')}")
    print()


def main(argv=None):
    args = parse_args(argv)

    # Search mode
    if args.search:
        run_search(args.search, args.bank_dir)
        return

    # Load prompt text if provided
    prompt_text = ''
    if args.prompt_file:
        with open(args.prompt_file, 'r') as f:
            prompt_text = f.read().strip()

    # Create run ID and directories
    run_id = create_run_id()
    os.makedirs(args.out_dir, exist_ok=True)
    slices_dir = os.path.join(args.out_dir, 'slices')
    os.makedirs(slices_dir, exist_ok=True)

    print(f"Bracket Prompt Lab — Run {run_id}")
    print(f"Loading audio...")

    # Load audio
    y_orig, sr = load_audio(args.original)
    y_var, _ = load_audio(args.variant)
    dur_orig = get_duration(y_orig, sr)
    dur_var = get_duration(y_var, sr)
    print(f"  Original: {dur_orig:.1f}s | Variant: {dur_var:.1f}s")

    # Parse bracket windows
    brackets = [parse_bracket(b) for b in args.bracket]
    print(f"  Brackets: {[format_window(s, e) for s, e in brackets]}")

    # Parse or generate anchor windows
    if args.anchors:
        anchors = [parse_bracket(a) for a in args.anchors]
    else:
        anchors = generate_auto_anchors(min(dur_orig, dur_var), brackets)
        print(f"  Auto-anchors: {[format_window(s, e) for s, e in anchors]}")

    # Process bracket windows
    print(f"\nAnalyzing bracket windows...")
    bracket_results = []
    slice_files = []

    for i, (bstart, bend) in enumerate(brackets):
        label = f"bracket_{i}"
        print(f"  [{format_window(bstart, bend)}] extracting features...")

        # Slice with pre/post roll for saving
        slice_orig = slice_audio(y_orig, sr, bstart, bend,
                                 args.pre_roll, args.post_roll)
        slice_var = slice_audio(y_var, sr, bstart, bend,
                                args.pre_roll, args.post_roll)

        # Save slices
        orig_slice_path = os.path.join(slices_dir, f'{label}_original.wav')
        var_slice_path = os.path.join(slices_dir, f'{label}_variant.wav')
        save_slice(slice_orig, sr, orig_slice_path)
        save_slice(slice_var, sr, var_slice_path)
        slice_files.extend([orig_slice_path, var_slice_path])

        # Extract features on the exact bracket region (no padding)
        exact_orig = slice_audio_exact(y_orig, sr, bstart, bend)
        exact_var = slice_audio_exact(y_var, sr, bstart, bend)

        feat_orig = extract_features(exact_orig, sr)
        feat_var = extract_features(exact_var, sr)
        deltas = compute_deltas(feat_orig, feat_var)

        # Score compliance
        compliance = score_compliance(deltas, args.intent)

        # Generate notes
        window_notes = generate_notes(
            bstart, bend, feat_orig, feat_var,
            deltas, args.intent, compliance,
        )

        bracket_results.append({
            'window': format_window(bstart, bend),
            'start': bstart,
            'end': bend,
            'original_features': feat_orig,
            'variant_features': feat_var,
            'deltas': deltas,
            'compliance': compliance,
            'notes': window_notes,
        })

        print(f"    Compliance: {compliance['verdict']} (score: {compliance['score']:.2f})")

    # Process anchor windows for drift
    print(f"\nAnalyzing drift across {len(anchors)} anchor(s)...")
    anchor_deltas = []

    for i, (astart, aend) in enumerate(anchors):
        label = f"anchor_{i}"
        exact_orig = slice_audio_exact(y_orig, sr, astart, aend)
        exact_var = slice_audio_exact(y_var, sr, astart, aend)

        feat_orig = extract_features(exact_orig, sr)
        feat_var = extract_features(exact_var, sr)
        deltas = compute_deltas(feat_orig, feat_var)
        anchor_deltas.append(deltas)

        # Save anchor slices too
        orig_slice_path = os.path.join(slices_dir, f'{label}_original.wav')
        var_slice_path = os.path.join(slices_dir, f'{label}_variant.wav')
        save_slice(slice_audio_exact(y_orig, sr, astart, aend), sr, orig_slice_path)
        save_slice(slice_audio_exact(y_var, sr, astart, aend), sr, var_slice_path)
        slice_files.extend([orig_slice_path, var_slice_path])

    drift = score_drift(anchor_deltas)
    print(f"  Drift: {drift['verdict']} (score: {drift['overall_drift']:.4f})")

    # Assemble run data
    run_data = {
        'run_id': run_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'original_path': os.path.abspath(args.original),
        'variant_path': os.path.abspath(args.variant),
        'prompt_text': prompt_text,
        'intent': args.intent,
        'brackets': [{'start': s, 'end': e} for s, e in brackets],
        'anchors': [{'start': s, 'end': e} for s, e in anchors],
        'bracket_results': bracket_results,
        'drift': drift,
        'slice_files': slice_files,
        'bank_dir': args.bank_dir,
    }

    # Save to snippet bank
    bank_slices_dir = get_slices_dir(run_id, args.bank_dir)
    save_run(run_id, run_data, args.bank_dir)

    # Copy slices to snippet bank
    for sf_path in slice_files:
        dest = os.path.join(bank_slices_dir, os.path.basename(sf_path))
        if os.path.abspath(sf_path) != os.path.abspath(dest):
            import shutil
            shutil.copy2(sf_path, dest)

    # Append to index
    index_summary = {
        'timestamp': run_data['timestamp'],
        'intent': args.intent,
        'brackets': [format_window(s, e) for s, e in brackets],
        'compliance_verdict': bracket_results[0]['compliance']['verdict'] if bracket_results else 'N/A',
        'compliance_score': bracket_results[0]['compliance']['score'] if bracket_results else 0,
        'drift_verdict': drift['verdict'],
        'drift_score': drift['overall_drift'],
        'original': args.original,
        'variant': args.variant,
    }
    append_index(run_id, index_summary, args.bank_dir)

    # Write reports
    write_report_md(run_data, os.path.join(args.out_dir, 'report.md'))
    write_report_json(run_data, os.path.join(args.out_dir, 'report.json'))

    # Console summary
    print_console_summary(run_data)

    print(f"Reports written to: {args.out_dir}/")
    print(f"Snippet bank entry: {args.bank_dir}/{run_id}/")


if __name__ == '__main__':
    main()
