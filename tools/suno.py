"""Suno REST client for Bracket Prompt Lab.

Generation requires the browser (Playwright MCP handles hCaptcha).
This module handles everything else: JWT management, polling, downloading.

Two-phase workflow:
  1. Generation  — Claude Code fills suno.com/create via Playwright MCP,
                   clicks Create, captures the timestamp before clicking.
  2. Poll+DL     — call poll_for_new_clips(after_ts, jwt) until complete,
                   then download_clips(clips, dest_dir).

The JWT is a Clerk-issued access token from the __session cookie.
It expires hourly; re-extract from the browser via:
    document.cookie → __session=<jwt>
"""

import os
import time
import json
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# Bracket Lab workspace on Suno
BRACKET_LAB_PROJECT_ID = "96ca7a5f-3057-41ae-93d7-5692b770aa3a"

FEED_URL = "https://studio-api-prod.suno.com/api/feed/v3"
STATUS_URL = "https://studio-api-prod.suno.com/api/generate/concurrent-status"
SESSION_URL = "https://studio-api-prod.suno.com/api/session/"
CDN_BASE = "https://cdn1.suno.ai"


# ── JWT helpers ────────────────────────────────────────────────────────────────

def load_jwt(jwt_path: str = "./suno_jwt.txt") -> Optional[str]:
    """Load JWT from file. Returns None if missing or expired."""
    if not os.path.isfile(jwt_path):
        return None
    with open(jwt_path) as f:
        token = f.read().strip()
    if not token:
        return None
    # Quick expiry check (decode payload without verifying signature)
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        exp = payload.get("exp", 0)
        if time.time() >= exp - 30:  # 30s grace
            return None
        return token
    except Exception:
        return None


def save_jwt(token: str, jwt_path: str = "./suno_jwt.txt"):
    """Save JWT to file."""
    with open(jwt_path, "w") as f:
        f.write(token.strip())


def validate_jwt(token: str) -> bool:
    """Check that the token is accepted by the session endpoint."""
    req = urllib.request.Request(SESSION_URL)
    req.add_header("Authorization", f"Bearer {token}")
    for k, v in _BROWSER_HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── Status & polling ───────────────────────────────────────────────────────────

_BROWSER_HEADERS = {
    "Origin": "https://suno.com",
    "Referer": "https://suno.com/create",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}


def get_concurrent_status(jwt: str) -> dict:
    """Check if a generation is currently running."""
    req = urllib.request.Request(STATUS_URL)
    req.add_header("Authorization", f"Bearer {jwt}")
    for k, v in _BROWSER_HEADERS.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def fetch_recent_clips(jwt: str, count: int = 10) -> list:
    """Fetch the most recent clips from the feed.

    Note: FEED_URL requires session cookies alongside the Bearer token.
    This will 401 when called from Python without browser cookies.
    Use browser-side fetch (via Playwright evaluate) for polling instead.
    """
    payload = json.dumps({
        "is_only_following": False,
        "explore_mode": "new",
    }).encode()
    req = urllib.request.Request(FEED_URL, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {jwt}")
    req.add_header("Content-Type", "application/json")
    for k, v in _BROWSER_HEADERS.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("clips", [])[:count]


def poll_for_new_clips(
    after_ts: float,
    jwt: str,
    timeout: int = 300,
    poll_interval: int = 5,
    expected_count: int = 2,
) -> list:
    """Poll until new completed clips appear after a given Unix timestamp.

    Args:
        after_ts: Unix timestamp (time.time()) captured *before* clicking Create.
        jwt: Bearer token.
        timeout: Maximum seconds to wait (default 300).
        poll_interval: Seconds between polls (default 5).
        expected_count: Number of clips to wait for (Suno generates 2 per submit).

    Returns:
        List of clip dicts with at least: id, title, status, audio_url, metadata.

    Raises:
        TimeoutError: If clips don't appear within timeout.
    """
    deadline = time.time() + timeout
    after_iso = datetime.fromtimestamp(after_ts, tz=timezone.utc).isoformat()

    while time.time() < deadline:
        try:
            clips = fetch_recent_clips(jwt, count=20)
        except Exception as e:
            print(f"  [suno] poll error: {e}, retrying...")
            time.sleep(poll_interval)
            continue

        new = [
            c for c in clips
            if c.get("created_at", "") >= after_iso
        ]

        if not new:
            print(f"  [suno] waiting for clips (0/{expected_count})...")
            time.sleep(poll_interval)
            continue

        complete = [c for c in new if c.get("status") == "complete" and c.get("audio_url")]
        pending = [c for c in new if c.get("status") not in ("complete", "error")]

        print(f"  [suno] {len(complete)} complete, {len(pending)} pending...")

        if len(complete) >= expected_count or (complete and not pending):
            return complete

        time.sleep(poll_interval)

    raise TimeoutError(f"Suno clips did not appear within {timeout}s")


# ── Download ───────────────────────────────────────────────────────────────────

def download_clip(audio_url: str, dest_dir: str, filename: Optional[str] = None) -> str:
    """Download a clip's MP3 to dest_dir. Returns local path."""
    os.makedirs(dest_dir, exist_ok=True)
    if not filename:
        clip_id = audio_url.rstrip("/").split("/")[-1]
        filename = clip_id if clip_id.endswith(".mp3") else f"{clip_id}.mp3"

    dest = os.path.join(dest_dir, filename)
    req = urllib.request.Request(audio_url)
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())

    size = os.path.getsize(dest)
    print(f"  [suno] downloaded {filename} ({size/1024/1024:.1f} MB)")
    return dest


def download_clips(clips: list, dest_dir: str) -> list:
    """Download all clips in list. Returns list of local paths."""
    paths = []
    for clip in clips:
        url = clip.get("audio_url")
        if not url:
            continue
        clip_id = clip.get("id", "unknown")
        path = download_clip(url, dest_dir, filename=f"{clip_id}.mp3")
        paths.append({"clip_id": clip_id, "local_path": path, "clip": clip})
    return paths


# ── Full workflow helper ───────────────────────────────────────────────────────

def wait_and_download(
    after_ts: float,
    jwt: str,
    dest_dir: str = "./suno_audio",
    timeout: int = 300,
    poll_interval: int = 5,
) -> list:
    """Wait for generation triggered at after_ts, download and return results.

    Called by Claude Code immediately after clicking Create in the browser.

    Returns list of:
        {clip_id, local_path, clip: {title, duration, metadata, ...}}
    """
    print(f"[suno] polling for clips after {datetime.fromtimestamp(after_ts, tz=timezone.utc).isoformat()}")
    clips = poll_for_new_clips(after_ts, jwt, timeout=timeout, poll_interval=poll_interval)
    print(f"[suno] {len(clips)} clips complete, downloading...")
    return download_clips(clips, dest_dir)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="Suno REST client")
    sub = p.add_subparsers(dest="cmd", required=True)

    # status
    stat = sub.add_parser("status", help="Check concurrent generation status")
    stat.add_argument("--jwt-file", default="./suno_jwt.txt")

    # poll
    poll = sub.add_parser("poll", help="Poll for new clips")
    poll.add_argument("--after", type=float, required=True, help="Unix timestamp")
    poll.add_argument("--jwt-file", default="./suno_jwt.txt")
    poll.add_argument("--dest", default="./suno_audio")
    poll.add_argument("--timeout", type=int, default=300)

    # download
    dl = sub.add_parser("download", help="Download a clip by URL")
    dl.add_argument("url")
    dl.add_argument("--dest", default="./suno_audio")
    dl.add_argument("--name")

    args = p.parse_args()

    if args.cmd == "status":
        jwt = load_jwt(args.jwt_file)
        if not jwt:
            print("No valid JWT found")
            return
        result = get_concurrent_status(jwt)
        print(json.dumps(result, indent=2))

    elif args.cmd == "poll":
        jwt = load_jwt(args.jwt_file)
        if not jwt:
            print("No valid JWT found")
            return
        results = wait_and_download(args.after, jwt, dest_dir=args.dest, timeout=args.timeout)
        print(json.dumps([{k: v for k, v in r.items() if k != "clip"} for r in results], indent=2))

    elif args.cmd == "download":
        download_clip(args.url, args.dest, args.name)


if __name__ == "__main__":
    main()
