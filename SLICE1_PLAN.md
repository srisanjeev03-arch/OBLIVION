# Slice 1 Implementation Plan — DISCOVER → PROFILE → HASH → DRY-RUN → VALIDATE
# Read-only only. No delete/overwrite/wipe/format/encrypt/vault/restore.
# TDD: interfaces → failing tests → minimal impl → pass → review.

## Created files (Slice 1 backend)
- src/oblivion/__init__.py
- src/oblivion/core/__init__.py
- src/oblivion/core/safety/__init__.py
- src/oblivion/core/discovery/__init__.py
- src/oblivion/api/__init__.py
- tests/__init__.py
- tests/fixtures.py
- tests/test_safety.py (security, 5 cases)
- tests/test_discovery.py (functional, 4 cases + 3 hash)
- tests/test_api_analyze.py (integration, 8 cases)
- SLICE1_PLAN.md

## Security tests (15 — from approved list)
1-9. Safety/reparse/allowed-root/system-drive (test_safety + fixtures)
10-14. Hashing/large-file/empty/dir/unicode (test_discovery)
15. Dry-run no mutation (test_api_analyze)

## Safety rules enforced
- All targets must pass allowed-root check
- All targets must pass system-volume check
- All targets must pass reparse-point check
- No destructive filesystem operations
- No user-system files used for testing (only temp fixtures)
- No arbitrary shell execution
