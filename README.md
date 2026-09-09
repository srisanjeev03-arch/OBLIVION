# Oblivion

**Oblivion — Intelligent Data Erasure, Recovery & Verification Platform**

A Windows-first, NTFS-focused platform for controlled data erasure, recovery, residual analysis, assurance and signed evidence.

## Tooling split

### BoltAI
Builds the frontend/UI.

### Claude Code + Omniroute
Builds the backend and security-critical services.

The frontend and backend communicate through the canonical OpenAPI contract.

## Three modes

- Complete Erasure
- Selective Permanent Deletion
- Controlled Recoverable Deletion

## Core pipeline

Discover → Analyze → Recommend → Erase → Test Recovery → Analyze Residuals → Assess → Certify

## Key differentiator

Oblivion combines deletion with post-operation recovery testing, residual analysis and signed evidence rather than treating filesystem delete success as proof of secure erasure.

## Scope

MVP is intentionally limited to Windows + NTFS + controlled environments.

See `docs/LIMITATIONS.md` before making product claims.
