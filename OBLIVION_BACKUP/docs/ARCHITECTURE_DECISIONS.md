# Architecture Decisions

## ADR-001 Frontend separation

**Decision:** BoltAI owns the frontend.

**Reason:** allows rapid UI iteration while isolating security-critical backend logic.

## ADR-002 OpenAPI boundary

**Decision:** OpenAPI is the canonical frontend/backend contract.

**Reason:** reduces integration drift.

## ADR-003 AI advisory boundary

**Decision:** AI recommends; deterministic policy code executes.

**Reason:** model output is probabilistic and untrusted.

## ADR-004 Privileged boundary

**Decision:** isolate destructive filesystem operations in a minimal privileged service.

**Reason:** limits blast radius.

## ADR-005 Evidence signing

**Decision:** sign canonical evidence, not unstable serialized objects.

**Reason:** reproducible verification.

## ADR-006 MVP scope

**Decision:** Windows + NTFS + controlled test environment.

**Reason:** improves reliability and demo credibility.

---

## ADR-007 Stack Selection

**Decision:** Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0/Alembic + pyca `cryptography` + SQLite (MVP).

**Reason:** Strong signal from `.env.example` (SQLAlchemy URL), OpenAPI-first design, vetted crypto library, rapid prototyping.

**See:** `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_NOTES.md`

---

## ADR-008 OBLIVION_ALLOWED_ROOTS

**Decision:** Fail-closed allowed-root enforcement; configured via `OBLIVION_ALLOWED_ROOTS` environment variable or config file. Every target must be within an allowed root before any operation.

**Mechanism:**
- Path canonicalization produces a resolved path
- Resolved path must be a descendant (by path component, not string prefix) of an allowed root
- Allowed roots are validated at startup and refreshed on config reload
- Test/dev defaults to a single controlled temp directory

**Reason:** Prevents accidental/escalated deletion outside controlled volumes. Fail-closed ensures safety when config is missing or malformed.

**See:** `docs/SECURITY.md` "Path security"

---

## ADR-009 Volume-Identity System-Drive Protection

**Decision:** System-volume protection uses `VolumeSerialNumber` (via `GetVolumeInformationByHandle`), not drive-letter alone. Boot-critical volumes are identified by their volume GUID and serial number.

**Mechanism:**
- On startup, capture the system volume's `VolumeSerialNumber` and GUID
- For every target, resolve its volume via open handle
- Reject targets where `volume_serial == system_volume_serial`
- Independent validation in both API (advisory) and privileged service (enforcing)

**Reason:** Drive letters can change (USB drives, network mappings). Volume identity is stable and cannot be bypassed by remapping a drive letter.

**See:** `docs/SECURITY.md` "Path security", `docs/WINDOWS_NTFS_NOTES.md`

---

## ADR-010 DB/Filesystem Crash Reconciliation

**Decision:** Database records operation state as `PENDING_DELETION` before invoking privileged service. On process restart, reconcile state from actual filesystem state. Never mark an in-flight destructive operation as COMPLETED without evidence of success.

**Reconciliation rules:**
1. Scan DB for operations in `PENDING_DELETION` state
2. For each, query actual filesystem state (target exists? hash matches?)
3. If target absent: operation succeeded; update to COMPLETED
4. If target present: operation may have partially succeeded; update to PARTIAL or FAILED with evidence
5. Log reconciliation actions as SecurityEvent

**Reason:** Process crash during/after filesystem operation but before DB update must not result in silent COMPLETED. The actual filesystem state is the source of truth.

**See:** `docs/ARCHITECTURE.md` "State machine", `reference/OPERATION_STATES.md`

---

## ADR-011 Authenticated Named-Pipe IPC for Privileged Service

**Decision:** Named-pipe IPC between unprivileged API and privileged Windows service. DACL restricted to API process identity. Token-based peer authentication with message signing.

**IPC Protocol:**
- Named pipe: `\\.\pipe\OblivionPrivsvc`
- Server runs as a restricted service account (or high-integrity process)
- Client (API) authenticates via signed token containing its process ID and nonce
- Server verifies token signature before accepting any operation request
- Each message includes a unique operation ID for correlation

**Allowed Verbs (closed allowlist):**
- `inspect_target` — query target metadata without mutation
- `delete_file` — delete single file by handle
- `delete_tree` — delete directory tree by manifest
- `prepare_recovery_object` — hash + encrypt + store
- `restore_recovery_object` — decrypt + restore to validated destination
- `scan_scope` — residual scan within defined scope

**Prohibited (never implemented):**
- `execute_command`, `powershell`, `cmd`, `run`, `shell`
- Any operation accepting arbitrary string commands

**Reason:** Named pipes provide Windows-native process isolation, DACL enforcement, and message-level integrity. The closed verb allowlist prevents arbitrary command execution even if the API is compromised.

**See:** `docs/PRIVILEGE_BOUNDARY.md`, `docs/THREAT_MODEL.md`
