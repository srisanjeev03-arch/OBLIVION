# Recovery Engine Specification

## Purpose

Measure whether data can be recovered using defined, repeatable supported techniques.

## Baseline experiment

Before deletion:
- record target hash
- create recovery fixture
- run recovery method
- record whether target is recoverable

## Post-operation experiment

After deletion:
- repeat supported recovery method
- compare hashes/content where applicable
- record exact method and result

## Result values

- RECOVERED
- NOT_RECOVERED
- PARTIALLY_RECOVERED
- INCONCLUSIVE
- NOT_RUN

## Important

Recovery results are evidence about tested methods, not universal proof about every possible forensic technique.

## Safety

Recovery tests must operate only on controlled test media/fixtures.
