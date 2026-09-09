# API Contract

The detailed machine-readable contract is `docs/OPENAPI.yaml`.

## Targets

`POST /api/targets/analyze`
- input: path
- output: target profile, storage profile, sensitivity analysis

`GET /api/targets/{id}`

## Operations

`POST /api/operations`
Creates a validated operation.

`GET /api/operations/{id}`

`POST /api/operations/{id}/cancel`

`GET /api/operations/{id}/events`

## Recovery

`GET /api/recovery-objects`

`POST /api/recovery-objects/{id}/restore`

The backend must authorize restoration.

## Certificates

`GET /api/certificates/{id}`

`POST /api/certificates/{id}/verify`

## Authentication

Use secure session/token architecture appropriate to the implementation.

## API principles

- JSON only
- versioned API
- structured errors
- idempotency where appropriate
- correlation/request IDs
- no arbitrary commands
- no secrets in responses
- no plaintext recovery keys

## Standard error shape

```json
{
  "error": {
    "code": "TARGET_REVALIDATION_FAILED",
    "message": "The target changed after analysis.",
    "retryable": false,
    "request_id": "..."
  }
}
```
