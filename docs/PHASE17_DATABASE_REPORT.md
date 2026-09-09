# Phase 17: Persistent Database & Application State V1 Report

## Implementation Summary
Introduced SQLAlchemy 2.x and Alembic for persistent application state. SQLite is the development database. PostgreSQL can be used later by changing the connection URL — no domain-layer changes required.

## Architecture
- **`src/oblivion/persistence/database.py`**: Engine, session factory, and declarative `Base`.
- **`src/oblivion/persistence/models/`**: SQLAlchemy 2.x mapped classes.
- **`src/oblivion/persistence/repositories/`**: Repository pattern for DB access.
- **`src/oblivion/api/schemas/`**: Pydantic v2 API schemas (separated from DB models).
- **`alembic/`**: Alembic migrations with a clean initial schema.

## Schema
- `users`, `roles`, `permissions`, `role_permissions`, `sessions` (auth/RBAC tables; no plaintext passwords).
- `targets`, `operations`, `operation_events` (state machine events).
- `baselines`, `recovery_tests`, `residual_findings`, `assurance_results`.
- `evidence_records`, `certificates`.
- `audit_events` (no sensitive plaintext content).

## Migration Strategy
- `alembic.ini` and `alembic/env.py` configured.
- `alembic/versions/0001_initial.py` creates the complete schema.
- `init_db()` provides a test/bootstrap alternative.

## Security Decisions
- **No plaintext passwords** stored (auth is out of scope for Phase 17).
- **No private keys** stored in DB (only public keys and signatures for certificates).
- **JSON-encoded metadata** is used for structured data.
- **Append-only event log** preserves history across crashes.
- **Foreign-key cascades** ensure referential integrity.

## Tests
- `tests/test_database.py`: 8 tests covering database initialization, empty database startup, CRUD, rollback/error handling, and crash recovery.

## Test Results
- **pytest**: 98 passed, 1 skipped.
- **mypy**: 0 errors across 62 source files.

## Limitations
- **No full Auth/RBAC**: Users/roles/permissions tables are defined but no authentication flow is implemented.
- **SQLite for development**: Production PostgreSQL deployment requires changing `OBLIVION_DATABASE_URL`.

## Readiness Assessment
GREEN - No Critical/High findings, tests pass, security boundary enforced, schema migrates cleanly.

Stop after Phase 17.
