"""Tests for the discrete CLI tools (tools/ package)."""

import json
import os
import sys
import pytest
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import make_test_track, apply_region_boost, SR


@pytest.fixture
def audio_pair(tmp_path):
    """Create a pair of WAV files: original + louder variant."""
    orig = make_test_track(30.0)
    variant = apply_region_boost(orig, SR, 10.0, 20.0, loudness_boost=2.0)

    orig_path = str(tmp_path / 'original.wav')
    var_path = str(tmp_path / 'variant.wav')
    sf.write(orig_path, orig, SR)
    sf.write(var_path, variant, SR)
    return orig_path, var_path


@pytest.fixture
def single_audio(tmp_path):
    """Create a single WAV file."""
    y = make_test_track(15.0)
    path = str(tmp_path / 'track.wav')
    sf.write(path, y, SR)
    return path


class TestListen:
    """Tests for tools/listen.py."""

    def test_listen_full_track(self, single_audio):
        from tools.listen import listen
        result = listen(single_audio)

        assert 'features' in result
        assert result['duration'] > 14.0
        assert result['features']['rms_mean'] > 0
        assert result['features']['tempo'] > 0

    def test_listen_with_regions(self, single_audio):
        from tools.listen import listen
        result = listen(single_audio, regions=['0:00-0:05', '0:05-0:10'])

        assert 'regions' in result
        assert len(result['regions']) == 2
        assert result['regions'][0]['window'] == '0:00-0:05'
        assert 'features' in result['regions'][0]
        assert result['regions'][0]['features']['rms_mean'] > 0

    def test_listen_cli(self, single_audio, capsys):
        from tools.listen import main
        main([single_audio])
        output = json.loads(capsys.readouterr().out)
        assert 'features' in output

    def test_listen_cli_with_region(self, single_audio, capsys):
        from tools.listen import main
        main([single_audio, '--region', '0:00-0:05'])
        output = json.loads(capsys.readouterr().out)
        assert 'regions' in output
        assert len(output['regions']) == 1


class TestAnalyze:
    """Tests for tools/analyze.py."""

    def test_analyze_basic(self, audio_pair, tmp_path):
        from tools.analyze import analyze
        orig, var = audio_pair
        bank_dir = str(tmp_path / 'bank')
        out_dir = str(tmp_path / 'out')

        result = analyze(
            orig, var, ['10-20'], 'louder',
            out_dir=out_dir, bank_dir=bank_dir,
        )

        assert result['intent'] == 'louder'
        assert len(result['bracket_results']) == 1
        br = result['bracket_results'][0]
        assert br['compliance']['verdict'] == 'PASS'
        assert br['compliance']['score'] >= 0.7
        assert 'drift' in result

    def test_analyze_no_save(self, audio_pair, tmp_path):
        from tools.analyze import analyze
        orig, var = audio_pair
        bank_dir = str(tmp_path / 'bank')

        result = analyze(
            orig, var, ['10-20'], 'louder',
            bank_dir=bank_dir, save=False,
        )

        assert result['run_id']
        # Bank directory should not have been created
        assert not os.path.exists(os.path.join(bank_dir, result['run_id']))

    def test_analyze_cli(self, audio_pair, tmp_path, capsys):
        from tools.analyze import main
        orig, var = audio_pair
        main([
            '--original', orig,
            '--variant', var,
            '--bracket', '10-20',
            '--intent', 'louder',
            '--out-dir', str(tmp_path / 'out'),
            '--bank-dir', str(tmp_path / 'bank'),
        ])
        output = json.loads(capsys.readouterr().out)
        assert output['bracket_results'][0]['compliance']['verdict'] == 'PASS'


class TestSearch:
    """Tests for tools/search.py."""

    def test_search_empty_bank(self, tmp_path):
        from tools.search import search
        result = search(query='louder', bank_dir=str(tmp_path / 'empty'))
        assert result['count'] == 0

    def test_search_list_all_empty(self, tmp_path):
        from tools.search import search
        result = search(list_all=True, bank_dir=str(tmp_path / 'empty'))
        assert result['count'] == 0

    def test_search_after_analyze(self, audio_pair, tmp_path):
        from tools.analyze import analyze
        from tools.search import search

        orig, var = audio_pair
        bank_dir = str(tmp_path / 'bank')

        analyze(orig, var, ['10-20'], 'louder drums',
                bank_dir=bank_dir, out_dir=str(tmp_path / 'out'))

        result = search(query='louder', bank_dir=bank_dir)
        assert result['count'] >= 1

    def test_search_run_id(self, audio_pair, tmp_path):
        from tools.analyze import analyze
        from tools.search import search

        orig, var = audio_pair
        bank_dir = str(tmp_path / 'bank')

        run_data = analyze(orig, var, ['10-20'], 'louder',
                           bank_dir=bank_dir, out_dir=str(tmp_path / 'out'))

        result = search(run_id=run_data['run_id'], bank_dir=bank_dir)
        assert 'run' in result
        assert result['run']['intent'] == 'louder'


class TestGenerate:
    """Tests for tools/generate.py (dry run only — no API calls)."""

    def test_dry_run(self):
        from tools.generate import generate
        result = generate(prompt='test prompt', dry_run=True)
        assert result['dry_run'] is True
        assert result['prompt'] == 'test prompt'
        assert result['file'] is None

    def test_dry_run_with_bracket(self):
        from tools.generate import generate
        result = generate(
            prompt='lo-fi beat',
            bracket_inject='0:30-0:45',
            intent='louder drums',
            dry_run=True,
        )
        assert result['dry_run'] is True
        assert 'BRACKET MODIFICATION' in result['prompt']
        assert 'louder drums' in result['prompt']

    def test_generate_cli_dry_run(self, capsys):
        from tools.generate import main
        main(['--prompt', 'test', '--dry-run'])
        output = json.loads(capsys.readouterr().out)
        assert output['dry_run'] is True
