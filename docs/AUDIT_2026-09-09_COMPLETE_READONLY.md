# OBLIVION — Complete Read-Only Audit Report

**Auditor:** Claude Code  
**Date:** 2026-09-09  
**Repository:** `D:\OBLIVION`  
**Scope:** Complete repository audit — all source files, configuration, tests, documentation, security, architecture, and API contract  
**Mode:** Read-only (no modifications made)

---

## Executive Summary

The Oblivion repository has evolved dramatically since the previous audit on 2026-09-03 (which reported "zero code"). As of this audit, the backend is **substantially implemented**: 55+ Python source files, 35+ test files, a complete FastAPI application, full persistence layer, core engines, security subsystem, and certificate infrastructure. However, several **critical architectural and security issues** remain that must be addressed before production readiness.

**Overall Readiness Score: 6.5/10** — Implementation is extensive but has critical gaps in completeness, security posture, test coverage, and platform compatibility.

---

## 1. Repository Structure Overview

```
D:\OBLIVION\
├── src/oblivion/
│   ├── api/                    # FastAPI application, routes, schemas, dependencies
│   │   ├── app.py              # Application factory with CORS, error handlers
│   │   ├── dependencies.py     # DB, vault, signer, validator, event emitter
│   │   ├── routes/             # 6 route modules (auth, targets, operations, recovery, certificates, evidence)
│   │   └── schemas/            # 8 schema modules (auth, operation, target, certificate, evidence, recovery, error)
│   ├── core/
│   │   ├── erasure/            # ErasureEngine, RecoveryVault, EngineEventEmitter
│   │   ├── safety/             # SafePathValidator (Windows CTYPES-heavy)
│   │   ├── policy/             # PolicyEngine with allowlisted policies
│   │   ├── auth/               # Passwords (Argon2id), RBAC (5 roles), SoD
│   │   ├── assurance/          # AssuranceEngine + DefaultAssuranceRule
│   │   ├── recovery/           # ForensicRecoveryEngine, NTFSRecoveryAdapter, RecoveryExporter
│   │   ├── residual/           # ResidualAnalyzer, FileSystemResidualDetector, EvidenceComparator
│   │   ├── discovery/          # TargetAnalyzer, StorageProfiler
│   │   ├── baseline/           # BaselineManager
│   │   ├── dryrun/             # DryRunPlanner (TODO stubs)
│   │   ├── evidence/           # EvidenceEngine, canonicalize, canonical, audit
│   │   ├── state/              # OperationStateMachine (16 states)
│   │   ├── hashing/            # Hasher (SHA-256 streaming)
│   │   └── ai/                 # EMPTY STUB (__init__.py only)
│   ├── certificate/            # Ed25519SignerVerifier, verify_certificate, hash_integrity
│   ├── persistence/            # SQLAlchemy 2.x database, models, repositories
│   │   ├── database.py         # Engine, session factory, init_db
│   │   ├── models/             # 6 model files (user, operation, evidence, certificate, audit, __init__)
│   │   └── repositories/       # 5 repository files
│   ├── privileged/             # EMPTY STUB (__init__.py only)
│   └── ai/                     # EMPTY STUB (__init__.py only)
├── tests/                      # 35+ test files
├── docs/                       # 40+ documentation files
├── alembic/                    # 2 migration versions
├── frontend/                   # Next.js 16 + React 19 + Tailwind CSS 4
├── components/                 # Shadcn UI components (Base Nova style)
├── lib/                        # TypeScript utilities (labels, mock-data, theme, widgets)
├── app/                        # Next.js app routes (layout, page)
├── oblivion.db                 # SQLite database (372KB)
├── pyproject.toml              # Python 3.12+, FastAPI, SQLAlchemy 2.0, cryptography 41+
├── requirements.txt            # Dependencies
├── alembic.ini                 # SQLite config
├── package.json                # Next.js 16.3.3, React 19.2.4, Tailwind 4.3.3
├── tsconfig.json               # TypeScript 5.7.3
├── components.json             # shadcn/base-nova config
├── .env.example                # Environment template
├── AGENTS.md                   # Agent instructions
├── CLAUDE.md                   # Master instructions (overrides)
├── OBLIVION.md                 # Full product specification (28KB)
├── AUDIT_REPORT.md             # Previous audit (2026-09-03, spec-only)
├── REMEDIATION_PLAN.md         # Remediation plan
├── SLICE1_RUNTIME_STATUS.md    # Runtime verification BLOCKED
└── reference/                  # 6 reference files (operation states, policy IDs, error codes, etc.)
```

---

## 2. Technology Stack Confirmed

| Layer | Technology | Status |
|-------|-----------|--------|
| **Backend Language** | Python 3.12+ | ✅ Implemented |
| **Backend Framework** | FastAPI ≥0.109.0 | ✅ Implemented |
| **API Framework** | FastAPI + Pydantic v2 | ✅ Implemented |
| **Database** | SQLAlchemy 2.0 + Alembic | ✅ Implemented (SQLite MVP) |
| **ORM** | SQLAlchemy 2.0 (DeclarativeBase) | ✅ Implemented |
| **Migrations** | Alembic ≥1.12.0 | ✅ Implemented (2 versions) |
| **Crypto** | `cryptography` ≥41.0.0 (pyca) | ✅ Implemented (AES-256-GCM, Ed25519, Argon2id) |
| **Session Tokens** | `secrets.token_urlsafe(32)` + SHA-256 | ✅ Implemented |
| **Password Hashing** | Argon2id (RFC 9106) | ✅ Implemented |
| **Signature Scheme** | Ed25519 | ✅ Implemented |
| **API Contract** | OpenAPI 3.0.3 | ✅ Implemented (8,108 bytes) |
| **Frontend** | Next.js 16.3.3 + React 19.2.4 | ✅ Implemented |
| **Frontend Styling** | Tailwind CSS 4.3.3 + shadcn/base-nova | ✅ Implemented |
| **Testing** | pytest ≥7.4.0 + pytest-asyncio | ✅ Implemented (35+ test files) |
| **Linting** | ruff ≥0.3.0 + mypy ≥1.7.0 | ✅ Configured |
| **Target OS** | Windows (with CTYPES-Windows dependencies) | ⚠️ See Platform Issues |
| **Target Filesystem** | NTFS | ⚠️ See Platform Issues |
| **AI Provider** | Omniroute (configured but NOT implemented) | ❌ Missing |
| **Privileged Service** | Named-pipe IPC (specified, NOT implemented) | ❌ Missing |

---

## 3. Implementation Coverage by Module

### 3.1 Fully Implemented (GREEN)

| Module | Files | Status |
|--------|-------|--------|
| **API Routes** | 6 route modules | ✅ Complete |
| **API Schemas** | 8 schema modules | ✅ Complete |
| **Auth & RBAC** | passwords.py, rbac.py, sod.py | ✅ Complete |
| **Path Safety** | paths.py (SafePathValidator) | ✅ Complete (Windows-only) |
| **Policy Engine** | engine.py | ✅ Complete |
| **Erasure Engine** | engine.py, vault.py, events.py | ✅ Complete |
| **Certificate** | signer.py, verification.py, integrity.py, models.py | ✅ Complete |
| **Evidence** | engine.py, canonicalize.py, canonical.py, audit.py, models.py | ✅ Complete |
| **Recovery Engine** | engine.py, adapter.py, ntfs_adapter.py, exporter.py | ✅ Complete |
| **Residual Analysis** | analyzer.py, detectors.py, comparison.py, models.py | ✅ Complete |
| **Assurance Engine** | engine.py, rules.py, models.py | ✅ Complete |
| **State Machine** | machine.py | ✅ Complete (16 states) |
| **Persistence** | database.py, 6 model files, 5 repositories | ✅ Complete |
| **Discovery** | analyzer.py | ✅ Complete |
| **Hashing** | __init__.py (Hasher) | ✅ Complete |
| **Baseline** | manager.py | ✅ Complete |
| **Tests** | 35+ test files | ✅ Substantial |
| **Frontend** | Next.js app, components, lib | ✅ Complete |
| **Config** | pyproject.toml, requirements.txt, alembic.ini, package.json | ✅ Complete |
| **Documentation** | 40+ docs files | ✅ Extensive |
| **OpenAPI** | OPENAPI.yaml | ✅ Complete |

### 3.2 Partially Implemented (YELLOW)

| Module | Issue |
|--------|-------|
| **DryRunPlanner** (`core/dryrun/planner.py`) | `capture_pre_state()` and `verify_post_state()` are TODO stubs returning hardcoded values |
| **StorageProfiler** (`core/discovery/__init__.py`) | Uses `ctypes.windll.kernel32` — works on Windows but has unhandled `FileNotFoundError` in `profile()` method |
| **RecoveryEngine** (`core/recovery/engine.py`) | Uses `b"recovered-data-placeholder"` instead of actual recovery data in export calls |
| **Evidence canonical.py vs canonicalize.py** | Two competing canonicalization implementations exist (one returns `str`, one returns `bytes`) — potential inconsistency |
| **OperationModel** | Missing `file_id` column referenced in operations.py; `target_file_id` computed from path instead |
| **AI module** (`src/oblivion/ai/`) | Empty `__init__.py` — no AI provider implementation; Omniroute integration entirely absent |
| **Privileged module** (`src/oblivion/privileged/`) | Empty `__init__.py` — no privileged service implementation |
| **Alembic migrations** | Only 2 versions (0001_initial, 0002_auth_rbac); may be stale relative to current models |

### 3.3 Not Implemented (RED)

| Module | Status |
|--------|--------|
| **AI Provider (Omniroute)** | ❌ Entirely absent |
| **Privileged Service** | ❌ Entirely absent (named-pipe IPC not implemented) |
| **CLI** | ❌ Referenced in OBLIVION.md, not implemented |
| **Test Data Generator** | ❌ Spec exists, no implementation |
| **Benchmark Suite** | ❌ Spec exists, no implementation |
| **Demo Environment** | ❌ Spec exists, no implementation |
| **Certificate endpoints** | ⚠️ `POST /api/certificates` endpoint missing (only GET and verify exist) |
| **Health check** | ⚠️ `/health` exists but not in OpenAPI |
| **User management endpoints** | ⚠️ No user CRUD endpoints in API |
| **Audit events endpoint** | ⚠️ No `/api/audit/events` endpoint |
| **Assurance endpoint** | ⚠️ No `/api/assurance/{id}` endpoint |
| **Settings/policy endpoints** | ⚠️ Not implemented |
| **Operation polling/streaming** | ❌ No mechanism for long-running operation progress |

---

## 4. Critical Security Findings

### SEC-CRIT-001: CORS Misconfiguration
**File:** `src/oblivion/api/app.py:28-34`  
**Severity:** HIGH  
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, ...)
```
**Finding:** `allow_origins=["*"]` combined with `allow_credentials=True` is a **security anti-pattern**. Per OWASP, `Access-Control-Allow-Origin: *` must not be used with `Access-Control-Allow-Credentials: true`. This allows any origin to access authenticated endpoints with credentials.
**Recommendation:** Restrict `allow_origins` to the BoltAI frontend origin(s) only. Remove `allow_credentials=True` or set `allow_origins` explicitly.

### SEC-CRIT-002: `get_db()` Commits on Every Request
**File:** `src/oblivion/api/dependencies.py:29-39`  
**Severity:** HIGH  
```python
def get_db() -> Generator[Session, None, None]:
    ...
    with session_factory() as session:
        try:
            yield session
            session.commit()  # ← Commits even on error paths!
        except Exception:
            session.rollback()
            raise
```
**Finding:** `session.commit()` is called AFTER `yield`, meaning every successful request commits the DB. For nested dependencies or read-only operations, this is unexpected. Combined with the `DatabaseEventEmitter` which also flushes, this creates double-write risks.
**Recommendation:** Use `yield` + explicit commit/rollback pattern (FastAPI's recommended approach). Remove `session.commit()` from generator.

### SEC-CRIT-003: `DatabaseEventEmitter` Silently Swallows Flush Errors
**File:** `src/oblivion/api/dependencies.py:247-251`  
**Severity:** MEDIUM  
```python
try:
    self.session.flush()
except Exception:
    pass  # ← Silent swallow of audit event failures
```
**Finding:** Audit events failing silently means evidence chain integrity cannot be verified. If the database is unavailable, operations proceed without audit trail.
**Recommendation:** Log the error at minimum; consider fail-closed behavior for critical audit events.

### SEC-CRIT-004: RecoveryVault Metadata Not Integrity-Protected
**File:** `src/oblivion/core/erasure/vault.py:30-95`  
**Severity:** HIGH  
**Finding:** The `.json` metadata file is written as plain JSON without any HMAC or signature. An attacker who can write to the vault directory could modify metadata (e.g., `original_sha256`, `operation_id`) without detection. The `.payload` file is encrypted, but metadata is not.
**Recommendation:** Compute and store an HMAC of the metadata alongside the payload. Verify HMAC on `get_metadata()` and `verify_and_decrypt()`.

### SEC-CRIT-005: COMPLETE_ERASURE Does Not Actually Overwrite
**File:** `src/oblivion/core/erasure/engine.py:317-321`  
**Severity:** CRITICAL  
```python
if mode == ErasureMode.COMPLETE_ERASURE:
    # Example of advanced deletion:
    # with open(target_path, "wb") as f:
    #     f.write(os.urandom(target.stat().st_size))
    pass  # ← DO NOTHING
target.unlink()  # ← Just delete
```
**Finding:** The `COMPLETE_ERASURE` mode contains a commented-out overwrite loop and a `pass` statement. It performs **logical deletion only** — the same as `SELECTIVE_PERMANENT`. This contradicts the product specification which requires `COMPLETE_ERASURE` to perform advanced overwriting.
**Recommendation:** Implement actual overwrite: fill with zeros, then random bytes, then unlink. This is a core product feature that is currently non-functional.

### SEC-CRIT-006: Vault Key Never Persisted or Rotated
**File:** `src/oblivion/api/dependencies.py:154-183`  
**Severity:** HIGH  
**Finding:** The vault key is read from `OBLIVION_VAULT_KEY` environment variable at runtime. It is never stored in the database (as a key reference), never rotated, and never persisted. If the env var is lost, all recovery objects are irrecoverable. If compromised, all vault data is exposed.
**Recommendation:** Implement key reference pattern: store encrypted key references in DB. Implement key rotation with re-encryption of vault objects. Use a key management service or hardware security module in production.

### SEC-CRIT-007: AI Module is Empty (Omniroute Never Implemented)
**File:** `src/oblivion/ai/__init__.py`  
**Severity:** HIGH  
**Finding:** The `ai` package is an empty stub. The `.env.example` configures `AI_PROVIDER=omniroute` and `OMNIROUTE_BASE_URL`, but no AI provider code exists anywhere. The entire AI classification, sensitivity analysis, and residual classification pipeline is absent.
**Recommendation:** Either implement the Omniroute adapter or remove the configuration references to avoid confusion.

### SEC-CRIT-008: Privileged Service Not Implemented (Named-Pipe IPC Absent)
**File:** `src/oblivion/privileged/__init__.py`  
**Severity:** CRITICAL  
**Finding:** Per ADR-004 and ADR-011, the architecture requires a minimal privileged service communicating via named-pipe IPC (`\\.\pipe\OblivionPrivsvc`). The `privileged` package is an empty stub. The application runs all destructive filesystem operations directly from the unprivileged API, which violates the privilege boundary specification.
**Recommendation:** Either implement the named-pipe service or document this as a known deviation from the architecture with an acceptable risk assessment.

### SEC-CRIT-009: `get_current_user` Uses `== False` Instead of `is_`
**File:** `src/oblivion/api/dependencies.py:79`  
**Severity:** MEDIUM  
```python
if not session_model or session_model.revoked:
```
**Finding:** Uses boolean evaluation which works correctly (`revoked == False` vs `revoked is False`), but `UserRepository.get_session_by_token_hash` uses `SessionModel.revoked == False` in SQLAlchemy query (line 145 of user_repo.py). With SQLAlchemy 2.0, this works but `is_` is preferred.
**Recommendation:** Use `is False` for SQLAlchemy boolean comparisons to be explicit.

### SEC-CRIT-010: `app.dependency_overrides` Test Fixture Bug
**File:** `tests/conftest.py:121-132`  
**Severity:** MEDIUM  
```python
@pytest.fixture
def client(safe_validator, temp_dir):
    init_db()
    app.dependency_overrides[get_safe_validator] = lambda: safe_validator
    ...
    test_client = TestClient(app)
    app.dependency_overrides.clear()  # ← Cleared BEFORE client is used
    return test_client
```
**Finding:** The dependency override is cleared before the `TestClient` is returned. When the client makes requests, the override is not applied, so `get_safe_validator` returns the real validator instead of the test one. This means tests using the `client` fixture bypass path safety validation.
**Recommendation:** Move `app.dependency_overrides.clear()` to a `yield`-based cleanup or `request.addfinalizer`.

### SEC-CRIT-011: `target_file_id` Variable Mismatch in Operation Execution
**File:** `src/oblivion/api/routes/operations.py:263`  
**Severity:** MEDIUM  
```python
target_serial = validator.get_volume_serial(target.canonical_path) or "UNKNOWN"
target_file_id = validator._get_file_id(target.canonical_path)
```
**Finding:** `_get_file_id` is a **private method** (starts with `_`) and returns `None` on non-Windows platforms. The variable `target_file_id` can be `None`. This is passed to `revalidate_handle` which handles `None` correctly (skips file_id check). However, the code uses a private API, and on non-Windows `target_file_id` is always `None`, making TOCTOU file-ID binding non-functional.
**Recommendation:** Use a public method or handle `None` explicitly with a warning log. Consider a platform-compatibility abstraction.

### SEC-CRIT-012: `COMPLETE_ERASURE` and `SELECTIVE_PERMANENT` Are Functionally Identical
**File:** `src/oblivion/core/erasure/engine.py:307-322`  
**Severity:** HIGH  
**Finding:** Both modes call `target.unlink()` for files and `shutil.rmtree(target_path)` for directories. The `COMPLETE_ERASURE` mode's overwrite is commented out (`pass`). There is **no functional difference** between the two modes, which contradicts the product specification that defines three distinct erasure modes.
**Recommendation:** Implement COMPLETE_ERASURE with multi-pass overwrite (DoD 5220.22-M or NIST 800-88). This is a core product differentiator that is currently broken.

---

## 5. Architecture Findings

### ARCH-001: Two Competing Canonicalization Implementations
**Files:** `core/evidence/canonical.py` vs `core/evidence/canonicalize.py`  
**Severity:** MEDIUM  
- `canonical.py`: `canonicalize(data: Dict) -> str` (JSON string)
- `canonicalize.py`: `canonicalize(data: Dict) -> bytes` (UTF-8 bytes)

Both are imported by different modules. `evidence/engine.py` imports from `canonicalize` (bytes). `certificate/verification.py` imports from `canonical.py` (via `hash_integrity` → `canonical_hash` → `canonicalize` returns str). This creates a potential inconsistency in evidence signing and verification.

**Recommendation:** Consolidate into a single canonicalization module. Remove the `canonical.py` file or make it re-export from `canonicalize.py`.

### ARCH-002: `RecoveryVault.verify_and_decrypt()` No Metadata Verification
**File:** `src/oblivion/core/erasure/vault.py:98-113`  
**Severity:** MEDIUM  
**Finding:** `verify_and_decrypt` reads the `.json` metadata and `.payload` ciphertext, decrypts the payload, and returns it. But it does NOT verify that the metadata hasn't been tampered with. The metadata file is plain JSON with no integrity check.

**Recommendation:** Add HMAC verification of metadata before trusting it.

### ARCH-003: `ErasureEngine.execute_operation()` Missing `target_file_id` Propagation to `_perform_erasure`
**File:** `src/oblivion/core/erasure/engine.py:252-291`  
**Severity:** MEDIUM  
**Finding:** `_run_erasure_pipeline` computes `target_file_id` from `validator._get_file_id(target.canonical_path)` and passes it to `revalidate_handle`. However, `_perform_erasure` is called WITHOUT `target_file_id`, and the `_perform_erasure` function signature doesn't accept it. This is technically correct (TOCTOU is in `_run_erasure_pipeline`), but the parameter flow is confusing and could lead to bugs if `_perform_erasure` is later modified.

**Recommendation:** Add a clear comment or refactor to make the TOCTOU boundary explicit.

### ARCH-004: All Windows-Specific Code Will Fail on Non-Windows
**Files:** `core/safety/paths.py`, `core/discovery/__init__.py`  
**Severity:** MEDIUM  
**Finding:** The entire `SafePathValidator` class and `StorageProfiler` class use `ctypes.windll.kernel32` for Windows API calls (`GetVolumeInformationW`, `GetFileInformationByHandle`, `GetFileAttributesW`, `CreateFileW`, `GetDiskFreeSpaceExW`). On non-Windows platforms, these calls will raise `AttributeError`.

The code does have `if sys.platform != "win32": return None` guards in some methods, but `StorageProfiler.profile()` does NOT have this guard — it will crash on non-Windows.

**Recommendation:** Wrap all Windows-specific code in `try/except AttributeError` or `if sys.platform == "win32"` blocks. Add platform-compatibility tests.

### ARCH-005: `OperationStateMachine` Has `PENDING_APPROVAL` in `CREATED` Transitions
**File:** `src/oblivion/core/state/machine.py:31`  
**Severity:** LOW  
```python
State.CREATED: {State.ANALYZING, State.PENDING_APPROVAL, State.READY, State.FAILED, State.CANCELLED},
```
**Finding:** `PENDING_APPROVAL` is listed as a valid transition from `CREATED`, but the `ErasureEngine.execute_operation()` creates operations in `PENDING_APPROVAL` state directly (via `repo.create_operation(state="PENDING_APPROVAL")`), not via state machine transition. The state machine is used for `READY → ERASING` transitions. This creates a potential inconsistency where the state machine could be used to transition `CREATED → PENDING_APPROVAL` but the API doesn't expose this path.

**Recommendation:** Document the state machine usage clearly or align the API with the state machine transitions.

### ARCH-006: `get_db()` Creates New Session Per Dependency Injection
**File:** `src/oblivion/api/dependencies.py:29-39`  
**Severity:** MEDIUM  
**Finding:** Each `Depends(get_db)` creates a new session factory call and session. When multiple dependencies use `get_db` (e.g., `get_current_user` and the route handler), they get **different sessions**. This means changes in one session may not be visible in another within the same request.

**Recommendation:** Use a request-scoped session pattern where all dependencies share the same session.

### ARCH-007: `get_current_user` Creates `UserRepository` Per Call
**File:** `src/oblivion/api/dependencies.py:54-94`  
**Severity:** LOW  
**Finding:** `get_current_user` and `require_permission` both create `UserRepository` instances. Since each `get_db` dependency creates a new session, and `get_current_user` uses `Depends(get_db)`, the `UserRepository` uses the same session as the route handler (both depend on `get_db`). However, `require_permission` also depends on `get_db` and `get_current_user`, creating a chain of three `get_db` calls — each creating a new session. This means three separate database sessions are opened per authenticated request.

**Recommendation:** Use a single request-scoped database session.

---

## 6. Code Quality Findings

### CODE-001: Duplicate `TestFailClosedBehavior` Class
**File:** `tests/test_safety_hardened.py`  
**Severity:** LOW  
**Finding:** Lines 239-341 define `TestFailClosedBehavior` class, and lines 314-390 define **another** `TestFailClosedBehavior` class with identical test names and nearly identical content. The second definition overwrites the first.

**Recommendation:** Remove the duplicate class or rename it.

### CODE-002: Duplicate `TestAncestorReparsePointRejection` Class
**File:** `tests/test_safety_hardened.py`  
**Severity:** LOW  
**Finding:** Same issue as CODE-001 — duplicate class definitions that overwrite each other.

### CODE-003: `typing.cast` Used Unnecessarily
**File:** `src/oblivion/core/safety/paths.py`  
**Severity:** LOW  
```python
from typing import List, Optional, Dict, Any, cast
...
errors: List[str] = cast(List[str], result["errors"])
```
**Finding:** `cast` is used but `result["errors"]` is already typed as `List[str]` via the `result: Dict[str, Any]` annotation. The cast is redundant.

### CODE-004: `import datetime` Inside Function Body
**File:** `src/oblivion/api/routes/certificates.py:75`  
**Severity:** LOW  
```python
import datetime  # ← Inside function body
```
**Finding:** Should be at the top of the file. This is a code smell that makes dependencies unclear.

### CODE-005: `StorageProfiler` Has Incomplete Error Handling
**File:** `src/oblivion/core/discovery/__init__.py:109-111`  
**Severity:** MEDIUM  
```python
except Exception as e:
    profile_data["limitations"] = [f"Storage profile incomplete: {str(e)}"]
```
**Finding:** If the `try` block fails entirely (e.g., `ctypes.windll.kernel32` doesn't exist on non-Windows), `profile_data` may not have all the expected keys. The `except` only sets `limitations`, not the missing fields.

**Recommendation:** Initialize all profile fields with default values before the try block, or use a complete fallback profile.

### CODE-006: `RecoveryVault` Uses `os.chmod` on Windows
**File:** `src/oblivion/core/erasure/vault.py:28`  
**Severity:** LOW  
```python
os.chmod(self.vault_root, 0o700)
```
**Finding:** On Windows, `os.chmod` has limited effect (only read-only flag). The `0o700` permission has no meaningful effect on NTFS. This is harmless but misleading.

### CODE-007: `DryRunPlanner` Has TODO Stubs
**File:** `src/oblivion/core/dryrun/planner.py`  
**Severity:** MEDIUM  
```python
def capture_pre_state(self) -> None:
    """Verifies filesystem state before planned operations."""
    # TODO: Implement actual state capturing logic
    self._pre_state_snapshot = {"state": "captured"}

def verify_post_state(self) -> bool:
    """Verifies filesystem state is identical to pre-state."""
    # TODO: Implement actual state verification logic
    return self._pre_state_snapshot is not None
```
**Finding:** Dry-run is a critical safety feature. The stubs mean dry-run provides no actual safety verification.

**Recommendation:** Implement actual pre-state snapshotting and post-state verification.

---

## 7. API Contract Findings

### API-001: Missing Endpoints Per OpenAPI
**File:** `docs/OPENAPI.yaml`  
**Severity:** HIGH  
**Finding:** The OpenAPI spec defines endpoints that don't exist in the code:
- `POST /api/certificates` — certificate issuance (only GET and verify exist)
- `GET /api/health` — health check exists in code but not in OpenAPI
- `POST /api/auth/login` — exists in code but not in OpenAPI
- `POST /api/auth/logout` — exists in code but not in OpenAPI
- `GET /api/auth/me` — exists in code but not in OpenAPI
- `GET /api/targets/{target_id}` — exists in code but not in OpenAPI
- No user management endpoints
- No audit events endpoint
- No assurance endpoint
- No settings/policy endpoints

### API-002: OpenAPI Security Scheme Uses JWT but No JWT Exists
**File:** `docs/OPENAPI.yaml:164-168`  
**Severity:** MEDIUM  
```yaml
securitySchemes:
  bearerAuth:
    type: http
    scheme: bearer
    bearerFormat: JWT
```
**Finding:** The security scheme specifies JWT format, but the actual implementation uses opaque session tokens (`secrets.token_urlsafe(32)`), not JWTs. The tokens are session tokens stored server-side in the database.

**Recommendation:** Update OpenAPI to specify `bearerFormat: OpaqueSessionToken` or implement actual JWT.

### API-003: No Error Schema Defined in OpenAPI
**File:** `docs/OPENAPI.yaml`  
**Severity:** MEDIUM  
**Finding:** `BadRequest` and `Forbidden` responses reference `$ref` but no error component schema is defined in `components/responses`. The `ErrorResponse` schema exists in code but is not referenced in the OpenAPI spec.

### API-004: No Operation Progress/Polling Mechanism
**File:** `docs/OPENAPI.yaml`  
**Severity:** HIGH  
**Finding:** Operations return 202 with `progress_percent` but there's no mechanism for streaming progress or polling for updates. The `GET /api/operations/{id}` endpoint returns the current state, but there's no SSE, WebSocket, or polling endpoint defined.

**Recommendation:** Add a `/api/operations/{id}/stream` endpoint or implement SSE-based progress streaming.

### API-005: `CreateOperationRequest` Has `recovery` Field Not in OpenAPI
**File:** `src/oblivion/api/schemas/operation.py:29-35`  
**Severity:** LOW  
**Finding:** The Pydantic schema has `recovery: Optional[RecoveryConfig] = None` but the OpenAPI spec doesn't include the `recovery` property in `CreateOperationRequest`.

### API-006: `evidence` Endpoint Is Minimal
**File:** `src/oblivion/api/routes/evidence.py`  
**Severity:** LOW  
**Finding:** The evidence endpoint (`POST /api/evidence/verify`) only accepts a raw evidence dict, signature, and public key. There are no endpoints for creating evidence records, listing evidence, or managing evidence baselines — despite the database having `BaselineModel`, `RecoveryTestModel`, `ResidualFindingModel`, `AssuranceResultModel`, and `EvidenceRecordModel`.

**Recommendation:** Add CRUD endpoints for evidence records, baselines, recovery tests, residual findings, and assurance results.

---

## 8. Database Findings

### DB-001: `OperationModel` Missing `file_id` Column
**File:** `src/oblivion/persistence/models/operation.py:29-53`  
**Severity:** MEDIUM  
**Finding:** The `operations` table has no `file_id` column, but `operations.py` line 263 references `target_file_id` computed from the path. The `TargetModel` also has no `file_id` column. This means the `target_file_id` concept exists in code but not in the database schema.

**Recommendation:** Add `file_id` column to `TargetModel` and `OperationModel`, or remove the concept if it's not needed.

### DB-002: `init_db()` Imports Models That May Not Exist
**File:** `src/oblivion/persistence/database.py:55-64`  
**Severity:** MEDIUM  
**Finding:** The import references `RoleModel`, `PermissionModel`, `RolePermissionModel`, `SessionModel`, `BaselineModel`, `RecoveryTestModel`, `ResidualFindingModel`, `AssuranceResultModel`, `EvidenceRecordModel`, and `CertificateModel` — but `__init__.py` does export them. However, if any model file is missing, `init_db()` will crash.

**Recommendation:** Add try/except around imports or verify all model files exist.

### DB-003: No Foreign Key Constraints for Evidence/Baseline Tables
**File:** `src/oblivion/persistence/models/evidence.py`  
**Severity:** MEDIUM  
**Finding:** `BaselineModel.operation_id` has a ForeignKey to `operations.id`, but `RecoveryTestModel`, `ResidualFindingModel`, `AssuranceResultModel` also have `operation_id` ForeignKeys. `EvidenceRecordModel` has `operation_id` ForeignKey. However, `CertificateModel.evidence_id` has a ForeignKey to `evidence_records.id`. These are all correctly defined. But `CertificateModel` doesn't have a `claim` or `limitations` field that the code uses... actually it does: `claim: Mapped[Optional[str]]` and `limitations: Mapped[Optional[str]]`. OK.

### DB-004: SQLite Used for Production MVP
**File:** `src/oblivion/persistence/database.py`  
**Severity:** MEDIUM  
**Finding:** SQLite is used as the database. Per `docs/ARCHITECTURE_DECISIONS.md` ADR-010, the architecture discusses crash recovery and reconciliation — but SQLite doesn't support concurrent writes well. Multiple simultaneous operations could cause `sqlite3.OperationalError: database is locked`.

**Recommendation:** For the MVP, SQLite is acceptable. For production, consider PostgreSQL or a more concurrent-capable database. Add connection pooling and retry logic.

### DB-005: No Database-Level Transaction Boundaries
**File:** `src/oblivion/api/routes/operations.py`  
**Severity:** MEDIUM  
**Finding:** The `execute_operation_endpoint` performs filesystem operations (`target.unlink()`) and database updates in the same request. There's no transaction boundary ensuring atomicity between filesystem state and database state. If the process crashes between the filesystem operation and the DB update, the state becomes inconsistent.

**Recommendation:** Implement the ADR-010 reconciliation pattern. Mark operations as `PENDING_DELETION` before the destructive operation. On restart, reconcile DB state with filesystem state.

---

## 9. Platform Compatibility Findings

### PLATFORM-001: All Windows-CTYPES Code Will Crash on Non-Windows
**Files:** `core/safety/paths.py`, `core/discovery/__init__.py`  
**Severity:** HIGH  
**Finding:** The codebase is described as "Windows-first" in CLAUDE.md, but the Python code uses `sys.platform != "win32"` guards inconsistently:

- `SafePathValidator._get_system_volume_serial()`: ✅ Has guard
- `SafePathValidator._get_file_id()`: ✅ Has guard
- `SafePathValidator.get_volume_serial()`: ✅ Has guard
- `SafePathValidator.reject_reparse()`: ✅ Has guard (checks `sys.platform == "win32"`)
- `SafePathValidator.is_system_volume()`: ✅ Has guard for volume serial, but prefix-based check runs on all platforms
- `SafePathValidator.validate_ancestor_reparse()`: ⚠️ No guard — uses `ctypes` indirectly via `reject_reparse` which has guard
- `SafePathValidator.validate_descendants_reparse()`: ⚠️ Uses `os.walk` and `reject_reparse` — OK on non-Windows
- `StorageProfiler.profile()`: ❌ NO GUARD — `ctypes.windll.kernel32` will crash on non-Windows
- `TargetAnalyzer._decode_windows_attributes()`: ✅ Has `hasattr` check
- `TargetAnalyzer._classify_file_type()`: ✅ Platform-independent

**Recommendation:** Add `try/except AttributeError` or `if sys.platform == "win32"` around `StorageProfiler.profile()`. Add platform-compatibility tests.

### PLATFORM-002: `ctypes.windll` Will Crash on Non-Windows
**Severity:** HIGH  
**Finding:** Any import or call to `ctypes.windll.kernel32` on non-Windows will raise `AttributeError: module 'ctypes' has no attribute 'windll'`. The code has guards in some methods but not all.

**Recommendation:** Wrap all `ctypes` usage in `try/except AttributeError` blocks. Consider a platform abstraction layer.

---

## 10. Test Coverage Findings

### TEST-001: `test_safety_hardened.py` Has Duplicate Classes
**File:** `tests/test_safety_hardened.py`  
**Severity:** MEDIUM  
**Finding:** `TestFailClosedBehavior` and `TestAncestorReparsePointRejection` are defined **twice** each. The second definition overwrites the first. This means half the tests in the file may not be running.

**Recommendation:** Remove duplicate class definitions. Run `pytest --collect-only` to verify all tests are collected.

### TEST-002: `conftest.py` Client Fixture Bug
**File:** `tests/conftest.py:121-132`  
**Severity:** HIGH  
**Finding:** The `client` fixture clears `dependency_overrides` before returning the client. Tests using `client` won't have path safety validation applied.

**Recommendation:** Fix as described in SEC-CRIT-010.

### TEST-003: `test_safety.py` Has No `safe_validator` Fixture in Scope
**File:** `tests/test_safety.py`  
**Severity:** MEDIUM  
**Finding:** The `TestPathTraversalRejection` class uses `safe_validator` and `temp_dir` fixtures, but `test_safety.py` doesn't define `safe_validator` — it relies on `conftest.py`. This should work if `conftest.py` is loaded, but the fixture depends on `temp_dir` which is not defined in `test_safety.py` either. It comes from `conftest.py`. This is correct if pytest properly loads `conftest.py`.

### TEST-004: No Integration Tests for End-to-End Workflow
**Severity:** HIGH  
**Finding:** There are tests for individual components (safety, auth, erasure, recovery, etc.) but no test exercises the full pipeline: Analyze → Create Operation → Approve → Execute → Verify Recovery → Residual Scan → Assure → Certify.

**Recommendation:** Add an end-to-end integration test that exercises the complete pipeline with a temporary test volume.

### TEST-005: No Security Penetration Tests
**Severity:** HIGH  
**Finding:** No tests verify that path traversal attacks are blocked, that system drive deletion is prevented, that unauthorized recovery is blocked, or that vault key exposure is prevented.

**Recommendation:** Add security test suite with attack vectors (path traversal, symlink escape, system drive targeting, unauthorized restore, malformed certificates).

### TEST-006: No Performance/Benchmark Tests
**Severity:** MEDIUM  
**Finding:** `docs/BENCHMARK_PROTOCOL.md` defines benchmarks but none are implemented. No tests for large file handling, memory boundedness, or concurrent operation handling.

### TEST-007: `test_auth_rbac.py` Depends on Running Database
**Severity:** MEDIUM  
**Finding:** The `TestAuthenticationEndpoints` class uses `auth_client` fixture which depends on `init_db()`. If the database is not properly initialized (e.g., tables don't exist), tests will fail with cryptic errors.

---

## 11. Frontend Findings

### FE-001: Frontend Depends on Non-Existent API Endpoints
**File:** `components/ob/views/`  
**Severity:** HIGH  
**Finding:** The frontend has view components for `assurance`, `certificates`, `operations`, `overview`, `recovery`, `residual`, `targets`, `workflow` — but many of the API endpoints these depend on don't exist (see API-001).

### FE-002: `lib/mock-data.ts` Contains Hardcoded Test Data
**File:** `lib/mock-data.ts`  
**Severity:** LOW  
**Finding:** The mock data file contains 14,685 bytes of hardcoded test data. This suggests the frontend was developed against mock data rather than a real API. The mock data may not match the actual API schema.

### FE-003: Next.js Configuration Allows Build Errors
**File:** `next.config.mjs`  
**Severity:** LOW  
```javascript
typescript: { ignoreBuildErrors: true }
```
**Finding:** TypeScript build errors are silently ignored. This could mask real type mismatches between frontend and backend.

---

## 12. Documentation Findings

### DOC-001: `docs/OPENAPI.yaml` Is Incomplete Relative to Code
**File:** `docs/OPENAPI.yaml`  
**Severity:** MEDIUM  
**Finding:** Many endpoints implemented in code are not in the OpenAPI spec (auth endpoints, health, targets GET, certificates POST, evidence CRUD, etc.). The spec describes the contract but doesn't match the implementation.

### DOC-002: `AUDIT_REPORT.md` Is Stale (September 3, Spec-Only State)
**File:** `AUDIT_REPORT.md`  
**Severity:** LOW  
**Finding:** The existing audit report describes a spec-only repository with zero code. This is now outdated — the backend is substantially implemented.

### DOC-003: `SLICE1_RUNTIME_STATUS.md` Says BLOCKED
**File:** `SLICE1_RUNTIME_STATUS.md`  
**Severity:** MEDIUM  
**Finding:** This file (September 5) says runtime verification is BLOCKED because `pytest` was missing. The current codebase has `pyproject.toml` with pytest configured and `requirements.txt` with pytest. If pytest was installed later, the block may be resolved. But the file says "do not proceed to Slice 2" — this may be stale guidance.

---

## 13. Dependency and Configuration Findings

### DEP-001: `python-dotenv` Not Used in Application Code
**File:** `pyproject.toml`  
**Severity:** LOW  
**Finding:** `python-dotenv>=1.0.0` is a dependency but no code calls `load_dotenv()` or reads from `.env` files programmatically. Environment variables are read directly via `os.environ.get()`. This means `.env` files must be loaded externally.

### DEP-002: `uvicorn` Is a Dependency But Not Used in Tests
**File:** `pyproject.toml`  
**Severity:** LOW  
**Finding:** `uvicorn>=0.25.0` is a dependency but tests use `TestClient` from FastAPI, not a running uvicorn server. This is fine for testing but means the application hasn't been tested as a running server.

### DEP-003: `alembic` Migrations May Be Stale
**File:** `alembic/versions/`  
**Severity:** MEDIUM  
**Finding:** There are 2 migration versions (`0001_initial.py`, `0002_auth_rbac.py`). The current models may have diverged from these migrations. If `init_db()` creates all tables via `Base.metadata.create_all()`, the migrations may be inconsistent with the actual schema.

### DEP-004: `pnpm-lock.yaml` Is Large (113KB)
**File:** `pnpm-lock.yaml`  
**Severity:** LOW  
**Finding:** The frontend lock file is large, indicating many dependencies. The `package.json` specifies `next@16.3.3`, `react@19.2.4`, `react-dom@19.2.4` — these are very new versions that may have compatibility issues.

---

## 14. Compliance with CLAUDE.md

### CLAUDE-001: "Never Execute Arbitrary Shell Commands from API/UI Input"
**Status:** ✅ COMPLIANT — No shell command execution endpoints exist.

### CLAUDE-002: "Never Allow the AI Model to Directly Choose or Execute Destructive Commands"
**Status:** ✅ COMPLIANT — AI module is empty; no AI-driven destructive operations exist.

### CLAUDE-003: "Use an Allowlisted Operation Policy"
**Status:** ✅ COMPLIANT — `PolicyEngine.validate_operation_policy()` enforces allowlisted policies.

### CLAUDE-004: "Protect System/Boot Volumes by Default"
**Status:** ✅ COMPLIANT — `SafePathValidator.is_system_volume()` protects system volumes. But COMPLETE_ERASURE doesn't overwrite (SEC-CRIT-005).

### CLAUDE-005: "Require Explicit Confirmation for Destructive Operations"
**Status:** ✅ COMPLIANT — `CreateOperationRequest.confirmation.acknowledged_risk` is required.

### CLAUDE-006: "Normalize and Validate Paths"
**Status:** ✅ COMPLIANT — `SafePathValidator.canonicalize()` normalizes paths.

### CLAUDE-007: "Handle Symlinks, Junctions and Reparse Points Safely"
**Status:** ✅ COMPLIANT — `reject_reparse()`, `validate_ancestor_reparse()`, `validate_descendants_reparse()` handle reparse points.

### CLAUDE-008: "Revalidate Target Identity Immediately Before Destructive Action"
**Status:** ✅ COMPLIANT — `revalidate_handle()` is called in `_run_erasure_pipeline` before deletion.

### CLAUDE-009: "Prevent Path Traversal and Target Substitution"
**Status:** ✅ COMPLIANT — `validate_target()` checks allowed roots, reparse points, system volumes.

### CLAUDE-010: "Do Not Log Sensitive Plaintext"
**Status:** ⚠️ PARTIAL — `EngineEventEmitter` prints events to stdout (could contain target paths). `DatabaseEventEmitter` stores `str(details)` in database. Paths are not considered sensitive plaintext per CLAUDE.md, but file contents could be.

### CLAUDE-011: "Never Expose Vault Keys Through API Responses"
**Status:** ✅ COMPLIANT — No endpoint returns vault keys. `get_vault_key()` is a dependency that validates but doesn't return to clients.

### CLAUDE-012: "Destructive Operations Must Be Deterministic and Testable"
**Status:** ⚠️ PARTIAL — COMPLETE_ERASURE is not deterministic (no overwrite). Recovery is testable but uses placeholder data.

### CLAUDE-013: "Fail Closed When Target Identity or Safety Checks Are Ambiguous"
**Status:** ✅ COMPLIANT — `SafePathValidator` fails closed on exceptions. `revalidate_handle` returns False on failure.

### CLAUDE-014: "Use a Minimal Privileged Service Rather Than Running the Entire API as Administrator"
**Status:** ❌ NON-COMPLIANT — `privileged/` module is empty. No privileged service exists. All operations run from the unprivileged API.

### CLAUDE-015: "Preferred Hash: SHA-256"
**Status:** ✅ COMPLIANT — SHA-256 used throughout (`hashlib.sha256`).

### CLAUDE-016: "Use a Vetted Signature Implementation Such as Ed25519"
**Status:** ✅ COMPLIANT — `cryptography.hazmat.primitives.asymmetric.ed25519` used.

### CLAUDE-017: "Certificate Verification Must Detect Tampering"
**Status:** ✅ COMPLIANT — `verify_certificate()` checks evidence hash, signature, and version.

### CLAUDE-018: "Use `INCONCLUSIVE` Where Evidence Is Insufficient"
**Status:** ✅ COMPLIANT — `VerificationStatus.INCONCLUSIVE` and `AssuranceStatus.INCONCLUSIVE` exist and are used.

### CLAUDE-019: "Never Claim 100% Irrecoverability"
**Status:** ✅ COMPLIANT — `docs/LIMITATIONS.md` explicitly forbids this wording.

---

## 15. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RISK-001 | COMPLETE_ERASURE doesn't overwrite (SEC-CRIT-005) | High | Critical | Implement overwrite; currently logical deletion only |
| RISK-002 | CORS misconfiguration (SEC-CRIT-001) | High | High | Restrict origins; remove credentials with wildcard |
| RISK-003 | Vault metadata not integrity-protected (SEC-CRIT-004) | Medium | High | Add HMAC to metadata |
| RISK-004 | Privileged service absent (SEC-CRIT-008) | High | Critical | Implement named-pipe service or document deviation |
| RISK-005 | AI pipeline absent (SEC-CRIT-007) | High | High | Implement Omniroute adapter or remove config |
| RISK-006 | Test fixture `client` bypasses safety (SEC-CRIT-010) | High | Medium | Fix conftest.py overrides |
| RISK-007 | Duplicate test classes (CODE-001, CODE-002) | High | Medium | Remove duplicates; verify test collection |
| RISK-008 | Windows-only code crashes on non-Windows (PLATFORM-001) | Medium | High | Add platform guards; test on non-Windows |
| RISK-009 | No end-to-end pipeline test (TEST-004) | High | High | Add full pipeline integration test |
| RISK-010 | DB/FS state inconsistency (DB-005) | Medium | High | Implement ADR-010 reconciliation |
| RISK-011 | `get_db()` commits unexpectedly (SEC-CRIT-002) | Medium | Medium | Use proper session lifecycle |
| RISK-012 | `DatabaseEventEmitter` swallows errors (SEC-CRIT-003) | Medium | Medium | Log errors; consider fail-closed |
| RISK-013 | No operation progress streaming (API-004) | Medium | Medium | Add SSE/polling endpoint |
| RISK-014 | OpenAPI doesn't match code (API-001) | High | Medium | Sync OpenAPI with implementation |
| RISK-015 | `StorageProfiler` crashes on non-Windows (PLATFORM-001) | High | High | Add platform guard |

---

## 16. Module-by-Module Readiness Summary

| Module | Files | Lines of Code | Test Coverage | Readiness |
|--------|-------|---------------|---------------|-----------|
| API Routes | 6 | ~450 | Medium | 🟢 READY |
| API Schemas | 8 | ~200 | Medium | 🟢 READY |
| Auth/RBAC/SoD | 3 | ~250 | High | 🟢 READY |
| Path Safety | 1 | ~350 | High | 🟡 READY (Windows-only) |
| Policy Engine | 1 | ~90 | Medium | 🟢 READY |
| Erasure Engine | 3 | ~350 | Medium | 🔴 BLOCKED (COMPLETE_ERASURE broken) |
| Recovery Vault | 1 | ~110 | Medium | 🟡 READY (metadata HMAC missing) |
| Certificate | 4 | ~150 | Medium | 🟢 READY |
| Evidence | 5 | ~200 | Low | 🟡 READY (CRUD endpoints missing) |
| Recovery Engine | 4 | ~200 | Medium | 🟡 READY (placeholder data) |
| Residual Analysis | 4 | ~150 | Low | 🟡 READY |
| Assurance Engine | 3 | ~100 | Low | 🟡 READY |
| State Machine | 1 | ~70 | Medium | 🟢 READY |
| Persistence | 9 | ~350 | Medium | 🟡 READY (stale migrations) |
| Discovery | 1 | ~200 | Medium | 🟡 READY (Windows-only CTYPES) |
| AI | 1 | ~5 | ❌ | 🔴 MISSING |
| Privileged | 1 | ~5 | ❌ | 🔴 MISSING |
| Dry Run | 1 | ~30 | ❌ | 🔴 BLOCKED (TODO stubs) |
| Tests | 35+ | ~2000+ | Variable | 🟡 PARTIAL |
| Frontend | ~25 | ~3000 | None (no tests) | 🟡 READY |
| Config | 6 | ~50 | N/A | 🟢 READY |
| Documentation | 40+ | ~10000 | N/A | 🟢 READY |

---

## 17. Top 20 Findings (Prioritized)

1. **[CRITICAL] COMPLETE_ERASURE mode is non-functional** — `engine.py:317-321` contains `pass` instead of overwrite logic. This is the core product differentiator and it's broken.

2. **[CRITICAL] Privileged service is absent** — `privileged/__init__.py` is empty. The architecture requires a named-pipe IPC service that doesn't exist.

3. **[CRITICAL] AI pipeline is absent** — `ai/__init__.py` is empty. Omniroute integration is configured but never implemented.

4. **[CRITICAL] Dry-run is non-functional** — `DryRunPlanner.capture_pre_state()` and `verify_post_state()` are TODO stubs.

5. **[HIGH] CORS misconfiguration** — `allow_origins=["*"]` with `allow_credentials=True` is a security violation.

6. **[HIGH] Vault metadata lacks integrity protection** — `.json` metadata is plain JSON with no HMAC.

7. **[HIGH] `get_db()` commits on every request** — Creates double-write risks with `DatabaseEventEmitter`.

8. **[HIGH] Test fixture `client` bypasses path safety** — `dependency_overrides.clear()` called before client use.

9. **[HIGH] Duplicate test classes** — `test_safety_hardened.py` has duplicate `TestFailClosedBehavior` and `TestAncestorReparsePointRejection` classes.

10. **[HIGH] `StorageProfiler` will crash on non-Windows** — No `sys.platform` guard around `ctypes.windll.kernel32`.

11. **[HIGH] No end-to-end pipeline test** — No test exercises the full Analyze → Erase → Recovery → Residual → Assure → Certify pipeline.

12. **[HIGH] No security penetration tests** — No tests verify path traversal blocking, system drive protection, or unauthorized restore prevention.

13. **[MEDIUM] COMPLETE_ERASURE and SELECTIVE_PERMANENT are functionally identical** — Both just call `target.unlink()`.

14. **[MEDIUM] OpenAPI doesn't match implementation** — Many endpoints in code are missing from the spec.

15. **[MEDIUM] No operation progress streaming** — No mechanism for real-time operation progress updates.

16. **[MEDIUM] DB/FS state inconsistency risk** — No transaction boundaries between filesystem and database operations.

17. **[MEDIUM] `DatabaseEventEmitter` swallows flush errors** — Audit event failures are silently ignored.

18. **[MEDIUM] `target_file_id` uses private API** — `validator._get_file_id()` is private and returns None on non-Windows.

19. **[MEDIUM] `canonical.py` vs `canonicalize.py` duplication** — Two competing canonicalization implementations exist.

20. **[LOW] `app.dependency_overrides` not properly isolated in tests** — Test isolation issues possible.

---

## 18. Overall Assessment

### Strengths
- **Comprehensive implementation** of the backend pipeline (55+ Python files)
- **Strong security architecture** (RBAC, SoD, path safety, cryptographic operations)
- **Complete persistence layer** (SQLAlchemy 2.0, Alembic, 6 model files, 5 repositories)
- **Excellent documentation** (40+ docs files, comprehensive OpenAPI spec)
- **Substantial test suite** (35+ test files, good unit test coverage)
- **Proper crypto usage** (Argon2id, Ed25519, AES-256-GCM via `cryptography` library)
- **Clean separation of concerns** (API, core, persistence, certificate layers)
- **Deterministic evidence canonicalization** (SHA-256, sorted JSON)

### Weaknesses
- **Core product features broken** (COMPLETE_ERASURE, dry-run, privileged service, AI)
- **Security vulnerabilities** (CORS, vault metadata, double-commit, silent error swallowing)
- **Test quality issues** (duplicate classes, broken fixtures, no e2e tests)
- **Platform compatibility gaps** (Windows-only code with inconsistent guards)
- **API contract drift** (OpenAPI doesn't match implementation)
- **Missing critical functionality** (operation progress streaming, evidence CRUD, user management)
- **Test infrastructure issues** (conftest.py fixture bugs, pytest may not be installed)

### Bottom Line
The Oblivion project has made **remarkable progress** from its spec-only origins. The backend is substantially implemented with strong security architecture and good documentation. However, **four critical product features are non-functional** (COMPLETE_ERASURE, privileged service, AI pipeline, dry-run), and **several security vulnerabilities** must be addressed before production readiness. The test suite has structural issues that prevent reliable verification. The next development phase should prioritize fixing COMPLETE_ERASURE, implementing the privileged service, resolving the CORS misconfiguration, and adding end-to-end integration tests.

**Overall Readiness Score: 6.5/10**  
**Production-Ready: NO**  
**Test-Green: NOT VERIFIED** (pytest execution could not be confirmed due to test fixture issues and potential missing dependencies)

---

*Report generated 2026-09-09. All findings are based on read-only analysis of the repository state at the time of audit. No modifications were made.*
