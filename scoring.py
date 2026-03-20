"""Intent compliance scoring and collateral drift detection."""

from features import delta_magnitude


# Maps intent keywords to expected feature directions.
# "increase" = we expect the delta to be positive
# "decrease" = we expect the delta to be negative
# "change"   = any significant change is a match
KEYWORD_RULES = {
    # Volume / dynamics
    'louder':   {'rms_mean': 'increase'},
    'quieter':  {'rms_mean': 'decrease'},
    'soft':     {'rms_mean': 'decrease'},
    'hard':     {'rms_mean': 'increase'},
    'punchy':   {'rms_mean': 'increase', 'rms_std': 'increase'},
    'dynamic':  {'rms_std': 'increase'},
    'compressed': {'rms_std': 'decrease'},
    'less':     {'rms_mean': 'decrease', 'onset_density': 'decrease'},

    # Brightness / tone
    'brighter': {'centroid_mean': 'increase'},
    'darker':   {'centroid_mean': 'decrease'},
    'warmer':   {'centroid_mean': 'decrease'},
    'crisp':    {'centroid_mean': 'increase'},
    'dull':     {'centroid_mean': 'decrease'},
    'airy':     {'centroid_mean': 'increase'},

    # Rhythm / busyness
    'tight':    {'onset_density': 'increase', 'rms_std': 'decrease'},
    'busy':     {'onset_density': 'increase'},
    'busier':   {'onset_density': 'increase'},
    'sparse':   {'onset_density': 'decrease', 'rms_mean': 'decrease'},
    'simpler':  {'onset_density': 'decrease'},
    'simple':   {'onset_density': 'decrease'},
    'dense':    {'onset_density': 'increase'},
    'swung':    {'onset_density': 'change'},
    'swing':    {'onset_density': 'change'},

    # Instrument-specific hints
    'no crash':  {'centroid_mean': 'decrease', 'rms_mean': 'decrease'},
    'no cymbal': {'centroid_mean': 'decrease'},
    'riser':     {'centroid_mean': 'increase', 'rms_mean': 'increase'},
    'no riser':  {'centroid_mean': 'decrease', 'rms_mean': 'decrease'},
    'less edm':  {'centroid_mean': 'decrease', 'onset_density': 'decrease'},

    # Feel
    'subtle':    {'rms_mean': 'decrease', 'centroid_mean': 'decrease'},
    'aggressive': {'rms_mean': 'increase', 'centroid_mean': 'increase'},
    'gentle':    {'rms_mean': 'decrease'},
    'heavy':     {'rms_mean': 'increase', 'centroid_mean': 'decrease'},
    'light':     {'rms_mean': 'decrease'},
}

# Threshold for "significant" delta when checking "change" direction
CHANGE_THRESHOLD = 0.05


def score_compliance(deltas: dict, intent_text: str) -> dict:
    """Score how well the variant followed the bracket intent.

    Returns:
        score: 0.0-1.0 (fraction of expectations met)
        confidence: 0.0-1.0 (how many keywords matched)
        verdict: PASS | MIXED | FAIL
        matched_rules: list of matched keyword results
        explanation: human-readable summary
    """
    intent_lower = intent_text.lower()
    matched_rules = []
    met_count = 0
    total_expectations = 0

    for keyword, expectations in KEYWORD_RULES.items():
        if keyword in intent_lower:
            for feature, direction in expectations.items():
                if feature not in deltas:
                    continue
                total_expectations += 1
                delta_val = deltas[feature]
                met = _check_expectation(delta_val, direction)
                matched_rules.append({
                    'keyword': keyword,
                    'feature': feature,
                    'expected': direction,
                    'actual_delta': delta_val,
                    'met': met,
                })
                if met:
                    met_count += 1

    if total_expectations == 0:
        return {
            'score': 0.5,
            'confidence': 0.0,
            'verdict': 'MIXED',
            'matched_rules': [],
            'explanation': 'No keyword rules matched the intent text. Score is neutral.',
        }

    score = met_count / total_expectations
    confidence = min(1.0, len(set(r['keyword'] for r in matched_rules)) / 3.0)

    if score >= 0.7:
        verdict = 'PASS'
    elif score >= 0.4:
        verdict = 'MIXED'
    else:
        verdict = 'FAIL'

    met_list = [r for r in matched_rules if r['met']]
    missed_list = [r for r in matched_rules if not r['met']]
    explanation_parts = []
    if met_list:
        explanation_parts.append(
            f"Met {len(met_list)} expectation(s): " +
            ', '.join(f"{r['keyword']}→{r['feature']}" for r in met_list)
        )
    if missed_list:
        explanation_parts.append(
            f"Missed {len(missed_list)} expectation(s): " +
            ', '.join(f"{r['keyword']}→{r['feature']}" for r in missed_list)
        )

    return {
        'score': round(score, 3),
        'confidence': round(confidence, 3),
        'verdict': verdict,
        'matched_rules': matched_rules,
        'explanation': '. '.join(explanation_parts),
    }


def _check_expectation(delta_val: float, direction: str) -> bool:
    """Check if a delta matches the expected direction."""
    if direction == 'increase':
        return delta_val > CHANGE_THRESHOLD
    elif direction == 'decrease':
        return delta_val < -CHANGE_THRESHOLD
    elif direction == 'change':
        return abs(delta_val) > CHANGE_THRESHOLD
    return False


def score_drift(anchor_deltas: list) -> dict:
    """Score collateral drift across anchor windows.

    Args:
        anchor_deltas: List of delta dicts, one per anchor window.

    Returns:
        per_anchor: list of per-anchor drift scores
        overall_drift: mean drift score
        verdict: LOW | MED | HIGH
    """
    if not anchor_deltas:
        return {
            'per_anchor': [],
            'overall_drift': 0.0,
            'verdict': 'LOW',
        }

    per_anchor = []
    for i, deltas in enumerate(anchor_deltas):
        mag = delta_magnitude(deltas)
        per_anchor.append({
            'anchor_index': i,
            'drift_score': round(mag, 4),
            'deltas': deltas,
        })

    overall = sum(a['drift_score'] for a in per_anchor) / len(per_anchor)

    if overall < 0.15:
        verdict = 'LOW'
    elif overall < 0.35:
        verdict = 'MED'
    else:
        verdict = 'HIGH'

    return {
        'per_anchor': per_anchor,
        'overall_drift': round(overall, 4),
        'verdict': verdict,
    }
