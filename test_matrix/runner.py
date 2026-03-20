"""
test_matrix/runner.py — Suno bracket test matrix runner.

Queue file: test_matrix/queue.json
Clip layout:
  test_matrix/batch{N}/{gen_id}_sub{M}_gen1.mp3
  test_matrix/batch{N}/{gen_id}_sub{M}_gen2.mp3
  test_matrix/batch{N}/{gen_id}_sub{M}_prompt.txt
  test_matrix/batch{N}/{gen_id}_sub{M}_gen{K}_analysis.json

Importable as a module; run directly for a status summary.
"""

import json
import os
import subprocess
import sys

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "queue.json")
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

# Two brackets covering early and mid-song sections
ANALYSIS_BRACKETS = ["0:10-0:50", "0:50-1:30"]


# ---------------------------------------------------------------------------
# Queue I/O
# ---------------------------------------------------------------------------

def _load_queue():
    with open(QUEUE_PATH, "r") as f:
        return json.load(f)


def _save_queue(queue):
    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_next_pending():
    """Return the next queue item whose status is 'pending', or None."""
    queue = _load_queue()
    for item in queue:
        if item.get("status") == "pending":
            return item
    return None


def mark_done(gen_id, sub_num, clip_ids):
    """
    Mark a submission as done and record the clip IDs generated.

    Parameters
    ----------
    gen_id   : str   — e.g. "1A"
    sub_num  : int   — submission number (1-based)
    clip_ids : list  — Suno clip IDs returned for this submission
    """
    queue = _load_queue()
    for item in queue:
        if item["id"] == gen_id:
            if "results" not in item:
                item["results"] = {}
            key = f"sub{sub_num}"
            item["results"][key] = {"clip_ids": clip_ids}
            total_subs = item.get("submissions", 1)
            done_subs = len(item.get("results", {}))
            if done_subs >= total_subs:
                item["status"] = "done"
            break
    _save_queue(queue)


def get_control_path():
    """
    Return the local path of the first 1A clip (sub1, gen1) if it exists,
    otherwise None.
    """
    control_path = os.path.join(
        os.path.dirname(__file__), "batch1", "1A_sub1_gen1.mp3"
    )
    return control_path if os.path.exists(control_path) else None


def batch_dir(batch_num):
    return os.path.join(os.path.dirname(__file__), f"batch{batch_num}")


def run_analysis(gen_id, sub_num, local_paths, control_path, queue_item):
    """
    Run tools.analyze for each clip in local_paths against control_path.

    Uses the actual CLI:
      python -m tools.analyze \\
          --original <control> --variant <clip> \\
          --bracket "0:10-0:50" --bracket "0:50-1:30" \\
          --intent <bracket_desc> \\
          --prompt-text <lyrics> \\
          --out-dir <batch_dir> \\
          --source suno

    Analysis JSON is saved by the tool to out-dir/<run_id>_report.json.
    We also write a convenience symlink at the expected path.
    """
    bdir = batch_dir(queue_item["batch"])
    os.makedirs(bdir, exist_ok=True)

    if not control_path or not os.path.exists(control_path):
        print(f"  [analysis] skipping {gen_id} sub{sub_num} — no control path")
        return []

    results = []
    for k, clip_path in enumerate(local_paths, start=1):
        out_file = os.path.join(bdir, f"{gen_id}_sub{sub_num}_gen{k}_analysis.json")

        intent = queue_item.get("bracket_desc", "bracket test")
        prompt_text = queue_item.get("lyrics", "")

        cmd = [
            sys.executable, "-m", "tools.analyze",
            "--original", control_path,
            "--variant", clip_path,
            "--bracket", ANALYSIS_BRACKETS[0],
            "--bracket", ANALYSIS_BRACKETS[1],
            "--intent", intent,
            "--prompt-text", prompt_text[:500],  # truncate for CLI
            "--out-dir", bdir,
            "--source", "suno",
        ]

        print(f"  [analysis] {gen_id} sub{sub_num} gen{k}...")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )
            if result.returncode != 0:
                print(f"  [analysis] ERROR: {result.stderr.strip()[:200]}")
                results.append({"gen_num": k, "error": result.stderr.strip()[:200]})
            else:
                # Parse the JSON output printed to stdout
                try:
                    data = json.loads(result.stdout.strip())
                    with open(out_file, "w") as f:
                        json.dump(data, f, indent=2)
                    compliance = data.get("bracket_results", [{}])[0].get("compliance", {})
                    drift = data.get("drift", {})
                    print(f"  [analysis] OK — compliance={compliance.get('score', '?'):.2f} drift={drift.get('overall_drift', '?'):.4f}")
                    results.append({"gen_num": k, "out_path": out_file, "data": data})
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"  [analysis] parse error: {e}")
                    # Save raw stdout anyway
                    with open(out_file, "w") as f:
                        f.write(result.stdout)
                    results.append({"gen_num": k, "out_path": out_file})
        except Exception as e:
            print(f"  [analysis] EXCEPTION: {e}")
            results.append({"gen_num": k, "error": str(e)})

    return results


# ---------------------------------------------------------------------------
# Status summary
# ---------------------------------------------------------------------------

def print_status():
    queue = _load_queue()

    col_id     = 6
    col_batch  = 7
    col_subs   = 6
    col_status = 8
    col_desc   = 45

    header = (
        f"{'ID':<{col_id}} {'Batch':<{col_batch}} {'Subs':<{col_subs}} "
        f"{'Status':<{col_status}} {'Description':<{col_desc}}"
    )
    print(header)
    print("-" * len(header))

    counts = {"pending": 0, "done": 0, "other": 0}
    for item in queue:
        status = item.get("status", "unknown")
        desc   = item.get("bracket_desc", "")
        if len(desc) > col_desc:
            desc = desc[: col_desc - 1] + "…"
        print(
            f"{item['id']:<{col_id}} {item['batch']:<{col_batch}} "
            f"{item['submissions']:<{col_subs}} {status:<{col_status}} {desc}"
        )
        if status == "pending":
            counts["pending"] += 1
        elif status == "done":
            counts["done"] += 1
        else:
            counts["other"] += 1

    print()
    print(
        f"Total: {len(queue)}  |  Pending: {counts['pending']}  "
        f"|  Done: {counts['done']}  |  Other: {counts['other']}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_status()
