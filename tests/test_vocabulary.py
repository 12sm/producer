"""Tests for the vocabulary index module."""

import json
import os
import sys
import pytest
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import make_test_track, apply_region_boost, SR
from vocabulary import (
    build_vocab_index, load_vocab, lookup_keyword,
    find_keywords_for_feature, _tokenize_intent,
)


class TestTokenizer:
    """Tests for intent text tokenization."""

    def test_basic_tokenization(self):
        tokens = _tokenize_intent('louder drums, punchy kick')
        assert 'louder' in tokens
        assert 'drums' in tokens
        assert 'punchy' in tokens
        assert 'kick' in tokens

    def test_stop_words_removed(self):
        tokens = _tokenize_intent('add more percussion and make it louder')
        assert 'add' not in tokens
        assert 'more' not in tokens
        assert 'and' not in tokens
        assert 'louder' in tokens
        assert 'percussion' in tokens

    def test_phrase_tokens(self):
        tokens = _tokenize_intent('no crash, less edm riser')
        assert 'no crash' in tokens
        assert 'less edm' in tokens

    def test_hi_hats(self):
        tokens = _tokenize_intent('busier hi-hats')
        assert 'hi-hats' in tokens
        assert 'busier' in tokens


class TestVocabBuild:
    """Tests for building the vocabulary index."""

    @pytest.fixture
    def populated_bank(self, tmp_path):
        """Create a snippet bank with several runs."""
        bank_dir = str(tmp_path / 'bank')
        os.makedirs(bank_dir)

        # Create fake run entries
        runs = [
            {
                'run_id': 'run_001',
                'intent': 'louder drums',
                'bracket_results': [{
                    'deltas': {
                        'rms_mean': 0.25, 'rms_std': 0.1,
                        'centroid_mean': 0.02, 'centroid_std': 0.01,
                        'onset_strength_mean': 0.05, 'onset_density': 0.03,
                        'tempo': 0.0,
                    },
                    'compliance': {'verdict': 'PASS'},
                }],
            },
            {
                'run_id': 'run_002',
                'intent': 'louder kick',
                'bracket_results': [{
                    'deltas': {
                        'rms_mean': 0.30, 'rms_std': 0.15,
                        'centroid_mean': -0.05, 'centroid_std': 0.0,
                        'onset_strength_mean': 0.10, 'onset_density': 0.0,
                        'tempo': 0.01,
                    },
                    'compliance': {'verdict': 'PASS'},
                }],
            },
            {
                'run_id': 'run_003',
                'intent': 'busier hi-hats, brighter',
                'bracket_results': [{
                    'deltas': {
                        'rms_mean': 0.05, 'rms_std': 0.02,
                        'centroid_mean': 0.20, 'centroid_std': 0.10,
                        'onset_strength_mean': 0.15, 'onset_density': 0.40,
                        'tempo': 0.0,
                    },
                    'compliance': {'verdict': 'PASS'},
                }],
            },
            {
                'run_id': 'run_004',
                'intent': 'darker tone, less edm',
                'bracket_results': [{
                    'deltas': {
                        'rms_mean': -0.10, 'rms_std': -0.05,
                        'centroid_mean': -0.25, 'centroid_std': -0.10,
                        'onset_strength_mean': -0.08, 'onset_density': -0.15,
                        'tempo': 0.0,
                    },
                    'compliance': {'verdict': 'MIXED'},
                }],
            },
        ]

        for run in runs:
            run_dir = os.path.join(bank_dir, run['run_id'])
            os.makedirs(run_dir)
            with open(os.path.join(run_dir, 'entry.json'), 'w') as f:
                json.dump(run, f)

        return bank_dir

    def test_build_creates_index(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        index = build_vocab_index(populated_bank, vocab_path)

        assert index['total_runs'] == 4
        assert len(index['keywords']) > 0
        assert os.path.exists(vocab_path)

    def test_louder_keyword_aggregated(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        index = build_vocab_index(populated_bank, vocab_path)

        assert 'louder' in index['keywords']
        louder = index['keywords']['louder']
        assert louder['count'] == 2  # run_001 and run_002
        assert louder['avg_deltas']['rms_mean'] > 0.2  # average of 0.25 and 0.30
        assert louder['pass_rate'] == 1.0

    def test_phrase_token_detected(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        index = build_vocab_index(populated_bank, vocab_path)

        assert 'less edm' in index['keywords']

    def test_lookup_keyword(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        build_vocab_index(populated_bank, vocab_path)
        vocab = load_vocab(vocab_path)

        result = lookup_keyword(vocab, 'louder')
        assert result['found'] is True
        assert result['count'] == 2
        assert len(result['effects']) > 0

    def test_lookup_missing_keyword(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        build_vocab_index(populated_bank, vocab_path)
        vocab = load_vocab(vocab_path)

        result = lookup_keyword(vocab, 'reverb')
        assert result['found'] is False

    def test_find_keywords_for_feature(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        build_vocab_index(populated_bank, vocab_path)
        vocab = load_vocab(vocab_path)

        result = find_keywords_for_feature(vocab, 'rms_mean', 'increase')
        assert len(result['matches']) > 0
        # "louder" should be in the results
        kws = [m['keyword'] for m in result['matches']]
        assert 'louder' in kws

    def test_find_keywords_decrease(self, populated_bank, tmp_path):
        vocab_path = str(tmp_path / 'vocab.json')
        build_vocab_index(populated_bank, vocab_path)
        vocab = load_vocab(vocab_path)

        result = find_keywords_for_feature(vocab, 'centroid_mean', 'decrease')
        kws = [m['keyword'] for m in result['matches']]
        assert 'darker' in kws

    def test_empty_bank(self, tmp_path):
        bank_dir = str(tmp_path / 'empty_bank')
        vocab_path = str(tmp_path / 'vocab.json')
        index = build_vocab_index(bank_dir, vocab_path)
        assert index['total_runs'] == 0
        assert index['keywords'] == {}


class TestVocabWithRealAudio:
    """Integration test: build vocab from actual bracket lab runs."""

    def test_end_to_end(self, tmp_path):
        from tools.analyze import analyze

        bank_dir = str(tmp_path / 'bank')
        out_dir = str(tmp_path / 'out')

        # Generate audio pairs and run analysis
        orig = make_test_track(30.0)
        louder_var = apply_region_boost(orig, SR, 10.0, 20.0, loudness_boost=2.0)
        bright_var = apply_region_boost(orig, SR, 10.0, 20.0, brightness_boost=0.3)

        orig_path = str(tmp_path / 'orig.wav')
        loud_path = str(tmp_path / 'loud.wav')
        bright_path = str(tmp_path / 'bright.wav')

        sf.write(orig_path, orig, SR)
        sf.write(loud_path, louder_var, SR)
        sf.write(bright_path, bright_var, SR)

        # Run analyses
        analyze(orig_path, loud_path, ['10-20'], 'louder drums',
                bank_dir=bank_dir, out_dir=out_dir)
        analyze(orig_path, bright_path, ['10-20'], 'brighter tone',
                bank_dir=bank_dir, out_dir=out_dir)

        # Build vocab
        vocab_path = str(tmp_path / 'vocab.json')
        index = build_vocab_index(bank_dir, vocab_path)

        assert index['total_runs'] == 2
        assert 'louder' in index['keywords']
        assert 'brighter' in index['keywords']

        # Verify louder → rms_mean increase
        louder_entry = index['keywords']['louder']
        assert louder_entry['avg_deltas']['rms_mean'] > 0.05
