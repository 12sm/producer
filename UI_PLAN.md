# Producer Dashboard — UI Build Plan

## Overview

Local web dashboard for the bracket prompt lab. Shows session history,
vocabulary learnings, waveform analysis, and snippet bank browsing.
Served alongside the existing bridge server on port 7862.

The system is **source-agnostic** — audio can come from Suno (via Chrome
extension or manual download), ElevenLabs (via API), or any other source.
The analysis pipeline doesn't care where audio originates.

---

## Architecture

```
ui/                          # All frontend code lives here
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx             # Entry point
│   ├── App.tsx              # Router + layout shell
│   ├── api.ts               # Bridge server API client
│   ├── types.ts             # TypeScript types matching backend schemas
│   ├── pages/
│   │   ├── Dashboard.tsx    # Session list + overview stats
│   │   ├── Session.tsx      # Single session detail + iteration timeline
│   │   ├── Vocab.tsx        # Vocabulary explorer
│   │   ├── Analysis.tsx     # Waveform comparison view
│   │   └── Bank.tsx         # Snippet bank browser
│   └── components/
│       ├── Layout.tsx       # Nav sidebar + content area
│       ├── SessionCard.tsx  # Session summary card
│       ├── IterationRow.tsx # Single iteration in session timeline
│       ├── VerdictBadge.tsx # PASS/MIXED/FAIL + LOW/MED/HIGH badges
│       ├── FeatureBar.tsx   # Mini bar chart for feature deltas
│       ├── Waveform.tsx     # wavesurfer.js wrapper with bracket overlays
│       └── DeltaTag.tsx     # Feature delta badge for waveform timeline
```

**Stack:** React 18, Vite, TypeScript, TanStack Router, wavesurfer.js
**Styling:** Tailwind CSS (dark theme — it's a music production tool)
**No backend changes needed** except:
1. Static file serving for built assets (add to bridge_server.py)
2. `/audio` proxy endpoint to serve local audio files to the browser
3. `source` field on analysis runs (suno / elevenlabs / manual)

---

## Bridge Server Changes

### 1. Static file serving

```python
# In BridgeHandler.do_GET, before the 404:
if path == '/' or path.startswith('/assets/'):
    self._serve_static(path)
    return
```

Serve `ui/dist/` contents. `index.html` for `/`, assets for `/assets/*`.

### 2. Audio proxy endpoint

```
GET /audio?path=/absolute/path/to/file.mp3

Returns the raw audio file with appropriate Content-Type.
Only serves files with audio extensions (.mp3, .wav, .flac, .ogg).
```

This lets wavesurfer.js load audio from local paths through the browser.

### 3. Source tracking (data model addition)

Add optional `source` field to analysis runs:

```python
# In tools/analyze.py, the run_data dict:
"source": body.get('source', 'manual'),  # suno | elevenlabs | manual
```

This propagates into snippet_bank entries and becomes filterable.

---

## Page Specs

### Page 1: Dashboard (`/`)

**Purpose:** Overview of all sessions and system stats.

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  Producer Lab                          [Vocab]  │
├────────┬────────────────────────────────────────┤
│        │                                        │
│  Nav   │  Stats Row                             │
│        │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  Dash  │  │ 12   │ │ 8    │ │ 47   │ │ 142  │  │
│  Vocab │  │ Sess │ │ Acpt │ │ Keys │ │ Runs │  │
│  Bank  │  └──────┘ └──────┘ └──────┘ └──────┘  │
│        │                                        │
│        │  Sessions                              │
│        │  ┌────────────────────────────────────┐│
│        │  │ ● active  lo-fi beat session       ││
│        │  │   3/5 iterations | best: PASS/LOW  ││
│        │  ├────────────────────────────────────┤│
│        │  │ ✓ accepted  trap beat session      ││
│        │  │   2/10 iters | accepted run: abc   ││
│        │  └────────────────────────────────────┘│
└────────┴────────────────────────────────────────┘
```

**Data sources:**
- `GET /session` → list all sessions
- `GET /search?all=1` → total run count
- `GET /vocab` → keyword count

**Interactions:**
- Click session → navigate to `/session/:id`

---

### Page 2: Session Detail (`/session/:id`)

**Purpose:** Full iteration timeline for one session.

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  ← Back    Session 20260320_030541              │
│  Status: accepted                               │
│  Prompt: "Lo-fi hip hop beat, mellow piano..."  │
│  Intent: "louder drums, punchy kick"            │
│  Brackets: [10s-20s]                            │
│  Targets: compliance ≥ 0.7, drift ≤ 0.15       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Iteration Timeline                             │
│                                                 │
│  1 ─●─ PASS/LOW  "gentle boost"                │
│       │  compliance: 1.0  drift: 0.0            │
│       │  "Louder but not punchy enough"         │
│       │                         [View Analysis] │
│  2 ─●─ PASS/LOW  "heavy boost + onset" ★accepted│
│       │  compliance: 1.0  drift: 0.0            │
│       │  "Real punch. This is the one."         │
│       │                         [View Analysis] │
│  3 ─●─ PASS/LOW  "too aggressive"              │
│          compliance: 1.0  drift: 0.0            │
│          "Way too loud, blew out the track"     │
│                                 [View Analysis] │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Data sources:**
- `GET /session/:id` → full session with iterations
- Each iteration's `run_id` links to `/analysis/:run_id`

**Interactions:**
- "View Analysis" → navigate to `/analysis/:run_id`
- Accepted run gets a star badge

---

### Page 3: Waveform Analysis (`/analysis/:run_id`)

**Purpose:** The flagship view. Side-by-side or overlay waveform
comparison with bracket regions and feature deltas.

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  ← Back    Run 20260320_030626                  │
│  Intent: "louder drums, punchy kick"            │
│  Source: suno | Compliance: PASS | Drift: LOW   │
├─────────────────────────────────────────────────┤
│                                                 │
│  Original                          [Toggle ▾]   │
│  ┌─────────────────────────────────────────────┐│
│  │▁▂▃▄▅▃▂▁▂▃║▄▅▆▇▆▅▄▃▄▅║▃▂▁▂▃▄▅▃▂▁▂▃▄▅▃▂▁  ││
│  │          ║ bracket   ║                      ││
│  │   0:00   ║   0:10    ║  0:20         0:30   ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  Variant                                        │
│  ┌─────────────────────────────────────────────┐│
│  │▁▂▃▄▅▃▂▁▂▃║▆▇█▇▆▇█▇▆▅║▃▂▁▂▃▄▅▃▂▁▂▃▄▅▃▂▁  ││
│  │          ║ bracket   ║                      ││
│  │   0:00   ║   0:10    ║  0:20         0:30   ││
│  └──────────╨───────────╨──────────────────────┘│
│                                                 │
│  Bracket [0:10-0:20] Deltas                     │
│  ┌─────────────────────────────────────────────┐│
│  │ rms_mean    ████████████████░░  +101%  ↑    ││
│  │ rms_std     ████████████████░░  +101%  ↑    ││
│  │ centroid    ░░░░░░░░░░░░░░░░░░    0%   —   ││
│  │ onsets/sec  ████░░░░░░░░░░░░░░   +17%  ↑   ││
│  │ tempo       ██░░░░░░░░░░░░░░░░    -4%  ↓   ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  Notes                                          │
│  What changed: Region is louder (101% RMS)...   │
│  What improved: Loudness increase aligns...     │
│  Suggested tweak: Consider locking this...      │
│                                                 │
│  Compliance Rules Matched                       │
│  ✓ "louder" → rms_mean increase (delta: +1.01) │
│  ✓ "punchy" → rms_mean increase (delta: +1.01) │
│  ✓ "punchy" → rms_std increase (delta: +1.01)  │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Data sources:**
- `GET /search?run_id=:run_id` → full entry.json
- `GET /audio?path=<original_path>` → waveform audio
- `GET /audio?path=<variant_path>` → waveform audio

**Key implementation details:**
- Use wavesurfer.js for waveform rendering
- Bracket regions rendered as wavesurfer Region plugins (colored overlay)
- Anchor regions rendered in a different color (these are drift-check zones)
- Both waveforms should sync scroll/zoom
- Play button for each waveform
- Toggle: side-by-side vs overlay mode

---

### Page 4: Vocabulary Explorer (`/vocab`)

**Purpose:** Browse the learned keyword dictionary.

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  Vocabulary    [Rebuild Index]                   │
│  47 keywords from 142 observations              │
│                                                 │
│  Search: [____________]    Filter: [All ▾]      │
│                                                 │
│  Keyword    │ Obs │ Pass% │ Effects             │
│  ───────────┼─────┼───────┼──────────────────── │
│  louder     │  8  │  75%  │ ▓▓▓░ rms  ░░ cent  │
│  punchy     │  6  │  83%  │ ▓▓▓░ rms  ▓░ onset │
│  darker     │  4  │ 100%  │ ░░░░ rms  ▓▓▓ cent │
│  tight      │ 12  │  83%  │ ░░ rms ▓▓▓ onset   │
│  ...        │     │       │                     │
│                                                 │
│  ─── Selected: "louder" ────────────────────    │
│  Observed 8 times, 75% pass rate                │
│  Effects:                                       │
│    rms_mean     +0.23 ± 0.12                    │
│    centroid     +0.05 ± 0.03                    │
│    onset_dens   -0.01 ± 0.20                    │
│  Associated intents:                            │
│    "louder drums", "louder kick", "increase vol"│
│                                                 │
└─────────────────────────────────────────────────┘
```

**Data sources:**
- `GET /vocab` → full vocabulary index
- `GET /vocab?action=lookup&keyword=X` → detail for selected keyword

**Feature bar chart:**
- Each keyword row shows a mini horizontal bar for each feature delta
- Green = positive delta, red = negative, gray = negligible
- Width proportional to avg_delta magnitude

---

### Page 5: Snippet Bank (`/bank`)

**Purpose:** Browse and filter all analysis runs.

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  Snippet Bank    142 runs                       │
│                                                 │
│  Search: [____________]                         │
│  Compliance: [All ▾]  Drift: [All ▾]            │
│  Source: [All ▾]                                │
│                                                 │
│  Run ID          │ Intent        │ C    │ D     │
│  ────────────────┼───────────────┼──────┼────── │
│  0320_030626...  │ louder drums  │ PASS │ LOW   │
│  0320_030558...  │ louder drums  │ PASS │ LOW   │
│  0319_221400...  │ darker pads   │ MIXED│ LOW   │
│  0319_193000...  │ tighter kick  │ FAIL │ HIGH  │
│                                                 │
│  Click any row → opens Analysis view            │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Data sources:**
- `GET /search?all=1` → all runs
- `GET /search?q=keyword` → filtered runs

**Filtering:**
- Text search matches against intent field
- Dropdown filters for compliance verdict, drift verdict, source

---

## ElevenLabs Integration

ElevenLabs has a real REST API for music generation. Unlike the fictional
Suno API we removed, this one actually exists.

### Phase 1: Source tracking (do this now)

Add `source` field throughout the pipeline:
- `tools/analyze.py` accepts `--source suno|elevenlabs|manual`
- Stored in snippet bank entries
- Filterable in UI bank browser
- Vocabulary can be built per-source or globally

### Phase 2: ElevenLabs generation (do this later)

```
tools/elevenlabs.py  — thin wrapper around ElevenLabs music API

Usage:
  ELEVENLABS_API_KEY=... python -m tools.elevenlabs \
    --prompt "lo-fi hip hop beat" \
    --out ./audio/output.mp3

Returns:
  {"file": "./audio/output.mp3", "source": "elevenlabs", "id": "..."}
```

Add to bridge server:
```
POST /generate
{
  "source": "elevenlabs",
  "prompt": "...",
  "out_dir": "./audio"
}
```

This replaces the fictional Suno generate endpoint with a real one.
Suno generation still happens via Chrome extension (no API exists).

### Phase 3: Cross-platform vocabulary

The vocab system already works per-keyword. Adding source tracking
lets us answer questions like:
- "What does 'punchy' do on ElevenLabs vs Suno?"
- "Which platform responds better to brightness keywords?"

This requires minimal code — just a `source` filter in `vocabulary.py`'s
`build_vocab_index()` function.

---

## Build Order

### Sprint 1: Foundation
1. `npm create vite@latest ui -- --template react-ts`
2. Install deps: tailwindcss, react-router, wavesurfer.js
3. Build `api.ts` client matching all bridge server endpoints
4. Build `types.ts` from the schemas documented above
5. Build `Layout.tsx` shell with sidebar nav
6. Add static file serving + audio proxy to bridge_server.py

### Sprint 2: Data Views
7. Dashboard page — session list with stats
8. Session detail page — iteration timeline
9. Snippet bank page — filterable run list
10. Vocab explorer page — keyword table + detail panel

### Sprint 3: Waveform View
11. Waveform component with wavesurfer.js
12. Bracket region overlays
13. Anchor region overlays
14. Feature delta bars anchored to regions
15. Playback controls + sync scroll

### Sprint 4: ElevenLabs + Polish
16. Add `source` field to analyze pipeline
17. Build `tools/elevenlabs.py` if API key available
18. Cross-platform vocab filtering
19. Dark theme polish
20. Responsive layout

---

## Testing

- Existing Python tests must keep passing (`python -m pytest tests/`)
- Add Vitest for UI component tests
- Use the synthetic audio from `tests/conftest.py` for waveform dev:
  ```python
  python -c "
  from tests.conftest import make_test_track, SR
  import soundfile as sf
  sf.write('test_audio.wav', make_test_track(30.0), SR)
  "
  ```

---

## Dev Workflow

```bash
# Terminal 1: bridge server
python bridge_server.py --port 7862

# Terminal 2: vite dev server (proxies API to 7862)
cd ui && npm run dev

# Terminal 3: run analysis to populate data
python -m tools.analyze --original a.mp3 --variant b.mp3 \
  --bracket "0:30-0:45" --intent "louder drums"
```

Vite dev server proxies `/api/*` to the bridge server. In production,
bridge_server.py serves the built `ui/dist/` directly.

---

## Handoff: Combined Next Session Instructions

### What's already done

**Sprint 1-2 complete:**
- React + Vite + TypeScript + Tailwind (dark theme, monospace)
- Full API client (`ui/src/api.ts`) matching all bridge server endpoints
- TypeScript types (`ui/src/types.ts`) mirroring all backend JSON schemas
- Layout shell with sidebar nav
- 5 pages: Dashboard, Session Detail, Vocab Explorer, Snippet Bank, Analysis
- Waveform view with wavesurfer.js, bracket/anchor region overlays, playback
- Feature delta bar charts, compliance/drift verdict badges
- Bridge server: `/audio` proxy endpoint, static file serving for `ui/dist/`
- `source` field (suno/elevenlabs/manual) added to analyze pipeline
- All 111 Python tests pass, Vite build clean

**Chrome extension (`chrome_ext/`) complete:**
- Content script injects on suno.com, finds prompt textarea, fills it,
  clicks generate, waits for audio element, returns URL
- Background service worker handles job tracking with timeouts
- Popup shows connection status, bridge server health, logs
- Communication: Claude Code → bridge server → background.js → content.js → Suno UI

### Phase 1: Verify UI Against Real Data

1. Generate synthetic test audio and populate the snippet bank:
   ```bash
   python -c "
   from tests.conftest import make_test_track, SR
   import soundfile as sf
   sf.write('test_original.wav', make_test_track(30.0), SR)
   sf.write('test_variant.wav', make_test_track(30.0, freq_mod=1.15), SR)
   "
   ```

2. Run a few analyses to populate data:
   ```bash
   python -m tools.analyze \
     --original test_original.wav --variant test_variant.wav \
     --bracket "0:05-0:15" --intent "louder drums, punchy kick" \
     --source manual

   python -m tools.analyze \
     --original test_original.wav --variant test_variant.wav \
     --bracket "0:10-0:20" --intent "brighter hi-hats, crisp" \
     --source manual
   ```

3. Init a session and record iterations:
   ```bash
   # Use the session endpoints via bridge server or session.py CLI
   python -m session init \
     --prompt "test lo-fi beat" \
     --bracket "0:05-0:15" \
     --intent "louder drums" \
     --session-dir ./sessions
   ```

4. Build the vocab index:
   ```bash
   python -m tools.vocab build --bank-dir ./snippet_bank
   ```

5. Start both servers and verify all 5 pages render correctly:
   ```bash
   python bridge_server.py --port 7862 &
   cd ui && npx vite build && echo "Build OK"
   # Then curl http://localhost:7862/ to verify static serving
   ```

6. Fix any rendering issues, data loading errors, or missing fields.

### Phase 2: Waveform Polish

- Sync scroll and zoom between original and variant waveforms
- Improve bracket region overlay styling (semi-transparent fill,
  labeled borders, snap to waveform peaks)
- Add A/B toggle: click bracket region to switch between original
  and variant playback for that specific region
- Ensure playback position indicator is visible against dark theme

### Phase 3: Chrome Extension + Suno Live Test

**Goal:** End-to-end test of the full pipeline using real Suno output.

The Chrome extension (`chrome_ext/`) is already built. The bridge server
already has all the endpoints. What needs testing:

1. **Verify the extension external messaging works.** The bridge server
   needs a `/generate` endpoint that forwards to the Chrome extension.
   Currently `bridge_server.py` does NOT have this endpoint — it was
   removed when we cleaned out the fictional Suno API client. The
   extension's `background.js` listens for `chrome.runtime.onMessageExternal`
   but there's no HTTP endpoint to trigger it.

   **Add to bridge_server.py:**
   ```
   POST /generate
   {
     "prompt": "...",
     "source": "suno"  // or "elevenlabs" later
   }
   ```
   For source=suno: This should send a message to the Chrome extension.
   BUT — the bridge server can't directly message Chrome extensions.
   The architecture is: Chrome extension polls the bridge server for
   pending jobs, or uses WebSocket. Check `background.js` to see
   which pattern it expects.

   Actually, looking at the extension code: `background.js` uses
   `chrome.runtime.onMessageExternal` which means the CALLER needs
   the extension ID and must be on the extension's `externally_connectable`
   list. The bridge server is plain HTTP — it can't call Chrome APIs.

   **The real flow for Suno is manual:**
   1. Claude Code tells the user what prompt to paste into Suno
   2. User generates on suno.com (extension auto-captures the output)
   3. User downloads the audio file
   4. Claude Code runs analysis on the downloaded file

   **OR** the extension captures the audio URL and POSTs it back to
   the bridge server. Check if `background.js` does this — if it has
   a fetch/POST back to localhost:7862 with the captured audio.

2. **Test the capture flow:**
   - Load the extension in Chrome (chrome://extensions, developer mode,
     load unpacked from `chrome_ext/`)
   - Navigate to suno.com
   - Verify popup shows "Connected to Suno"
   - Generate a track manually
   - Check if the extension captures the audio URL
   - Check bridge server logs for any incoming requests

3. **Run bracket lab on real Suno output:**
   ```bash
   # After capturing original and variant from Suno:
   python -m tools.analyze \
     --original ~/Downloads/suno_original.mp3 \
     --variant ~/Downloads/suno_variant.mp3 \
     --bracket "0:30-0:45" \
     --intent "louder drums, punchy kick" \
     --source suno
   ```

4. **Verify UI shows the real analysis:**
   - Check Dashboard shows the new session
   - Check Analysis page shows real waveforms (not synthetic)
   - Check Vocab page updates with new keyword observations
   - Check Snippet Bank has the new run with source=suno

### Phase 4: Session Runner Integration

Test the full iterative loop:
1. Init a session with an intent
2. Generate on Suno with the initial prompt
3. Run analysis (records as iteration 1)
4. If FAIL/MIXED — Claude Code suggests a prompt modification
5. Generate again with the modified prompt
6. Run analysis (records as iteration 2)
7. Continue until PASS + LOW drift, then accept

This is the core workflow the entire system was built for. The
session runner (`session.py`) handles the bookkeeping, the analysis
tools score each iteration, and the UI shows progress.

### Constraints

- `python -m pytest tests/` must stay green (currently 111 tests)
- `cd ui && npx vite build` must stay clean
- Don't modify the Chrome extension unless something is actually broken
- Keep the bridge server backward-compatible (existing endpoints
  must keep their signatures)

