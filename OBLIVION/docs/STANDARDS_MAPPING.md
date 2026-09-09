# Standards Mapping

**Purpose:** Map OBLIVION policies and assurance to recognized sanitization standards. Policy layer only. No external certification claimed.

**Last Updated:** 2026-09-05

---

## Reference Standards

| Standard | Version | Scope |
|---|---|---|
| NIST SP 800-88 | Rev. 2 (2014) | Media sanitization |
| IEEE 2883 | 2022 | Storage sanitization taxonomy |
| IEEE 2883.1 | 2025 | Method selection practice |
| ISO/IEC 27040 | 2024 | Storage security |

---

## NIST SP 800-88 Categories

| Category | Description | OBLIVION Mapping |
|---|---|---|
| Clear | Logical deletion with overwrite | Logical unlink (below Clear) |
| Purge | Physical/media sanitization | NOT CLAIMED |
| Destroy | Physical destruction | NOT IN SCOPE |

---

## Policy → Standards

| Policy ID | Category | Claim | Limitation |
|---|---|---|---|
| ERASURE.LOGICAL.SELECTIVE.V1 | Logical | Below Clear | "Recovery not successful within test scope" |
| ERASURE.LOGICAL.TREE.V1 | Logical | Below Clear | "Recovery not successful within test scope" |
| ERASURE.RECOVERABLE.ENCRYPTED.V1 | Recoverable | Not sanitization | "Key retained; controlled recovery" |

---

## Assurance → Standards Language

| State | Language | Permitted |
|---|---|---|
| VALIDATED | "Logically deleted; recovery not successful" | Recovery test + residual scan |
| PARTIALLY_VALIDATED | "Partially deleted" | Partial success |
| INCONCLUSIVE | "Insufficient evidence" | No positive claim |
| FAILED | "Operation failed" | No removal claim |

---

## Claim Discipline

1. Never label logical deletion as NIST Purge/Destroy
2. Never claim universal irrecoverability
3. Never claim SSD/NVMe NAND sanitization without device evidence
4. Always surface media/scope caveats
5. Build-time forbidden-phrase test (100%, guaranteed, military-grade, etc.)

---

## Certificate Standards Block

```json
{
  "standards": [{
    "standard": "NIST SP 800-88 Rev. 2",
    "category_attempted": "Clear",
    "verification_method": "recovery_test + residual_scan",
    "scope": "logical",
    "limitations": ["physical media state not verified"]
  }]
}
```

---

## ISO/IEC 27040 Mapping

| Requirement | OBLIVION |
|---|---|
| Media sanitization | Policy-based logical deletion |
| Evidence of sanitization | Hash chain + signed certificate |
| Verification | Recovery test + residual scan |
| Documentation | Certificate + evidence + limitations |

---

**End of STANDARDS_MAPPING.md**