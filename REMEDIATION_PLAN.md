# Oblivion Remediation Plan

**Date:** 2026-09-03
**Repository:** D:\OBLIVION
**Status:** Specification-only — all items are implementation tasks, not bug fixes.

---

## Phase 0 — Critical Security Foundations

> Anything that can delete unintended data, expose secrets, bypass authorization, execute arbitrary commands, corrupt evidence, or compromise recovery keys must be addressed before any destructive feature.

### P0-01: Project Scaffold & Technology Selection
**Priority:** CRITICAL
**Task:** Choose backend language/framework and initialize project structure.
**Why:** No code exists. All implementation depends on a chosen stack.
**Spec reference:** `.env.example` (suggests Python/FastAPI), `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_PLAN.md` Phase 1
**Deliverables:**
- Confirm language/framework (recommendation: Python with FastAPI — port 8000 and SQLite in `.env.example` are strong signals)
- Create project structure
- Set up dependency management (requirements.txt or pyproject.toml)
- Implement configuration loading from environment variables
- Implement structured logging (consistent with `docs/CLAUDE_TASKS.md` TASK-001)
- Set up testing framework (pytest or equivalent)
- Create `.gitignore` excluding secrets
**Validation:** Project initializes; health endpoint returns 200; structured logs work; config loads from env

### P0-02: Path Traversal & Filesystem Safety
**Priority:** CRITICAL
**Task:** Implement path canonicalization, allowed-root enforcement, reparse-point rejection, and target revalidation.
**Why:** Without this, any destructive operation could delete unintended data. This is the #1 security concern.
**Spec reference:** `docs/SECURITY.md`, `docs/WINDOWS_NTFS_NOTES.md`, `docs/ERASURE_ENGINE_SPEC.md`, `docs/PRIVILEGE_BOUNDARY.md`
**Deliverables:**
- Path canonicalization function (handle `\\?\` prefix, normalize `..`, resolve relative paths)
- Allowed-root enforcement function
- Reparse-point detection and rejection function (junctions, symlinks, ADS)
- Target identity revalidation function (recheck path identity immediately before destructive mutation)
- System-drive protection (reject `C:\`, `Windows`, `Program Files`, system volumes by default)
- Unit tests for all safety functions
**Validation:** Path traversal attempts are rejected; system-drive paths are rejected; reparse points are detected and rejected; target identity is revalidated before each destructive operation

### P0-03: Privilege Boundary — Structured Protocol Only
**Priority:** CRITICAL
**Task:** Design and implement the privileged service protocol. Ensure NO arbitrary command execution surface exists.
**Why:** The architecture requires that the API never exposes `execute_command`, `powershell`, `cmd`, `arbitrary executable`, or `arbitrary script`.
**Spec reference:** `docs/PRIVILEGE_BOUNDARY.md`, `docs/ARCHITECTURE_DECISIONS.md` ADR-004
**Deliverables:**
- Define structured privileged request schema (inspect_target, delete_file, delete_tree, prepare_recovery_object, restore_recovery_object, scan_scope)
- Implement request validation (operation type, normalized target, allowed root, expected target identity, operation ID, actor authorization, policy ID)
- Return structured status, not shell output
- Implement response validation (no shell output in responses)
- Write tests confirming no arbitrary command surface exists
**Validation:** No command-execution endpoint exists; privileged requests are strictly validated; responses contain no shell output

### P0-04: Cryptographic Primitives Selection
**Priority:** CRITICAL
**Task:** Select and configure vetted cryptographic libraries.
**Why:** All cryptographic operations must use established libraries. Manual implementation of AES/Ed25519 is explicitly forbidden.
**Spec reference:** `docs/CRYPTO_KEY_MANAGEMENT.md`, `docs/SECURITY.md`, `CLAUDE.md` ("Use vetted cryptographic libraries. Never implement AES/Ed25519 primitives manually.")
**Deliverables:**
- Select and configure cryptography library (e.g., Python `cryptography` package)
- Implement SHA-256 hashing (streaming for large files)
- Implement AES-256-GCM encryption for vault
- Implement Ed25519 signing for evidence/certificates
- Implement secure random number generation
- Implement key separation (vault keys vs. signing keys vs. session secrets)
- Write tests for each cryptographic operation
**Validation:** Each primitive works correctly; streaming hashing handles large files; keys are never returned in API responses; signing/verification round-trip succeeds

---

## Phase 1 — Core Correctness

> Implement the state machine, target validation, erasure, recovery, and residual scanning with evidence emission.

### P1-01: Operation State Machine
**Priority:** HIGH
**Task:** Implement the full state machine with transition validation.
**Spec reference:** `reference/OPERATION_STATES.md`, `docs/ARCHITECTURE.md`, `docs/CLAUDE_TASKS.md` TASK-003
**Deliverables:**
- State machine with states: CREATED, ANALYZING, READY, ERASING, VERIFYING, RECOVERY_TEST, RESIDUAL_SCAN, ASSESSING, CERTIFYING, COMPLETED
- Failure states: PARTIAL, FAILED, INCONCLUSIVE, CANCELLED
- Transition validation (reject invalid transitions)
- Progress tracking (progress_percent)
- Duplicate-request detection
- Crash recovery mechanism
- Unit tests for all transitions
**Validation:** Invalid transitions are rejected; operations can progress through the full lifecycle; crash recovery preserves state

### P1-02: Target Analysis
**Priority:** HIGH
**Task:** Implement file/folder discovery, SHA-256 hashing, storage profiling, dry-run, and sensitivity analysis.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-002, `docs/DATA_MODEL.md`, `docs/OPENAPI.yaml`
**Deliverables:**
- Target discovery (enumerate files, directories, metadata)
- Streaming SHA-256 hashing
- Storage profiling (volume, filesystem, media type, encryption status, capabilities, limitations)
- Dry-run mode
- Sensitivity analysis (initial/AI-assisted)
- Unit tests with synthetic fixtures
**Validation:** Targets are correctly discovered and hashed; storage profiles are accurate; dry-run produces no side effects

### P1-03: Erasure Engine (Permanent Deletion)
**Priority:** HIGH
**Task:** Implement permanent deletion for files and folders with evidence recording.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-003, `docs/ERASURE_ENGINE_SPEC.md`
**Deliverables:**
- File deletion (SELECTIVE_PERMANENT)
- Folder deletion (COMPLETE_ERASURE)
- Target manifest freezing
- Pre-erasure revalidation
- Structured result recording
- Postcondition verification
- Partial/failure handling (PARTIAL, FAILED, INCONCLUSIVE)
- Progress reporting
- Evidence event emission
- Unit and integration tests with synthetic fixtures
**Validation:** Files are deleted; state transitions correctly; evidence events are recorded; partial failures are reported correctly; system-drive paths are rejected

### P1-04: Recovery Test Engine
**Priority:** HIGH
**Task:** Implement recovery testing with baseline and post-erasure experiments.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-004, `docs/RECOVERY_ENGINE_SPEC.md`
**Deliverables:**
- Baseline recovery experiment (before erasure)
- Post-erasure recovery experiment
- Result vocabulary: RECOVERED, NOT_RECOVERED, PARTIALLY_RECOVERED, INCONCLUSIVE, NOT_RUN
- Recovery test safety controls (only controlled test media)
- Evidence emission
- Unit and integration tests
**Validation:** Recovery tests produce valid results; baseline vs. post-erasure comparison works; INCONCLUSIVE is used where evidence is insufficient

### P1-05: Residual Scanner
**Priority:** HIGH
**Task:** Implement residual artifact detection and classification.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-005, `docs/RESIDUAL_ANALYSIS_SPEC.md`
**Deliverables:**
- Scan scope definition
- Artifact detection (filename remnants, metadata, temp files, cache, thumbnails, fragments)
- Finding structure (ID, artifact type, path, timestamp, hash/similarity, relationship confidence, sensitivity, risk, explanation)
- AI-assisted classification
- Unit tests with synthetic fixtures
**Validation:** Artifacts are detected; findings include all required fields; false positive rate is measured

### P1-06: Assurance Engine
**Priority:** MEDIUM
**Task:** Implement assurance scoring with explainability and limitation documentation.
**Spec reference:** `OBLIVION.md` Section 22, `docs/PROJECT_SPEC.md`
**Deliverables:**
- Assurance scoring from recovery result, residual result, storage confidence
- Explainability (reasons for each score component)
- Limitation documentation
- Result vocabulary: LOW, MEDIUM, HIGH, INCONCLUSIVE
- Unit tests
**Validation:** Assurance scores are computed from evidence; explanations are included; limitations are documented

---

## Phase 2 — Security

> Implement RBAC, vault, cryptography, privilege boundary, and audit.

### P2-01: Authentication & RBAC
**Priority:** HIGH
**Task:** Implement JWT authentication and role-based access control.
**Spec reference:** `docs/OPENAPI.yaml` (bearerAuth), `docs/PROJECT_SPEC.md` (user roles), `docs/SECURITY.md`
**Deliverables:**
- User authentication (password hashing, session/token handling)
- RBAC with roles: OPERATOR, RECOVERY_AUTHORIZED, AUDITOR, ADMINISTRATOR
- Server-side authorization for every sensitive operation
- Recovery authorization workflow
- Audit logging for security events
- Unit tests
**Validation:** Unauthorized operations are blocked; role enforcement works server-side; audit events are recorded

### P2-02: Recovery Vault
**Priority:** HIGH
**Task:** Implement AES-256-GCM encrypted recovery vault with key management and authorized restore.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-006, `docs/CRYPTO_KEY_MANAGEMENT.md`, `docs/PRIVILEGE_BOUNDARY.md`
**Deliverables:**
- Vault storage (AES-256-GCM authenticated encryption)
- Unique key per recovery object
- Key reference in database (never return keys via API)
- Recovery object lifecycle (create, store, authorize, restore, expire, destroy)
- Retention/expiration (7/30/90 days)
- Restore destination validation
- SHA-256 comparison after restore
- Unauthorized restore blocking
- Vault audit logging
- Unit tests
**Validation:** Recovery objects are encrypted; keys are never exposed; unauthorized restore is blocked; authorized restore produces matching SHA-256; expired objects are destroyed

### P2-03: Evidence Engine & Audit Log
**Priority:** HIGH
**Task:** Implement tamper-evident evidence event chain.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-007, `docs/CERTIFICATE_FORMAT.md`, `docs/ARCHITECTURE_DECISIONS.md` ADR-005
**Deliverables:**
- Evidence canonicalization (deterministic serialization)
- Hash chain (each event includes previous event hash)
- Structured event recording (operation ID, sequence, event type, timestamp, canonical payload hash, previous event hash, actor ID)
- Schema version and software version in evidence
- Unit tests
**Validation:** Evidence is canonical; hash chain detects tampering; schema version and software version are included

### P2-04: Certificate Engine
**Priority:** HIGH
**Task:** Implement Ed25519-signed certificate generation and verification.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-007, `docs/CERTIFICATE_FORMAT.md`
**Deliverables:**
- Certificate generation (all required fields from CERTIFICATE_FORMAT.md)
- Ed25519 signing of canonical evidence
- Certificate verification (schema validity, evidence hash, signature, signer key identity, version compatibility)
- Tamper detection (modified evidence → invalid certificate)
- Unit tests
**Validation:** Valid certificates verify; modified evidence fails verification; modified signature fails verification

### P2-05: Audit & Security Events
**Priority:** MEDIUM
**Task:** Implement tamper-evident audit logging for security events.
**Spec reference:** `docs/OBLIVION.md` Section 26, `docs/DATA_MODEL.md` (SecurityEvent)
**Deliverables:**
- Security event recording (unauthorized recovery, auth failures, policy changes, privilege escalation)
- Structured, safe metadata (no sensitive plaintext)
- Unit tests
**Validation:** Security events are recorded; no sensitive data in logs; event integrity is protected

---

## Phase 3 — AI

> Implement AI sensitivity, residual classification, risk assessment, and Omniroute integration.

### P3-01: AIProvider Abstraction & Omniroute Adapter
**Priority:** HIGH
**Task:** Create AI provider abstraction and Omniroute integration.
**Spec reference:** `docs/AI.md`, `docs/OMNIROUTE_INTEGRATION.md`, `docs/IMPLEMENTATION_NOTES.md`
**Deliverables:**
- `AIProvider` abstract interface
- `OmnirouteProvider` implementation with timeout and bounded retries
- Optional `LocalProvider` for offline operation
- Structured output schema validation (per `reference/AI_OUTPUT_SCHEMA.json`)
- Safe fallback when AI is unavailable (deterministic analysis continues)
- Unit tests with mocked provider responses
**Validation:** AI calls are schema-validated; timeouts trigger safe fallback; model/provider metadata is included; no destructive tool access

### P3-02: Sensitivity Classification
**Priority:** HIGH
**Task:** Implement AI-assisted sensitive data detection.
**Spec reference:** `docs/AI.md`, `docs/FEATURES.md` (P1)
**Deliverables:**
- Regex-based detection
- Structured data analysis
- Category classification (names, emails, phones, addresses, financial, credentials)
- Sensitivity levels: PUBLIC, INTERNAL, CONFIDENTIAL, CRITICAL
- Explanation generation
- Unit tests with synthetic data
**Validation:** Sensitivity levels are correctly assigned; explanations are included; deterministic rules provide fallback

### P3-03: Residual Classification & Risk Assessment
**Priority:** MEDIUM
**Task:** Implement AI-assisted residual artifact classification and recovery risk assessment.
**Spec reference:** `docs/AI.md` (Sections 2 and 3)
**Deliverables:**
- Residual artifact classification (type, relationship hypothesis, sensitivity, qualitative risk)
- Recovery risk assessment (factors: filesystem, storage type, encryption, deletion method, TRIM, allocation)
- Risk levels: LOW, MEDIUM, HIGH, INCONCLUSIVE
- Explainability
- Unit tests
**Validation:** Classifications are schema-validated; risk levels are qualitative; explanations are included; no fabricated recovery percentages

### P3-04: Policy Recommendation
**Priority:** MEDIUM
**Task:** Implement AI-assisted policy recommendation from allowlist.
**Spec reference:** `docs/AI.md` Section 4, `reference/POLICY_IDS.md`
**Deliverables:**
- AI recommends from allowlist only
- Allowlisted policies: ERASURE.LOGICAL.SELECTIVE.V1, ERASURE.LOGICAL.TREE.V1, ERASURE.RECOVERABLE.ENCRYPTED.V1
- Deterministic policy engine remains authoritative
- Unit tests
**Validation:** AI recommendations are constrained to allowlist; deterministic engine decides what actually executes; AI cannot create new policies

---

## Phase 4 — BoltAI Integration

> Complete the OpenAPI contract, error handling, operation polling, and frontend contract tests.

### P4-01: OpenAPI Completion & Validation
**Priority:** HIGH
**Task:** Complete the OpenAPI contract and validate it.
**Spec reference:** `docs/OPENAPI.yaml`, `docs/API.md`, `frontend/FRONTEND_API_CONTRACT.md`
**Deliverables:**
- Add error schema definition to OpenAPI components
- Add health endpoint
- Add missing endpoints (user management, settings, assurance)
- Add correlation/request ID support
- Add idempotency where appropriate
- Add versioning strategy
- Validate OpenAPI with a schema validator
- Generate typed client models
**Validation:** OpenAPI validates without errors; all endpoints have complete schemas; error codes are documented

### P4-02: Error Handling & API Polish
**Priority:** HIGH
**Task:** Implement structured error handling matching the error code list.
**Spec reference:** `reference/ERROR_CODES.md`, `docs/API.md` (standard error shape)
**Deliverables:**
- Implement all error codes with safe human-readable messages
- Map errors to HTTP status codes
- Include retryable flag and request/correlation ID
- Frontend-compatible error shapes
- Unit tests
**Validation:** All error codes return correct HTTP status; errors include code, message, retryable, and request_id

### P4-03: Operation Polling & Streaming
**Priority:** MEDIUM
**Task:** Implement long-running operation observation.
**Spec reference:** `frontend/FRONTEND_API_CONTRACT.md` (suggested client flow)
**Deliverables:**
- Operation status endpoint with progress
- Evidence events streaming or polling
- Frontend-compatible state transitions
- Support for PARTIAL and INCONCLUSIVE states
- Unit tests
**Validation:** Frontend can observe operation progress; state transitions are accurate; INCONCLUSIVE is handled as uncertainty, not success

### P4-04: Certificate Verification Endpoint
**Priority:** MEDIUM
**Task:** Implement certificate verification endpoint for BoltAI.
**Spec reference:** `docs/OPENAPI.yaml` (`POST /api/certificates/{certificate_id}/verify`), `docs/API.md`
**Deliverables:**
- Implement verification endpoint
- Return valid/invalid, evidence integrity, signature valid, reason
- Unit tests
**Validation:** Valid certificates verify successfully; modified certificates fail verification

### P4-05: Frontend Contract Tests
**Priority:** MEDIUM
**Task:** Implement contract tests to verify API compatibility with BoltAI.
**Spec reference:** `frontend/FRONTEND_API_CONTRACT.md`, `docs/API.md`
**Deliverables:**
- Contract tests for every endpoint
- Error case testing
- State compatibility testing
- Version compatibility testing
- Unit/integration tests
**Validation:** All contract tests pass; API changes are validated against contracts

---

## Phase 5 — Demo & Hardening

> Synthetic demo data, end-to-end flow, benchmarking, and polished API behavior.

### P5-01: Synthetic Test Data & Demo Environment
**Priority:** HIGH
**Task:** Create synthetic test data and demo environment.
**Spec reference:** `docs/TEST_DATA_GENERATOR_SPEC.md`, `reference/DEMO_SEED_DATA.md`, `docs/DEMO.md`
**Deliverables:**
- Generate synthetic demo dataset (confidential_customer_data.csv, employee_records.csv, ordinary_document.txt, recoverable_project_notes.md, temp files, nested directories)
- Known ground truth (expected sensitivity, SHA-256, file relationships, deletion mode, recovery outcome)
- Demo script for 5 scenes
- Unit and integration tests
**Validation:** All data is synthetic; ground truth is documented; demo scenes are executable

### P5-02: End-to-End Test Scenarios
**Priority:** HIGH
**Task:** Implement the three required end-to-end test scenarios.
**Spec reference:** `docs/TEST_PLAN.md`
**Deliverables:**
- Scenario 1: create synthetic file → hash → baseline recovery → permanent deletion → post-recovery test → residual scan → assurance → certificate → certificate verification
- Scenario 2: create synthetic file → hash → controlled recoverable deletion → original removed → unauthorized restore blocked → authorized restore → SHA-256 matches
- Scenario 3: valid certificate → modify evidence → verification fails
- Unit/integration tests
**Validation:** All three scenarios pass; unauthorized restores are blocked; modified evidence fails verification

### P5-03: Security Tests
**Priority:** HIGH
**Task:** Implement comprehensive security tests.
**Spec reference:** `docs/TEST_PLAN.md` (Security section), `docs/SECURITY_REVIEW_CHECKLIST.md`
**Deliverables:**
- Traversal rejection tests
- System-drive protection tests
- Invalid policy rejection tests
- Unauthorized restore blocking tests
- Malformed AI response rejection tests
- AI timeout fallback tests
- Vault key protection tests
- Privilege escalation tests
- Unit/integration tests
**Validation:** All security tests pass; no bypasses exist

### P5-04: Failure-Mode Tests
**Priority:** MEDIUM
**Task:** Implement failure-mode tests.
**Spec reference:** `docs/TEST_PLAN.md` (Failure tests)
**Deliverables:**
- Source disappearance during operation
- Target changes during operation
- Permission denied handling
- Disk full handling
- Vault write failure handling
- Recovery test inconclusive handling
- Residual scan error handling
- Unit/integration tests
**Validation:** All failure modes are handled gracefully; no silent success; appropriate error states are set

### P5-05: Performance & Benchmarking
**Priority:** LOW
**Task:** Implement performance benchmarks and optimize.
**Spec reference:** `docs/BENCHMARK_PROTOCOL.md`, `docs/IMPLEMENTATION_NOTES.md` (performance section)
**Deliverables:**
- Streaming hashing verification
- Memory bounding verification
- Duplicate hashing prevention
- Bounded concurrency verification
- Benchmark suite (erasure GB/min, files/sec, recovery rates, residual detection rates)
- Unit/integration tests
**Validation:** Performance meets benchmarks; memory is bounded; no unnecessary duplicate hashing

### P5-06: Hardening & SIH Readiness
**Priority:** MEDIUM
**Task:** Final hardening and SIH demo preparation.
**Spec reference:** `docs/CLAUDE_TASKS.md` TASK-010, `docs/DEMO.md`, `docs/SECURITY_REVIEW_CHECKLIST.md`
**Deliverables:**
- Complete security checklist
- Integration tests pass
- End-to-end demo ready
- Limitations documented
- `docs/LIMITATIONS.md` reviewed and updated
- Approved wording compliance verified
**Validation:** Security review checklist is complete; all tests pass; demo runs successfully; no forbidden wording

---

## Risk Register (Implementation)

| ID | Risk | Phase | Mitigation |
|---|---|---|---|
| RISK-IMP-001 | Path traversal vulnerability during implementation | Phase 0 | Implement canonicalization and allowed roots before any destructive code |
| RISK-IMP-002 | System-drive accidental deletion | Phase 0 | Implement protected path check as first filesystem function |
| RISK-IMP-003 | Arbitrary command execution surface | Phase 0 | Prohibit execute_command/powershell/cmd at the API and privileged service level |
| RISK-IMP-004 | Manual crypto implementation | Phase 0 | Use vetted libraries only; code review for crypto usage |
| RISK-IMP-005 | Evidence tampering goes undetected | Phase 2 | Implement hash chain + Ed25519 signing + verification tests |
| RISK-IMP-006 | AI output reaches destructive operations | Phase 3 | Schema validation; deterministic policy engine authoritative |
| RISK-IMP-007 | Vault key exposure | Phase 2 | Key reference pattern; never return keys via API; separate key storage |
| RISK-IMP-008 | False irrecoverability claims | Phase 1 | Use approved wording; INCONCLUSIVE for insufficient evidence |
| RISK-IMP-009 | Database/fs state inconsistency | Phase 1 | Transaction boundaries; target revalidation before mutation |
| RISK-IMP-010 | Unauthorized recovery | Phase 2 | RBAC enforcement; recovery authorization workflow |

---

## Implementation Sequence Summary

```
Phase 0 (Critical Security):
  ├── P0-01: Project scaffold
  ├── P0-02: Path traversal protection
  ├── P0-03: Privilege boundary
  └── P0-04: Crypto primitives

Phase 1 (Core Correctness):
  ├── P1-01: State machine
  ├── P1-02: Target analysis
  ├── P1-03: Erasure engine
  ├── P1-04: Recovery test engine
  ├── P1-05: Residual scanner
  └── P1-06: Assurance engine

Phase 2 (Security):
  ├── P2-01: Auth/RBAC
  ├── P2-02: Recovery vault
  ├── P2-03: Evidence engine & audit
  ├── P2-04: Certificate engine
  └── P2-05: Audit & security events

Phase 3 (AI):
  ├── P3-01: AIProvider & Omniroute
  ├── P3-02: Sensitivity classification
  ├── P3-03: Residual classification & risk
  └── P3-04: Policy recommendation

Phase 4 (BoltAI Integration):
  ├── P4-01: OpenAPI completion
  ├── P4-02: Error handling
  ├── P4-03: Operation polling
  ├── P4-04: Certificate verification
  └── P4-05: Contract tests

Phase 5 (Demo & Hardening):
  ├── P5-01: Synthetic test data
  ├── P5-02: End-to-end scenarios
  ├── P5-03: Security tests
  ├── P5-04: Failure-mode tests
  ├── P5-05: Performance & benchmarks
  └── P5-06: Hardening & SIH readiness
```

---

## Vertical Slice — First End-to-End Path

Per `docs/IMPLEMENTATION_NOTES.md`, the first vertical slice is:

```
Analyze → Hash → Dry-run → Permanent Delete → Recovery Test → Residual Scan → Assurance → Certificate
```

This path should be implemented before broadening to other features. It combines elements from Phase 0 (crypto, path safety) and Phase 1 (state machine, target analysis, erasure, recovery, residual, assurance, certificates) into a single testable workflow.

After this vertical slice passes, proceed to:
- Controlled Recoverable Deletion → Vault → Authorization → Restore → Hash Verification
- AI Sensitivity → Risk Analysis → Policy Recommendation
