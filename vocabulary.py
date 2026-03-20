"""Vocabulary index — maps prompt keywords to observed feature effects.

Scans the snippet bank to build a statistical model of which words in
intent/prompt text correlate with which feature changes. Claude uses
this to reason about prompt engineering: "if I want more onset_density,
I should try 'busy', '16th-note', 'rapid'."

The index is a JSON file with structure:
{
    "total_runs": 42,
    "built_at": "2024-01-15T...",
    "keywords": {
        "louder": {
            "count": 8,
            "avg_deltas": {"rms_mean": 0.23, "centroid_mean": 0.05, ...},
            "std_deltas": {"rms_mean": 0.12, ...},
            "pass_rate": 0.75,
            "associated_intents": ["louder drums", "louder kick", ...]
        },
        ...
    }
}
"""

import json
import math
import os
import re
from collections import defaultdict
from datetime import datetime, timezone


# Words to skip when tokenizing intents
STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'it', 'its', 'this', 'that', 'as',
    'be', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
    'might', 'can', 'shall', 'not', 'no', 'more', 'very', 'too', 'so',
    'just', 'than', 'then', 'also', 'into', 'over', 'such', 'some',
    'add', 'make', 'use', 'like', 'want', 'need', 'try',
}

# Multi-word phrases to detect as single tokens (checked before splitting)
PHRASE_TOKENS = [
    'no crash', 'no cymbal', 'no riser', 'hi-hats', 'hi hats',
    'less edm', 'half-time', 'half time', 'lo-fi', 'lo fi',
    'low-mid', 'low mid', 'high-pass', 'high pass',
]


def _tokenize_intent(text):
    """Extract meaningful keywords from intent text."""
    text_lower = text.lower()
    tokens = []

    # Extract phrase tokens first
    for phrase in PHRASE_TOKENS:
        if phrase in text_lower:
            tokens.append(phrase)
            text_lower = text_lower.replace(phrase, ' ')

    # Split remaining into words
    words = re.findall(r'[a-z][a-z\-]+', text_lower)
    for w in words:
        if w not in STOP_WORDS and len(w) > 1:
            tokens.append(w)

    return list(set(tokens))


def build_vocab_index(bank_dir='./snippet_bank', vocab_path=None):
    """Build vocabulary index by scanning all snippet bank entries.

    Reads every entry.json, extracts intent keywords, and aggregates
    the observed feature deltas per keyword.
    """
    if vocab_path is None:
        vocab_path = os.path.join(bank_dir, 'vocab_index.json')

    keyword_data = defaultdict(lambda: {
        'deltas_list': [],
        'verdicts': [],
        'intents': set(),
    })

    total_runs = 0

    # Walk all run directories
    if not os.path.isdir(bank_dir):
        return _save_empty(vocab_path)

    for entry_name in sorted(os.listdir(bank_dir)):
        entry_path = os.path.join(bank_dir, entry_name, 'entry.json')
        if not os.path.isfile(entry_path):
            continue

        try:
            with open(entry_path, 'r') as f:
                entry = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        intent = entry.get('intent', '')
        if not intent:
            continue

        total_runs += 1
        tokens = _tokenize_intent(intent)

        # Gather deltas from all bracket results
        for br in entry.get('bracket_results', []):
            deltas = br.get('deltas', {})
            verdict = br.get('compliance', {}).get('verdict', 'MIXED')

            for token in tokens:
                kd = keyword_data[token]
                kd['deltas_list'].append(deltas)
                kd['verdicts'].append(verdict)
                kd['intents'].add(intent)

    # Compute aggregates
    keywords = {}
    for kw, data in keyword_data.items():
        if not data['deltas_list']:
            continue

        count = len(data['deltas_list'])
        avg_deltas = _average_deltas(data['deltas_list'])
        std_deltas = _std_deltas(data['deltas_list'], avg_deltas)
        pass_count = sum(1 for v in data['verdicts'] if v == 'PASS')
        pass_rate = pass_count / count if count > 0 else 0.0

        keywords[kw] = {
            'count': count,
            'avg_deltas': avg_deltas,
            'std_deltas': std_deltas,
            'pass_rate': round(pass_rate, 3),
            'associated_intents': sorted(data['intents'])[:10],
        }

    index = {
        'total_runs': total_runs,
        'built_at': datetime.now(timezone.utc).isoformat(),
        'keywords': dict(sorted(keywords.items(), key=lambda x: -x[1]['count'])),
    }

    os.makedirs(os.path.dirname(vocab_path) or '.', exist_ok=True)
    with open(vocab_path, 'w') as f:
        json.dump(index, f, indent=2)

    return index


def _save_empty(vocab_path):
    index = {
        'total_runs': 0,
        'built_at': datetime.now(timezone.utc).isoformat(),
        'keywords': {},
    }
    os.makedirs(os.path.dirname(vocab_path) or '.', exist_ok=True)
    with open(vocab_path, 'w') as f:
        json.dump(index, f, indent=2)
    return index


def _average_deltas(deltas_list):
    """Compute mean of each feature across a list of delta dicts."""
    if not deltas_list:
        return {}
    keys = deltas_list[0].keys()
    avg = {}
    for k in keys:
        vals = [d.get(k, 0) for d in deltas_list]
        avg[k] = round(sum(vals) / len(vals), 4)
    return avg


def _std_deltas(deltas_list, avg_deltas):
    """Compute std dev of each feature across a list of delta dicts."""
    if len(deltas_list) < 2:
        return {k: 0.0 for k in avg_deltas}
    std = {}
    for k in avg_deltas:
        vals = [d.get(k, 0) for d in deltas_list]
        mean = avg_deltas[k]
        variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        std[k] = round(math.sqrt(variance), 4)
    return std


def load_vocab(vocab_path='./snippet_bank/vocab_index.json'):
    """Load the vocabulary index from disk."""
    if not os.path.exists(vocab_path):
        return {'total_runs': 0, 'keywords': {}, 'error': 'No vocab index found. Run --build first.'}
    with open(vocab_path, 'r') as f:
        return json.load(f)


def lookup_keyword(vocab, keyword):
    """Look up a keyword's average feature effects.

    Returns the keyword entry plus a human-readable summary.
    """
    kw_lower = keyword.lower()
    keywords = vocab.get('keywords', {})

    if kw_lower not in keywords:
        # Fuzzy: check if it's a substring of any keyword
        matches = {k: v for k, v in keywords.items() if kw_lower in k or k in kw_lower}
        if not matches:
            return {'keyword': keyword, 'found': False, 'message': 'Not in vocabulary yet.'}
        return {
            'keyword': keyword,
            'found': False,
            'partial_matches': list(matches.keys()),
            'message': f'Exact match not found. Partial matches: {list(matches.keys())}',
        }

    entry = keywords[kw_lower]
    # Build a plain-English summary
    effects = []
    for feat, delta in entry['avg_deltas'].items():
        if abs(delta) > 0.03:
            direction = 'increases' if delta > 0 else 'decreases'
            effects.append(f"{feat} {direction} by {abs(delta):.2f}")

    return {
        'keyword': keyword,
        'found': True,
        'count': entry['count'],
        'pass_rate': entry['pass_rate'],
        'effects': effects,
        'avg_deltas': entry['avg_deltas'],
        'std_deltas': entry['std_deltas'],
        'associated_intents': entry['associated_intents'],
    }


def find_keywords_for_feature(vocab, feature, direction=None):
    """Find keywords that affect a given feature.

    Args:
        vocab: The vocabulary index.
        feature: Feature name (e.g. 'onset_density').
        direction: 'increase' or 'decrease' (optional filter).

    Returns list of keywords ranked by effect magnitude.
    """
    keywords = vocab.get('keywords', {})
    results = []

    for kw, entry in keywords.items():
        delta = entry.get('avg_deltas', {}).get(feature)
        if delta is None:
            continue
        if direction == 'increase' and delta <= 0.03:
            continue
        if direction == 'decrease' and delta >= -0.03:
            continue
        if direction is None and abs(delta) <= 0.03:
            continue

        results.append({
            'keyword': kw,
            'avg_delta': delta,
            'std_delta': entry.get('std_deltas', {}).get(feature, 0),
            'count': entry['count'],
            'pass_rate': entry['pass_rate'],
        })

    results.sort(key=lambda x: abs(x['avg_delta']), reverse=True)
    return {
        'feature': feature,
        'direction': direction,
        'matches': results,
    }
