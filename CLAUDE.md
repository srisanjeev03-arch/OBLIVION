# OBLIVION — Claude Code Master Instructions

## Project Identity

**Name:** Oblivion  
**Full name:** Oblivion — Intelligent Data Erasure, Recovery & Verification Platform

Oblivion is a Windows-first, NTFS-focused security platform for controlled data erasure, controlled recovery, residual analysis, assurance assessment, and cryptographically verifiable evidence.

### Frontend ownership

The Oblivion frontend is built separately by **BoltAI**.

Claude Code owns:
- backend/API
- filesystem discovery
- storage profiling
- hashing
- erasure engine
- recovery testing
- residual scanning
- recovery vault
- authentication/RBAC
- cryptographic operations
- evidence/audit
- certificate generation and verification
- AI service integration
- privileged Windows boundary
- automated tests
- backend documentation and OpenAPI contract

BoltAI owns:
- web UI
- visual design
- client-side state management
- frontend routing
- dashboard
- forms
- operation progress screens
- recovery screens
- certificate viewer
- audit/evidence viewer
- API client integration

Never move destructive filesystem logic into the frontend.

## Core Product Principle

Oblivion does not merely ask whether a delete command returned success.

It asks:

> What evidence exists that the target data is no longer recoverable within the supported recovery and verification scope?

Use the language:
- assurance
- supported recovery techniques
- residual risk
- recovery test
- evidence
- inconclusive
- supported media/filesystem

Do not claim:
- 100% irrecoverability
- universal forensic resistance
- military-grade deletion
- physical destruction
- guaranteed removal from every backup/snapshot
- guaranteed SSD/NAND physical sanitization

## MVP Scope

Target environment:
- Windows
- NTFS
- controlled test volume / VM / dedicated test drive
- files and folders

Modes:
1. COMPLETE_ERASURE
2. SELECTIVE_PERMANENT
3. CONTROLLED_RECOVERABLE

Required pipeline:

Discover → Analyze → Recommend → Erase → Test Recovery → Analyze Residuals → Assess → Certify

## Safety Rules

1. Never execute arbitrary shell commands from API/UI input.
2. Never allow the AI model to directly choose or execute destructive commands.
3. Use an allowlisted operation policy.
4. Protect system/boot volumes by default.
5. Require explicit confirmation for destructive operations.
6. Normalize and validate paths.
7. Handle symlinks, junctions and reparse points safely.
8. Revalidate target identity immediately before destructive action.
9. Prevent path traversal and target substitution.
10. Do not log sensitive plaintext.
11. Never expose vault keys through API responses.
12. Destructive operations must be deterministic and testable.
13. Fail closed when target identity or safety checks are ambiguous.
14. Use a minimal privileged service rather than running the entire API as administrator.

## Frontend/API Boundary

The canonical integration contract is `docs/OPENAPI.yaml`.

Frontend requests must use structured fields:
- target_id
- operation mode
- policy ID
- confirmation
- recovery authorization where applicable

Never accept:
- raw PowerShell
- raw CMD
- arbitrary executable paths
- arbitrary filesystem commands

The backend returns machine-readable:
- operation ID
- state
- progress
- warnings
- evidence references
- assurance result
- certificate reference

The frontend must render backend truth and must not invent security status.

## Architecture

UI/BoltAI
→ REST API
→ Application Service
→ validated operation policy
→ core engines
→ evidence/assurance
→ signed certificate

Privileged boundary:
Unprivileged API
→ minimal local privileged service
→ structured validated request
→ filesystem operation
→ structured result

## AI Boundary

AI may:
- classify sensitivity
- explain findings
- classify residual artifacts
- estimate qualitative recovery risk
- recommend an allowlisted policy
- explain why a policy was selected

AI may not:
- issue arbitrary commands
- bypass safety controls
- decide authorization
- directly delete files
- modify audit evidence
- generate or retrieve recovery keys
- override deterministic policy checks

Deterministic policy engine remains authoritative.

## Recovery Vault

Controlled recoverable deletion:
1. hash target
2. package target data/metadata according to defined format
3. encrypt using authenticated encryption
4. store recovery object
5. remove original
6. authorize restoration through RBAC
7. restore
8. compare restored hash to original evidence

Use vetted cryptographic libraries. Never implement AES/Ed25519 primitives manually.

## Evidence and Certificates

Evidence must include:
- operation identity
- target identity
- target hash where applicable
- storage profile
- selected policy
- start/end timestamps
- operation results
- recovery test result
- residual scan result
- assurance result
- warnings/failures
- software version

Canonicalize evidence before signing.

Preferred hash: SHA-256.

Use a vetted signature implementation such as Ed25519 where appropriate.

Certificate verification must detect tampering.

## Required Operation State Machine

CREATED
→ ANALYZING
→ READY
→ ERASING
→ VERIFYING
→ RECOVERY_TEST
→ RESIDUAL_SCAN
→ ASSESSING
→ CERTIFYING
→ COMPLETED

Failure/terminal alternatives:
PARTIAL
FAILED
INCONCLUSIVE
CANCELLED

## Definition of Done

A backend feature is not complete until:
- API contract exists
- authorization is checked
- safety validation exists
- failure behavior is defined
- evidence is emitted
- logs are safe
- tests exist
- frontend integration example exists
- OpenAPI is updated
- limitations are documented

## Development Order

1. Repository/config/logging/database/shared schemas
2. Discovery/hashing/dry-run/safety
3. Erasure/state machine/progress/errors
4. Recovery tests/residual scanner
5. Recovery vault/authorization/restore
6. Evidence/tamper-evident event chain/signatures/certificates
7. AI classification/risk/recommendation
8. OpenAPI/frontend integration support
9. hardening/benchmarks/demo validation

## Engineering Style

Prefer:
- typed interfaces
- dependency injection
- deterministic services
- small modules
- structured logging
- explicit error types
- idempotency where practical
- unit + integration + end-to-end tests

Do not silently swallow errors.

Every destructive path must have a testable precondition and postcondition.
