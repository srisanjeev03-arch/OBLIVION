# Certificate Format

## Purpose

Provide a portable signed statement of the operation evidence.

## Required fields

- certificate_version
- certificate_id
- operation_id
- target_summary
- target_sha256
- operation_mode
- policy_id
- storage_profile
- recovery_result
- residual_result
- assurance
- limitations
- timestamps
- software_version
- evidence_hash
- signature_algorithm
- signer_key_id
- signature

## Canonicalization

Canonical serialization must be deterministic:
- fixed field names
- fixed encoding
- stable ordering
- explicit schema version
- normalized timestamps

Sign the canonical byte representation.

## Verification

Verifier checks:
1. schema validity
2. evidence hash
3. signature
4. signer key identity
5. certificate version compatibility

Any mismatch => invalid.
