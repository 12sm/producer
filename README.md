# Bracket Prompt Lab

CLI tool for evaluating Suno "bracket prompt" experiments. Compare an original track to a variant/cover track, focus on specific bracketed time regions, score how well the variant followed your intent, detect unintended drift in other parts of the song, and save everything into a searchable snippet bank.

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.9+ and `ffmpeg` for MP3 support:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

## Usage

### Basic run

```bash
python bracket_lab.py \
  --original path/to/original.mp3 \
  --variant path/to/variant.mp3 \
  --bracket "1:12-1:28" \
  --intent "Chorus 2 drum entry: tight 2-step, no crash, swung hats, less EDM riser" \
  --prompt_file prompt.txt \
  --out_dir ./lab_out
```

### Multiple bracket windows

```bash
python bracket_lab.py \
  --original original.mp3 \
  --variant variant.mp3 \
  --bracket "0:42-0:55" \
  --bracket "1:12-1:28" \
  --intent "tighter drums in both chorus sections" \
  --out_dir ./lab_out
```

### With explicit anchor windows

```bash
python bracket_lab.py \
  --original original.mp3 \
  --variant variant.mp3 \
  --bracket "1:12-1:28" \
  --intent "no crash cymbal, swung hats" \
  --anchors "0:10-0:25" "0:55-1:05" "2:10-2:25" \
  --out_dir ./lab_out
```

If `--anchors` is not provided, 4 evenly-spaced anchor windows are automatically generated (avoiding bracket regions) for drift detection.

### Search the snippet bank

```bash
python bracket_lab.py --search "tight drums" --original x --variant x --bracket "0:00-0:01" --intent x
```

## Output

Each run produces:

```
lab_out/
├── report.md              # Human-readable Markdown report
├── report.json            # Machine-readable full data
└── slices/
    ├── bracket_0_original.wav
    ├── bracket_0_variant.wav
    ├── anchor_0_original.wav
    ├── anchor_0_variant.wav
    └── ...

snippet_bank/
├── index.jsonl            # One-line-per-run searchable index
└── 20260320_015500_a1b2c3/
    ├── entry.json         # Full run data
    └── slices/
        └── *.wav          # Copied audio slices
```

### Report contents

- **Compliance score** (0-1): Did the variant follow the bracket intent?
  - `PASS` (≥0.7) / `MIXED` (0.4-0.7) / `FAIL` (<0.4)
- **Collateral drift score**: Did the variant change other parts unintentionally?
  - `LOW` (<0.15) / `MED` (0.15-0.35) / `HIGH` (>0.35)
- **Producer notes** per bracket window:
  - What changed
  - What improved
  - What got worse / artifacts
  - Suggested next bracket prompt tweak
- **Feature comparison tables**: RMS, spectral centroid, onset density, tempo

## How it works

1. Load both audio files (mono, 22050Hz)
2. Slice out bracket windows (with ±2s pre/post roll) and anchor windows
3. Extract features per slice: RMS loudness, spectral centroid, onset density, tempo
4. Score compliance by matching intent keywords against feature deltas
5. Generate producer-style notes from feature analysis
6. Score drift across anchor windows
7. Save everything to the snippet bank

### Intent keyword matching

The tool maps keywords in your intent text to expected feature changes:

| Keyword | Expected change |
|---------|----------------|
| louder, punch | RMS increase |
| soft, quiet, less | RMS decrease |
| bright, crisp | Centroid increase |
| dark, warm, no crash | Centroid decrease |
| tight, busy, dense | Onset density increase |
| sparse, simple | Onset density decrease |
| swung | Onset pattern change |

## Architecture

```
bracket_lab.py     # CLI entry point + pipeline
audio_utils.py     # Audio I/O, slicing, timestamp parsing
features.py        # Feature extraction (librosa)
scoring.py         # Compliance + drift scoring
notes.py           # Producer note generation (template-based, model-ready)
snippet_bank.py    # Storage + JSONL index
report.py          # Console + MD + JSON output
```

The notes generator has a placeholder for swapping in an audio-capable model later (`notes.py:_generate_notes_from_model`).
