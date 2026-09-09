# Windows / NTFS Notes

## Scope

MVP assumes Windows + NTFS.

## Handle carefully

- NTFS ACLs
- hidden/system/read-only attributes
- alternate data streams
- reparse points
- junctions
- symlinks
- long paths
- locked files
- volume identity
- file IDs where available

## Safety

Do not recursively follow junctions/reparse points without explicit policy.

Do not assume a path string uniquely identifies a target.

Revalidate target identity immediately before destructive mutation.

## Storage

Record:
- volume
- filesystem
- logical capacity
- free space
- encryption status where detectable
- media type where detectable
- capability limitations

Do not claim direct knowledge of physical NAND state.
