# Frontend Security

## Authentication

Use secure session handling.

Do not store sensitive tokens in insecure browser storage unless the chosen architecture explicitly requires it and has been reviewed.

## Authorization

Frontend can hide unavailable controls for UX, but backend authorization is authoritative.

## XSS

Treat API-provided strings as untrusted.

## Path display

Escape and safely render filesystem paths.

## Sensitive information

Avoid caching plaintext file content.

Avoid sending file contents to AI or backend when metadata/features are sufficient.

## Destructive confirmation

Confirmation must be explicit and tied to the operation shown to the user.

Do not allow stale confirmation to authorize a changed target.

## Network

For production deployment, use authenticated encrypted transport as appropriate.

## Error handling

Never show internal stack traces, secrets or sensitive filesystem details unnecessarily.
