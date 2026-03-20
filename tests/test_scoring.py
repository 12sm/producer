"""Unit tests for compliance and drift scoring."""

import pytest
from scoring import score_compliance, score_drift, _check_expectation, CHANGE_THRESHOLD


# ── Expectation Checking ───────────────────────────────────────────

class TestCheckExpectation:
    def test_increase_met(self):
        assert _check_expectation(0.2, 'increase') is True

    def test_increase_not_met(self):
        assert _check_expectation(-0.1, 'increase') is False

    def test_increase_below_threshold(self):
        assert _check_expectation(0.03, 'increase') is False

    def test_decrease_met(self):
        assert _check_expectation(-0.2, 'decrease') is True

    def test_decrease_not_met(self):
        assert _check_expectation(0.1, 'decrease') is False

    def test_change_met_positive(self):
        assert _check_expectation(0.2, 'change') is True

    def test_change_met_negative(self):
        assert _check_expectation(-0.2, 'change') is True

    def test_change_not_met(self):
        assert _check_expectation(0.01, 'change') is False


# ── Compliance Scoring ─────────────────────────────────────────────

class TestScoreCompliance:
    def test_louder_intent_with_positive_rms(self):
        deltas = {
            'rms_mean': 0.5, 'rms_std': 0.0, 'centroid_mean': 0.0,
            'centroid_std': 0.0, 'onset_strength_mean': 0.0,
            'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'make it louder')
        assert result['verdict'] == 'PASS'
        assert result['score'] >= 0.7

    def test_louder_intent_with_negative_rms_fails(self):
        deltas = {
            'rms_mean': -0.5, 'rms_std': 0.0, 'centroid_mean': 0.0,
            'centroid_std': 0.0, 'onset_strength_mean': 0.0,
            'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'make it louder')
        assert result['verdict'] == 'FAIL'
        assert result['score'] < 0.4

    def test_brighter_intent_pass(self):
        deltas = {
            'rms_mean': 0.0, 'rms_std': 0.0, 'centroid_mean': 0.3,
            'centroid_std': 0.0, 'onset_strength_mean': 0.0,
            'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'brighter cymbals')
        assert result['verdict'] == 'PASS'

    def test_no_keyword_match_neutral(self):
        deltas = {
            'rms_mean': 0.5, 'rms_std': 0.0, 'centroid_mean': 0.0,
            'centroid_std': 0.0, 'onset_strength_mean': 0.0,
            'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'add more cowbell')
        assert result['verdict'] == 'MIXED'
        assert result['confidence'] == 0.0
        assert result['score'] == 0.5

    def test_multi_keyword_intent(self):
        """Intent 'louder and brighter' should check both rms and centroid."""
        deltas = {
            'rms_mean': 0.3, 'rms_std': 0.0, 'centroid_mean': 0.3,
            'centroid_std': 0.0, 'onset_strength_mean': 0.0,
            'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'louder and brighter')
        assert result['verdict'] == 'PASS'
        assert len(result['matched_rules']) >= 2

    def test_partial_compliance_mixed(self):
        """Intent 'punchy' expects rms_mean↑ and rms_std↑. Only one met → MIXED."""
        deltas = {
            'rms_mean': 0.3, 'rms_std': -0.1,  # rms up but std down
            'centroid_mean': 0.0, 'centroid_std': 0.0,
            'onset_strength_mean': 0.0, 'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'make it punchy')
        assert result['verdict'] == 'MIXED'

    def test_matched_rules_contain_details(self):
        deltas = {
            'rms_mean': 0.3, 'rms_std': 0.0, 'centroid_mean': 0.0,
            'centroid_std': 0.0, 'onset_strength_mean': 0.0,
            'onset_density': 0.0, 'tempo': 0.0,
        }
        result = score_compliance(deltas, 'louder')
        rules = result['matched_rules']
        assert len(rules) > 0
        r = rules[0]
        assert 'keyword' in r
        assert 'feature' in r
        assert 'expected' in r
        assert 'actual_delta' in r
        assert 'met' in r


# ── Drift Scoring ──────────────────────────────────────────────────

class TestScoreDrift:
    def test_zero_deltas_low_drift(self):
        anchor_deltas = [
            {'rms_mean': 0.0, 'centroid_mean': 0.0, 'onset_density': 0.0,
             'rms_std': 0.0, 'centroid_std': 0.0, 'onset_strength_mean': 0.0, 'tempo': 0.0},
        ]
        result = score_drift(anchor_deltas)
        assert result['verdict'] == 'LOW'
        assert result['overall_drift'] == 0.0

    def test_large_deltas_high_drift(self):
        anchor_deltas = [
            {'rms_mean': 0.5, 'centroid_mean': 0.5, 'onset_density': 0.5,
             'rms_std': 0.5, 'centroid_std': 0.5, 'onset_strength_mean': 0.5, 'tempo': 0.5},
        ]
        result = score_drift(anchor_deltas)
        assert result['verdict'] == 'HIGH'

    def test_empty_anchors_low_drift(self):
        result = score_drift([])
        assert result['verdict'] == 'LOW'
        assert result['overall_drift'] == 0.0

    def test_per_anchor_scores(self):
        anchor_deltas = [
            {'rms_mean': 0.1, 'centroid_mean': 0.0, 'onset_density': 0.0,
             'rms_std': 0.0, 'centroid_std': 0.0, 'onset_strength_mean': 0.0, 'tempo': 0.0},
            {'rms_mean': 0.0, 'centroid_mean': 0.1, 'onset_density': 0.0,
             'rms_std': 0.0, 'centroid_std': 0.0, 'onset_strength_mean': 0.0, 'tempo': 0.0},
        ]
        result = score_drift(anchor_deltas)
        assert len(result['per_anchor']) == 2
        for a in result['per_anchor']:
            assert 'drift_score' in a
            assert 'anchor_index' in a
