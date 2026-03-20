#!/usr/bin/env python3
"""Search — query the snippet bank for past experiments.

Claude Code uses this to recall what worked before, look up keywords,
and build intuition about which prompts produce which results.

Usage:
    python -m tools.search "louder"
    python -m tools.search "dusty drums" --bank-dir ./snippet_bank
    python -m tools.search --list-all
    python -m tools.search --run-id 20240115_123456_abc123
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from snippet_bank import search_bank, list_runs, save_run


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Search the snippet bank')
    p.add_argument('query', nargs='?', default=None, help='Search query')
    p.add_argument('--bank-dir', default='./snippet_bank', help='Snippet bank dir')
    p.add_argument('--list-all', action='store_true', help='List all runs')
    p.add_argument('--run-id', default=None, help='Get full details for a run')
    return p.parse_args(argv)


def search(query=None, bank_dir='./snippet_bank', list_all=False, run_id=None):
    """Search or list snippet bank entries."""
    if run_id:
        entry_path = os.path.join(bank_dir, run_id, 'entry.json')
        if not os.path.exists(entry_path):
            return {'error': f'Run {run_id} not found', 'results': []}
        with open(entry_path, 'r') as f:
            return {'run': json.load(f)}

    if list_all:
        runs = list_runs(bank_dir)
        return {'count': len(runs), 'runs': runs}

    if query:
        results = search_bank(query, bank_dir)
        return {'query': query, 'count': len(results), 'results': results}

    return {'error': 'Provide a query, --list-all, or --run-id'}


def main(argv=None):
    args = parse_args(argv)
    result = search(
        query=args.query, bank_dir=args.bank_dir,
        list_all=args.list_all, run_id=args.run_id,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
