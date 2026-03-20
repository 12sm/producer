#!/usr/bin/env python3
"""Bridge server — HTTP endpoint that Claude Code talks to.

Exposes bracket lab tools as a local HTTP API. Generation happens
externally (e.g. via Chrome extension on suno.com) — this server
handles analysis, listening, search, vocab, and session management.

Usage:
    python bridge_server.py
    python bridge_server.py --port 7862

Endpoints:
    POST /analyze      — Run bracket lab analysis
    GET  /listen       — Extract features from audio
    GET  /search       — Search snippet bank
    GET  /vocab        — Query vocabulary index
    GET  /health       — Health check
    GET  /session      — Session management
    POST /session/*    — Session init/record/accept

Claude Code calls these endpoints. Audio generation happens through
the Chrome extension or manual upload — not through this server.
"""

import argparse
import json
import mimetypes
import os
import sys
import threading
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))

# In-memory queue for audio captured by the Chrome extension.
# The extension should POST to /capture with { audioUrl, title, source }.
# Claude Code polls /jobs to pick up completed captures.
_capture_lock = threading.Lock()
_capture_queue: deque = deque(maxlen=50)  # rolling window, newest last


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
            self._send_json({'status': 'ok'})
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

        if path == '/audio':
            self._handle_audio(params)
            return

        if path == '/jobs':
            self._handle_jobs(params)
            return

        # Static file serving for UI
        if self._serve_static(path):
            return

        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == '/analyze':
            self._handle_analyze(body)
            return

        if path.startswith('/session'):
            self._handle_session_post(path, body)
            return

        if path == '/capture':
            self._handle_capture(body)
            return

        if path == '/generate/poll':
            self._handle_generate_poll(body)
            return

        if path == '/generate/download':
            self._handle_generate_download(body)
            return

        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)

    # ── Static / Audio ────────────────────────────────────────────

    def _serve_static(self, path):
        """Serve built UI assets from ui/dist/. Returns True if handled."""
        ui_dist = os.path.join(os.path.dirname(__file__), 'ui', 'dist')
        if not os.path.isdir(ui_dist):
            return False

        # SPA fallback: serve index.html for non-asset paths
        if path == '/' or not os.path.splitext(path)[1]:
            file_path = os.path.join(ui_dist, 'index.html')
        else:
            file_path = os.path.join(ui_dist, path.lstrip('/'))

        file_path = os.path.realpath(file_path)
        if not file_path.startswith(os.path.realpath(ui_dist)):
            return False

        if not os.path.isfile(file_path):
            return False

        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        with open(file_path, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def _handle_audio(self, params):
        """Proxy local audio files to the browser."""
        audio_path = params.get('path', [None])[0]
        if not audio_path:
            self._send_json({'error': 'path param required'}, 400)
            return

        ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a'}
        ext = os.path.splitext(audio_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            self._send_json({'error': f'Unsupported audio type: {ext}'}, 400)
            return

        audio_path = os.path.realpath(audio_path)
        if not os.path.isfile(audio_path):
            self._send_json({'error': 'File not found'}, 404)
            return

        content_type = mimetypes.guess_type(audio_path)[0] or 'application/octet-stream'
        with open(audio_path, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    # ── Handlers ──────────────────────────────────────────────────

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
                source=body.get('source', 'manual'),
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
                args = argparse.Namespace(session_dir=session_dir)
                self._send_json(cmd_list(args))
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_session_post(self, path, body):
        try:
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


    def _handle_capture(self, body):
        """Receive an audio capture from the Chrome extension.

        Expected body: { audioUrl, title, source, jobId? }

        The Chrome extension should POST here when it captures a new track
        from suno.com. Claude Code polls /jobs to pick up results.
        """
        audio_url = body.get('audioUrl')
        if not audio_url:
            self._send_json({'error': 'audioUrl required'}, 400)
            return

        from datetime import datetime, timezone
        entry = {
            'id': f"cap_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            'audioUrl': audio_url,
            'title': body.get('title', ''),
            'source': body.get('source', 'suno'),
            'jobId': body.get('jobId'),
            'capturedAt': datetime.now(timezone.utc).isoformat(),
            'consumed': False,
        }

        with _capture_lock:
            _capture_queue.append(entry)

        self._send_json({'ok': True, 'id': entry['id']})

    def _handle_jobs(self, params):
        """List pending audio captures from the Chrome extension.

        Query params:
          ?pending=1   — only unclaimed captures (default)
          ?all=1       — all captures in queue
          ?consume=1   — mark returned items as consumed
        """
        consume = 'consume' in params
        list_all = 'all' in params

        with _capture_lock:
            items = list(_capture_queue)
            if not list_all:
                items = [j for j in items if not j['consumed']]
            if consume:
                for item in items:
                    item['consumed'] = True

        self._send_json({'count': len(items), 'jobs': items})


    def _handle_generate_poll(self, body):
        """Poll for Suno clips generated after a given timestamp.

        Body: {
            after_ts: float   — Unix timestamp captured before clicking Create
            jwt?: str         — Bearer token (falls back to ./suno_jwt.txt)
            dest_dir?: str    — Where to download MP3s (default: ./suno_audio)
            timeout?: int     — Max wait seconds (default: 300)
            poll_interval?: int
        }

        Returns: { clips: [{clip_id, local_path, title, duration, audio_url}] }
        """
        after_ts = body.get('after_ts')
        if not after_ts:
            self._send_json({'error': 'after_ts required'}, 400)
            return

        try:
            from tools.suno import load_jwt, save_jwt, wait_and_download
            jwt = body.get('jwt')
            if not jwt:
                jwt = load_jwt('./suno_jwt.txt')
            if not jwt:
                self._send_json({'error': 'No valid JWT — provide jwt in body or save to ./suno_jwt.txt'}, 401)
                return
            # Update JWT file if a fresh one was passed
            if body.get('jwt'):
                save_jwt(body['jwt'], './suno_jwt.txt')

            dest_dir = body.get('dest_dir', './suno_audio')
            timeout = int(body.get('timeout', 300))
            poll_interval = int(body.get('poll_interval', 5))

            results = wait_and_download(
                after_ts=float(after_ts),
                jwt=jwt,
                dest_dir=dest_dir,
                timeout=timeout,
                poll_interval=poll_interval,
            )

            clips = []
            for r in results:
                c = r.get('clip', {})
                clips.append({
                    'clip_id': r['clip_id'],
                    'local_path': r['local_path'],
                    'title': c.get('title', ''),
                    'duration': c.get('metadata', {}).get('duration'),
                    'audio_url': c.get('audio_url', ''),
                    'bpm': c.get('metadata', {}).get('avg_bpm'),
                    'key': c.get('metadata', {}).get('key'),
                    'tags': c.get('metadata', {}).get('tags', ''),
                })

            self._send_json({'clips': clips})
        except TimeoutError as e:
            self._send_json({'error': str(e)}, 504)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_generate_download(self, body):
        """Download a single Suno clip by audio URL.

        Body: { audio_url: str, dest_dir?: str, filename?: str }
        Returns: { local_path: str }
        """
        audio_url = body.get('audio_url')
        if not audio_url:
            self._send_json({'error': 'audio_url required'}, 400)
            return

        try:
            from tools.suno import download_clip
            dest = download_clip(
                audio_url=audio_url,
                dest_dir=body.get('dest_dir', './suno_audio'),
                filename=body.get('filename'),
            )
            self._send_json({'local_path': dest})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)


def run_server(port=7862, host='127.0.0.1'):
    server = HTTPServer((host, port), BridgeHandler)
    print(f'Producer Bridge running on http://{host}:{port}')
    print(f'Press Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down.')
        server.server_close()


def main():
    p = argparse.ArgumentParser(description='Producer Bridge Server')
    p.add_argument('--port', type=int, default=7862, help='Port (default: 7862)')
    p.add_argument('--host', default='0.0.0.0', help='Bind host (default: 0.0.0.0)')
    args = p.parse_args()
    run_server(args.port, args.host)


if __name__ == '__main__':
    main()
