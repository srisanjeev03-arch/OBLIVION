# Agent Handoff

## Current product

Oblivion — Intelligent Data Erasure, Recovery & Verification Platform.

## Frontend

BoltAI owns the frontend.

Do not build a parallel frontend unless explicitly requested.

## Backend

Claude Code + Omniroute owns the backend.

Primary objective:
Build a safe, deterministic backend that BoltAI can consume through OpenAPI.

## Current architectural boundary

BoltAI
→ REST/JSON
→ Oblivion backend
→ core engines
→ evidence/certificate

Privileged Windows operations are isolated behind a minimal privileged service.

## First end-to-end slice

Implement:

1. create controlled test target
2. analyze target
3. dry-run
4. calculate SHA-256
5. permanent deletion
6. recovery test
7. residual scan
8. assurance assessment
9. signed evidence
10. certificate verification

Then implement controlled recoverable deletion and authorized restoration.

## Never do

- arbitrary command execution
- uncontrolled system-drive deletion
- AI-driven destructive execution
- plaintext recovery keys in logs
- absolute irrecoverability claims
