# Frontend State Specification

## Global

- authenticated_user
- permissions
- backend_health
- API_version

## Target

- selected_path
- target_profile
- storage_profile
- sensitivity
- warnings

## Operation

- operation_id
- mode
- policy_id
- state
- progress
- current_stage
- warnings
- error

## Recovery

- recovery_object_id
- status
- authorization_result
- restore_result

## Assurance

- recovery_result
- residual_result
- risk_level
- reasons
- limitations

## Certificate

- certificate_id
- verification_state
- evidence_hash
- signature_state

## State rules

If backend state is `FAILED`, do not display completed.

If backend state is `INCONCLUSIVE`, display uncertainty prominently.

If certificate verification is invalid, display invalid regardless of prior operation success.
