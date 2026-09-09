# BoltAI ↔ Oblivion API Contract

## Canonical source

`docs/OPENAPI.yaml`

## Rules

1. API versioning is backend-controlled.
2. Frontend must not invent undocumented endpoints.
3. Backend errors use stable error codes.
4. Frontend must preserve operation IDs.
5. Long-running operations are observed by operation ID.
6. UI must tolerate `PARTIAL` and `INCONCLUSIVE`.
7. UI must not translate `INCONCLUSIVE` into success.
8. Certificate validity comes from backend verification.

## Suggested client flow

### Analyze
POST `/api/targets/analyze`

### Create operation
POST `/api/operations`

### Observe
GET `/api/operations/{operation_id}`

### Evidence
GET `/api/operations/{operation_id}/events`

### Recovery
GET `/api/recovery-objects`

POST `/api/recovery-objects/{recovery_id}/restore`

### Certificate
GET `/api/certificates/{certificate_id}`

POST `/api/certificates/{certificate_id}/verify`

## Compatibility testing

For every API change:
- update OpenAPI
- update generated/client types
- run contract tests
- verify error cases
- verify BoltAI integration
