# Implementation Notes

## First vertical slice

Implement one complete path before broadening features:

Analyze → Hash → Dry-run → Permanent Delete → Recovery Test → Residual Scan → Assurance → Certificate.

## Interfaces

Use explicit interfaces such as:
- TargetAnalyzer
- StorageProfiler
- Hasher
- ErasurePolicy
- ErasureExecutor
- RecoveryTester
- ResidualScanner
- AssuranceEvaluator
- Vault
- EvidenceStore
- Signer
- AIProvider

## Omniroute adapter

Create an abstraction such as:

`AIProvider.analyze(request) -> validated structured response`

The rest of the backend must not depend directly on a specific model provider.

## Performance

Do not load entire large files into memory merely to hash/classify them.

Use streaming hashing and bounded processing.

## Evidence

Canonicalize evidence before hashing/signing.
Include schema version and software version.

## UI integration

BoltAI should receive:
- state
- progress
- warnings
- errors
- assurance
- certificate ID

Frontend should not derive security claims from HTTP status alone.

## Data minimization

Prefer metadata/features over plaintext content.
If content analysis is necessary, process locally where practical and retain only findings.
