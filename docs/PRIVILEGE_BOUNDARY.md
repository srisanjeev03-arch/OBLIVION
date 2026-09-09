# Privilege Boundary

## Goal

Keep the main API unprivileged and isolate dangerous filesystem operations.

## Flow

BoltAI
→ API
→ authorization
→ operation validation
→ privileged service request
→ structured filesystem operation
→ result
→ evidence

## Privileged service API

Allowed operations should be explicit, for example:
- inspect_target
- delete_file
- delete_tree
- prepare_recovery_object
- restore_recovery_object
- scan_scope

There must be no:
- execute_command
- powershell
- cmd
- arbitrary executable
- arbitrary script

## Request validation

Validate:
- operation type
- normalized target
- allowed root
- expected target identity
- operation ID
- actor authorization
- policy ID

## Response

Return structured status, not shell output.
