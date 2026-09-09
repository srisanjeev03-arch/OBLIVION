# Security Specification

## Threats

- malicious local user
- unauthorized operator
- path traversal
- symlink/junction/reparse-point abuse
- TOCTOU target substitution
- malicious recovery object
- vault key theft
- forged certificate
- evidence tampering
- AI prompt manipulation
- log leakage
- accidental system-drive deletion

## Required controls

### Path security
- canonicalize paths
- enforce allowed roots
- reject traversal
- resolve/revalidate reparse points
- verify target identity immediately before mutation

### Privilege
- least privilege
- separate privileged service
- narrow operation API
- no shell command execution

### Authentication
Use secure password/session/token handling appropriate to implementation stack.

### Authorization
Check permissions server-side for every sensitive operation.

### Vault
Use authenticated encryption such as AES-256-GCM through a vetted library.
Keys must not be returned to frontend clients.

### Signing
Sign canonical evidence using a vetted signature implementation.
Protect signing keys.

### Logs
Never record:
- passwords
- private keys
- recovery keys
- plaintext sensitive contents
- full sensitive document bodies

### AI
Treat model output as untrusted advice.
Validate all AI output against a strict schema.
Do not execute model-generated commands.
