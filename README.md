# Oblivion

**Oblivion — Intelligent Data Erasure, Recovery & Verification Platform**

A Windows-first, NTFS-focused platform for controlled data erasure, recovery testing, residual
analysis, assurance assessment and cryptographically verifiable evidence.

Submitted against **SIH26149** (NTRO).

---

## Documentation

**[`docs/OBLIVION_DOCUMENTATION.md`](docs/OBLIVION_DOCUMENTATION.md)** is the single canonical
record: architecture, security model, standards alignment, implementation and audit history,
test state, demonstration procedure and known limitations.

`docs/OPENAPI.yaml` is the API contract. It is **generated** from the running application by
`scripts/gen_openapi.py` — do not hand-edit it.

---

## The core question

Oblivion does not ask whether a delete command returned success. It asks:

> What evidence exists that the target data is no longer recoverable within the supported
> recovery and verification scope?

## Three modes

- **Complete Erasure**
- **Selective Permanent Deletion**
- **Controlled Recoverable Deletion** (encrypted recovery object, restorable under RBAC)

## Core pipeline

```
Discover → Analyze → Recommend → Erase → Test Recovery → Analyze Residuals → Assess → Certify
```

Every stage records what it did, **including nothing**. A scan that could not run is reported as
unavailable, never as "clean", and assurance is derived strictly from the coverage actually
achieved.

---

## Quick start

```bash
# Backend
pip install -r requirements.txt
alembic upgrade head
python -m pytest -q
python -m uvicorn oblivion.api:app --reload

# Frontend
cd frontend
npm install
npm run check      # contract gate + typecheck + lint + tests + build
npm run dev
```

Configuration is by environment variable; see `.env.example`. Every key is fail-closed — an
absent signing key means the system cannot sign rather than generating one, and an absent trust
anchor yields `INCONCLUSIVE` rather than `VALID`.

---

## Scope and claims

MVP is intentionally limited to **Windows + NTFS + controlled environments**.

Oblivion performs **logical deletion**, verified within a stated scope. It does **not** perform
physical or NAND-level sanitization, makes **no** claim of universal irrecoverability, and holds
**no** certification. Terminology aligns to NIST SP 800-88 Rev. 2, ISO/IEC 27040:2024,
IEEE 2883-2022 and IEEE 2883.1-2025 — alignment is not certification.

Read
[§29 Standards](docs/OBLIVION_DOCUMENTATION.md#29-standards-and-methodology) and
[§36 Known Limitations](docs/OBLIVION_DOCUMENTATION.md#36-known-limitations) before making any
product claim.
