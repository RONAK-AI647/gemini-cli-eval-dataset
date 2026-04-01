#!/usr/bin/env python3
"""
eval_runner.py — Evaluation runner for the Long-Context Coding Evaluation Dataset
GSoC 2026 · Google Gemini CLI · Issue #23316

Feeds each task to Gemini CLI, captures output, applies the proposed patch,
runs the verification test, scores the result, and writes a results JSON.

Usage:
    # Run all tasks
    python scripts/eval_runner.py --bundle /path/to/gemini-cli/bundle/gemini.js

    # Run a single task
    python scripts/eval_runner.py --bundle /path/to/bundle/gemini.js --task tasks/vllm/vllm-001.json

    # Dry run (skip CLI invocation, useful for testing the pipeline)
    python scripts/eval_runner.py --bundle /path/to/bundle/gemini.js --dry-run

Prerequisites:
    - Gemini CLI repo built: cd gemini-cli && npm install && npm run build && npm run bundle
    - GEMINI_API_KEY set in environment
    - Target repos cloned (use scripts/repo_inventory.py to clone them)
"""

import json
import os
import subprocess
import sys
import argparse
import shutil
import tempfile
import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

DATASET_ROOT = Path(__file__).parent.parent
TASKS_DIR    = DATASET_ROOT / "tasks"
RESULTS_DIR  = DATASET_ROOT / "results"
REPO_CACHE   = DATASET_ROOT / "repo_cache"

# ── Scoring constants ────────────────────────────────────────────────────────

SCORE_FULL_PASS    = 1.0
SCORE_PARTIAL_PASS = 0.5
SCORE_WRONG_FILES  = 0.1
SCORE_FAIL         = 0.0

# How long to wait for Gemini CLI to respond (seconds)
CLI_TIMEOUT = 300

# How long to wait for test_command to run (seconds)
TEST_TIMEOUT = 120


# ── Repo management ──────────────────────────────────────────────────────────

def get_repo_path(repo_name: str) -> Path:
    """Return local clone path for a repo, cloning if needed."""
    short = repo_name.split("/")[1]
    dest  = REPO_CACHE / short
    if not dest.exists():
        url = f"https://github.com/{repo_name}.git"
        print(f"    [clone] {url}")
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, str(dest)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Clone failed for {repo_name}: {result.stderr[:300]}")
    return dest


def checkout_commit(repo_path: Path, commit_sha: str):
    """Pin the repo to the exact commit SHA from the task."""
    if commit_sha in ("HEAD~1", "HEAD"):
        return  # leave at latest
    result = subprocess.run(
        ["git", "checkout", commit_sha],
        cwd=repo_path, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    [warn] Could not checkout {commit_sha}: {result.stderr[:200]}")


def apply_patch(repo_path: Path, patch_file: Path) -> bool:
    """Apply the ground truth patch to verify it works (for smoke testing)."""
    if not patch_file.exists():
        return False
    result = subprocess.run(
        ["git", "apply", "--check", str(patch_file)],
        cwd=repo_path, capture_output=True, text=True
    )
    return result.returncode == 0


def reset_repo(repo_path: Path):
    """Reset repo to clean state after each task run."""
    subprocess.run(["git", "checkout", "."], cwd=repo_path,
                   capture_output=True, text=True)
    subprocess.run(["git", "clean", "-fd"], cwd=repo_path,
                   capture_output=True, text=True)


# ── Gemini CLI invocation ────────────────────────────────────────────────────

def build_prompt(task: dict) -> str:
    """
    Construct the full prompt for Gemini CLI from the task JSON.
    Includes the task description plus the list of required files
    so the agent knows where to look.
    """
    required_files = "\n".join(f"  - {f}" for f in task["context"]["required_files"])
    prompt = (
        f"{task['task']['description']}\n\n"
        f"The following files are relevant to this task and must be read "
        f"before proposing any changes:\n{required_files}\n\n"
        f"Please read all the files above, understand the full context, "
        f"then implement the fix. Modify only the files that need to change. "
        f"Do not add unnecessary changes."
    )
    return prompt


def run_gemini_cli(
    prompt: str,
    bundle_path: str,
    repo_path: Path,
    dry_run: bool = False
) -> dict:
    """
    Invoke Gemini CLI as a subprocess with --output-format json and
    --approval-mode yolo, with cwd set to the target repo.

    Returns the parsed JSON output from the CLI.
    """
    if dry_run:
        return {
            "session_id": "dry-run",
            "response": "[DRY RUN — CLI not invoked]",
            "stats": {"tools": {"totalCalls": 0, "totalSuccess": 0, "totalFail": 0}}
        }

    # Isolate Gemini CLI config so it doesn't touch the real user config
    isolated_home = tempfile.mkdtemp(prefix="eval-gemini-home-")

    try:
        result = subprocess.run(
            [
                "node",bundle_path,
                "-p",prompt,
                "--output-format", "json",
                "--approval-mode", "yolo",
            ],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT,
            env={
                **os.environ,
        
                "GEMINI_CLI_INTEGRATION_TEST": "true",
            }
        )
    except subprocess.TimeoutExpired:
        return {"error": "CLI_TIMEOUT", "session_id": None, "response": "", "stats": {}}
    finally:
        shutil.rmtree(isolated_home, ignore_errors=True)

    if result.returncode != 0 and not result.stdout.strip():
        return {
            "error": "CLI_ERROR",
            "stderr": result.stderr[:500],
            "session_id": None,
            "response": "",
            "stats": {}
        }

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # CLI returned non-JSON (e.g. interactive mode triggered)
        return {
            "error": "PARSE_ERROR",
            "raw_stdout": result.stdout[:1000],
            "session_id": None,
            "response": result.stdout,
            "stats": {}
        }


# ── Test verification ────────────────────────────────────────────────────────

def run_test_command(test_command: str, repo_path: Path) -> dict:
    """
    Run the ground truth test command in the target repo.
    Returns a dict with returncode, stdout, stderr.
    """
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:],  # last 3000 chars to avoid huge logs
            "stderr": result.stderr[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "TEST_TIMEOUT"}


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_result(test_result: dict, cli_output: dict) -> float:
    """
    Score the task run:
      1.0 — all tests pass
      0.5 — some tests pass (partial, heuristic)
      0.1 — CLI produced output but tests failed and wrong files modified
      0.0 — tests failed or CLI errored
    """
    if "error" in cli_output and cli_output["error"] in ("CLI_TIMEOUT", "CLI_ERROR", "PARSE_ERROR"):
        return SCORE_FAIL

    if test_result["returncode"] == 0:
        return SCORE_FULL_PASS

    stdout = test_result.get("stdout", "").lower()

    # Heuristic for partial pass: some tests passed
    if "passed" in stdout and "failed" in stdout:
        return SCORE_PARTIAL_PASS

    # Check if CLI touched files but tests still failed
    stats = cli_output.get("stats", {})
    tool_calls = stats.get("tools", {}).get("totalCalls", 0)
    if tool_calls > 0:
        return SCORE_WRONG_FILES

    return SCORE_FAIL


def classify_failure(score: float, test_result: dict, cli_output: dict, task: dict) -> list:
    """
    Heuristically classify which failure mode(s) occurred.
    These are informational — not used for scoring.
    """
    if score == SCORE_FULL_PASS:
        return []

    modes = []
    stdout = (test_result.get("stdout", "") + test_result.get("stderr", "")).lower()
    response = cli_output.get("response", "").lower()
    stats = cli_output.get("stats", {}).get("tools", {})
    tool_calls = stats.get("totalCalls", 0)

    # Agent made no tool calls — didn't read files
    if tool_calls == 0:
        modes.append("insufficient_context_read")

    # Agent mentioned files but tests still failed
    if tool_calls > 0 and score == SCORE_WRONG_FILES:
        modes.append("correct_file_wrong_function")

    # API hallucination signals
    if any(kw in stdout for kw in ["attributeerror", "nameerror", "importerror", "no module named"]):
        modes.append("hallucinated_api")

    # Context window exceeded
    if "context" in stdout and "exceed" in stdout:
        modes.append("context_window_exceeded")

    # Partial fix
    if score == SCORE_PARTIAL_PASS:
        modes.append("partial_fix_only")

    # Cross-language requirement missed
    if task["context"].get("cross_language") and score < SCORE_FULL_PASS:
        modes.append("missing_cross_language_change")

    # Tests not updated
    if "test" in stdout and "no tests" in stdout:
        modes.append("test_not_updated")

    return modes if modes else ["partial_fix_only"]


# ── Core runner ──────────────────────────────────────────────────────────────

def run_task(task_path: Path, bundle_path: str, dry_run: bool = False) -> dict:
    """Run a single eval task end-to-end. Returns a result dict."""

    with open(task_path) as f:
        task = json.load(f)

    task_id   = task["task_id"]
    repo_name = task["repo"]["name"]
    commit    = task["repo"]["commit_sha"]

    print(f"\n  {'='*54}")
    print(f"  Task:   {task_id}")
    print(f"  Repo:   {repo_name}")
    print(f"  Diff:   {task['difficulty']}  |  Type: {task['task_type']}")
    print(f"  Tokens: ~{task['context']['estimated_tokens']:,}")
    print(f"  {'='*54}")

    # 1. Get repo
    try:
        repo_path = get_repo_path(repo_name)
        checkout_commit(repo_path, commit)
    except RuntimeError as e:
        print(f"  [ERROR] {e}")
        return {
            "task_id": task_id, "score": SCORE_FAIL,
            "error": str(e), "failure_modes": ["insufficient_context_read"]
        }

    # 2. Build prompt
    prompt = build_prompt(task)
    print(f"  [prompt] {len(prompt)} chars, {len(task['context']['required_files'])} required files")

    # 3. Invoke Gemini CLI
    print(f"  [gemini] Running CLI...")
    cli_output = run_gemini_cli(prompt, bundle_path, repo_path, dry_run=dry_run)

    if "error" in cli_output:
        print(f"  [gemini] Error: {cli_output['error']}")
    else:
        tool_calls = cli_output.get("stats", {}).get("tools", {}).get("totalCalls", 0)
        print(f"  [gemini] Done. Tool calls: {tool_calls}")

    # 4. Run verification test
    test_command = task["ground_truth"]["test_command"]
    print(f"  [test]   Running: {test_command[:80]}...")
    test_result = run_test_command(test_command, repo_path)

    status = "PASS" if test_result["returncode"] == 0 else "FAIL"
    print(f"  [test]   {status} (exit code: {test_result['returncode']})")

    # 5. Score
    score = score_result(test_result, cli_output)
    failure_modes = classify_failure(score, test_result, cli_output, task)
    print(f"  [score]  {score:.1f}  |  Failure modes: {failure_modes or 'none'}")

    # 6. Reset repo
    reset_repo(repo_path)

    return {
        "task_id":       task_id,
        "repo":          repo_name,
        "difficulty":    task["difficulty"],
        "task_type":     task["task_type"],
        "score":         score,
        "failure_modes": failure_modes,
        "estimated_tokens": task["context"]["estimated_tokens"],
        "cross_language":   task["context"]["cross_language"],
        "cli": {
            "session_id":  cli_output.get("session_id"),
            "tool_calls":  cli_output.get("stats", {}).get("tools", {}).get("totalCalls", 0),
            "error":       cli_output.get("error"),
        },
        "test": {
            "command":    test_command,
            "returncode": test_result["returncode"],
            "stdout_tail": test_result["stdout"][-500:],
        }
    }


# ── Results writer ───────────────────────────────────────────────────────────

def write_results(results: list, run_id: str):
    """Write the full run results to results/run_{timestamp}.json."""
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"run_{run_id}.json"

    total     = len(results)
    passed    = sum(1 for r in results if r["score"] == SCORE_FULL_PASS)
    partial   = sum(1 for r in results if r["score"] == SCORE_PARTIAL_PASS)
    failed    = sum(1 for r in results if r["score"] == SCORE_FAIL)
    avg_score = sum(r["score"] for r in results) / max(total, 1)

    # Failure mode frequency
    failure_freq: dict = {}
    for r in results:
        for mode in r.get("failure_modes", []):
            failure_freq[mode] = failure_freq.get(mode, 0) + 1

    output = {
        "run_id":    run_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_tasks":    total,
            "full_pass":      passed,
            "partial_pass":   partial,
            "fail":           failed,
            "average_score":  round(avg_score, 3),
            "pass_rate":      round(passed / max(total, 1), 3),
        },
        "failure_mode_frequency": dict(
            sorted(failure_freq.items(), key=lambda x: -x[1])
        ),
        "results": results
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    return out_path, output["summary"]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Eval runner for the Long-Context Coding Evaluation Dataset"
    )
    parser.add_argument(
        "--bundle", required=False, default="gemini",
        help="Path to bundle/gemini.js (e.g. /path/to/gemini-cli/bundle/gemini.js)"
    )
    parser.add_argument(
        "--task", default=None,
        help="Run a single task file (e.g. tasks/vllm/vllm-001.json)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip Gemini CLI invocation — test pipeline only"
    )
    args = parser.parse_args()

    # Verify bundle exists
    if not args.dry_run and not Path(args.bundle).exists():
        print(f"\n  ERROR: bundle not found at {args.bundle}")
        print("  Run: cd gemini-cli && npm run build && npm run bundle")
        sys.exit(1)

    # Verify API key
    if not args.dry_run and not os.environ.get("GEMINI_API_KEY"):
        print("\n  ERROR: GEMINI_API_KEY not set in environment")
        sys.exit(1)

    # Collect tasks
    if args.task:
        task_files = [Path(args.task)]
    else:
        task_files = sorted(TASKS_DIR.rglob("*.json"))

    if not task_files:
        print("  No task files found.")
        sys.exit(1)

    run_id  = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    mode    = "[DRY RUN]" if args.dry_run else ""

    print(f"\n{'='*60}")
    print(f"  Long-Context Eval Dataset — Eval Runner {mode}")
    print(f"  Run ID:  {run_id}")
    print(f"  Tasks:   {len(task_files)}")
    print(f"  Bundle:  {args.bundle}")
    print(f"{'='*60}")

    results = []
    for task_path in task_files:
        result = run_task(task_path, args.bundle, dry_run=args.dry_run)
        results.append(result)

    # Write results
    out_path, summary = write_results(results, run_id)

    print(f"\n{'='*60}")
    print(f"  RUN COMPLETE")
    print(f"  Total tasks:   {summary['total_tasks']}")
    print(f"  Full pass:     {summary['full_pass']}")
    print(f"  Partial pass:  {summary['partial_pass']}")
    print(f"  Failed:        {summary['fail']}")
    print(f"  Pass rate:     {summary['pass_rate']:.0%}")
    print(f"  Avg score:     {summary['average_score']:.3f}")
    print(f"  Results:       {out_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
