# BoltAI UI Specification

BoltAI owns the visual implementation.

## Screens

1. Dashboard
2. Target Analysis
3. Erasure Configuration
4. Operation Progress
5. Recovery Vault
6. Recovery Authorization
7. Residual Analysis
8. Assurance Report
9. Certificate Viewer
10. Certificate Verification
11. Audit Log
12. Settings / Security

## Dashboard

Show:
- active operations
- completed operations
- recent assurance results
- recovery objects
- security events
- quick actions

## Target Analysis

Show:
- path
- type
- size
- file count
- SHA-256
- filesystem
- media type
- encryption
- sensitivity
- detected categories
- warnings
- limitations

## Erasure Configuration

Show three clearly separated modes:
- Complete Erasure
- Selective Permanent
- Controlled Recoverable

Show:
- policy
- consequences
- target summary
- safety warnings
- confirmation

## Progress

Render backend state machine:
- state
- percentage
- current stage
- warnings
- failures
- evidence events

Never fabricate progress.

## Recovery Vault

Show:
- recovery object
- source summary
- status
- expiry
- authorization state

Do not display encryption keys.

## Assurance

Show:
- recovery result
- residual result
- risk level
- reasons
- limitations
- final status

Use `INCONCLUSIVE` clearly.

## Certificate

Show:
- operation
- target
- policy
- evidence hash
- assurance
- signature status
- verification result

Tampered certificate must visibly show invalid.

## Design principle

Security state should be visually unambiguous.
Do not use green checkmarks merely because an HTTP request succeeded.
The backend's semantic result is authoritative.
