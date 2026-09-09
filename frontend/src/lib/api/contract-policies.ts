// GENERATED FILE - DO NOT EDIT.
// Written by scripts/gen_openapi.py from oblivion.core.policy.engine.POLICY_REGISTRY.
// Regenerate with: python scripts/gen_openapi.py
//
// The backend validates policy_id against this allowlist and rejects anything else, and it
// also enforces mode and target-type compatibility. Offering a policy the registry does not
// contain would produce a 400 that reads like an operator mistake.

export interface AllowlistedPolicy {
  readonly policy_id: string
  readonly name: string
  readonly allowed_modes: readonly string[]
  readonly allowed_target_types: readonly string[]
  readonly requires_approval: boolean
  readonly description: string
}

export const ALLOWLISTED_POLICIES: readonly AllowlistedPolicy[] = [
  {
    "policy_id": "ERASURE.LOGICAL.SELECTIVE.V1",
    "name": "Logical Selective File Erasure v1",
    "allowed_modes": [
      "SELECTIVE_PERMANENT"
    ],
    "allowed_target_types": [
      "file"
    ],
    "requires_approval": true,
    "description": "Permanently unlinks selected files under supported logical-erasure scope."
  },
  {
    "policy_id": "ERASURE.LOGICAL.TREE.V1",
    "name": "Logical Tree Erasure v1",
    "allowed_modes": [
      "COMPLETE_ERASURE"
    ],
    "allowed_target_types": [
      "directory"
    ],
    "requires_approval": true,
    "description": "Permanently removes all validated contents under a folder/tree target."
  },
  {
    "policy_id": "ERASURE.RECOVERABLE.ENCRYPTED.V1",
    "name": "Controlled Recoverable Encrypted Erasure v1",
    "allowed_modes": [
      "CONTROLLED_RECOVERABLE"
    ],
    "allowed_target_types": [
      "file"
    ],
    "requires_approval": true,
    "description": "Preserves an authenticated AES-256-GCM recovery object in vault before unlinking."
  }
] as const

/** Policies whose allowed modes include `mode`. */
export function policiesForMode(mode: string): readonly AllowlistedPolicy[] {
  return ALLOWLISTED_POLICIES.filter((p) => p.allowed_modes.includes(mode))
}
