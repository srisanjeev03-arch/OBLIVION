# Threat Model

## Assets

- target data
- recovery objects
- vault keys
- signing keys
- evidence
- user identities
- certificates

## Trust boundaries

1. BoltAI frontend ↔ backend API
2. backend ↔ privileged service
3. backend ↔ AI provider
4. backend ↔ recovery vault
5. backend ↔ filesystem

## Key threats

### Frontend compromise
Impact: unauthorized requests.
Mitigation: server-side authorization and validation.

### Path substitution
Impact: deletion of unintended data.
Mitigation: canonicalization + identity revalidation.

### Privileged-service abuse
Impact: arbitrary deletion.
Mitigation: narrow structured protocol and allowlist.

### AI manipulation
Impact: unsafe recommendation.
Mitigation: schema validation + deterministic policy enforcement.

### Vault theft
Impact: data disclosure.
Mitigation: authenticated encryption + key protection + access control.

### Evidence tampering
Impact: false assurance.
Mitigation: hash chain + digital signatures.

### Operator error
Impact: accidental deletion.
Mitigation: dry-run + protected roots + confirmation + target preview.
