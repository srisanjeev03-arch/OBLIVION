# BoltAI Frontend Build Specification

## Mission

Build the Oblivion frontend as a security-oriented operator console.

Backend is the source of truth.

## Do not implement

- filesystem deletion
- recovery algorithms
- encryption
- certificate signing
- privileged operations
- shell execution
- arbitrary command execution

## Frontend responsibilities

- API client
- authentication UI
- route protection
- target selection
- analysis presentation
- operation configuration
- confirmation flows
- progress polling/streaming
- recovery authorization UI
- residual visualization
- assurance visualization
- certificate viewer
- audit viewer
- error handling

## API integration

Use `docs/OPENAPI.yaml` as the canonical contract.

Generate typed API models from the OpenAPI specification where practical.

Never duplicate business rules in frontend code unless needed for UX validation.

Server-side validation remains authoritative.

## State handling

Represent operation state exactly:
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
PARTIAL
FAILED
INCONCLUSIVE
CANCELLED

## Error UX

Display:
- error code
- safe human-readable message
- retryability
- request/correlation ID

Never display raw stack traces in production UI.

## Destructive action UX

Before execution:
1. target summary
2. exact mode
3. policy
4. storage limitations
5. backup/snapshot warning if available
6. explicit confirmation

For complete erasure, make the scope visually obvious.

## Security UX

Never display:
- private keys
- vault keys
- authentication secrets
- sensitive plaintext unnecessarily

## Demo priority

The UI should make this story obvious:

ordinary delete → recovery succeeds

Oblivion:
analyze → sensitive data detected → recommended policy → delete → recovery test → residual scan → assurance → signed certificate

Then:

recoverable delete → unauthorized restore blocked → authorized restore → hash match

Finally:

certificate valid → modify evidence → certificate invalid
