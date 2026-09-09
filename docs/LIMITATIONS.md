# Limitations and Product Claims

## Supported MVP

- Windows
- NTFS
- controlled test environments
- files/folders
- logical erasure
- controlled recovery
- recovery testing
- residual analysis

## Important limitations

Software cannot guarantee that data is physically irrecoverable from every possible medium or copy.

SSD/NVMe controllers, overprovisioning, wear leveling and firmware behavior can prevent ordinary software from proving the state of every NAND cell.

Backups, snapshots, cloud copies and other external replicas are outside the MVP unless explicitly integrated.

Recovery tests demonstrate what the implemented/tested recovery methods can and cannot recover. They are not proof against every future or undisclosed forensic technique.

Use `INCONCLUSIVE` where evidence is insufficient.

## Approved wording

"Recovery was not successful within the supported test scope."

"Residual analysis found no matching artifacts within the configured scan scope."

"Assurance is limited by the storage and recovery techniques available."

## Forbidden wording

"Impossible to recover by any method."

"100% secure deletion."

"Guaranteed physical destruction."

"All copies have been deleted."
