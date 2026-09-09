# Architecture

```text
                    OBLIVION
                       |
             +---------+---------+
             |                   |
         BoltAI UI          Backend/API
                                 |
                 +---------------+----------------+
                 |               |                |
             Discovery        Security          AI Service
                 |               |                |
             Storage         Auth/RBAC       Classification
             Hashing         Key access       Risk
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

## Backend modules

- API layer
- authentication
- authorization/RBAC
- target discovery
- storage profiler
- hashing
- policy engine
- operation orchestrator
- erasure engine
- recovery engine
- residual scanner
- AI adapter
- assurance engine
- recovery vault
- evidence engine
- certificate/signature engine
- audit/security event service

## Privilege model

The HTTP API should remain unprivileged when possible.

A minimal local privileged service performs only explicitly validated filesystem operations.

Communication must use:
- local IPC or loopback
- authenticated/authorized requests
- structured operation IDs
- strict schema validation
- no arbitrary command strings

## State machine

CREATED → ANALYZING → READY → ERASING → VERIFYING → RECOVERY_TEST → RESIDUAL_SCAN → ASSESSING → CERTIFYING → COMPLETED

Failures:
PARTIAL, FAILED, INCONCLUSIVE, CANCELLED
