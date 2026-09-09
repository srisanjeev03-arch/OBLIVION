# Oblivion — Deletion & Recovery Engine
## Features, Existing Apps to Study, and Build Prompts

Project split:
1. Frontend
2. Deletion & Recovery Engine
3. Audit Log & Authentication

This document covers Part 2 only.

## 1. Deletion Features

- File/folder/multi-file selection
- Recursive discovery
- Target fingerprint
- Target ID
- File count and total size
- File-type distribution
- Metadata collection
- SHA-256 hashing
- Storage/filesystem profiling
- Scope preview
- Safe-root validation
- System-drive protection
- Oblivion-path protection
- Symlink/junction/reparse-point handling
- Scope containment
- TOCTOU-aware revalidation
- Dry-run
- Pre-erasure baseline
- Selective Permanent Deletion
- Complete Supported Erasure
- Controlled Recoverable Deletion
- Policy-driven erasure strategy
- Capability detection
- Unsupported-method handling
- Explicit scope/limitation reporting
- Authorization handoff
- Operation state machine
- Progress reporting
- Per-item success/failure
- Partial-operation handling
- Cancellation
- Crash/state reconciliation
- Post-operation verification

## 2. Recovery Features

- Deleted-file detection
- Filesystem-aware recovery
- Deleted-entry/metadata recovery
- Unallocated-space scanning
- File-signature/carving
- Configurable scan scope
- File-type filtering
- Recovery preview
- Separate recovery destination
- RECOVERED result
- NOT_DETECTED result
- PARTIAL result
- FAILED result
- INCONCLUSIVE result
- Recovery confidence/qualification
- Recovery evidence
- Original-vs-recovered SHA-256 comparison
- Recovery logs
- Source protection
- Read-only recovery scanning
- Destination validation
- No silent overwrite
- Resource/time limits
- Cancellation
- Crash-safe recovery state

## 3. Remnant / Residual Analysis

- Post-erasure scan
- Before/after comparison
- Filename traces
- Metadata traces
- Deleted filesystem entries
- Content fragments
- File signatures
- Unallocated-space residuals
- Temporary files
- Cache artifacts
- Thumbnail artifacts
- Derivative files
- Related-file detection
- Original hash matching
- Content similarity
- Sensitivity classification
- Residual risk classification
- DIRECT_MATCH
- LIKELY_RELATED
- POSSIBLY_RELATED
- UNRELATED
- INCONCLUSIVE
- Residual evidence
- Residual scope declaration
- Unsupported-scope declaration
- “Why is this still here?” explanation
- Recovery/residual correlation

## 4. Existing Apps to Study

### Deletion
- Microsoft SDelete — secure deletion, free-space handling, NTFS-aware behavior, CLI
- BleachBit — preview, selective cleaning, cleaner/rule architecture
- Revo Uninstaller — pre-operation tracing, leftover discovery, operation history
- Eraser — secure file/folder deletion and erasure methods

### Recovery
- TestDisk — filesystem-aware recovery and deleted entries
- PhotoRec — signature-based carving and unallocated-space scanning
- R-Studio — intelligent scanning, recovery assessment, preview, imaging architecture
- DMDE — quick/full scans, deleted-file recovery, source/destination separation
- Windows File Recovery — Windows-native recovery modes
- Recuva — deep scan, recoverability indication, preview

### Forensic/Evidence Concepts
- Autopsy / The Sleuth Kit — evidence organization, timelines, artifacts
- FTK / FTK Imager — evidence handling, hashing, verification
- EnCase — forensic case/evidence organization

Borrow capabilities and architectural ideas; do not copy implementations.

## 5. Engine Architecture

    DELETION & RECOVERY ENGINE
              |
      +-------+-------+
      |       |       |
    TARGET  DELETION RECOVERY
    ENGINE  ENGINE   ENGINE
      |       |       |
   Scope   Strategy  Scanner
   Hash    Executor  FS Adapter
   Profile Verify   Metadata
                    Carving
              |
        RESIDUAL ANALYZER
              |
        BEFORE / AFTER
              |
        ASSURANCE INPUTS
              |
       ENGINE EVENT INTERFACE
              |
       AUDIT / AUTH MODULE

The engine owns deletion, recovery, residual analysis, target discovery, hashing, verification and operation results.

The engine does NOT own:
- authentication
- users
- roles
- sessions
- authoritative audit storage

It emits structured events/results to Part 3.

## 6. Prompt 1 — Reconcile the Existing Repository

You are implementing Part 2 of Oblivion: THE DELETION & RECOVERY ENGINE.

The project is split into:
1. FRONTEND
2. DELETION & RECOVERY ENGINE — YOUR RESPONSIBILITY
3. AUDIT LOG & AUTHENTICATION

Do not implement the frontend.
Do not implement the audit/auth subsystem.
Do not move authentication or authoritative audit ownership into the engine.

Before writing code:
1. Recursively inspect the repository.
2. Read all existing Markdown specifications relevant to architecture, deletion/erasure, recovery, residual analysis, safety, state machine, data model, API/OpenAPI, security, Windows/NTFS, limitations and tests.
3. Inspect source and tests.
4. Identify existing code and missing components.
5. Preserve documented architecture.
6. Produce ENGINE_RECONCILIATION.md.

Include:
- existing engine code
- existing tests
- relevant specifications
- missing components
- conflicts
- module boundaries
- API/engine interface
- engine/audit-auth interface
- safety boundaries
- implementation order
- test strategy

Do not implement major deletion/recovery functionality yet.
Stop after the reconciliation report.

## 7. Prompt 2 — Target Discovery and Safety

Implement the first engine slice:
TARGET DISCOVERY + SAFE SCOPE VALIDATION.

Implement:
- file/folder discovery
- recursive enumeration
- target fingerprint
- SHA-256 hashing
- metadata collection
- storage/filesystem profile
- safe-root validation
- system-drive protection
- protected-path protection
- symlink/junction/reparse handling
- dry-run

Do NOT implement permanent deletion, drive wiping, recovery, authentication or authoritative audit storage.

Requirements:
- stable target_id
- normalized paths
- OBLIVION_ALLOWED_ROOTS
- traversal rejection
- system-volume protection
- Oblivion-data protection
- no following links outside scope
- immediate revalidation before destructive operations
- deterministic structured results

States:
SAFE
RESTRICTED
BLOCKED
UNAVAILABLE
REQUIRES_AUTHORIZATION

Tests:
- valid file
- valid directory
- recursive directory
- outside allowed root
- traversal
- system drive
- Oblivion path
- symlink
- junction
- missing target
- permission failure
- target changed before revalidation
- hash correctness
- empty directory
- large file

Run the actual test suite. Do not claim success unless tests execute and pass.

## 8. Prompt 3 — Deletion Engine

Implement the Oblivion DELETION ENGINE.

Supported initial modes:
1. SELECTIVE_PERMANENT_DELETION
2. COMPLETE_SUPPORTED_ERASURE
3. CONTROLLED_RECOVERABLE_DELETION

Do not claim that ordinary file deletion guarantees physical media sanitization.

NIST SP 800-88 Rev. 2 is the current NIST sanitization reference and defines sanitization in terms of making access to target data infeasible for a given level of effort. It also emphasizes appropriate standards/approved techniques and validation.

Implement:
- ErasureStrategy
- ErasureExecutor
- ErasureVerifier
- ErasureResult
- ErasureCapabilities

Required:
1. receive validated target
2. revalidate immediately before execution
3. require explicit operation configuration
4. never expand scope
5. create pre-erasure baseline
6. execute only allowlisted operations
7. track per-item success/failure
8. handle partial failures
9. support safe cancellation where feasible
10. verify expected post-operation state
11. return structured evidence data
12. emit engine events instead of writing the authoritative audit log

Recoverable deletion:
- hash original
- create recovery package
- encrypt with vetted AES-256-GCM
- store through recovery-vault abstraction
- verify vault round-trip
- only then remove original
- return original hash and recovery-object metadata

Do not implement global wiping or arbitrary shell commands.
Do not claim SSD/NVMe physical sanitization from file deletion.

Tests must cover successful deletion, recursion, dry-run, protected target, scope expansion, target changes, partial failure, vault round-trip, hash preservation, restore hash equality, vault failure before original deletion, invalid destination and cancellation/error states.

Run actual tests.

## 9. Prompt 4 — Recovery Engine

Implement the Oblivion RECOVERY ENGINE.

Initial scope:
- controlled test directory/volume
- Windows/NTFS-oriented architecture
- filesystem-aware recovery
- deleted-entry detection where safely supported
- configurable scanning
- recovery to a separate destination

Architecture:
RecoveryEngine
  -> RecoveryScanner
  -> FilesystemAdapter
  -> MetadataRecoveryAdapter
  -> SignatureCarver
  -> RecoveryVerifier
  -> RecoveryResult

Results:
RECOVERED
NOT_DETECTED
PARTIAL
FAILED
INCONCLUSIVE
UNSUPPORTED

Safety:
1. recovery scanning must not modify source
2. source is read-only during analysis
3. never restore into source by default
4. validate recovery destination separately
5. no silent overwrite
6. resource/time limits
7. cancellation
8. preserve recovery evidence
9. SHA-256 recovered files
10. compare to known original hashes when available
11. distinguish exact, partial, probable, unrelated and inconclusive
12. never fabricate confidence

Future adapters should be possible for NTFS, FAT/exFAT, ext-family filesystems and disk images.

Tests:
- source protection
- separate destination
- exact recovery
- partial recovery
- unrelated candidate
- corrupted candidate
- hash match
- hash mismatch
- unsupported filesystem
- invalid destination
- cancellation
- scan limits

Run actual tests.

## 10. Prompt 5 — Residual Analyzer

Implement the Oblivion RESIDUAL ANALYZER.

Purpose:
After deletion, determine what evidence of the target remains within the explicitly tested scope.

Do not claim that a software scan proves that no representation exists anywhere on physical media.

Architecture:
ResidualAnalyzer
  -> ResidualScanner
  -> ArtifactDetector
  -> HashMatcher
  -> SimilarityAnalyzer
  -> RelationshipAnalyzer
  -> ResidualClassifier

Detect where supported:
- filename traces
- metadata traces
- deleted filesystem entries
- content fragments
- file signatures
- unallocated-space candidates
- temporary artifacts
- cache artifacts
- thumbnails
- derivatives
- related files

Classifications:
DIRECT_MATCH
LIKELY_RELATED
POSSIBLY_RELATED
UNRELATED
INCONCLUSIVE

Each finding includes:
- finding_id
- target_id
- detection technique
- scope
- evidence
- qualification/confidence
- classification
- sensitivity if known
- risk
- limitation

Implement:
1. pre-erasure baseline
2. post-erasure scan
3. original hash matching
4. candidate relationship detection
5. residual risk classification
6. “Why is this still here?” explanation
7. unsupported-scope reporting

No fake percentages.

## 11. Prompt 6 — Integrate the Engine

Integrate:
DISCOVER
-> ANALYZE
-> BASELINE
-> AUTHORIZE
-> ERASE
-> VERIFY
-> RECOVERY_TEST
-> RESIDUAL_SCAN
-> ASSESS

Use the existing Oblivion state machine. Do not invent a second one.

States:
CREATED
ANALYZING
READY
ERASING
VERIFYING
RECOVERY_TEST
RESIDUAL_SCAN
ASSESSING
CERTIFYING
COMPLETED

Terminal failure states:
PARTIAL
FAILED
INCONCLUSIVE
CANCELLED

OperationResult must contain:
- operation_id
- target_id
- mode
- scope
- baseline
- erasure method/capability
- erasure result
- verification result
- recovery result
- residual findings
- limitations
- assurance inputs
- evidence references
- final status

The engine does not own authentication or authoritative audit storage.

Expose a structured event interface such as:
EngineEventEmitter.emit(event)

Test:
A. normal deletion -> recovery test
B. permanent deletion -> verify -> residual scan
C. recoverable deletion -> encrypted vault -> delete -> authorized restore -> hash comparison
D. failure -> PARTIAL/FAILED with preserved evidence

## 12. Prompt 7 — Production Hardening

Perform a security hardening review of the Deletion & Recovery Engine.

Review:
- path traversal
- normalization
- symlinks
- junctions
- reparse points
- TOCTOU
- scope expansion
- protected paths
- system-drive targeting
- race conditions
- partial deletion
- cancellation
- crash recovery
- concurrency
- permission failures
- source modification during recovery
- destination traversal
- overwrite behavior
- recovered-data leakage
- resource exhaustion
- authenticated encryption
- key handling
- plaintext lifetime
- hash correctness
- baseline consistency
- deterministic results
- API/engine boundary
- audit/auth boundary
- privileged-service boundary
- AI advisory-only rule

Run:
- unit tests
- integration tests
- security tests
- concurrency tests where applicable
- static analysis
- type checking

Do not modify the frontend.
Do not weaken safety checks to make tests pass.

Produce ENGINE_SECURITY_REVIEW.md.

Classify:
CRITICAL
HIGH
MEDIUM
LOW
INFORMATIONAL

Fix CRITICAL/HIGH findings before declaring the engine production-ready.

## 13. Recommended Build Order

1. Repository/spec reconciliation
2. Target discovery
3. Path/scope safety
4. Hashing + baseline
5. Storage profiling
6. Dry-run
7. Selective deletion
8. Complete supported erasure
9. Recovery vault
10. Recovery scanner
11. Recovery verification
12. Residual analyzer
13. Before/after comparison
14. Integrated operation pipeline
15. API integration
16. Security hardening
17. Performance testing
18. Demo/test dataset

## 14. Definition of Done

- destructive operations are allowlisted
- protected paths cannot be targeted
- system-drive protection works
- scope cannot silently expand
- dry-run is non-destructive
- target hashes are reproducible
- deletion results are deterministic
- partial failures are represented
- recovery scanning never modifies source
- recovery uses a separate validated destination
- recovered files can be hash-verified
- residual findings contain evidence
- unsupported capabilities are explicit
- no fake confidence values
- engine events are structured
- audit/auth remain separate
- actual automated tests execute
- security tests pass
- no unexplained skips
- no universal irrecoverability claim

## 15. Product Positioning

Oblivion is not simply “secure delete + undelete”.

The engine should demonstrate:

TARGET
-> UNDERSTAND
-> BASELINE
-> DELETE
-> ATTEMPT RECOVERY
-> FIND REMNANTS
-> COMPARE
-> ASSESS
-> PRODUCE EVIDENCE

The differentiator is closed-loop validation of deletion rather than merely issuing a delete command.
