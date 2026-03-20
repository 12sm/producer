"""Producer-style timestamped note generation from feature deltas."""

from audio_utils import format_window


def generate_notes(window_start: float, window_end: float,
                   orig_features: dict, variant_features: dict,
                   deltas: dict, intent: str, compliance: dict) -> dict:
    """Generate producer-style notes for a bracket window.

    Architecture: calls _generate_notes_from_features internally.
    A _generate_notes_from_model stub exists for future model swap-in.

    Returns:
        window: formatted time window string
        what_changed: description of changes
        what_improved: what likely got better
        what_got_worse: what might have degraded
        suggested_tweak: next bracket prompt suggestion
    """
    return _generate_notes_from_features(
        window_start, window_end,
        orig_features, variant_features,
        deltas, intent, compliance,
    )


def _generate_notes_from_features(window_start, window_end,
                                  orig_features, variant_features,
                                  deltas, intent, compliance) -> dict:
    """Template-based notes from feature deltas + intent keywords."""
    window = format_window(window_start, window_end)
    changes = []
    improvements = []
    concerns = []
    intent_lower = intent.lower()

    # Analyze each feature delta
    d_rms = deltas.get('rms_mean', 0)
    d_centroid = deltas.get('centroid_mean', 0)
    d_onset = deltas.get('onset_density', 0)
    d_rms_std = deltas.get('rms_std', 0)
    d_tempo = deltas.get('tempo', 0)

    # --- Loudness ---
    if abs(d_rms) > 0.05:
        direction = 'louder' if d_rms > 0 else 'quieter'
        pct = abs(d_rms * 100)
        changes.append(f"Region is {direction} ({pct:.0f}% change in RMS)")
        if any(w in intent_lower for w in ['louder', 'punch', 'hard']) and d_rms > 0:
            improvements.append("Loudness increase aligns with intent")
        elif any(w in intent_lower for w in ['soft', 'quiet', 'subtle', 'less', 'gentle']) and d_rms < 0:
            improvements.append("Quieter dynamics align with intent")
        elif abs(d_rms) > 0.3:
            concerns.append(f"Large loudness shift ({direction}) — may be unintended")

    # --- Dynamics / consistency ---
    if abs(d_rms_std) > 0.1:
        if d_rms_std > 0:
            changes.append("More dynamic range / less consistent level")
        else:
            changes.append("Tighter dynamics / more consistent level")
        if 'tight' in intent_lower and d_rms_std < 0:
            improvements.append("Tighter dynamics match 'tight' intent")
        if 'dynamic' in intent_lower and d_rms_std > 0:
            improvements.append("More dynamic range matches intent")

    # --- Brightness ---
    if abs(d_centroid) > 0.05:
        direction = 'brighter' if d_centroid > 0 else 'darker/warmer'
        changes.append(f"Spectral balance shifted {direction}")
        if any(w in intent_lower for w in ['bright', 'crisp', 'airy']) and d_centroid > 0:
            improvements.append("Brighter tone aligns with intent")
        elif any(w in intent_lower for w in ['dark', 'warm', 'no crash', 'no cymbal']) and d_centroid < 0:
            improvements.append("Darker/warmer tone aligns with intent")
        elif abs(d_centroid) > 0.3:
            concerns.append(f"Large spectral shift ({direction}) — check for tonal artifacts")

    # --- Rhythm / busyness ---
    if abs(d_onset) > 0.05:
        if d_onset > 0:
            changes.append(f"Busier rhythm ({d_onset * 100:.0f}% more onsets/sec)")
        else:
            changes.append(f"Sparser rhythm ({abs(d_onset) * 100:.0f}% fewer onsets/sec)")
        if any(w in intent_lower for w in ['busy', 'dense', 'tight']) and d_onset > 0:
            improvements.append("Increased rhythmic activity matches intent")
        elif any(w in intent_lower for w in ['sparse', 'simple', 'simpler', 'less']) and d_onset < 0:
            improvements.append("Reduced rhythmic activity matches intent")

    # --- Tempo ---
    if abs(d_tempo) > 0.02:
        orig_bpm = orig_features.get('tempo', 0)
        var_bpm = variant_features.get('tempo', 0)
        changes.append(f"Tempo shifted: {orig_bpm:.0f} → {var_bpm:.0f} BPM")
        if abs(d_tempo) > 0.1:
            concerns.append("Significant tempo change — likely an estimation artifact or real drift")

    # Fallbacks
    if not changes:
        changes.append("No significant feature changes detected in this window")
    if not improvements:
        if compliance.get('verdict') == 'PASS':
            improvements.append("Overall compliance is good based on keyword matching")
        else:
            improvements.append("No clear improvements aligned with intent detected")
    if not concerns:
        concerns.append("No obvious artifacts or regressions detected")

    # --- Suggested tweak ---
    tweak = _suggest_tweak(deltas, intent_lower, compliance)

    return {
        'window': window,
        'what_changed': '; '.join(changes),
        'what_improved': '; '.join(improvements),
        'what_got_worse': '; '.join(concerns),
        'suggested_tweak': tweak,
    }


def _suggest_tweak(deltas: dict, intent_lower: str, compliance: dict) -> str:
    """Generate a suggested next bracket prompt tweak."""
    verdict = compliance.get('verdict', 'MIXED')

    if verdict == 'PASS':
        return "Current prompt is working well. Consider locking this snippet and testing edge cases."

    suggestions = []
    missed = [r for r in compliance.get('matched_rules', []) if not r['met']]

    for rule in missed:
        kw = rule['keyword']
        feat = rule['feature']
        expected = rule['expected']

        if feat == 'rms_mean':
            if expected == 'decrease':
                suggestions.append(f"Try reinforcing '{kw}' with volume words: 'soft', 'gentle', 'pull back'")
            else:
                suggestions.append(f"Try reinforcing '{kw}' with energy words: 'punchy', 'drive', 'push'")
        elif feat == 'centroid_mean':
            if expected == 'decrease':
                suggestions.append(f"For '{kw}', try adding: 'warm', 'mellow', 'low-mid focus'")
            else:
                suggestions.append(f"For '{kw}', try adding: 'crisp', 'airy', 'open hi-hats'")
        elif feat == 'onset_density':
            if expected == 'decrease':
                suggestions.append(f"For '{kw}', try: 'half-time', 'minimal hits', 'spacious'")
            else:
                suggestions.append(f"For '{kw}', try: '16th-note', 'rapid', 'fill every beat'")

    if not suggestions:
        suggestions.append("Try being more specific with production terminology in the bracket prompt")

    return '; '.join(suggestions[:3])


def _generate_notes_from_model(window_start, window_end,
                               orig_features, variant_features,
                               deltas, intent, compliance) -> dict:
    """Placeholder for future audio-capable model integration.

    When an audio-capable model is available, this function should:
    1. Send the bracket audio slices (original + variant) to the model
    2. Include the intent text and feature deltas as context
    3. Ask for producer-style notes
    4. Return the same dict structure as _generate_notes_from_features
    """
    raise NotImplementedError(
        "Model-based notes not yet implemented. "
        "Swap in an audio-capable model here when available."
    )
