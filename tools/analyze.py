#!/usr/bin/env python3
"""Analyze — run bracket lab comparison and output JSON report.

Compares an original track to a variant, scoring compliance and drift
for specified bracket regions. This is the core evaluation tool.

Usage:
    python -m tools.analyze \
        --original original.mp3 \
        --variant variant.mp3 \
        --bracket "0:30-0:45" \
        --intent "louder drums, punchy kick"

    # Multiple brackets
    python -m tools.analyze \
        --original orig.mp3 --variant var.mp3 \
        --bracket "0:30-0:45" --bracket "1:00-1:15" \
        --intent "busier hi-hats"
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from audio_utils import (
    load_audio, get_duration, parse_bracket, slice_audio_exact,
    generate_auto_anchors, format_window, SAMPLE_RATE,
)
from features import extract_features, compute_deltas
from scoring import score_compliance, score_drift
from notes import generate_notes
from snippet_bank import create_run_id, save_run, append_index
from report import write_report_json


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Run bracket lab analysis')
    p.add_argument('--original', required=True, help='Original audio file')
    p.add_argument('--variant', required=True, help='Variant audio file')
    p.add_argument('--bracket', required=True, action='append',
                   help='Bracket window e.g. "0:30-0:45" (repeatable)')
    p.add_argument('--intent', required=True, help='Intent description')
    p.add_argument('--prompt-text', default='', help='Full generation prompt')
    p.add_argument('--out-dir', default='./lab_out', help='Output directory')
    p.add_argument('--bank-dir', default='./snippet_bank', help='Snippet bank dir')
    p.add_argument('--save', action='store_true', default=True,
                   help='Save to snippet bank (default: true)')
    p.add_argument('--no-save', dest='save', action='store_false',
                   help='Skip saving to snippet bank')
    return p.parse_args(argv)


def analyze(original_path, variant_path, bracket_strs, intent,
            prompt_text='', out_dir='./lab_out', bank_dir='./snippet_bank',
            save=True):
    """Run full bracket lab analysis and return structured results."""
    y_orig, sr = load_audio(original_path)
    y_var, _ = load_audio(variant_path)
    duration = min(get_duration(y_orig, sr), get_duration(y_var, sr))

    brackets = [parse_bracket(b) for b in bracket_strs]
    anchors = generate_auto_anchors(duration, brackets)

    # Analyze brackets
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

    # Analyze anchors for drift
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
        'prompt_text': prompt_text,
        'intent': intent,
        'brackets': [{'start': s, 'end': e} for s, e in brackets],
        'anchors': [{'start': s, 'end': e} for s, e in anchors],
        'bracket_results': bracket_results,
        'drift': drift,
        'slice_files': [],
        'bank_dir': bank_dir,
    }

    if save:
        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(bank_dir, exist_ok=True)
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
        run_out = os.path.join(out_dir, run_id)
        os.makedirs(run_out, exist_ok=True)
        write_report_json(run_data, os.path.join(run_out, 'report.json'))

    return run_data


def main(argv=None):
    args = parse_args(argv)
    result = analyze(
        args.original, args.variant, args.bracket, args.intent,
        prompt_text=args.prompt_text, out_dir=args.out_dir,
        bank_dir=args.bank_dir, save=args.save,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
