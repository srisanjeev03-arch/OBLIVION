# Erasure Engine Specification

## Modes

### COMPLETE_ERASURE
Purpose: remove all selected content under a validated folder/dataset target.

### SELECTIVE_PERMANENT
Purpose: permanently remove selected files under the supported logical-erasure scope.

### CONTROLLED_RECOVERABLE
Purpose: preserve an encrypted recovery object, then remove the original.

## Preconditions

- authenticated user
- authorized policy
- target exists
- target is inside permitted root
- target identity matches analysis
- no protected-system violation
- explicit confirmation

## Execution

1. freeze target manifest
2. revalidate identity
3. execute allowlisted operation
4. record structured results
5. verify expected postcondition
6. proceed to recovery/residual testing

## Failure behavior

Use explicit outcomes:
- PARTIAL
- FAILED
- INCONCLUSIVE

Never report success if the postcondition was not demonstrated.

## Folder handling

Define behavior for:
- nested files
- hidden files
- read-only files
- junctions
- symlinks
- reparse points
- permission errors

Do not follow reparse points outside the approved target scope.

## Media caveat

Logical deletion behavior must not be presented as physical sanitization of all storage media.
