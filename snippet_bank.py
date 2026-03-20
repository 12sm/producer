"""Snippet bank storage and JSONL index management."""

import hashlib
import json
import os
from datetime import datetime, timezone


def create_run_id() -> str:
    """Generate a run ID: YYYYMMDD_HHMMSS_<6-char hash>."""
    now = datetime.now(timezone.utc)
    ts = now.strftime('%Y%m%d_%H%M%S')
    h = hashlib.sha256(ts.encode() + os.urandom(8)).hexdigest()[:6]
    return f"{ts}_{h}"


def save_run(run_id: str, run_data: dict, bank_dir: str = './snippet_bank'):
    """Save a complete run to the snippet bank.

    Creates:
        <bank_dir>/<run_id>/entry.json
    """
    run_dir = os.path.join(bank_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    entry_path = os.path.join(run_dir, 'entry.json')
    with open(entry_path, 'w') as f:
        json.dump(run_data, f, indent=2, default=str)

    return run_dir


def get_slices_dir(run_id: str, bank_dir: str = './snippet_bank') -> str:
    """Get (and create) the slices directory for a run."""
    slices_dir = os.path.join(bank_dir, run_id, 'slices')
    os.makedirs(slices_dir, exist_ok=True)
    return slices_dir


def append_index(run_id: str, summary: dict, bank_dir: str = './snippet_bank'):
    """Append a summary line to the index.jsonl file.

    Summary should include: run_id, timestamp, intent, verdict, drift, bracket windows.
    """
    os.makedirs(bank_dir, exist_ok=True)
    index_path = os.path.join(bank_dir, 'index.jsonl')

    entry = {'run_id': run_id, **summary}
    with open(index_path, 'a') as f:
        f.write(json.dumps(entry, default=str) + '\n')


def search_bank(query: str, bank_dir: str = './snippet_bank') -> list:
    """Simple substring search over index.jsonl entries.

    Returns list of matching entries.
    """
    index_path = os.path.join(bank_dir, 'index.jsonl')
    if not os.path.exists(index_path):
        return []

    query_lower = query.lower()
    results = []
    with open(index_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if query_lower in line.lower():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return results


def list_runs(bank_dir: str = './snippet_bank') -> list:
    """List all runs in the snippet bank."""
    index_path = os.path.join(bank_dir, 'index.jsonl')
    if not os.path.exists(index_path):
        return []

    runs = []
    with open(index_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return runs
