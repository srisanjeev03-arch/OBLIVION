# Data Model

## Target

- id
- path
- type
- size
- file_count
- metadata
- sha256
- storage_profile_id
- discovered_at

## StorageProfile

- id
- volume
- filesystem
- media_type
- encryption_status
- allocation_characteristics
- capability_flags
- limitations

## Operation

- id
- target_id
- mode
- policy_id
- state
- actor_id
- created_at
- started_at
- completed_at
- progress
- warnings
- error_code

## RecoveryObject

- id
- operation_id
- encrypted_object_path
- encryption_algorithm
- key_reference
- original_sha256
- created_at
- expires_at
- status

## EvidenceEvent

- id
- operation_id
- sequence
- event_type
- timestamp
- canonical_payload_hash
- previous_event_hash
- actor_id

## Assurance

- operation_id
- recovery_result
- residual_result
- risk_level
- reasons
- limitations
- final_status

## Certificate

- id
- operation_id
- evidence_hash
- signature_algorithm
- signature
- issued_at
- verifier_version

## SecurityEvent

- id
- actor_id
- event_type
- timestamp
- outcome
- safe_metadata
