#!/usr/bin/env python3
"""Session runner — multi-step production workflow for Claude Code.

A session represents a complete music production task: generate an
original track, then iteratively generate and evaluate variants until
the results meet quality thresholds.

Claude Code drives sessions by:
1. Starting a session with a prompt and intent
2. Reviewing analysis results (JSON)
3. Deciding whether to iterate or accept
4. Building vocabulary knowledge along the way

Usage:
    # Initialize a new session
    python session.py init \
        --prompt "Lo-fi hip hop beat, mellow piano, dusty drums, 85 BPM" \
        --bracket "0:30-0:45" \
        --intent "louder drums, punchy kick" \
        --session-dir ./sessions

    # Record a generation attempt
    python session.py record \
        --session-id <id> \
        --variant-path variant.mp3 \
        --analysis-json report.json

    # Get session status
    python session.py status --session-id <id>

    # Mark session as complete
    python session.py accept --session-id <id> --accepted-run <run_id>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from snippet_bank import create_run_id


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Production session runner')
    sub = p.add_subparsers(dest='command', required=True)

    # init
    init_p = sub.add_parser('init', help='Start a new session')
    init_p.add_argument('--prompt', required=True, help='Base generation prompt')
    init_p.add_argument('--bracket', action='append', required=True,
                        help='Bracket window (repeatable)')
    init_p.add_argument('--intent', required=True, help='Intent description')
    init_p.add_argument('--session-dir', default='./sessions',
                        help='Sessions directory')
    init_p.add_argument('--max-iterations', type=int, default=10,
                        help='Max generation attempts (default: 10)')
    init_p.add_argument('--target-compliance', type=float, default=0.7,
                        help='Target compliance score (default: 0.7)')
    init_p.add_argument('--target-drift', type=float, default=0.15,
                        help='Max acceptable drift (default: 0.15)')

    # record
    rec_p = sub.add_parser('record', help='Record a generation attempt')
    rec_p.add_argument('--session-id', required=True, help='Session ID')
    rec_p.add_argument('--variant-prompt', required=True,
                       help='The prompt used for this variant')
    rec_p.add_argument('--run-id', required=True,
                       help='Bracket lab run ID from analysis')
    rec_p.add_argument('--compliance-score', type=float, required=True)
    rec_p.add_argument('--compliance-verdict', required=True)
    rec_p.add_argument('--drift-score', type=float, required=True)
    rec_p.add_argument('--drift-verdict', required=True)
    rec_p.add_argument('--notes', default='', help='Claude\'s reasoning')
    rec_p.add_argument('--session-dir', default='./sessions')

    # status
    stat_p = sub.add_parser('status', help='Get session status')
    stat_p.add_argument('--session-id', required=True)
    stat_p.add_argument('--session-dir', default='./sessions')

    # accept
    acc_p = sub.add_parser('accept', help='Mark session as complete')
    acc_p.add_argument('--session-id', required=True)
    acc_p.add_argument('--accepted-run', required=True,
                       help='Run ID of the accepted variant')
    acc_p.add_argument('--notes', default='', help='Why this was accepted')
    acc_p.add_argument('--session-dir', default='./sessions')

    # list
    list_p = sub.add_parser('list', help='List all sessions')
    list_p.add_argument('--session-dir', default='./sessions')

    return p.parse_args(argv)


def _session_path(session_dir, session_id):
    return os.path.join(session_dir, f'{session_id}.json')


def _load_session(session_dir, session_id):
    path = _session_path(session_dir, session_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def _save_session(session_dir, session_id, data):
    os.makedirs(session_dir, exist_ok=True)
    path = _session_path(session_dir, session_id)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def cmd_init(args):
    """Initialize a new production session."""
    session_id = create_run_id()
    session = {
        'session_id': session_id,
        'status': 'active',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'prompt': args.prompt,
        'brackets': args.bracket,
        'intent': args.intent,
        'max_iterations': args.max_iterations,
        'target_compliance': args.target_compliance,
        'target_drift': args.target_drift,
        'iterations': [],
        'accepted_run': None,
        'accepted_at': None,
    }
    _save_session(args.session_dir, session_id, session)
    return session


def cmd_record(args):
    """Record a generation attempt in the session."""
    session = _load_session(args.session_dir, args.session_id)
    if not session:
        return {'error': f'Session {args.session_id} not found'}

    iteration = {
        'iteration': len(session['iterations']) + 1,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'variant_prompt': args.variant_prompt,
        'run_id': args.run_id,
        'compliance_score': args.compliance_score,
        'compliance_verdict': args.compliance_verdict,
        'drift_score': args.drift_score,
        'drift_verdict': args.drift_verdict,
        'notes': args.notes,
    }

    # Check if targets met
    met_compliance = args.compliance_score >= session['target_compliance']
    met_drift = args.drift_score <= session['target_drift']
    iteration['met_targets'] = met_compliance and met_drift

    session['iterations'].append(iteration)

    # Auto-check if we've hit max iterations
    if len(session['iterations']) >= session['max_iterations']:
        session['status'] = 'max_iterations_reached'

    _save_session(args.session_dir, args.session_id, session)

    return {
        'session_id': args.session_id,
        'iteration': iteration['iteration'],
        'met_targets': iteration['met_targets'],
        'met_compliance': met_compliance,
        'met_drift': met_drift,
        'remaining': session['max_iterations'] - len(session['iterations']),
        'status': session['status'],
    }


def cmd_status(args):
    """Get session status summary."""
    session = _load_session(args.session_dir, args.session_id)
    if not session:
        return {'error': f'Session {args.session_id} not found'}

    iterations = session['iterations']
    best = None
    if iterations:
        # Best = highest compliance with lowest drift
        best = max(iterations,
                   key=lambda i: (i['compliance_score'], -i['drift_score']))

    return {
        'session_id': session['session_id'],
        'status': session['status'],
        'prompt': session['prompt'],
        'intent': session['intent'],
        'iterations_completed': len(iterations),
        'max_iterations': session['max_iterations'],
        'target_compliance': session['target_compliance'],
        'target_drift': session['target_drift'],
        'any_met_targets': any(i.get('met_targets') for i in iterations),
        'best_iteration': best,
        'accepted_run': session.get('accepted_run'),
    }


def cmd_accept(args):
    """Mark session as complete with an accepted variant."""
    session = _load_session(args.session_dir, args.session_id)
    if not session:
        return {'error': f'Session {args.session_id} not found'}

    session['status'] = 'accepted'
    session['accepted_run'] = args.accepted_run
    session['accepted_at'] = datetime.now(timezone.utc).isoformat()
    session['accept_notes'] = args.notes

    _save_session(args.session_dir, args.session_id, session)
    return {
        'session_id': args.session_id,
        'status': 'accepted',
        'accepted_run': args.accepted_run,
    }


def cmd_list(args):
    """List all sessions."""
    session_dir = args.session_dir
    if not os.path.isdir(session_dir):
        return {'sessions': []}

    sessions = []
    for fname in sorted(os.listdir(session_dir)):
        if fname.endswith('.json'):
            path = os.path.join(session_dir, fname)
            try:
                with open(path, 'r') as f:
                    s = json.load(f)
                sessions.append(s)
            except (json.JSONDecodeError, IOError, KeyError):
                continue

    return {'sessions': sessions}


def main(argv=None):
    args = parse_args(argv)
    commands = {
        'init': cmd_init,
        'record': cmd_record,
        'status': cmd_status,
        'accept': cmd_accept,
        'list': cmd_list,
    }
    result = commands[args.command](args)
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
