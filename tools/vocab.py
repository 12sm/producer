#!/usr/bin/env python3
"""Vocab — build and query the prompt vocabulary index.

Aggregates snippet bank data to learn which prompt keywords reliably
produce which audio feature changes. This is how Claude builds intuition
about how to write Suno prompts.

Usage:
    # Build/rebuild the vocabulary index from snippet bank
    python -m tools.vocab --build

    # Look up what a keyword does
    python -m tools.vocab --lookup "dusty"

    # Find keywords that increase a feature
    python -m tools.vocab --find-for "onset_density" --direction increase

    # Show full vocabulary
    python -m tools.vocab --show
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vocabulary import build_vocab_index, load_vocab, lookup_keyword, find_keywords_for_feature


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Prompt vocabulary index')
    p.add_argument('--build', action='store_true',
                   help='Build/rebuild vocabulary from snippet bank')
    p.add_argument('--lookup', default=None,
                   help='Look up a keyword\'s average feature effects')
    p.add_argument('--find-for', default=None,
                   help='Find keywords that affect a given feature')
    p.add_argument('--direction', default=None, choices=['increase', 'decrease'],
                   help='Filter by direction (with --find-for)')
    p.add_argument('--show', action='store_true',
                   help='Show the full vocabulary index')
    p.add_argument('--bank-dir', default='./snippet_bank', help='Snippet bank dir')
    p.add_argument('--vocab-path', default='./snippet_bank/vocab_index.json',
                   help='Vocabulary index file path')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.build:
        index = build_vocab_index(args.bank_dir, args.vocab_path)
        print(json.dumps({
            'action': 'build',
            'keywords': len(index.get('keywords', {})),
            'total_observations': index.get('total_runs', 0),
            'path': args.vocab_path,
        }, indent=2))
        return

    if args.lookup:
        vocab = load_vocab(args.vocab_path)
        result = lookup_keyword(vocab, args.lookup)
        print(json.dumps(result, indent=2))
        return

    if args.find_for:
        vocab = load_vocab(args.vocab_path)
        result = find_keywords_for_feature(vocab, args.find_for, args.direction)
        print(json.dumps(result, indent=2))
        return

    if args.show:
        vocab = load_vocab(args.vocab_path)
        print(json.dumps(vocab, indent=2))
        return

    print(json.dumps({'error': 'Specify --build, --lookup, --find-for, or --show'}))


if __name__ == '__main__':
    main()
