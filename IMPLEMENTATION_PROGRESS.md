# Oblivion Implementation Progress

**Last Updated:** 2026-09-05  
**Current Phase:** Phase 1 — Discovery + Profiling + Dry-run  
**Current Milestone:** Foundation  
**Next Milestone:** Milestone A (end Phase 7)

---

## Status Legend
- **Not Started** — phase not yet begun
- **In Progress** — active development
- **Blocked** — waiting on unresolved dependencies or findings
- **Tests Passing** — functional + security tests green
- **Security Reviewed** — security-reviewer sign-off complete
- **Done** — tests passing + security reviewed + all DoD boxes checked

---

## Quality Gate Rules

1. **Universal blocking condition:** Do NOT advance to the next phase while the current phase has:
   - Any failing test
   - Any unresolved CRITICAL security finding
   - Any unresolved HIGH security finding
   - Inconsistent API contracts
   - Documentation contradicting implementation

2. **Destructive-phase gate (Phases 2, 8, 10):**
   - Serialized (never run two destructive phases concurrently)
   - Mandatory security-reviewer sign-off before merge
   - Must execute against isolated synthetic test volumes only

---

## Phase Status

| Phase | Slice | Destructive | Status | Tests | Security |
|---|---|---|---|---|---|
| 0 Foundation & Primitives | enabler | No | **Done** | N/A | **Reviewed** |
| 1 Discovery + Profiling + Dry-run | S1 | No | **In Progress** | Not Started | Not Started |
| 2 Selective Permanent Deletion | S2 | YES | Not Started | No | No |
| 3 Controlled Recovery Testing | S5 | No | Not Started | No | No |
| 4 Residual Analysis | S6 | No | Not Started | No | No |
| 5 Assurance Engine | S7 | No | Not Started | No | No |
| 6 Evidence Chain | S9 | No | Not Started | No | No |
| 7 Certificates (Milestone A) | S10,S11 | No | Not Started | No | No |
| 8 Complete Erasure | S3 | YES | Not Started | No | No |
| 9 RBAC | S12 | No | Not Started | No | No |
| 10 Vault (Milestone B) | S4 | YES | Not Started | No | No |
| 11 AI Classification | S8 | No | Not Started | No | No |
| 12 Standards Mapping | S13 | No | Not Started | No | No |
| 13 Full Integration (Milestone C) | S14 | No | Not Started | No | No |

---

## DoD Checklist (per phase)
- [ ] API contract exists
- [ ] Authorization checked server-side
- [ ] Safety validation exists
- [ ] Failure behavior defined
- [ ] Evidence emitted
- [ ] Logs safe
- [ ] Tests exist
- [ ] Frontend example exists
- [ ] OpenAPI updated
- [ ] Limitations documented

---

## Milestones
- [ ] A: permanent-delete slice (end Phase 7)
- [ ] B: recoverable slice (end Phase 10)
- [ ] C: SIH-ready (end Phase 13)

---

## Current Phase: Phase 1 — Slice 1

**Goal:** Analyze target (read-only) → TargetProfile + StorageProfile + DryRunPlan

**Completed:**
- Phase 0 architecture approved
- Stack: Python 3.12 + FastAPI + SQLAlchemy 2.0 + cryptography
- 5 blocking gaps resolved (ADR-007 through ADR-011)

**Planned (Slice 1):**
1. Project scaffold (src/oblivion/, tests/)
2. Path-safety library (canonicalize, allowed-roots, reparse)
3. FilesystemProvider abstraction + Windows impl
4. TargetAnalyzer (discovery, metadata, bounded walk)
5. Streaming Hasher (SHA-256)
6. StorageProfiler (volume, FS, media)
7. Dry-run planner (no mutation)
8. POST /api/targets/analyze
9. Security tests (15 cases)
10. OpenAPI update

---

## Architecture Decisions (Phase 0)

| ADR | Decision | Status |
|---|---|---|
| ADR-007 | Stack: Python 3.12 + FastAPI + SQLAlchemy 2.0 + cryptography + SQLite | Approved |
| ADR-008 | OBLIVION_ALLOWED_ROOTS: fail-closed, config-based | Approved |
| ADR-009 | Volume-identity system-drive protection (VolumeSerialNumber) | Approved |
| ADR-010 | DB/FS crash reconciliation: PENDING state + restart reconcile | Approved |
| ADR-011 | Privileged IPC: Named-pipe with DACL + token auth | Approved |

---

## Test Status

**Phase 1 Security Test Matrix (15 cases):**
1. Valid allowed-root target
2. Target outside allowed root
3. Path traversal
4. Parent-directory escape
5. Junction/reparse escape
6. Protected system volume
7. Alternate mount attempt
8. Nonexistent target
9. Permission failure
10. Hash consistency
11. Large-file hashing (memory bounded)
12. Empty file
13. Mixed directory
14. Unicode Windows paths
15. Dry-run no mutation

---

## Known Limitations
1. MVP: Windows + NTFS + controlled test volumes
2. No destructive ops in Slice 1 (read-only)
3. No AI (Phase 11)
4. No full RBAC (Phase 9)

---

## Unresolved Risks

| Severity | Risk | Mitigation |
|---|---|---|
| Medium | SQLite concurrency | MVP single-writer acceptable |
| Low | Dev signing keys | Document separation in CRYPTO_KEY_MANAGEMENT.md |

---

## Next Slice
**Phase 2 — Selective Permanent Deletion (first destructive)**

Prerequisites: Phase 1 tests passing, security reviewed, DoD complete.

---

## Phase 1 Acceptance Criteria

### Functional
- [ ] File discovery works
- [ ] Directory discovery works
- [ ] SHA-256 correct
- [ ] Storage profile populated
- [ ] Dry-run produces plan (no mutation)
- [ ] Protected paths rejected

### Security
- [ ] Path traversal rejected
- [ ] System-drive rejected
- [ ] Targets outside allowed roots rejected
- [ ] Reparse/junction escape blocked
- [ ] Large files memory-bounded
- [ ] All 15 security tests pass

### API
- [ ] POST /api/targets/analyze returns 200 + TargetProfile
- [ ] Error codes appropriate
- [ ] OpenAPI updated

---

**End of IMPLEMENTATION_PROGRESS.md**