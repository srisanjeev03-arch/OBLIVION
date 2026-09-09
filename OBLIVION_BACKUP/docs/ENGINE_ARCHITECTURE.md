# Oblivion Engine Architecture

## Overview
Oblivion is designed as a secure, Windows-first platform for intelligent data erasure and verification. The architecture emphasizes high-assurance outcomes through a structured pipeline and strict privilege separation.

## System Architecture

```text
                    OBLIVION
                       |
             +---------+---------+
             |                   |
         BoltAI UI          Backend/API (FastAPI)
                                 |
                 +---------------+----------------+
                 |               |                |
             Discovery        Security          AI Service
                 |               |                |
             Storage         Auth/RBAC       Classification
             Hashing         Key access       Risk Assessment
                 |               |             Policy advice
                 +---------------+----------------+
                                 |
                         Operation Orchestrator
                                 |
                 +---------------+----------------+
                 |               |                |
             Erasure          Recovery         Residual
             Engine           Engine            Scanner
                 |               |                |
                 +---------------+----------------+
                                 |
                         Assurance Engine
                                 |
                         Evidence Engine
                                 |
                    +------------+------------+
                    |                         |
                 Audit                    Certificate
```

## Module Responsibilities

### Core Modules
- **Discovery & Profiling**: Identifies targets, analyzes metadata, and profiles storage media (NTFS/SSD/HDD).
- **Hashing**: Provides SHA-256 integrity evidence for targets.
- **Erasure Engine**: Executes deterministic, allowlisted erasure policies.
- **Recovery Engine**: Performs controlled recovery tests to verify erasure effectiveness.
- **Residual Scanner**: Scans for artifacts within the supported recovery scope.
- **Assurance Engine**: Assesses evidence to determine an assurance level (e.g., VALIDATED, INCONCLUSIVE).
- **Evidence & Certification**: Generates a tamper-evident event chain and signed Ed25519 certificates.

### Support Modules
- **AI Service**: Provides non-destructive advisory classification and risk estimation.
- **Privileged Service**: A minimal Windows service for validated filesystem operations.
- **Recovery Vault**: Manages encrypted backups for controlled recoverable operations.

## Data Flow
1. **Analyze**: Discovery and profiling generate a `TargetProfile`.
2. **Plan**: Dry-run generates a `DryRunPlan` without mutation.
3. **Execute**: Orchestrator drives the state machine through ERASING, VERIFYING, and RECOVERY_TEST.
4. **Finalize**: Evidence is canonicalized, signed, and issued as a certificate.

## Trust and Privilege Boundaries
- **Frontend**: Untrusted; must use structured API requests.
- **API**: Trusted; handles auth/RBAC and coordination.
- **Privileged Service**: Isolated; uses a named pipe (`\\.\pipe\OblivionPrivsvc`) with a restricted verb allowlist to perform filesystem operations.
- **AI Boundary**: Advisory only; cannot execute commands or bypass safety controls.

## Safety Mechanisms
- **Path Validation**: Canonicalization and allowed-root enforcement.
- **System Protection**: VolumeSerialNumber-based blocking of boot/system drives.
- **TOCTOU Mitigation**: Revalidation by same handle immediately before destructive mutation.
- **Crash Reconciliation**: DB-driven state reconciliation for in-flight operations.
