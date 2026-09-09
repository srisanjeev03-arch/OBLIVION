# Residual Analysis Specification

## Scan scope

Define the exact scope before every scan:
- target directory
- filesystem metadata
- configured temporary locations
- test volume
- other explicitly enabled locations

## Findings

Each finding should contain:
- ID
- artifact type
- path/reference
- timestamp if relevant
- hash/similarity if supported
- relationship confidence
- sensitivity
- risk
- explanation

## Example

Residual Artifact #17
Type: temporary file
Relationship: likely target derivative
Sensitivity: HIGH
Risk: HIGH

## False positives

Residual classification is probabilistic.
Do not state certainty when evidence is only suggestive.

## Sensitive data

Do not store unnecessary plaintext fragments.
Prefer hashes, offsets, metadata and redacted previews.
