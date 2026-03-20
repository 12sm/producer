"""Tests for the session runner."""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import argparse
from session import cmd_init, cmd_record, cmd_status, cmd_accept, cmd_list


@pytest.fixture
def session_dir(tmp_path):
    return str(tmp_path / 'sessions')


class TestSessionInit:

    def test_init_creates_session(self, session_dir):
        args = argparse.Namespace(
            prompt='lo-fi beat',
            bracket=['0:30-0:45'],
            intent='louder drums',
            session_dir=session_dir,
            max_iterations=5,
            target_compliance=0.7,
            target_drift=0.15,
        )
        result = cmd_init(args)

        assert result['status'] == 'active'
        assert result['prompt'] == 'lo-fi beat'
        assert result['intent'] == 'louder drums'
        assert os.path.exists(os.path.join(session_dir, f"{result['session_id']}.json"))


class TestSessionRecord:

    @pytest.fixture
    def active_session(self, session_dir):
        args = argparse.Namespace(
            prompt='lo-fi beat',
            bracket=['0:30-0:45'],
            intent='louder drums',
            session_dir=session_dir,
            max_iterations=3,
            target_compliance=0.7,
            target_drift=0.15,
        )
        return cmd_init(args)

    def test_record_iteration(self, active_session, session_dir):
        args = argparse.Namespace(
            session_id=active_session['session_id'],
            variant_prompt='lo-fi beat [0:30-0:45] louder drums',
            run_id='test_run_001',
            compliance_score=0.8,
            compliance_verdict='PASS',
            drift_score=0.1,
            drift_verdict='LOW',
            notes='Sounds good',
            session_dir=session_dir,
        )
        result = cmd_record(args)

        assert result['iteration'] == 1
        assert result['met_targets'] is True
        assert result['remaining'] == 2

    def test_record_unmet_targets(self, active_session, session_dir):
        args = argparse.Namespace(
            session_id=active_session['session_id'],
            variant_prompt='test',
            run_id='test_run_002',
            compliance_score=0.3,
            compliance_verdict='FAIL',
            drift_score=0.4,
            drift_verdict='HIGH',
            notes='Not great',
            session_dir=session_dir,
        )
        result = cmd_record(args)

        assert result['met_targets'] is False
        assert result['met_compliance'] is False
        assert result['met_drift'] is False

    def test_max_iterations_reached(self, active_session, session_dir):
        for i in range(3):
            args = argparse.Namespace(
                session_id=active_session['session_id'],
                variant_prompt='test',
                run_id=f'run_{i}',
                compliance_score=0.3,
                compliance_verdict='FAIL',
                drift_score=0.4,
                drift_verdict='HIGH',
                notes='',
                session_dir=session_dir,
            )
            result = cmd_record(args)

        assert result['status'] == 'max_iterations_reached'
        assert result['remaining'] == 0


class TestSessionStatus:

    def test_status_with_iterations(self, session_dir):
        init_args = argparse.Namespace(
            prompt='test', bracket=['0:30-0:45'], intent='louder',
            session_dir=session_dir, max_iterations=5,
            target_compliance=0.7, target_drift=0.15,
        )
        session = cmd_init(init_args)

        # Record a good iteration
        rec_args = argparse.Namespace(
            session_id=session['session_id'],
            variant_prompt='test', run_id='run_001',
            compliance_score=0.85, compliance_verdict='PASS',
            drift_score=0.08, drift_verdict='LOW',
            notes='', session_dir=session_dir,
        )
        cmd_record(rec_args)

        # Check status
        stat_args = argparse.Namespace(
            session_id=session['session_id'],
            session_dir=session_dir,
        )
        result = cmd_status(stat_args)

        assert result['iterations_completed'] == 1
        assert result['any_met_targets'] is True
        assert result['best_iteration']['compliance_score'] == 0.85

    def test_status_not_found(self, session_dir):
        args = argparse.Namespace(
            session_id='nonexistent',
            session_dir=session_dir,
        )
        result = cmd_status(args)
        assert 'error' in result


class TestSessionAccept:

    def test_accept_session(self, session_dir):
        init_args = argparse.Namespace(
            prompt='test', bracket=['0:30-0:45'], intent='louder',
            session_dir=session_dir, max_iterations=5,
            target_compliance=0.7, target_drift=0.15,
        )
        session = cmd_init(init_args)

        acc_args = argparse.Namespace(
            session_id=session['session_id'],
            accepted_run='run_001',
            notes='This is the one',
            session_dir=session_dir,
        )
        result = cmd_accept(acc_args)

        assert result['status'] == 'accepted'
        assert result['accepted_run'] == 'run_001'


class TestSessionList:

    def test_list_sessions(self, session_dir):
        for i in range(3):
            args = argparse.Namespace(
                prompt=f'test {i}', bracket=['0:30-0:45'],
                intent=f'intent {i}', session_dir=session_dir,
                max_iterations=5, target_compliance=0.7, target_drift=0.15,
            )
            cmd_init(args)

        result = cmd_list(argparse.Namespace(session_dir=session_dir))
        assert len(result['sessions']) == 3

    def test_list_empty(self, session_dir):
        result = cmd_list(argparse.Namespace(session_dir=session_dir))
        assert result['sessions'] == []
