# COMPLETE_ERASURE — Capability Status

**Status: STUB (logical deletion only).**
**Last verified: 2026-09-10, by reading and executing `src/oblivion/core/erasure/engine.py`.**

This document exists so the product's claims cannot drift from its behaviour. The
capability statements below are also encoded in `MODE_CAPABILITY` in
`core/erasure/engine.py` and are returned in the `limitations` field of every
operation result, so an operator sees them without reading this file.

---

## What COMPLETE_ERASURE currently means

It removes a validated directory tree from the filesystem with `shutil.rmtree`,
after the same safety pipeline every other mode uses:

```
validate_target -> allowed-root containment
                -> system-volume protection
                -> ancestor reparse-point rejection
                -> leaf reparse-point rejection
                -> descendant reparse-point rejection (directory trees)
                -> Windows target-identity binding (volume serial + file ID)
state machine   -> ANALYZING -> READY -> ERASING
TOCTOU          -> revalidate_handle immediately before removal
removal         -> shutil.rmtree
verification    -> path no longer exists
```

**It performs no overwrite of any kind.** There is no single-pass, multi-pass,
zero-fill, random-fill, DoD 5220.22-M or NIST SP 800-88 Purge implementation
anywhere in this repository.

## Relationship to SELECTIVE_PERMANENT

The two permanent modes differ in **scope**, not in **guarantee**:

| | SELECTIVE_PERMANENT | COMPLETE_ERASURE |
|---|---|---|
| Target | one validated file | one validated directory tree |
| Filesystem call | `Path.unlink()` | `shutil.rmtree()` |
| Overwrite | none | **none** |
| Policy | `ERASURE.LOGICAL.SELECTIVE.V1` | `ERASURE.LOGICAL.TREE.V1` |

The policy identifiers are named `ERASURE.LOGICAL.*` for this reason. A previous
revision of the engine carried a commented-out `os.urandom` overwrite followed by
a bare `pass`, which read as though sanitization were nearly present. That dead
code has been removed: the absence of an overwrite is now a stated property
rather than an apparent oversight.

## Supported media and filesystems

| | Supported |
|---|---|
| OS | Windows (target-identity binding uses Win32 `GetFileInformationByHandle`) |
| Filesystem | NTFS, mounted and writable |
| Target kind | files and directories on a fixed volume |
| Not supported | raw/unmounted volumes, network shares (untested), removable media (untested), ReFS/FAT/exFAT (untested), any non-Windows filesystem |

On non-Windows hosts the volume-serial and file-ID checks return `None`, which
disables target-identity binding. That is why the platform is stated as a
limitation rather than a preference.

## What it can actually prove

1. The target passed every safety validation immediately before removal.
2. The target's volume serial and file ID matched the values captured at
   validation time, at the moment of the TOCTOU revalidation.
3. `shutil.rmtree` (or `unlink`) returned without error.
4. The path did not exist when checked immediately afterwards.

That is the complete set. It is a statement about the **filesystem namespace**.

## What it cannot prove

1. That the file *contents* are gone. No overwrite occurred, so the clusters that
   held the data are simply marked available.
2. That the data is unrecoverable by forensic tooling reading unallocated space,
   the MFT, `$LogFile` or `$UsnJrnl`.
3. Anything about NTFS file slack, alternate data streams outside the target, or
   directory-entry remnants.
4. Anything about Volume Shadow Copies, System Restore points, backups, sync
   clients or replicas.
5. Anything about SSD/NVMe behaviour — wear levelling, over-provisioning and
   controller remapping mean an overwrite would not settle this even if one
   existed.
6. That no other copy of the content exists anywhere.

## Standards position

Against NIST SP 800-88 the honest mapping is **below Clear**: Clear expects a
logical overwrite of user-addressable space, which this build does not perform.
`Purge` and `Destroy` are not claimed and not in scope. `docs/STANDARDS_MAPPING.md`
must be read with that correction in mind.

## Approved and forbidden wording

Permitted (see `docs/LIMITATIONS.md`):

- "The target was logically removed and is no longer present in the filesystem."
- "Recovery was not successful within the supported test scope."
- "Residual analysis found no matching artifacts within the configured scan scope."

Forbidden for this mode:

- "Securely erased", "sanitized", "purged", "wiped"
- "Irrecoverable", "unrecoverable", "100% deleted", "guaranteed removal"
- Any NIST/ISO/DoD conformance claim

## What would have to change to lift this status

Implementing an overwrite is necessary but **not sufficient** to claim
sanitization, and doing it carelessly would make the product's claims worse
rather than better. At minimum a future implementation needs:

1. A capability probe: media type (HDD/SSD/NVMe), filesystem, and whether the
   volume is mounted read-write, because the guarantee differs per medium.
2. A documented overwrite pattern with a stated standard, applied only where it
   is meaningful, and explicitly skipped with a recorded limitation where it is
   not (SSDs, compressed/sparse/resident files).
3. NTFS-resident-file handling: small files live inside the MFT record, where an
   overwrite through the file handle does not touch the record.
4. Verification that reads back what was written, and records the result as
   evidence rather than assuming success.
5. Assurance integration so the claim is bounded by `EvidenceCoverage`
   (see `core/assurance/rules.py`).

Until all five exist, this mode stays **STUB** and the limitations above are the
product's position.
