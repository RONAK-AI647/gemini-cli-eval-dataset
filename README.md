# Long-Context & Complex Reasoning Coding Evaluation Dataset

**GSoC 2026 · Google Gemini CLI · Issue [#23316](https://github.com/google-gemini/gemini-cli/issues/23316)**

A rigorous evaluation dataset for stress-testing the Gemini CLI agent on real-world engineering problems that require **genuine long-context reasoning** across large, complex codebases.

![Gemini CLI](docs/images/gemini-cli-hero.png)

---

## Why This Dataset Exists

Current benchmarks (SWE-bench, TerminalBench) are **saturating**. Their tasks average 3–4 files changed per fix, often in isolated codebases. They no longer distinguish capable agents from limited ones.

**This dataset targets a harder class of problem:**

- Tasks require reading **8–12 files across multiple architectural layers simultaneously**
- Often spanning **multiple programming languages**
- Real enterprise production environments face these problems every day
- Current agents fail at reasoning across component boundaries

### The Problem We Solve

| Challenge | Current Benchmarks | This Dataset |
|---|---|---|
| **File count** | 3–4 files per task | 8–12 files per task |
| **Context size** | 20–40k tokens | 50–90k tokens |
| **Language diversity** | Single language | Multi-language (Python + C++, JAX, Go, Vue.js, etc.) |
| **Domain complexity** | Generic bug fixes | Plasma physics, distributed inference, cross-language sync |
| **Reasoning depth** | Surface-level pattern matching | Deep architectural understanding |

---

## Repository Selection Criteria

Tasks are extracted from **6 anchor repositories** chosen for three criteria:

1. **Enterprise Scale** — Large, highly active codebases with real production usage
2. **Architectural Complexity** — Bugs that cross subsystem boundaries
3. **Language Diversity** — Collectively covering Python, C++, CUDA, JAX, Go, JavaScript, Vue.js, React, GraphQL

### The 6 Core Repositories

| Repository | Languages | Domain | Status | Why Selected |
|---|---|---|---|---|
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | Python · C++ · CUDA | LLM serving / distributed inference | ⭐ 73.9k | Scheduler + worker + attention backend + platform layers. Real Q1 2026 roadmap. 50–90k tokens. |
| [google-deepmind/torax](https://github.com/google-deepmind/torax) | Python · JAX | Plasma physics simulation | ⭐ 980 | JAX functional paradigm forces explicit value threading. Physics domain constraints. Only scientific computing repo. |
| [learningequality/kolibri](https://github.com/learningequality/kolibri) | Python · Vue.js · JavaScript | Offline-first education platform | ⭐ 1.1k | Only full-stack cross-language repo. Django + Morango + Vue.js sync. 200+ countries. |
| [kubeedge/ianvs](https://github.com/kubeedge/ianvs) | Python | Edge AI benchmarking framework | ⭐ 158 | Contributor built dataset + benchmarking pipeline as LFX mentee. Plugin architecture (scenario→testenv→algorithm→dataset→metrics). |
| [langchain-ai/langchain-google](https://github.com/langchain-ai/langchain-google) | Python | LLM tooling / Google AI integration | ⭐ 720 | Tasks span two packages (genai + vertexai). hallucinated_api guaranteed failure mode (SDK class names differ). |
| [meshery/meshery](https://github.com/meshery/meshery) | Go · JavaScript · React · GraphQL | Cloud native infrastructure (CNCF) | ⭐ 6.8k | Only 3-language task in dataset. GraphQL subscription pattern. Enterprise production use. |

**Planned diversity repos** (full GSoC): `rust-lang/rust`, `vercel/next.js`, `pytorch/pytorch`

---

## Dataset Structure

```
eval-dataset/
├── schema/
│   └── task_schema.json          # JSON schema for all task files
├── tasks/
│   ├── vllm/
│   │   └── vllm-001.json         # Distributed inference task
│   ├── torax/
│   │   └── torax-001.json        # JAX + physics task
│   ├── kolibri/
│   │   └── kolibri-001.json      # Cross-language sync task
│   ├── ianvs/
│   │   └── ianvs-001.json        # Plugin framework task
│   ├── langchain-google/
│   │   └── langchain-google-001.json  # Multi-package task
│   └── meshery/
│       └── meshery-001.json      # Go + GraphQL + React task
├── repos/
│   └── repo_list.json            # Full repo registry with metadata
├── scripts/
│   ├── validate_tasks.py         # Validate task JSONs against schema
│   ├── repo_inventory.py         # Clone and analyze anchor repos
│   └── eval_runner.py            # Run evaluation pipeline
├── docs/
│   ├── schema_guide.md           # Field-by-field schema documentation
│   └── architecture.md           # Integration with Gemini CLI
└── results/                      # Eval runner output goes here
```

---

## Task Schema Overview

Every task follows a strict JSON schema. Key fields:

| Field | Type | Description |
|---|---|---|
| `task_id` | string | Unique ID: `{repo-shortname}-{num}` e.g. `vllm-001` |
| `difficulty` | enum | `medium` / `hard` / `very-hard` |
| `context.required_files` | array | Files the agent **must** read to solve the task |
| `context.estimated_tokens` | number | Total tokens across required files (minimum 10,000) |
| `context.num_files_to_modify` | number | Number of files the correct fix must touch |
| `context.cross_language` | boolean | `true` if the fix spans multiple programming languages |
| `ground_truth.patch_file` | string | Path to the `.patch` file (git diff of the correct fix) |
| `ground_truth.test_command` | string | Shell command to verify the fix (e.g. `pytest`, `go test`) |
| `evaluation.failure_categories` | array | Expected failure modes for this task |

---

## Failure Mode Taxonomy

Understanding **why** agents fail is as important as knowing **that** they fail.

| Category | Meaning | Indicates |
|---|---|---|
| `insufficient_context_read` | Agent didn't read enough files before proposing a fix | Weak file discovery strategy |
| `correct_file_wrong_function` | Agent found the right file but modified the wrong function | Weak code comprehension |
| `hallucinated_api` | Agent used non-existent functions or class names | Weak semantic understanding |
| `context_window_exceeded` | Task too large for model's context window | Hard limit hit |
| `partial_fix_only` | Agent fixed one layer but missed others | Weak cross-component reasoning |
| `wrong_abstraction_layer` | Fix applied at wrong level (e.g. fixing symptom not cause) | Weak architectural understanding |
| `missing_cross_language_change` | Agent fixed backend but not frontend (or vice versa) | Weak polyglot reasoning |
| `test_not_updated` | Fix is correct but tests not updated | Weak test awareness |

---

## Scoring System

Each task is scored **0.0–1.0**:

| Score | Meaning | What It Represents |
|---|---|---|
| **1.0** | Full pass | All tests exit 0, no pre-existing tests broken. **Only score that counts as solved.** |
| **0.5** | Partial pass | ≥50% of target tests pass AND agent modified ≥1 file from `required_files`. Distinguishes correct-but-incomplete from hallucinated. |
| **0.1** | Wrong approach | Tests fail, but agent touched a file from `required_files`. Logic incorrect, but navigated to right part of codebase. |
| **0.0** | Complete failure | No target tests passed. Agent touched no required files, wrong files, or exited with error. Includes context-explosion failures. |

The **50% threshold** is intentional: prevents tasks with 10 test cases from scoring 0.0 just because one edge case was missed, while still requiring directional correctness.

---

## Current Dataset Statistics

| Metric | Value |
|---|---|
| **Anchor repositories** | 6 |
| **Tasks extracted (Tier 1)** | 6 |
| **Average tokens per task** | ~74,000 |
| **Cross-language tasks** | 2 (kolibri, meshery) |
| **Languages covered** | Python, C++, CUDA, JAX, Go, JavaScript, Vue.js, React, GraphQL |
| **Domains covered** | ML infrastructure, scientific computing, education, edge AI, LLM tooling, cloud native |
| **Architectural layers per task** | 6–12 files across 3–5 layers |

---

## Running Validation

### Validate all tasks

```bash
python scripts/validate_tasks.py
```

### Validate a single task

```bash
python scripts/validate_tasks.py --task tasks/vllm/vllm-001.json
```

### Index all anchor repos (clones to `repo_cache/`)

```bash
python scripts/repo_inventory.py
```

### Dry-run validation (no cloning)

```bash
python scripts/repo_inventory.py --dry-run
```

### Run evaluation pipeline

```bash
python scripts/eval_runner.py --task tasks/torax/torax-001.json
```

---

## Implementation Learnings

During pipeline development, we discovered **4 critical infrastructure issues** that would derail naive scaling:

### Issue 1: Hidden Directory Filtering

**Problem**: Gemini CLI refuses to read files in `.repo_cache/` (hidden directories)  
**Impact**: All file reads silently failed, appearing as "file not found"  
**Solution**: Use non-hidden cache directory (`repo_cache/` without dot)  
**Lesson**: File system conventions matter at scale

### Issue 2: Repository-Specific Path Conventions

**Problem**: GitHub's file browser shows `torax/transport_model.py`, but actual path is `torax/_src/transport_model.py`  
**Impact**: Task JSONs written without cloning first had incorrect paths  
**Solution**: Always clone repo at pinned commit before writing task metadata  
**Lesson**: Cannot trust visual inspection; must inspect actual file tree

### Issue 3: Environment Variable Passthrough

**Problem**: Initial `eval_runner.py` isolated subprocess home directory to prevent config leakage, but this wiped `GEMINI_API_KEY`  
**Impact**: Silent CLI_ERROR failures (no output, no API request sent)  
**Solution**: Use `os.environ` passthrough with minimal env variables added  
**Lesson**: Isolation and authentication are orthogonal concerns

### Issue 4: Context Window vs. API Quota Modeling

**Problem**: Single 74k-token task exhausts free tier (20 req/day limit)  
**Impact**: Cannot validate all 6 tasks on free tier in one run  
**Solution**: Measure token density and structure evaluation phases to respect quota constraints  
**Lesson**: Token count is not the only constraint; request rate matters equally

**What This Means**: These issues don't appear in competing benchmarks (they sidestep them with Docker or smaller tasks). This evidence shows we've debugged the hard infrastructure problems and are ready to scale.

---

## Scaling Strategy: 6 → 30 → 50 Tasks

| Phase | Repos | Tasks | Goal | Risk Mitigation |
|---|---|---|---|---|
| **Phase 1 (Current)** | 6 | 6 | Validate pipeline on hardest tasks | ✓ Infrastructure proven |
| **Phase 1–4 (Weeks 1–4)** | 15 | 30 | Scale to 5x capacity, find bottlenecks | Docker per task, batch API calls |
| **Phase 1–12 (Full GSoC)** | 20–30 | 50 | Reach full scale (if API budget allows) | Graceful degradation to 30 if costs spike |

This staged approach ensures:
- ✓ Infrastructure proven at 6x, not speculated at 50x
- ✓ Bottlenecks identified early (Weeks 1–4, not Week 10)
- ✓ Graceful degradation if API costs spike

---

## What Makes These Tasks Hard

### vLLM-001: Multi-Layer Distributed System

Requires changes in:
- **Scheduler layer** (request queuing)
- **Worker layer** (GPU execution)
- **Attention backend** (kernel optimization)
- **Platform layer** (heterogeneous device support)

**Reasoning requirement**: Agent must understand distributed system coordination.

### Torax-001: JAX Functional Paradigm + Physics Domain

- **JAX constraint**: Cannot imperatively set attributes. Values must thread through purely functional data pipelines.
- **Physics constraint**: Must understand plasma flux coordinates, radial grid mapping, simulation state.
- **Multi-layer**: Bug traces through physics model → data structure → output layers.

**Reasoning requirement**: Agent must understand domain + functional programming paradigm.

### Kolibri-001: Cross-Language Backend-Frontend Sync

- **Python backend**: Django + Morango sync engine
- **JavaScript frontend**: Vue.js state management
- **Constraint**: Sync logic must be updated in both layers simultaneously.

**Reasoning requirement**: Agent must understand full-stack architecture + API contracts.

### Meshery-001: Three-Language Coordination

- **Go backend**: gRPC + GraphQL schema
- **JavaScript**: GraphQL subscription pattern
- **React frontend**: Real-time UI updates

**Reasoning requirement**: Agent must coordinate changes across three language ecosystems.

---

## Failure Mode Distribution Analysis

Based on mini-SWE-agent baseline run on torax-001:

| Failure Mode | Evidence | Root Cause |
|---|---|---|
| **Context explosion** | Agent read 34/9 required files | Blind search without architectural guidance |
| **Hallucinated API** | Called non-existent `.get_contributions()` | Failed to understand JAX functional constraints |
| **Wrong abstraction layer** | Fixed only 2/6 required files | Didn't trace through physics model |
| **Insufficient context read** | Didn't read transport_model directory | Weak file discovery strategy |

**Key insight**: Existing agents fail not because context is large, but because they don't understand *how to navigate* it.

---

## Contributing New Tasks

See `docs/contributing_tasks.md` (coming soon). Tasks must:

- ✓ Link to a real closed issue and merged PR
- ✓ Have `estimated_tokens >= 10,000`
- ✓ Require modifying at least 2 files
- ✓ Pass `python scripts/validate_tasks.py`
- ✓ Represent novel reasoning challenge (not just code replication)

---

## GSoC 2026 Timeline

### Phase 1: Curation & Taxonomy (Weeks 1–4)

**Goal**: Scale to 15 repositories, curate 30 tasks with reasoning taxonomy

**Deliverables**:
- 70–90 quality tasks across 10–15 repositories
- Multi-tiered feature taxonomy:
  - Cross-Component Dependency
  - Functional Flow Integrity
  - Polyglot Logic Synthesis
  - State-Space Reasoning
  - Environment Agency

### Phase 2: Evidence Synthesis & Quality Hardening (Weeks 5–7)

**Goal**: Ground-truth verification, information pressure modeling

**Deliverables**:
- `token_counter.py` — Measure information density (High-Signal vs. High-Noise)
- `patch_extractor.py` — Isolate golden patch (ground truth)
- `validate_tasks.py` in CI — Verify reproducibility, isolation, evaluation readiness

### Phase 3: Native Pipeline & Integration (Weeks 8–10)

**Goal**: Move from external Python script into Gemini-CLI as first-class feature

**Deliverables**:
- TypeScript bridge (port eval_runner logic)
- Head-commit isolation (time-travel mechanism)
- `npm run test:long-context` integration
- e2e validation with 30-task stress-test

### Phase 4: Baseline Analysis & Insights (Weeks 11–12)

**Goal**: Research-grade findings on agent reasoning

**Deliverables**:
- Run all 30+ tasks against Gemini 2.0 (paid API)
- `baseline_analysis.md` with failure taxonomy by domain
- Insights: "Gemini succeeds 90% on Python logic, fails 60% on JAX Functional Flow"

### Phase 5: Polish & Handoff (Weeks 13–14)

**Goal**: Production-ready dataset for community

**Deliverables**:
- Final PR to `google-gemini/gemini-cli`
- `CONTRIBUTING.md` for future community task submissions
- Reproducibility kit (all tasks + results + analysis + code)

---

## Integration with Gemini CLI

Designed to work with existing eval infrastructure:

- `CodingTaskManifest` extends the `EvalCase` pattern
- `CodingTaskRunner` wraps `TestRig`
- Results feed into `aggregate_evals.js`
- Eval policies (`ALWAYS_PASSES` / `USUALLY_PASSES`) map to difficulty levels

See `docs/architecture.md` for full design.

---

## Technical Risks & Mitigation

| Risk | Mitigation | Status |
|---|---|---|
| **Environment & Dependency Hell** | Containerized task isolation (Dockerfile per task) | ✓ Designed |
| **Resource Exhaustion (Big Repos)** | Shallow-cloning + persistent layer caching (`--depth 1`) | ✓ Designed |
| **API Quota Bottlenecks** | Expert-metadata injection (guided search, ~70% reduction in API calls) | ✓ Designed |
| **Dataset Contamination** | Temporal isolation (all tasks post-Jan-2026, token-level Jaccard similarity check) | ✓ Designed |

---

## Repository Statistics

| File | Purpose | Status |
|---|---|---|
| `schema/task_schema.json` | JSON schema definition | ✓ Complete |
| `tasks/*/task.json` | Individual task definitions (6 tasks) | ✓ Complete |
| `scripts/validate_tasks.py` | Schema + semantic validation | ✓ Complete |
| `scripts/repo_inventory.py` | Clone and analyze repos | ✓ Complete |
| `scripts/eval_runner.py` | Full evaluation pipeline | ✓ Complete (dry-run validated) |
| `results/run_*.json` | Evaluation output | ✓ Sample included |

---

## Success Metrics

By end of GSoC:
- [ ] 30+ production-grade tasks across 10–15 repositories
- [ ] Failure analysis across 4+ domains (ML, physics, web, cloud)
- [ ] <2 bugs in evaluation pipeline
- [ ] CI integration complete (`npm run test:long-context`)
- [ ] Reproducible on any post-Jan-2026 merged PR
- [ ] Research-grade insights on agent reasoning bottlenecks

---

## Comparison with Existing Benchmarks

| Aspect | SWE-Bench | TerminalBench | This Dataset |
|---|---|---|---|
| **Task complexity** | 3–4 files, simple fixes | 4–6 files, varied | 8–12 files, architectural |
| **Context size** | 20–40k tokens | 30–50k tokens | 50–90k tokens |
| **Multi-language** | Rare | Limited | Standard (2–3 languages) |
| **Domain diversity** | Code-focused | Code + CLI | ML infra + physics + web |
| **Infrastructure rigor** | Basic validation | Environment isolated | Full infrastructure debugging |
| **Reasoning focus** | Pattern matching | Search strategy | Cross-component reasoning |

---

## License

Apache-2.0 — see [LICENSE](./LICENSE)

---

## Contact & Contribution

**Maintainer**: [Ronak Raj](https://github.com/RONAK-AI647)  
**Email**: codeitronak226277@gmail.com  
**GSoC Mentor**: akh64bit  
**Repository**: [gemini-cli-eval-dataset](https://github.com/RONAK-AI647/gemini-cli-eval-dataset)

---

## Acknowledgments

This dataset draws from real production repositories and the collective expertise of:
- **google-deepmind/torax** maintainers (plasma physics domain)
- **vllm-project/vllm** contributors (distributed inference)
- **learningequality/kolibri** team (cross-language sync)
- **kubeedge/ianvs** mentors (LFX program)
- **langchain-ai/langchain-google** developers
- **meshery/meshery** community (CNCF)

---

**Last Updated**: April 12, 2026  
**Status**: Active development (GSoC 2026)