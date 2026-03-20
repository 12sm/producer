"""Output formatting: console summary, report.md, report.json."""

import json
import os


def print_console_summary(run_data: dict):
    """Print a readable console summary."""
    print()
    print('=' * 60)
    print('  BRACKET PROMPT LAB — Run Report')
    print('=' * 60)
    print(f"  Run ID:   {run_data['run_id']}")
    print(f"  Intent:   {run_data['intent']}")
    print()

    # Bracket results
    for br in run_data.get('bracket_results', []):
        print(f"  ── Bracket: {br['window']} ──")
        c = br['compliance']
        print(f"  Compliance: {c['verdict']}  (score: {c['score']:.2f}, confidence: {c['confidence']:.2f})")
        print(f"  {c['explanation']}")
        print()
        n = br['notes']
        print(f"  What changed:   {n['what_changed']}")
        print(f"  What improved:  {n['what_improved']}")
        print(f"  What got worse: {n['what_got_worse']}")
        print(f"  Suggested tweak: {n['suggested_tweak']}")
        print()

    # Drift
    drift = run_data.get('drift', {})
    print(f"  ── Collateral Drift ──")
    print(f"  Overall drift: {drift.get('overall_drift', 0):.4f}  Verdict: {drift.get('verdict', 'N/A')}")
    for a in drift.get('per_anchor', []):
        print(f"    Anchor {a['anchor_index']}: drift={a['drift_score']:.4f}")
    print()

    # Snippet bank
    print(f"  Saved to snippet bank: {run_data.get('bank_dir', 'N/A')}/{run_data['run_id']}/")
    print('=' * 60)
    print()


def write_report_md(run_data: dict, out_path: str):
    """Write a Markdown report."""
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

    lines = []
    lines.append('# Bracket Prompt Lab — Report')
    lines.append('')
    lines.append(f'**Run ID:** `{run_data["run_id"]}`  ')
    lines.append(f'**Timestamp:** {run_data.get("timestamp", "N/A")}  ')
    lines.append(f'**Original:** `{run_data.get("original_path", "N/A")}`  ')
    lines.append(f'**Variant:** `{run_data.get("variant_path", "N/A")}`  ')
    lines.append(f'**Intent:** {run_data["intent"]}  ')
    lines.append('')

    if run_data.get('prompt_text'):
        lines.append('## Prompt Text')
        lines.append('')
        lines.append('```')
        lines.append(run_data['prompt_text'])
        lines.append('```')
        lines.append('')

    lines.append('## Bracket Analysis')
    lines.append('')
    for br in run_data.get('bracket_results', []):
        lines.append(f'### Window: {br["window"]}')
        lines.append('')
        c = br['compliance']
        lines.append(f'| Metric | Value |')
        lines.append(f'|--------|-------|')
        lines.append(f'| Compliance Score | {c["score"]:.3f} |')
        lines.append(f'| Confidence | {c["confidence"]:.3f} |')
        lines.append(f'| Verdict | **{c["verdict"]}** |')
        lines.append('')
        lines.append(f'**Explanation:** {c["explanation"]}')
        lines.append('')

        if c.get('matched_rules'):
            lines.append('**Rule matches:**')
            lines.append('')
            lines.append('| Keyword | Feature | Expected | Actual Δ | Met? |')
            lines.append('|---------|---------|----------|----------|------|')
            for r in c['matched_rules']:
                met_icon = 'Yes' if r['met'] else 'No'
                lines.append(f'| {r["keyword"]} | {r["feature"]} | {r["expected"]} | {r["actual_delta"]:.4f} | {met_icon} |')
            lines.append('')

        n = br['notes']
        lines.append('**Producer Notes:**')
        lines.append('')
        lines.append(f'- **What changed:** {n["what_changed"]}')
        lines.append(f'- **What improved:** {n["what_improved"]}')
        lines.append(f'- **What got worse:** {n["what_got_worse"]}')
        lines.append(f'- **Suggested tweak:** {n["suggested_tweak"]}')
        lines.append('')

        # Feature comparison table
        lines.append('**Feature Comparison:**')
        lines.append('')
        lines.append('| Feature | Original | Variant | Delta |')
        lines.append('|---------|----------|---------|-------|')
        for key in br.get('original_features', {}):
            o = br['original_features'][key]
            v = br['variant_features'][key]
            d = br['deltas'].get(key, 0)
            lines.append(f'| {key} | {o} | {v} | {d:+.4f} |')
        lines.append('')

    lines.append('## Collateral Drift')
    lines.append('')
    drift = run_data.get('drift', {})
    lines.append(f'**Overall Drift Score:** {drift.get("overall_drift", 0):.4f}  ')
    lines.append(f'**Verdict:** **{drift.get("verdict", "N/A")}**')
    lines.append('')
    if drift.get('per_anchor'):
        lines.append('| Anchor | Drift Score |')
        lines.append('|--------|-------------|')
        for a in drift['per_anchor']:
            lines.append(f'| {a["anchor_index"]} | {a["drift_score"]:.4f} |')
        lines.append('')

    lines.append('## Metadata')
    lines.append('')
    lines.append(f'- Brackets: {run_data.get("brackets", [])}')
    lines.append(f'- Anchors: {run_data.get("anchors", [])}')
    lines.append(f'- Slice files: {run_data.get("slice_files", [])}')
    lines.append('')

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))


def write_report_json(run_data: dict, out_path: str):
    """Write the full run data as JSON."""
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(run_data, f, indent=2, default=str)
