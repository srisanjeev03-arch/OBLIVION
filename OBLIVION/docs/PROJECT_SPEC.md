# Project Specification

## Problem

Normal file deletion does not establish what remains recoverable. Recovery tools, filesystem artifacts, metadata, temporary files and storage behavior complicate assurance.

## Objective

Build a controlled platform that:
- discovers targets
- profiles storage
- classifies sensitivity
- recommends an allowlisted erasure policy
- performs the selected erasure
- tests supported recovery paths
- scans residual artifacts
- produces an explainable assurance result
- creates tamper-evident signed evidence
- supports controlled encrypted recovery when requested

## User roles

### Operator
Can analyze targets and execute permitted erasure operations.

### Recovery Authorized User
Can restore controlled-recoverable objects when policy permits.

### Auditor
Can inspect evidence, certificates and audit events but cannot perform destructive actions.

### Administrator
Manages users, policies and security configuration.

## Success criteria

- baseline recovery is demonstrated before erasure
- permanent deletion reduces successful recovery within the supported test scope
- recoverable deletion removes the original while preserving an encrypted recovery object
- authorized restoration reproduces the original hash
- unauthorized restoration is blocked
- residual findings are visible
- certificates verify successfully
- tampered evidence fails verification
