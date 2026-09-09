# Security Review Checklist

## Before destructive operation
- [ ] authenticated
- [ ] authorized
- [ ] target analyzed
- [ ] target canonicalized
- [ ] target identity revalidated
- [ ] protected path check
- [ ] policy allowlisted
- [ ] explicit confirmation
- [ ] dry-run available

## During operation
- [ ] no arbitrary command execution
- [ ] structured logging
- [ ] no sensitive plaintext logging
- [ ] cancellation semantics defined
- [ ] partial failure recorded

## Recovery vault
- [ ] authenticated encryption
- [ ] key reference only
- [ ] authorization
- [ ] expiry/retention
- [ ] restore destination validated
- [ ] restored hash checked

## Evidence
- [ ] canonical serialization
- [ ] hash chain
- [ ] signature
- [ ] verification test
- [ ] tamper test

## AI
- [ ] schema validated
- [ ] prompt/data minimized
- [ ] no destructive tools
- [ ] deterministic policy validation
- [ ] failure fallback

## Frontend
- [ ] no secrets
- [ ] backend state authoritative
- [ ] INCONCLUSIVE visible
- [ ] errors safe
- [ ] confirmation tied to current target
