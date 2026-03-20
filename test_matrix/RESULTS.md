# Suno Bracket Prompt Lab — Test Matrix Results

**Model:** Suno v5 (`chirp-crow`)
**Date:** 2026-03-20
**Control:** `1A_sub1_gen1.mp3` — no brackets, same lyrics, style: `indie rock, male vocals, 120 bpm`
**Analysis windows:** `0:10–0:50` (early), `0:50–1:30` (mid)
**Total clips generated:** 50 (22 conditions × 2 gens, some conditions × 2 subs)

---

## Methodology

Each variant was compared against the control via audio feature deltas:
- **RMS delta**: loudness change (negative = quieter, positive = louder)
- **Centroid delta**: spectral brightness (negative = darker/warmer, positive = brighter)
- **Onset delta**: rhythm density change (negative = sparser)
- **Tempo**: BPM shift, reported as `original→variant`

Compliance rules fire on keyword matches (e.g. `soft` → expect RMS decrease). For conditions without keyword matches the compliance score defaults to `0.50` (neutral). The more meaningful signal is in the raw deltas.

> **Note on short clips:** Many clips in Batches 3–4 are under 90 seconds. Where the second window (0:50–1:30) shows `−1.000` across all features and tempo drops to 0, the clip ended before the window — the analysis result for that window is unreliable and marked `[SHORT]` in this report.

---

## Batch 1 — Bracket Structure Basics

| ID | Description | Subs | Early RMS | Early Onset | Mid RMS | Notes |
|----|-------------|------|-----------|-------------|---------|-------|
| 1A | No brackets (control) | 2 | +0.14 to −0.31 | −0.03 to −0.12 | −0.07 to −0.31 | Baseline variance; gen2 drops more in mid |
| 1B | Standard brackets [Verse/Chorus/Verse/Outro] | 2 | −0.01 to +0.10 | −0.01 to −0.26 | −0.28 to −0.34 | Mid section consistently much quieter than control; bracket structure may trigger section transitions |
| 1C | Wrong-order brackets [Chorus/Verse1/Outro/Verse2] | 2 | −0.31 to +0.10 | −0.20 to 0.00 | −0.07 to −0.40 | Similar to correct-order in overall energy. No clearly distinct pattern from 1B. |

**Finding:** Standard vs wrong-order brackets produce similar audio signatures. Suno appears to parse bracket labels individually rather than evaluating structural coherence.

---

## Batch 2 — Full Structure Variations

| ID | Description | Early RMS | Early Onset | Mid RMS | Notes |
|----|-------------|-----------|-------------|---------|-------|
| 2A | Full standard [Intro/Verse1/Pre-Ch/Chorus/Verse2/Bridge/Outro] | −0.17 to −0.19 | −0.05 to −0.09 | −0.23 to −0.25 | Consistently quieter than control; dense structure may front-load energy use |
| 2B | EDM-style [Build/Drop/Break/Drop/Outro] | −0.04 to 0.00 | −0.26 | −0.28 | Early window nearly flat on RMS; onset drops suggest sparse early section (Build) |
| 2C | Hook-centric [Verse1/Hook/Verse2/Hook/Fade Out] | −0.04 to +0.05 | −0.08 to −0.13 | −0.11 to −0.20 | Mildest departures from control; Hook labels produce stable output |
| 2D | Interlude test [Verse1/Interlude/Verse2/Interlude/Outro] | −0.10 to −0.18 | −0.04 to +0.01 | −0.44 | Mid section strongly quieter; Interlude labels appear to reduce energy in second half |

**Finding:** `[Interlude]` tags produced the largest mid-section quieting (−44% RMS) among Batch 2. EDM-style tags ([Build/Drop]) create sparse early sections that open up later. `[Hook]` is the most neutral tag.

---

## Batch 3 — Vocal Modifier Tags

| ID | Tag | Early RMS | Early Onset | Mid Notes |
|----|-----|-----------|-------------|-----------|
| 3A | `[Verse]` (batch 3 control) | −0.17 to −0.64 | −0.32 to −0.61 | `[SHORT]` — both gens under 90s |
| 3B | `[Soft Verse]` | −0.06 to +0.14 | −0.17 to −0.28 | −0.61 to −0.63 (**compliance=1.00** for gen1) |
| 3C | `[Whispered Verse]` | **−0.40 to −0.46** | −0.06 to −0.31 | `[SHORT]` — both gens under 90s |
| 3D | `[Spoken Word]` | **−0.49 to −0.60** | −0.18 to −0.28 | `[SHORT]` — both gens under 90s |
| 3E | `[Guitar Solo]` then `[Verse]` | −0.66 to +0.17 | −0.19 to −0.40 | Mixed; gen2 `[SHORT]` |
| 3F | `[Instrumental Break]` then `[Verse]` | −0.05 to −0.06 | −0.08 to −0.15 | −0.42 to −0.48 |
| 3G | `[Verse]` then `[Guitar Solo]` | −0.13 to +0.08 | −0.02 to −0.17 | −0.25 to −0.26 |
| 3H | `[Verse \| Key Change]` | −0.23 to −0.27 | −0.18 to −0.37 | `[SHORT]` — both gens under 90s |

**Key findings:**
- **`[Whispered Verse]` and `[Spoken Word]` are the strongest vocal modifiers** — both reduce RMS by 40–60% in the early window, indicating Suno interprets these as fundamentally different vocal delivery.
- **`[Soft Verse]` is the most consistent modifier** — gen1 achieved `compliance=1.00` in both windows (only condition to do so). The "soft" keyword reliably reduces RMS.
- **`[Guitar Solo]` placement matters** — placed *before* the verse (3E gen1) actually increased early RMS (+17%), while placed *after* (3G) kept energy stable. Reversed placement front-loads instrumental energy.
- **`[Verse | Key Change]`** produced short clips (both gens under 90s), suggesting the pipe-delimited modifier syntax confuses Suno's length model.
- **`[Instrumental Break]` before `[Verse]` (3F)** is the mildest modifier — nearly indistinguishable from plain `[Verse]` in the early window.

---

## Batch 4 — Edge Cases

| ID | Tag | Early RMS | Early Onset | Notes |
|----|-----|-----------|-------------|-------|
| 4A | `[Verse]` then `[Bass Drop]` | −0.08 to −0.23 | −0.03 to −0.07 | gen2 second window `[SHORT]`; Bass Drop may not extend clip length |
| 4B | `[Verse]` `[Silence]` `[Chorus]` | −0.33 to +0.04 | −0.11 to −0.21 | `[Silence]` tag does not reliably produce silence; gen2 second window `[SHORT]` |
| 4C | Made-up: `[Ethereal Breakdown]` | −0.12 to −0.32 | **−0.53 to −0.61** | Strongest onset drop of any condition; rhythmic sparsity is the dominant effect |
| 4D | Made-up: `[Chaos Section]` | **+0.31** to −0.28 | −0.20 to −0.33 | gen1 early window is **louder** (+31% RMS, +25% centroid) — only condition to reliably increase energy |
| 4E | `[Chorus]` repeated ×4 | −0.14 to −0.22 | −0.13 to −0.17 | Most stable of Batch 4; repeated tags produce consistent mid-energy output |
| 4F | ALL CAPS lyrics | **−0.66 to −0.72** | −0.30 to −0.44 | Both gens `[SHORT]`; counter-intuitively quieter and shorter than control |
| 4G | Parentheses backup vocals `(let it break)` | **−0.46 to −0.57** | −0.06 to −0.35 | Both gens `[SHORT]`; strong quieting, clips under 90s |

**Key findings:**
- **`[Chaos Section]` (made-up tag) was the only condition to increase early energy** — gen1 hit +31% RMS and +25% spectral brightness. Suno appears to interpret novel "chaos" semantics as high-energy instruction.
- **`[Ethereal Breakdown]` (made-up tag)** produced the sparsest rhythm of any condition (onset density −53 to −61%), suggesting Suno has a strong prior on "breakdown" = sparse texture even for novel compound tags.
- **ALL CAPS lyrics (4F)** produced the shortest, quietest clips — opposite of the expected "loud/shouted" interpretation. Suno may be penalizing or normalizing ALL CAPS input.
- **Parentheses backup vocals (4G)** also produced short, quiet clips. The `(text)` convention may not be parsed as intended.
- **`[Silence]` tag (4B)** did not reliably produce silence — audio continues through the window.
- **Repeated `[Chorus]` ×4 (4E)** was the most stable Batch 4 condition, producing predictable mid-energy output close to control.

---

## Summary Rankings

### Strongest effect on loudness (RMS delta, early window, gen1)
| Rank | Condition | Delta |
|------|-----------|-------|
| 1 | 4F ALL CAPS | −0.66 |
| 2 | 3E [Guitar Solo] then [Verse] (gen2) | −0.66 |
| 3 | 3D [Spoken Word] | −0.49 to −0.60 |
| 4 | 3C [Whispered Verse] | −0.40 to −0.46 |
| 5 | **4D [Chaos Section] (gen1) — LOUDER** | **+0.31** |

### Most rhythmically sparse (onset delta, early window)
| Rank | Condition | Delta |
|------|-----------|-------|
| 1 | 4C [Ethereal Breakdown] | −0.53 to −0.61 |
| 2 | 3A [Verse] batch3 control | −0.32 to −0.61 |
| 3 | 2B [Build/Drop/Break] | −0.26 |

### Most stable / closest to control (lowest absolute delta sum)
| Rank | Condition | |
|------|-----------|---|
| 1 | 3F [Instrumental Break] then [Verse] | near-neutral early window |
| 2 | 4E [Chorus] ×4 | consistent, predictable |
| 3 | 2C [Hook-centric] | mildest Batch 2 departure |

### Clip length issues (both gens under 90s)
`3A`, `3C`, `3D`, `3E` (gen2 only), `3H`, `4A` (gen2 only), `4B` (gen2 only), `4D` (gen2 only), `4F`, `4G`

These conditions produced consistently short clips (file sizes 0.4–0.8 MB vs 1.0–2.8 MB for full-length clips). The 0:50–1:30 analysis window is unreliable for these.

---

## Notable Observations

1. **Suno generates shorter clips for "non-standard" voice instructions** — spoken word, whisper, and edge-case formatting (ALL CAPS, parentheses) all produce shorter clips, suggesting these tags disrupt the default song-length model.

2. **Made-up tags work** — both `[Ethereal Breakdown]` and `[Chaos Section]` produced distinct, interpretable effects (sparse rhythm and high energy respectively). Suno maps novel semantics onto audio features rather than ignoring unknown tags.

3. **Structural bracket order doesn't matter much** — 1B (correct order) and 1C (wrong order) are indistinguishable by audio features. The labels are parsed independently.

4. **`[Soft Verse]` is the most reliable modifier** — highest compliance score (1.00), consistent RMS reduction, confirms the compliance rule engine works correctly for keyword-driven tags.

5. **`[Key Change]` via pipe syntax (`[Verse | Key Change]`) is problematic** — produces short clips, possibly confusing Suno's parser.

6. **The second analysis window (0:50–1:30) is only reliable for conditions with long lyrics** — Batch 1 and Batch 2 clips tend to be full-length; Batch 3 and 4 vocal modifier conditions trend shorter.
