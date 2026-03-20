"""Unit tests for snippet bank storage and search."""

import json
import os
import pytest
from snippet_bank import create_run_id, save_run, get_slices_dir, append_index, search_bank, list_runs


class TestRunId:
    def test_format(self):
        rid = create_run_id()
        parts = rid.split('_')
        assert len(parts) == 3
        assert len(parts[0]) == 8   # YYYYMMDD
        assert len(parts[1]) == 6   # HHMMSS
        assert len(parts[2]) == 6   # hash

    def test_unique(self):
        ids = {create_run_id() for _ in range(10)}
        assert len(ids) == 10


class TestSaveRun:
    def test_creates_entry_json(self, tmp_bank):
        rid = 'test_run_abc123'
        data = {'intent': 'louder drums', 'score': 0.8}
        run_dir = save_run(rid, data, tmp_bank)
        entry_path = os.path.join(run_dir, 'entry.json')
        assert os.path.exists(entry_path)
        with open(entry_path) as f:
            loaded = json.load(f)
        assert loaded['intent'] == 'louder drums'

    def test_slices_dir(self, tmp_bank):
        rid = 'test_run_abc123'
        slices = get_slices_dir(rid, tmp_bank)
        assert os.path.isdir(slices)
        assert slices.endswith('slices')


class TestIndex:
    def test_append_and_search(self, tmp_bank):
        append_index('run_001', {'intent': 'louder drums', 'verdict': 'PASS'}, tmp_bank)
        append_index('run_002', {'intent': 'softer piano', 'verdict': 'FAIL'}, tmp_bank)

        results = search_bank('louder', tmp_bank)
        assert len(results) == 1
        assert results[0]['run_id'] == 'run_001'

    def test_search_case_insensitive(self, tmp_bank):
        append_index('run_001', {'intent': 'LOUDER DRUMS'}, tmp_bank)
        results = search_bank('louder', tmp_bank)
        assert len(results) == 1

    def test_list_runs(self, tmp_bank):
        append_index('run_001', {'intent': 'test1'}, tmp_bank)
        append_index('run_002', {'intent': 'test2'}, tmp_bank)
        runs = list_runs(tmp_bank)
        assert len(runs) == 2

    def test_search_empty_bank(self, tmp_bank):
        assert search_bank('anything', tmp_bank) == []
