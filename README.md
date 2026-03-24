# gemini-cli-eval-dataset
Long-Context &amp; Complex Reasoning Coding Evaluation Dataset

# Long-Context & Complex Reasoning Coding Evaluation Dataset

**GSoC 2026 · Google Gemini CLI · Issue [#23316](https://github.com/google-gemini/gemini-cli/issues/23316)**

A novel evaluation dataset for stress-testing the Gemini CLI agent on real-world engineering problems that require **genuine long-context reasoning** across large, complex codebases.

---

## Why this dataset exists

Current benchmarks (SWE-bench, TerminalBench) are saturating. Their tasks average 3–4 files changed per fix, often in isolated codebases. They no longer distinguish capable agents from limited ones.

This dataset targets a harder class of problem: tasks where the correct fix requires reading **8–12 files across multiple architectural layers simultaneously**, often spanning multiple programming languages. These are the problems that appear in real enterprise production environments every day.

---

## Repository selection

Tasks are extracted from **6 anchor repositories** chosen for three criteria:

1. **Enterprise scale** — large, highly active codebases with real production usage
2. **Architectural complexity** — bugs that cross subsystem boundaries
3. **Language diversity** — collectively covering Python, C++, CUDA, JAX, Go, JavaScript, Vue.js, React, GraphQL

| Repository | Languages | Domain | Contributor |
|---|---|---|---|
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | Python · C++ · CUDA | LLM serving / distributed inference | Ronak |
| [google-deepmind/torax](https://github.com/google-deepmind/torax) | Python · JAX | Plasma physics simulation | Ronak |
| [learningequality/kolibri](https://github.com/learningequality/kolibri) | Python · Vue.js · JS | Offline-first education platform | Ronak |
| [kubeedge/ianvs](https://github.com/kubeedge/ianvs) | Python | Edge AI benchmarking | Ronak (LFX mentee) |
| [langchain-ai/langchain-google](https://github.com/langchain-ai/langchain-google) | Python | LLM tooling / Google AI integration | Ronak |
| [meshery/meshery](https://github.com/meshery/meshery) | Go · JS · React · GraphQL | Cloud native infrastructure (CNCF) | Ronak |

**Diversity repos** (tasks planned for full GSoC project): `rust-lang/rust`, `vercel/next.js`, `pytorch/pytorch`

---

## Dataset structure

```
eval-dataset/
├── schema/
│   └── task_schema.json          # JSON schema for all task files
├── tasks/
│   ├── vllm/
│   │   └── vllm-001.json
│   ├── torax/
│   │   └── torax-001.json
│   ├── kolibri/
│   │   └── kolibri-001.json
│   ├── ianvs/
│   │   └── ianvs-001.json
│   ├── langchain-google/
│   │   └── langchain-google-001.json
│   └── meshery/
│       └── meshery-001.json
├── repos/
│   └── repo_list.json            # Full repo registry with metadata
├── scripts/
│   ├── validate_tasks.py         # Validate all task JSONs against schema
│   └── repo_inventory.py         # Clone and analyze all anchor repos
├── docs/
│   └── schema_guide.md           # Field-by-field schema documentation
└── results/                      # Eval runner output goes here
```

---

## Task schema overview

Every task follows a strict JSON schema (see `schema/task_schema.json`). Key fields:

| Field | Description |
|---|---|
| `task_id` | Unique ID: `{repo-shortname}-{num}` e.g. `vllm-001` |
| `difficulty` | `medium` / `hard` / `very-hard` |
| `context.required_files` | Files the agent **must** read to solve the task |
| `context.estimated_tokens` | Total tokens across required files (minimum 10,000) |
| `context.num_files_to_modify` | Number of files the correct fix must touch |
| `context.cross_language` | `true` if the fix spans multiple programming languages |
| `ground_truth.patch_file` | Path to the `.patch` file (git diff of the correct fix) |
| `ground_truth.test_command` | Shell command to verify the fix |
| `evaluation.failure_categories` | Expected failure modes for this task |

---

## Failure mode taxonomy

| Category | Meaning |
|---|---|
| `insufficient_context_read` | Agent didn't read enough files before proposing a fix |
| `correct_file_wrong_function` | Agent found the right file but modified the wrong function |
| `hallucinated_api` | Agent used non-existent functions or class names |
| `context_window_exceeded` | Task too large for model's context window |
| `partial_fix_only` | Agent fixed one layer but missed others (most common) |
| `wrong_abstraction_layer` | Fix applied at wrong level (e.g. fixing symptom not cause) |
| `missing_cross_language_change` | Agent fixed backend but not frontend (or vice versa) |
| `test_not_updated` | Fix is correct but tests not updated |

---

## Scoring

Each task is scored 0.0–1.0:

| Score | Meaning |
|---|---|
| `1.0` | All tests pass, correct files modified |
| `0.5` | Partial fix — some tests pass |
| `0.1` | Wrong files modified |
| `0.0` | Tests fail or no output produced |

---

## Running validation

```bash
# Validate all tasks
python scripts/validate_tasks.py

# Validate a single task
python scripts/validate_tasks.py --task tasks/vllm/vllm-001.json

# Index all anchor repos (clones to .repo_cache/)
python scripts/repo_inventory.py

# Dry run (no cloning)
python scripts/repo_inventory.py --dry-run
```

---

## Current dataset statistics

- **Anchor repos:** 6
- **Tasks extracted:** 6
- **Average estimated tokens per task:** ~74,000
- **Cross-language tasks:** 2 (kolibri, meshery)
- **Languages covered:** Python, C++, CUDA, JAX, Vue.js, JavaScript, Go, React, GraphQL
- **Domains covered:** ML infrastructure, scientific computing, education, edge AI, LLM tooling, cloud native

---

## Contributing new tasks

See `docs/contributing_tasks.md` (coming soon). Tasks must:

1. Link to a real closed issue and merged PR
2. Have `estimated_tokens >= 10,000`
3. Require modifying at least 2 files
4. Pass `python scripts/validate_tasks.py`

---

## License

Apache-2.0 — see [LICENSE](../../LICENSE)