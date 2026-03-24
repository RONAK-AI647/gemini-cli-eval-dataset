#!/usr/bin/env python3
"""
validate_tasks.py — Dataset quality checker for the Long-Context Eval Dataset
GSoC 2026, Issue #23316

Validates every task JSON against the schema, checks field integrity,
flags tasks that are too easy or unrealistic, and reports statistics.

Usage:
    python scripts/validate_tasks.py
    python scripts/validate_tasks.py --task tasks/vllm/vllm-001.json
"""

import json
import os
import sys
import argparse
from pathlib import Path

TASKS_DIR = Path(__file__).parent.parent / "tasks"
SCHEMA_FILE = Path(__file__).parent.parent / "schema" / "task_schema.json"

REQUIRED_TOP_LEVEL = ["version", "task_id", "difficulty", "task_type", "repo", "task", "context", "ground_truth", "evaluation", "metadata"]
REQUIRED_REPO = ["name", "url", "languages", "commit_sha", "stars_approx"]
REQUIRED_TASK = ["title", "description", "linked_issue", "linked_pr"]
REQUIRED_CONTEXT = ["required_files", "estimated_tokens", "num_files_to_modify", "cross_language"]
REQUIRED_GROUND_TRUTH = ["patch_file", "test_command", "acceptance_criteria"]
REQUIRED_EVALUATION = ["scoring", "failure_categories"]
REQUIRED_METADATA = ["added_by", "date_added", "verified"]

VALID_DIFFICULTIES = {"medium", "hard", "very-hard"}
VALID_TASK_TYPES = {"bug_fix", "feature", "refactor", "performance"}
VALID_FAILURE_CATEGORIES = {
    "insufficient_context_read", "correct_file_wrong_function",
    "hallucinated_api", "context_window_exceeded", "partial_fix_only",
    "wrong_abstraction_layer", "missing_cross_language_change", "test_not_updated"
}

MIN_TOKENS = 10000
MAX_TOKENS = 200000
MIN_FILES = 3
MIN_FILES_TO_MODIFY = 2

errors = []
warnings = []

def check_required_fields(obj, required, path):
    for field in required:
        if field not in obj:
            errors.append(f"  MISSING field '{path}.{field}'")

def validate_task(filepath):
    task_errors = []
    task_warnings = []

    with open(filepath) as f:
        try:
            t = json.load(f)
        except json.JSONDecodeError as e:
            return [f"  INVALID JSON: {e}"], []

    # Top-level fields
    for field in REQUIRED_TOP_LEVEL:
        if field not in t:
            task_errors.append(f"  MISSING '{field}'")

    if "version" in t and t["version"] != "1.0":
        task_errors.append(f"  INVALID version '{t['version']}' (expected '1.0')")

    if "difficulty" in t and t["difficulty"] not in VALID_DIFFICULTIES:
        task_errors.append(f"  INVALID difficulty '{t['difficulty']}'")

    if "task_type" in t and t["task_type"] not in VALID_TASK_TYPES:
        task_errors.append(f"  INVALID task_type '{t['task_type']}'")

    if "task_id" in t:
        if not t["task_id"].replace("-", "").replace("0123456789", "").isalpha() and not all(c.isalnum() or c == "-" for c in t["task_id"]):
            task_warnings.append(f"  task_id '{t['task_id']}' should match pattern [a-z0-9-]+-[0-9]{{3}}")

    # Repo checks
    if "repo" in t:
        r = t["repo"]
        for field in REQUIRED_REPO:
            if field not in r:
                task_errors.append(f"  MISSING 'repo.{field}'")
        if "languages" in r and len(r["languages"]) == 0:
            task_errors.append("  repo.languages must not be empty")

    # Task checks
    if "task" in t:
        tk = t["task"]
        for field in REQUIRED_TASK:
            if field not in tk:
                task_errors.append(f"  MISSING 'task.{field}'")
        if "description" in tk and len(tk["description"]) < 200:
            task_warnings.append(f"  task.description is very short ({len(tk['description'])} chars) — add more context for the agent")

    # Context checks
    if "context" in t:
        c = t["context"]
        for field in REQUIRED_CONTEXT:
            if field not in c:
                task_errors.append(f"  MISSING 'context.{field}'")
        if "estimated_tokens" in c:
            if c["estimated_tokens"] < MIN_TOKENS:
                task_errors.append(f"  estimated_tokens {c['estimated_tokens']} < {MIN_TOKENS} (task too easy)")
            if c["estimated_tokens"] > MAX_TOKENS:
                task_warnings.append(f"  estimated_tokens {c['estimated_tokens']} > {MAX_TOKENS} (may be unrealistic)")
        if "required_files" in c and len(c["required_files"]) < MIN_FILES:
            task_errors.append(f"  required_files has {len(c['required_files'])} entries — need at least {MIN_FILES}")
        if "num_files_to_modify" in c and c["num_files_to_modify"] < MIN_FILES_TO_MODIFY:
            task_errors.append(f"  num_files_to_modify {c['num_files_to_modify']} < {MIN_FILES_TO_MODIFY}")

    # Ground truth checks
    if "ground_truth" in t:
        gt = t["ground_truth"]
        for field in REQUIRED_GROUND_TRUTH:
            if field not in gt:
                task_errors.append(f"  MISSING 'ground_truth.{field}'")
        if "patch_file" in gt and not gt["patch_file"].endswith(".patch"):
            task_warnings.append("  ground_truth.patch_file should end with .patch")

    # Evaluation checks
    if "evaluation" in t:
        ev = t["evaluation"]
        if "failure_categories" in ev:
            for cat in ev["failure_categories"]:
                if cat not in VALID_FAILURE_CATEGORIES:
                    task_errors.append(f"  INVALID failure_category '{cat}'")
            if len(ev["failure_categories"]) == 0:
                task_warnings.append("  failure_categories is empty — add at least one expected failure mode")

    # Metadata checks
    if "metadata" in t:
        m = t["metadata"]
        for field in REQUIRED_METADATA:
            if field not in m:
                task_errors.append(f"  MISSING 'metadata.{field}'")

    return task_errors, task_warnings


def main():
    parser = argparse.ArgumentParser(description="Validate eval dataset task files")
    parser.add_argument("--task", help="Validate a single task file", default=None)
    args = parser.parse_args()

    if args.task:
        task_files = [Path(args.task)]
    else:
        task_files = sorted(TASKS_DIR.rglob("*.json"))

    if not task_files:
        print("No task files found.")
        sys.exit(1)

    total = 0
    passed = 0
    total_tokens = 0
    cross_lang_count = 0

    print(f"\n{'='*60}")
    print(f"  Long-Context Eval Dataset — Task Validator")
    print(f"{'='*60}\n")

    for filepath in task_files:
        total += 1
        errs, warns = validate_task(filepath)
        status = "PASS" if not errs else "FAIL"
        if status == "PASS":
            passed += 1

        print(f"  [{status}] {filepath.relative_to(TASKS_DIR)}")
        for e in errs:
            print(f"        ERROR: {e}")
        for w in warns:
            print(f"        WARN:  {w}")

        # Collect stats
        try:
            with open(filepath) as f:
                t = json.load(f)
            if "context" in t and "estimated_tokens" in t["context"]:
                total_tokens += t["context"]["estimated_tokens"]
            if "context" in t and t["context"].get("cross_language"):
                cross_lang_count += 1
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} tasks passed")
    print(f"  Average tokens per task: {total_tokens // max(total, 1):,}")
    print(f"  Cross-language tasks: {cross_lang_count}/{total}")
    print(f"{'='*60}\n")

    if passed < total:
        sys.exit(1)
    else:
        print("  All tasks valid.\n")


if __name__ == "__main__":
    main()