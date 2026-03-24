#!/usr/bin/env python3
"""
repo_inventory.py — Repository indexer for the Long-Context Eval Dataset
GSoC 2026, Issue #23316

Clones all anchor repos, measures codebase size per language,
and outputs a summary JSON for the dataset README and proposal.

Usage:
    python scripts/repo_inventory.py
    python scripts/repo_inventory.py --dry-run   # print stats without cloning
"""

import json
import os
import subprocess
import sys
import argparse
from pathlib import Path
from collections import defaultdict

REPO_LIST = Path(__file__).parent.parent / "repos" / "repo_list.json"
CLONE_DIR = Path(__file__).parent.parent / ".repo_cache"

LANGUAGE_EXTENSIONS = {
    "Python": [".py"],
    "Go": [".go"],
    "JavaScript": [".js", ".jsx", ".mjs"],
    "TypeScript": [".ts", ".tsx"],
    "Vue": [".vue"],
    "C++": [".cpp", ".cc", ".cxx", ".h", ".hpp"],
    "CUDA": [".cu", ".cuh"],
    "Rust": [".rs"],
    "GraphQL": [".graphql", ".gql"],
    "JAX": [".py"],  # JAX is Python — counted separately by directory
}

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}


def count_lines(filepath):
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def analyze_repo(clone_path):
    stats = defaultdict(lambda: {"files": 0, "lines": 0})

    for root, dirs, files in os.walk(clone_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            ext = Path(fname).suffix.lower()
            fpath = Path(root) / fname
            for lang, exts in LANGUAGE_EXTENSIONS.items():
                if ext in exts:
                    stats[lang]["files"] += 1
                    stats[lang]["lines"] += count_lines(fpath)
                    break

    return dict(stats)


def clone_repo(repo_url, dest):
    if dest.exists():
        print(f"    [cached] {dest.name}")
        return True
    print(f"    [cloning] {repo_url} → {dest.name}")
    result = subprocess.run(
        ["git", "clone", "--depth=1", repo_url, str(dest)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    [ERROR] Clone failed: {result.stderr[:200]}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Skip cloning, just show repo list")
    args = parser.parse_args()

    with open(REPO_LIST) as f:
        repo_data = json.load(f)

    anchor_repos = repo_data["anchor_repos"]
    CLONE_DIR.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Long-Context Eval Dataset — Repository Inventory")
    print(f"{'='*60}\n")

    inventory = []

    for repo in anchor_repos:
        name = repo["name"]
        url = repo["url"]
        short = name.split("/")[1]
        print(f"  Processing: {name}")

        entry = {
            "name": name,
            "url": url,
            "languages": repo["languages"],
            "domain": repo["domain"],
            "stars_approx": repo["stars_approx"],
            "tasks_extracted": repo["tasks_extracted"],
        }

        if not args.dry_run:
            dest = CLONE_DIR / short
            success = clone_repo(url, dest)
            if success:
                stats = analyze_repo(dest)
                entry["language_stats"] = stats
                total_lines = sum(v["lines"] for v in stats.values())
                total_files = sum(v["files"] for v in stats.values())
                entry["total_lines"] = total_lines
                entry["total_source_files"] = total_files
                print(f"    Lines: {total_lines:,}  |  Files: {total_files:,}")
                for lang, s in sorted(stats.items(), key=lambda x: -x[1]["lines"]):
                    print(f"      {lang:15} {s['lines']:>8,} lines  {s['files']:>5} files")
        else:
            print(f"    [dry-run] Languages: {', '.join(repo['languages'])}")

        inventory.append(entry)
        print()

    output = {
        "version": "1.0",
        "generated": "2026-03-22",
        "anchor_repos": inventory,
        "summary": {
            "total_repos": len(inventory),
            "languages": sorted(set(
                lang for r in anchor_repos for lang in r["languages"]
            )),
            "domains": [r["domain"] for r in anchor_repos],
        }
    }

    out_path = Path(__file__).parent.parent / "repos" / "inventory.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Inventory written to {out_path}")
    print(f"  Total anchor repos: {len(inventory)}")
    print(f"  Languages covered: {', '.join(output['summary']['languages'])}\n")


if __name__ == "__main__":
    main()