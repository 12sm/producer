"""Integration tests: full pipeline with synthetic audio.

These tests generate known audio pairs, run the complete bracket lab pipeline,
and verify end-to-end behavior: feature extraction → scoring → notes → reports.
"""

import json
import os
import sys
import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
from conftest import make_test_track, apply_region_boost, SR
from audio_utils import SAMPLE_RATE, get_duration
from features import extract_features, compute_deltas
from scoring import score_compliance, score_drift
from notes import generate_notes
from snippet_bank import create_run_id, save_run, append_index, search_bank
from report import write_report_md, write_report_json


def _write_wav(path, y, sr=SR):
    sf.write(path, y, sr)


def _run_pipeline(orig, variant, brackets, intent, sr=SR,
                  anchors=None, bank_dir=None, out_dir=None):
    """Run the bracket lab pipeline programmatically (mirrors bracket_lab.main)."""
    from audio_utils import (
        slice_audio_exact, generate_auto_anchors, format_window, save_slice,
    )

    duration = min(get_duration(orig, sr), get_duration(variant, sr))

    if anchors is None:
        anchors = generate_auto_anchors(duration, brackets)

    bracket_results = []
    for bstart, bend in brackets:
        exact_orig = slice_audio_exact(orig, sr, bstart, bend)
        exact_var = slice_audio_exact(variant, sr, bstart, bend)
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
        exact_orig = slice_audio_exact(orig, sr, astart, aend)
        exact_var = slice_audio_exact(variant, sr, astart, aend)
        feat_orig = extract_features(exact_orig, sr)
        feat_var = extract_features(exact_var, sr)
        deltas = compute_deltas(feat_orig, feat_var)
        anchor_deltas.append(deltas)

    drift = score_drift(anchor_deltas)

    run_id = create_run_id()
    run_data = {
        'run_id': run_id,
        'timestamp': '2026-01-01T00:00:00Z',
        'original_path': '/synthetic/original.wav',
        'variant_path': '/synthetic/variant.wav',
        'prompt_text': '',
        'intent': intent,
        'brackets': [{'start': s, 'end': e} for s, e in brackets],
        'anchors': [{'start': s, 'end': e} for s, e in anchors],
        'bracket_results': bracket_results,
        'drift': drift,
        'slice_files': [],
        'bank_dir': bank_dir or '',
    }

    if bank_dir:
        save_run(run_id, run_data, bank_dir)
        summary = {
            'timestamp': run_data['timestamp'],
            'intent': intent,
            'brackets': [format_window(s, e) for s, e in brackets],
            'compliance_verdict': bracket_results[0]['compliance']['verdict'],
            'compliance_score': bracket_results[0]['compliance']['score'],
            'drift_verdict': drift['verdict'],
            'drift_score': drift['overall_drift'],
        }
        append_index(run_id, summary, bank_dir)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        write_report_md(run_data, os.path.join(out_dir, 'report.md'))
        write_report_json(run_data, os.path.join(out_dir, 'report.json'))

    return run_data


# ── Test: louder bracket → PASS compliance, LOW drift ──────────────

class TestLouderBracket:
    """Variant is 2x louder in bracket [10-20s], identical elsewhere."""

    def test_compliance_passes(self, track_pair_louder_bracket):
        orig, variant = track_pair_louder_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'make it louder')
        br = result['bracket_results'][0]
        assert br['compliance']['verdict'] == 'PASS'
        assert br['deltas']['rms_mean'] > 0.05

    def test_drift_is_low(self, track_pair_louder_bracket):
        orig, variant = track_pair_louder_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'make it louder')
        assert result['drift']['verdict'] == 'LOW'

    def test_notes_mention_louder(self, track_pair_louder_bracket):
        orig, variant = track_pair_louder_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'make it louder')
        notes = result['bracket_results'][0]['notes']
        assert 'louder' in notes['what_changed'].lower()


# ── Test: brighter bracket → compliance + low drift ────────────────

class TestBrighterBracket:
    def test_compliance_passes(self, track_pair_brighter_bracket):
        orig, variant = track_pair_brighter_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'brighter tone')
        br = result['bracket_results'][0]
        assert br['compliance']['verdict'] == 'PASS'
        assert br['deltas']['centroid_mean'] > 0.05

    def test_drift_is_low(self, track_pair_brighter_bracket):
        orig, variant = track_pair_brighter_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'brighter tone')
        assert result['drift']['verdict'] == 'LOW'


# ── Test: busier bracket ───────────────────────────────────────────

class TestBusierBracket:
    def test_onset_density_increases(self, track_pair_busier_bracket):
        orig, variant = track_pair_busier_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'busier drums')
        br = result['bracket_results'][0]
        assert br['deltas']['onset_density'] > 0


# ── Test: adversarial — wrong changes → FAIL ──────────────────────

class TestAdversarialWrongChange:
    """Variant gets louder but intent says 'quieter' → should FAIL."""

    def test_compliance_fails(self, track_pair_louder_bracket):
        orig, variant = track_pair_louder_bracket
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'make it quieter')
        br = result['bracket_results'][0]
        assert br['compliance']['verdict'] == 'FAIL'


# ── Test: global drift detection ───────────────────────────────────

class TestGlobalDrift:
    """Everything changes → drift should be HIGH."""

    def test_high_drift(self, track_pair_global_drift):
        orig, variant = track_pair_global_drift
        result = _run_pipeline(orig, variant, [(10.0, 20.0)], 'louder')
        assert result['drift']['verdict'] in ('MED', 'HIGH')


# ── Test: report output ───────────────────────────────────────────

class TestReportOutput:
    def test_markdown_report_written(self, track_pair_louder_bracket, tmp_out):
        orig, variant = track_pair_louder_bracket
        _run_pipeline(orig, variant, [(10.0, 20.0)], 'louder', out_dir=tmp_out)
        md_path = os.path.join(tmp_out, 'report.md')
        assert os.path.exists(md_path)
        with open(md_path) as f:
            content = f.read()
        assert 'Bracket Prompt Lab' in content
        assert 'PASS' in content or 'MIXED' in content or 'FAIL' in content

    def test_json_report_written(self, track_pair_louder_bracket, tmp_out):
        orig, variant = track_pair_louder_bracket
        _run_pipeline(orig, variant, [(10.0, 20.0)], 'louder', out_dir=tmp_out)
        json_path = os.path.join(tmp_out, 'report.json')
        assert os.path.exists(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert 'bracket_results' in data
        assert 'drift' in data


# ── Test: snippet bank round-trip ──────────────────────────────────

class TestSnippetBankIntegration:
    def test_save_and_search(self, track_pair_louder_bracket, tmp_bank):
        orig, variant = track_pair_louder_bracket
        _run_pipeline(orig, variant, [(10.0, 20.0)], 'louder drums',
                      bank_dir=tmp_bank)
        results = search_bank('louder', tmp_bank)
        assert len(results) == 1
        assert results[0]['compliance_verdict'] == 'PASS'


# ── Test: CLI entry point (via subprocess) ─────────────────────────

class TestCLI:
    def test_cli_with_wav_files(self, track_pair_louder_bracket, tmp_path):
        """Test the actual CLI entry point with WAV files on disk."""
        orig, variant = track_pair_louder_bracket
        orig_path = str(tmp_path / 'original.wav')
        var_path = str(tmp_path / 'variant.wav')
        out_dir = str(tmp_path / 'out')
        bank_dir = str(tmp_path / 'bank')

        _write_wav(orig_path, orig)
        _write_wav(var_path, variant)

        from bracket_lab import main
        main([
            '--original', orig_path,
            '--variant', var_path,
            '--bracket', '10-20',
            '--intent', 'make it louder',
            '--out_dir', out_dir,
            '--bank_dir', bank_dir,
        ])

        assert os.path.exists(os.path.join(out_dir, 'report.md'))
        assert os.path.exists(os.path.join(out_dir, 'report.json'))
        assert os.path.exists(os.path.join(bank_dir, 'index.jsonl'))
