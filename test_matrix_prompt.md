# Suno Bracket Test Matrix — Claude Code Prompt

Give this prompt to Claude Code to run the full test matrix.

---

## Prompt

```
You are running a systematic test of how Suno AI responds to bracket
meta tags. The goal is to generate songs via Suno, download them, run
our analyze pipeline on each, and build a dataset we can compare.

## Setup

- Use `python -m tools.analyze` for analysis
- Store all generations in `test_matrix/` organized by batch
- Use style tag "indie rock, male vocals, 120 bpm" for ALL generations
  (control variable — do not change this across batches)
- Use the SAME lyrics below for Batches 1-2 so structure is the only variable
- For each generation, save the Suno prompt used as a .txt alongside the audio

## Standard Lyrics (use for Batches 1-2)

Walking through the city lights again
Every street a story I can't explain
The neon hums a melody I know
A rhythm pulling me where I need to go

I'm caught in the echo of what we made
A sound that doesn't falter, doesn't fade
Turn it up and let the whole thing break
This is every chance I'm gonna take

The morning finds me halfway home
Static on the radio, dancing alone
But the beat keeps going, the bass stays low
And I'm still chasing what I'll never know

One last time before the silence calls
Let the music carry through these walls

## Batch 1 — Baseline: Does Suno Respect Brackets? (3 gens each = 9 total)

### 1A: No brackets (control)
Just paste the raw lyrics above with no bracket tags at all.

### 1B: Standard brackets
[Verse 1]
Walking through the city lights again
Every street a story I can't explain
The neon hums a melody I know
A rhythm pulling me where I need to go

[Chorus]
I'm caught in the echo of what we made
A sound that doesn't falter, doesn't fade
Turn it up and let the whole thing break
This is every chance I'm gonna take

[Verse 2]
The morning finds me halfway home
Static on the radio, dancing alone
But the beat keeps going, the bass stays low
And I'm still chasing what I'll never know

[Outro]
One last time before the silence calls
Let the music carry through these walls

### 1C: Wrong order (brackets don't match content)
[Chorus]
Walking through the city lights again
Every street a story I can't explain
The neon hums a melody I know
A rhythm pulling me where I need to go

[Verse 1]
I'm caught in the echo of what we made
A sound that doesn't falter, doesn't fade
Turn it up and let the whole thing break
This is every chance I'm gonna take

[Outro]
The morning finds me halfway home
Static on the radio, dancing alone
But the beat keeps going, the bass stays low
And I'm still chasing what I'll never know

[Verse 2]
One last time before the silence calls
Let the music carry through these walls

## Batch 2 — Structural Differentiation (1 gen each = 4 total)

### 2A: Full standard structure
[Intro]
[Verse 1]
Walking through the city lights again
Every street a story I can't explain
The neon hums a melody I know
A rhythm pulling me where I need to go

[Pre-Chorus]
The neon hums a melody I know

[Chorus]
I'm caught in the echo of what we made
A sound that doesn't falter, doesn't fade
Turn it up and let the whole thing break
This is every chance I'm gonna take

[Bridge]
The morning finds me halfway home
Static on the radio, dancing alone

[Chorus]
But the beat keeps going, the bass stays low
And I'm still chasing what I'll never know

[Outro]
One last time before the silence calls
Let the music carry through these walls

### 2B: EDM-style structure
[Build]
Walking through the city lights again
Every street a story I can't explain

[Drop]
The neon hums a melody I know
A rhythm pulling me where I need to go

[Break]
I'm caught in the echo of what we made
A sound that doesn't falter, doesn't fade

[Drop]
Turn it up and let the whole thing break
This is every chance I'm gonna take

[Outro]
One last time before the silence calls
Let the music carry through these walls

### 2C: Hook-centric
[Verse 1]
Walking through the city lights again
Every street a story I can't explain

[Hook]
The neon hums a melody I know
A rhythm pulling me where I need to go

[Verse 2]
The morning finds me halfway home
Static on the radio, dancing alone

[Hook]
Turn it up and let the whole thing break
This is every chance I'm gonna take

[Fade Out]

### 2D: Interlude test
[Verse 1]
Walking through the city lights again
Every street a story I can't explain

[Interlude]

[Verse 2]
The neon hums a melody I know
A rhythm pulling me where I need to go

[Interlude]

[Chorus]
I'm caught in the echo of what we made
A sound that doesn't falter, doesn't fade
Turn it up and let the whole thing break
This is every chance I'm gonna take

[Outro]
One last time before the silence calls
Let the music carry through these walls

## Batch 3 — Modifier & Instrument Tags (1 gen each = 8 total)

Use new lyrics for variety but keep same style tag.

### Lyrics for Batch 3:
Steel and glass reflecting cold December
Footsteps on the bridge I still remember
The water moves but never really leaves
Like every promise tangled in the breeze

### 3A: [Verse] (unmodified control)
### 3B: [Soft Verse]
### 3C: [Whispered Verse]
### 3D: [Spoken Word]
### 3E: [Guitar Solo] then the verse
### 3F: [Instrumental Break] then the verse
### 3G: [Verse] then [Guitar Solo]
### 3H: [Verse | Key Change]

## Batch 4 — Edge Cases (1 gen each = 7 total)

### 4A: [Bass Drop] with no lyrics after
Use Batch 3 lyrics as a verse, then just:
[Bass Drop]

### 4B: [Silence] tag
Verse lyrics, then [Silence], then chorus lyrics

### 4C: Made-up tag [Ethereal Breakdown]
Verse lyrics, then [Ethereal Breakdown], then chorus lyrics

### 4D: Made-up tag [Chaos Section]
Same pattern as 4C

### 4E: [Chorus] repeated 4x
[Chorus]
Same 4-line chorus lyrics
[Chorus]
Same 4-line chorus lyrics
[Chorus]
Same 4-line chorus lyrics
[Chorus]
Same 4-line chorus lyrics

### 4F: Vocal effect — ALL CAPS
[Verse]
STEEL AND GLASS REFLECTING COLD DECEMBER
FOOTSTEPS ON THE BRIDGE I STILL REMEMBER

### 4G: Backup vocal syntax — parentheses
[Chorus]
Turn it up and let the whole thing break (let it break)
This is every chance I'm gonna take (gonna take)

## Analysis Protocol

After each generation is downloaded:

1. Run analysis comparing each variant against 1A (no-brackets control):
   python -m tools.analyze --original test_matrix/batch1/1A_gen1.wav \
     --variant test_matrix/batch1/1B_gen1.wav \
     --intent "standard structure" --source suno

2. For same-batch comparisons, use the first generation as original

3. After all batches complete, create a summary report:
   test_matrix/RESULTS.md with a table showing:
   - Generation ID
   - Bracket tags used
   - RMS profile (did energy change at boundaries?)
   - Spectral centroid shifts (brightness changes?)
   - Onset density changes (rhythm changes?)
   - Tempo stability
   - Subjective notes on whether the tag was "respected"

4. Key questions to answer in RESULTS.md:
   - Do brackets cause measurable structural changes vs no-brackets?
   - Does Suno differentiate between section types (verse vs chorus energy)?
   - Does wrong bracket order change what Suno generates?
   - Which modifier tags ([Soft], [Whispered], [Spoken Word]) actually work?
   - Do made-up tags produce any effect?
   - Does [Guitar Solo] / [Instrumental Break] reliably remove vocals?
   - Does ALL CAPS or parentheses affect vocal delivery?

## Important

- Generate songs through the Suno web UI or API — I will handle this
  manually and drop the audio files into the appropriate directories
- YOUR job is to: set up the directory structure, prepare all prompt
  .txt files, and once I drop audio in, run the full analysis pipeline
  and produce the results report
- python -m pytest tests/ must stay green throughout
```
