# Oblivion Engine Limitations and Scope

## Supported MVP Scope
The Oblivion MVP is intentionally focused on a specific, high-assurance environment:
- **Operating System**: Windows (modern versions).
- **Filesystem**: NTFS.
- **Targets**: Files and folders within controlled test volumes.
- **Verification**: Logical erasure, recovery testing, and residual scan.

## Core Limitations

### Media Constraints
Oblivion cannot guarantee physical data destruction on SSD, NVMe, or other NAND-based flash media due to hardware-level wear leveling, overprovisioning, and firmware-controlled cell mapping. Software-level erasure on these devices provides logical sanitization but may not physically overwrite every underlying cell.

### Data Replication
Oblivion does not automatically identify or erase data stored in:
- External backups or snapshots.
- Cloud-synced copies (e.g., OneDrive, Dropbox).
- Temporary files or swap files outside the explicit target path (unless specifically configured).
- Volume Shadow Copies (VSS) unless explicitly within scope.

### Forensic Resistance
While Oblivion provides high assurance through recovery testing, it does not claim to resist all future or undisclosed forensic techniques. "Inconclusive" results will be issued where evidence is insufficient to verify erasure.

## Prohibited Claims
- No claims of "100% irrecoverability" or "guaranteed physical destruction."
- No claims of "military-grade" or "forensic-proof" deletion.
- No claims that all copies of data across all media have been erased.

## Verification Boundaries
The verification provided by Oblivion is limited to the **supported recovery techniques** implemented in the engine. Successful verification indicates that the data is no longer recoverable using those specific methods within the tested scope.
