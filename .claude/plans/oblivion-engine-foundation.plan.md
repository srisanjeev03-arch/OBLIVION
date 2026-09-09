# Plan: Oblivion Engine — Foundation (Phases 1-9)

**Source PRD**: `Oblivion_Engine_Features_and_Build_Prompts\Oblivion_Engine_Features_and_Build_Prompts.md`
**Selected Milestone**: Foundation — Repository analysis through State Machine (Phases 1-9)
**Complexity**: Large

## Summary

Build the complete Deletion & Recovery Engine foundation from scratch, implementing Phases 1-9: repository/specification analysis, project foundation, safety/path validation, target discovery, SHA-256 hashing, storage profiling, baseline, dry-run, and state-machine foundation. This phase produces a fully functional, tested read-only engine with no destructive operations.

## Context

The repository currently has a **Slice 1 scaffold** with:
- `src/oblivion/core/safety/paths.py` — Path safety (SafePathValidator)
- `src/oblivion/core/discovery/analyzer.py` — TargetAnalyzer (discovery + hashing)
- `src/oblivion/api/__init__.py` — FastAPI app with `/api/targets/analyze` endpoint
- `tests/test_safety.py`, `tests/test_discovery.py`, `tests/test_api_analyze.py` — Test files
- `tests/fixtures.py` — Test fixtures

The tests are **structurally defined but were NOT executed** (pytest was missing, runtime verification BLOCKED per SLICE1_RUNTIME_STATUS.md). The `src/oblivion/api/__init__.py` is actually a single-file FastAPI app (not a proper package with multiple modules), and `src/oblivion/core/discovery/__init__.py` contains both the actual code and Protocol stubs (not just imports).

The `Oblivion_Engine_Features_and_Build_Prompts.md` document defines the complete engineering task — this plan is the first execution pass implementing Phases 1-9.

## What Already Exists

| Component | Status | Location |
|---|---|---|
| Path safety (SafePathValidator) | Scaffold, needs improvement | `src/oblivion/core/safety/paths.py` |
| Target discovery (TargetAnalyzer) | Scaffold, basic | `src/oblivion/core/discovery/analyzer.py` |
| SHA-256 hashing | Basic streaming in TargetAnalyzer | `src/oblivion/core/discovery/analyzer.py` |
| Storage profiling | Minimal stub | `src/oblivion/core/discovery/__init__.py` |
| API endpoint | Basic FastAPI app | `src/oblivion/api/__init__.py` |
| Test files | Defined, not executed | `tests/` |
| Project config | No pyproject.toml/setup.py/requirements.txt | Root |
| Documentation | Comprehensive | `docs/`, `reference/` |

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `src/oblivion/core/safety/paths.py` | `path.py`, `analyzer.py`, `__init__.py` |
| Error handling | `src/oblivion/core/safety/paths.py` | `PathSafetyError(Exception)` custom errors |
| Tests | `tests/test_safety.py` | Class-based pytest, tempfile fixtures |
| API | `src/oblivion/api/__init__.py` | FastAPI, Pydantic models, JSON responses |
| Protocol/interface | `src/oblivion/core/discovery/__init__.py` | `Protocol` classes for interfaces |
| Config | `.env.example` | Environment variable based config |

## Files to Create/Modify

### Project Foundation (Phase 2)
| File | Action | Why |
|---|---|---|
| `pyproject.toml` | CREATE | Project configuration, dependencies, pytest setup |
| `requirements.txt` | CREATE | Pin dependencies for reproducibility |
| `src/oblivion/core/state/__init__.py` | CREATE | State machine module |
| `src/oblivion/core/state/machine.py` | CREATE | Deterministic state transition engine |
| `src/oblivion/core/erasure/__init__.py` | CREATE | Erasure module namespace |
| `src/oblivion/core/recovery/__init__.py` | CREATE | Recovery module namespace |
| `src/oblivion/core/residual/__init__.py` | CREATE | Residual analysis module namespace |
| `src/oblivion/core/assurance/__init__.py` | CREATE | Assurance module namespace |
| `src/oblivion/core/baseline/__init__.py` | CREATE | Baseline module namespace |
| `src/oblivion/core/dryrun/__init__.py` | CREATE | Dry-run module namespace |
| `src/oblivion/privileged/__init__.py` | CREATE | Privileged service namespace |
| `src/oblivion/ai/__init__.py` | CREATE | AI advisory namespace |
| `src/oblivion/certificate/__init__.py` | CREATE | Certificate module namespace |

### Safety Layer (Phase 3) — Refactor/Enhance
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/safety/paths.py` | MODIFY | Add system-drive protection via volume identity, reparse detection for junctions, TOCTOU revalidation |
| `src/oblivion/core/safety/__init__.py` | MODIFY | Add full module exports |

### Target Discovery (Phase 4) — Refactor/Enhance
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/discovery/analyzer.py` | MODIFY | Add target fingerprint, metadata collection, directory tree walk |
| `src/oblivion/core/discovery/__init__.py` | MODIFY | Properize StorageProfiler, add TargetFingerprint |

### Hashing (Phase 5) — Refactor/Enhance
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/discovery/analyzer.py` | MODIFY | Extract SHA-256 into dedicated Hasher class with streaming |
| Add `src/oblivion/core/hashing/__init__.py` | CREATE | Dedicated hashing module |

### Storage Profiling (Phase 6) — Refactor/Enhance
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/discovery/__init__.py` | MODIFY | Expand StorageProfiler with volume identity, filesystem details |
| Add `src/oblivion/core/storage/__init__.py` | CREATE | Storage profiling module |

### Baseline (Phase 7) — Create
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/baseline/__init__.py` | CREATE | Baseline module namespace |
| `src/oblivion/core/baseline/manager.py` | CREATE | Pre-erasure baseline creation |

### Dry-Run (Phase 8) — Create
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/dryrun/__init__.py` | CREATE | Dry-run module namespace |
| `src/oblivion/core/dryrun/planner.py` | CREATE | Dry-run planning, no-mutation verification |

### State Machine (Phase 9) — Create
| File | Action | Why |
|---|---|---|
| `src/oblivion/core/state/__init__.py` | CREATE | State machine exports |
| `src/oblivion/core/state/machine.py` | CREATE | Deterministic state transitions |

### Tests — Rewrite/Expand
| File | Action | Why |
|---|---|---|
| `tests/test_safety.py` | REWRITE | Comprehensive safety tests with actual execution |
| `tests/test_discovery.py` | REWRITE | Discovery + hashing tests |
| `tests/test_dryrun.py` | CREATE | Dry-run tests |
| `tests/test_state.py` | CREATE | State machine tests |
| `tests/test_baseline.py` | CREATE | Baseline tests |
| `tests/conftest.py` | CREATE | Shared fixtures |

### Documentation
| File | Action | Why |
|---|---|---|
| `ENGINE_ARCHITECTURE.md` | CREATE | Engine architecture documentation |
| `ENGINE_IMPLEMENTATION_STATUS.md` | CREATE | Implementation status tracking |
| `ENGINE_LIMITATIONS.md` | CREATE | Limitations documentation |
| `ENGINE_FOUNDATION_REPORT.md` | CREATE | Final report (after execution) |

## Tasks

### Task 1: Project Foundation (Phase 2)
- **Action**: Create `pyproject.toml`, `requirements.txt`, all module `__init__.py` files
- **Mirror**: `.env.example` env vars, existing module naming
- **Validate**: `pip install -e .` succeeds, `python -c "import oblivion"` works

### Task 2: Safety/Path Validation Foundation (Phase 3)
- **Action**: Enhance `SafePathValidator` with volume-based system-drive protection, junction/reparse detection, TOCTOU-aware revalidation, `OBLIVION_ALLOWED_ROOTS` env var support
- **Mirror**: `docs/SECURITY.md`, ADR-008, ADR-009
- **Validate**: All safety tests pass with actual pytest execution

### Task 3: Target Discovery Foundation (Phase 4)
- **Action**: Enhance `TargetAnalyzer` with deterministic `target_id`, full metadata collection, recursive directory enumeration, file-type distribution
- **Mirror**: `Oblivion_Engine_Features_and_Build_Prompts.md` Section 7, `docs/DATA_MODEL.md` Target model
- **Validate**: Discovery tests pass for files, directories, recursive, missing, empty

### Task 4: SHA-256 Hashing (Phase 5)
- **Action**: Create dedicated `Hasher` class with streaming SHA-256, chunked reads, deterministic output, known-value verification
- **Mirror**: `docs/Oblivion_Engine_Features_and_Build_Prompts.md` Rule 8
- **Validate**: Known SHA-256 test passes, empty file hash matches `e3b0c442...`

### Task 5: Storage Profiling (Phase 6)
- **Action**: Expand `StorageProfiler` with volume identity, filesystem, capacity, encryption state, reparse characteristics
- **Mirror**: `docs/Oblivion_Engine_Features_and_Build_Prompts.md` Rule 9, `docs/WINDOWS_NTFS_NOTES.md`
- **Validate**: Storage profile tests produce complete dicts with UNKNOWN/UNAVAILABLE for undetectable fields

### Task 6: Baseline (Phase 7)
- **Action**: Create `BaselineManager` that captures pre-erasure state: target_id, path, scope, file inventory, hashes, metadata, storage profile, timestamp, limitations
- **Mirror**: `docs/Oblivion_Engine_Features_and_Build_Prompts.md` Rule 10, `docs/DATA_MODEL.md`
- **Validate**: Baseline tests create and serialize complete baselines

### Task 7: Dry-Run (Phase 8)
- **Action**: Create `DryRunPlanner` that shows intended operation with zero filesystem changes, verifies state is identical before/after
- **Mirror**: `docs/Oblivion_Engine_Features_and_Build_Prompts.md` Rule 11, `SLICE1_RUNTIME_STATUS.md`
- **Validate**: Dry-run tests prove no filesystem mutation

### Task 8: State Machine (Phase 9)
- **Action**: Create `OperationStateMachine` with deterministic transitions from the documented state machine, rejects invalid transitions
- **Mirror**: `reference/OPERATION_STATES.md`, `docs/ARCHITECTURE.md`
- **Validate**: State machine tests verify valid transitions succeed, invalid ones raise errors

### Task 9: Tests — Full Execution
- **Action**: Rewrite all tests for actual execution, run `pytest`, type checking, verify all pass
- **Mirror**: `docs/TEST_PLAN.md`, `IMPLEMENTATION_PROGRESS.md` test matrix
- **Validate**: `pytest tests/ -v` passes all tests

### Task 10: Documentation
- **Action**: Create ENGINE_ARCHITECTURE.md, ENGINE_IMPLEMENTATION_STATUS.md, ENGINE_LIMITATIONS.md
- **Mirror**: `docs/FEATURES.md` section on documentation requirements
- **Validate**: Documents accurately reflect implemented state

## Validation Commands

```bash
# Install project
cd D:\OBLIVION && pip install -e .

# Run all tests
cd D:\OBLIVION && pytest tests/ -v

# Type check
cd D:\OBLIVION && python -c "import oblivion; print('Import OK')"

# Verify no destructive operations
cd D:\OBLIVION && grep -r "os.remove\|os.unlink\|shutil.rmtree\|subprocess\|execute\|shell" src/oblivion/core/ --include="*.py"

# Verify no pytest.skip
cd D:\OBLIVION && grep -r "pytest.skip" tests/ --include="*.py"
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| pytest not installed | High | Include in requirements.txt, install via pip |
| Windows-specific path issues | Medium | Use `os.path` and `pathlib` cross-platform, test on available platform |
| Volume identity API not available | Medium | Fallback to UNKNOWN/UNAVAILABLE, never pretend |
| Import errors from package structure | Medium | Careful `__init__.py` design, test imports early |
| Existing code conflicts with new structure | Medium | Preserve existing APIs, add alongside not replace |
| `src/oblivion/api/__init__.py` is a single-file app not a package | Medium | Keep as-is, add proper modules alongside |

## Acceptance

- [ ] All 10 tasks complete
- [ ] `pip install -e .` succeeds
- [ ] `pytest tests/ -v` passes all tests (actual execution, not skipped)
- [ ] Type checking passes
- [ ] No safety mechanism disabled to make tests pass
- [ ] No destructive operations introduced
- [ ] All documentation files created
- [ ] ENGINE_FOUNDATION_REPORT.md produced

**WAITING FOR CONFIRMATION**: Proceed with this plan? (yes/no/modify)
