#!/usr/bin/env python3
"""Bridge server — HTTP endpoint that Claude Code talks to.

Routes requests to either the Suno API client or the Chrome extension
bridge, depending on configuration.

Usage:
    # Start with API backend (uses SUNO_API_KEY)
    python bridge_server.py --backend api

    # Start with Chrome extension backend
    python bridge_server.py --backend chrome

    # Default port is 7862
    python bridge_server.py --port 7862

Endpoints:
    POST /generate     — Generate a track from a prompt
    POST /analyze      — Run bracket lab analysis
    GET  /listen       — Extract features from audio
    GET  /search       — Search snippet bank
    GET  /vocab        — Query vocabulary index
    GET  /health       — Health check
    GET  /status/:id   — Check generation status

Claude Code calls these endpoints. The server routes to the appropriate
backend and returns JSON results.
"""

import argparse
import json
import os
import sys
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))


class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the bridge server."""

    def log_message(self, format, *args):
        """Suppress default logging; use our own."""
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode())

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/health':
            self._send_json({'status': 'ok', 'backend': self.server.backend})
            return

        if path == '/listen':
            self._handle_listen(params)
            return

        if path == '/search':
            self._handle_search(params)
            return

        if path == '/vocab':
            self._handle_vocab(params)
            return

        if path.startswith('/session'):
            self._handle_session_get(path, params)
            return

        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == '/generate':
            self._handle_generate(body)
            return

        if path == '/analyze':
            self._handle_analyze(body)
            return

        if path.startswith('/session'):
            self._handle_session_post(path, body)
            return

        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)

    # ── Handlers ──────────────────────────────────────────────────

    def _handle_generate(self, body):
        prompt = body.get('prompt')
        if not prompt:
            self._send_json({'error': 'prompt is required'}, 400)
            return

        try:
            from tools.generate import generate
            result = generate(
                prompt=prompt,
                bracket_inject=body.get('bracket_inject'),
                intent=body.get('intent'),
                filename=body.get('filename'),
                out_dir=body.get('out_dir', './audio'),
                dry_run=body.get('dry_run', False),
            )
            self._send_json(result)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_analyze(self, body):
        required = ['original', 'variant', 'brackets', 'intent']
        missing = [k for k in required if k not in body]
        if missing:
            self._send_json({'error': f'Missing fields: {missing}'}, 400)
            return

        try:
            from tools.analyze import analyze
            result = analyze(
                original_path=body['original'],
                variant_path=body['variant'],
                bracket_strs=body['brackets'],
                intent=body['intent'],
                prompt_text=body.get('prompt_text', ''),
                out_dir=body.get('out_dir', './lab_out'),
                bank_dir=body.get('bank_dir', './snippet_bank'),
                save=body.get('save', True),
            )
            self._send_json(result)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_listen(self, params):
        audio = params.get('audio', [None])[0]
        if not audio:
            self._send_json({'error': 'audio param required'}, 400)
            return

        regions = params.get('region', None)
        try:
            from tools.listen import listen
            result = listen(audio, regions)
            self._send_json(result)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_search(self, params):
        query = params.get('q', [None])[0]
        list_all = 'all' in params
        run_id = params.get('run_id', [None])[0]

        try:
            from tools.search import search
            result = search(
                query=query,
                list_all=list_all,
                run_id=run_id,
                bank_dir=params.get('bank_dir', ['./snippet_bank'])[0],
            )
            self._send_json(result)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_vocab(self, params):
        action = params.get('action', ['show'])[0]

        try:
            from vocabulary import build_vocab_index, load_vocab, lookup_keyword, find_keywords_for_feature

            vocab_path = params.get('vocab_path', ['./snippet_bank/vocab_index.json'])[0]
            bank_dir = params.get('bank_dir', ['./snippet_bank'])[0]

            if action == 'build':
                index = build_vocab_index(bank_dir, vocab_path)
                self._send_json({
                    'action': 'build',
                    'keywords': len(index.get('keywords', {})),
                    'total_observations': index.get('total_runs', 0),
                })
                return

            vocab = load_vocab(vocab_path)

            if action == 'lookup':
                keyword = params.get('keyword', [None])[0]
                if not keyword:
                    self._send_json({'error': 'keyword param required'}, 400)
                    return
                self._send_json(lookup_keyword(vocab, keyword))
                return

            if action == 'find':
                feature = params.get('feature', [None])[0]
                direction = params.get('direction', [None])[0]
                if not feature:
                    self._send_json({'error': 'feature param required'}, 400)
                    return
                self._send_json(find_keywords_for_feature(vocab, feature, direction))
                return

            self._send_json(vocab)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_session_get(self, path, params):
        try:
            from session import _load_session
            session_dir = params.get('session_dir', ['./sessions'])[0]

            parts = path.strip('/').split('/')
            if len(parts) >= 2:
                session_id = parts[1]
                session = _load_session(session_dir, session_id)
                if session:
                    self._send_json(session)
                else:
                    self._send_json({'error': 'Session not found'}, 404)
            else:
                # List sessions
                from session import cmd_list
                import argparse
                args = argparse.Namespace(session_dir=session_dir)
                self._send_json(cmd_list(args))
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_session_post(self, path, body):
        try:
            import argparse
            session_dir = body.get('session_dir', './sessions')
            parts = path.strip('/').split('/')
            action = parts[1] if len(parts) >= 2 else None

            if action == 'init':
                from session import cmd_init
                args = argparse.Namespace(
                    prompt=body['prompt'],
                    bracket=body['brackets'],
                    intent=body['intent'],
                    session_dir=session_dir,
                    max_iterations=body.get('max_iterations', 10),
                    target_compliance=body.get('target_compliance', 0.7),
                    target_drift=body.get('target_drift', 0.15),
                )
                self._send_json(cmd_init(args))
            elif action == 'record':
                from session import cmd_record
                args = argparse.Namespace(
                    session_id=body['session_id'],
                    variant_prompt=body['variant_prompt'],
                    run_id=body['run_id'],
                    compliance_score=body['compliance_score'],
                    compliance_verdict=body['compliance_verdict'],
                    drift_score=body['drift_score'],
                    drift_verdict=body['drift_verdict'],
                    notes=body.get('notes', ''),
                    session_dir=session_dir,
                )
                self._send_json(cmd_record(args))
            elif action == 'accept':
                from session import cmd_accept
                args = argparse.Namespace(
                    session_id=body['session_id'],
                    accepted_run=body['accepted_run'],
                    notes=body.get('notes', ''),
                    session_dir=session_dir,
                )
                self._send_json(cmd_accept(args))
            else:
                self._send_json({'error': f'Unknown session action: {action}'}, 400)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)


def run_server(port=7862, backend='api'):
    server = HTTPServer(('127.0.0.1', port), BridgeHandler)
    server.backend = backend
    print(f'Suno Producer Bridge running on http://localhost:{port}')
    print(f'Backend: {backend}')
    print(f'Press Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down.')
        server.server_close()


def main():
    p = argparse.ArgumentParser(description='Suno Producer Bridge Server')
    p.add_argument('--port', type=int, default=7862, help='Port (default: 7862)')
    p.add_argument('--backend', default='api', choices=['api', 'chrome'],
                   help='Generation backend (default: api)')
    args = p.parse_args()
    run_server(args.port, args.backend)


if __name__ == '__main__':
    main()
