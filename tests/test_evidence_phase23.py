"""Evidence: canonical form, document, generation and chain.

The property under test throughout is that evidence never turns an absence into
a presence, and that its digest is a faithful function of its content.
"""

from datetime import UTC, datetime

import pytest

from oblivion.core.evidence.canonicalize import (
    CANONICALIZATION_VERSION,
    CanonicalizationError,
    canonical_hash,
    canonicalize,
)
from oblivion.core.evidence.generator import (
    EvidenceGenerationContext,
    EvidenceGenerator,
    Unavailable,
)
from oblivion.core.evidence.record import (
    EVIDENCE_SCHEMA_VERSION,
    ChainStatus,
    EvidenceError,
    EvidenceRecord,
    Observation,
    ObservationState,
    TargetDescriptor,
    new_evidence_id,
    verify_evidence_chain,
)

TARGET = TargetDescriptor(
    identity="H:/scratch/example.txt",
    target_type="file",
    volume_serial="0X1234ABCD",
    filesystem="NTFS",
    content_digest="a" * 64,
)


def _context(**overrides) -> EvidenceGenerationContext:
    base = {
        "operation_id": "op_test",
        "target": TARGET,
        "method": "SELECTIVE_PERMANENT",
        "policy_id": "ERASURE.LOGICAL.SELECTIVE.V1",
        "execution_result": {"status": "COMPLETED"},
    }
    base.update(overrides)
    return EvidenceGenerationContext(**base)


# -- canonicalization ------------------------------------------------------

def test_canonicalization_is_deterministic():
    a = {"b": 1, "a": {"z": [1, 2], "y": None}}
    b = {"a": {"y": None, "z": [1, 2]}, "b": 1}
    assert canonicalize(a) == canonicalize(b)
    assert canonical_hash(a) == canonical_hash(b)


def test_keys_are_sorted_and_output_is_compact():
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_nulls_are_preserved_not_dropped():
    """Dropping nulls made two different documents share one digest."""
    with_null = {"a": 1, "b": None}
    without = {"a": 1}
    assert canonicalize(with_null) != canonicalize(without)
    assert canonical_hash(with_null) != canonical_hash(without)


def test_changed_data_changes_the_digest():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_non_serialisable_values_are_rejected_not_coerced():
    """Silent str() coercion is how two objects end up sharing a digest."""
    with pytest.raises(CanonicalizationError):
        canonicalize({"a": object()})


def test_nan_and_infinity_are_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize({"a": float("nan")})
    with pytest.raises(CanonicalizationError):
        canonicalize({"a": float("inf")})


def test_non_string_keys_are_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize({1: "a"})


def test_unicode_keys_sort_by_utf16_code_unit():
    """RFC 8785 collation differs from Python's default above the BMP.

    By code point U+FFFF < U+1F600, so Python's default sort puts U+FFFF first.
    In UTF-16, U+1F600 is the surrogate pair D83D DE00 and 0xD83D < 0xFFFF, so
    RFC 8785 puts the emoji first. This test pins the UTF-16 answer: getting it
    wrong would make two implementations disagree about the canonical bytes, and
    therefore about whether a signature is valid.
    """
    encoded = canonicalize({"\uffff": 1, "\U0001f600": 2})
    assert encoded.index("\U0001f600".encode()) < encoded.index("\uffff".encode())
    # Python's own ordering would have produced the opposite.
    assert sorted(["\uffff", "\U0001f600"]) == ["\uffff", "\U0001f600"]


# -- the record ------------------------------------------------------------

def test_record_digest_changes_when_content_changes():
    record = EvidenceGenerator().generate(_context())
    modified = EvidenceRecord.from_canonical_dict(
        {**record.to_canonical_dict(), "method": "COMPLETE_ERASURE"}
    )
    assert modified.digest() != record.digest()


def test_record_round_trips_without_changing_its_digest():
    """Persistence must not alter the document, or verification breaks later."""
    record = EvidenceGenerator().generate(_context())
    restored = EvidenceRecord.from_canonical_dict(record.to_canonical_dict())
    assert restored.digest() == record.digest()
    assert restored.canonical_bytes() == record.canonical_bytes()


def test_record_declares_its_versions():
    record = EvidenceGenerator().generate(_context())
    assert record.schema_version == EVIDENCE_SCHEMA_VERSION
    assert record.canonicalization_version == CANONICALIZATION_VERSION


def test_missing_observation_reads_as_not_checked():
    record = EvidenceGenerator().generate(_context())
    absent = record.observation("nothing_like_this")
    assert absent.state is ObservationState.NOT_CHECKED
    assert absent.value is None


def test_absent_observation_cannot_carry_a_value():
    """The type refuses to express "missing, but here is the value"."""
    with pytest.raises(EvidenceError):
        Observation(ObservationState.NOT_CHECKED, value="something")
    with pytest.raises(EvidenceError):
        Observation(ObservationState.UNAVAILABLE, value="something")


def test_secret_bearing_field_names_are_refused():
    for name in ("password", "vault_key", "session_token", "api_key"):
        with pytest.raises(EvidenceError):
            EvidenceRecord(
                evidence_id=new_evidence_id(),
                operation_id="op1",
                target=TARGET,
                method="SELECTIVE_PERMANENT",
                observations={name: Observation.observed("x")},
            )


def test_half_a_chain_link_is_refused():
    with pytest.raises(EvidenceError):
        EvidenceRecord(
            evidence_id=new_evidence_id(),
            operation_id="op1",
            target=TARGET,
            method="m",
            previous_evidence_id="ev_something",
        )


# -- generation ------------------------------------------------------------

def test_evidence_is_actually_generated():
    record = EvidenceGenerator().generate(_context())
    assert record.evidence_id
    assert record.operation_id == "op_test"
    assert record.target.identity == TARGET.identity
    assert len(record.digest()) == 64


def test_stage_never_attempted_is_not_checked():
    record = EvidenceGenerator().generate(_context())
    for stage in ("recovery_test", "residual_analysis", "assurance"):
        assert record.observation(stage).state is ObservationState.NOT_CHECKED


def test_stage_attempted_but_impossible_is_unavailable():
    record = EvidenceGenerator().generate(
        _context(residual_result=Unavailable("Free-space scanning is not implemented."))
    )
    residual = record.observation("residual_analysis")
    assert residual.state is ObservationState.UNAVAILABLE
    assert "not implemented" in residual.detail
    assert residual.value is None


def test_stage_that_ran_is_observed_with_its_value():
    record = EvidenceGenerator().generate(
        _context(verification_result={"target_absent": True})
    )
    verification = record.observation("verification")
    assert verification.state is ObservationState.OBSERVED
    assert verification.value == {"target_absent": True}


def test_partial_evidence_is_still_valid_evidence():
    """Phase 23 has no recovery/residual/assurance; that must not block evidence."""
    record = EvidenceGenerator().generate(
        EvidenceGenerationContext(
            operation_id="op_partial", target=TARGET, method="SELECTIVE_PERMANENT"
        )
    )
    assert len(record.digest()) == 64
    assert record.observation("execution").state is ObservationState.NOT_CHECKED


def test_generator_will_not_let_a_caller_overwrite_a_stage():
    with pytest.raises(ValueError):
        EvidenceGenerator().generate(
            _context(extra_observations={"assurance": Observation.observed("PASSED")})
        )


# -- the chain -------------------------------------------------------------

def _chain(length: int) -> list[EvidenceRecord]:
    generator = EvidenceGenerator()
    records: list[EvidenceRecord] = []
    previous = None
    for index in range(length):
        record = generator.generate(
            _context(previous=previous, execution_result={"step": index})
        )
        records.append(record)
        previous = record
    return records


def test_intact_chain_verifies():
    result = verify_evidence_chain(_chain(3))
    assert result.status is ChainStatus.INTACT
    assert result.checked == 3


def test_lone_genesis_record_is_a_complete_chain():
    """Nothing precedes a genesis record, so nothing can be missing from it."""
    result = verify_evidence_chain(_chain(1))
    assert result.status is ChainStatus.INTACT
    assert result.checked == 1


def test_lone_record_that_references_a_predecessor_is_unverifiable():
    """The real risk: supplying only the newest record and calling it a chain.

    Its own digest is correct, which is exactly why that must not be mistaken
    for evidence that the history behind it is intact.
    """
    records = _chain(2)
    result = verify_evidence_chain([records[1]])
    assert result.status is ChainStatus.UNVERIFIABLE
    assert result.status is not ChainStatus.INTACT


def test_empty_chain_is_unverifiable_not_intact():
    result = verify_evidence_chain([])
    assert result.status is ChainStatus.UNVERIFIABLE


def test_modified_earlier_record_breaks_the_chain():
    records = _chain(3)
    tampered = EvidenceRecord.from_canonical_dict(
        {**records[0].to_canonical_dict(), "method": "COMPLETE_ERASURE"}
    )
    result = verify_evidence_chain([tampered, records[1], records[2]])
    assert result.status is ChainStatus.BROKEN
    assert result.first_invalid_evidence_id == records[1].evidence_id


def test_removed_record_breaks_the_chain():
    records = _chain(3)
    result = verify_evidence_chain([records[0], records[2]])
    assert result.status is ChainStatus.BROKEN


def test_chain_missing_its_head_is_unverifiable():
    records = _chain(3)
    result = verify_evidence_chain(records[1:])
    assert result.status is ChainStatus.UNVERIFIABLE


def test_reordered_chain_does_not_pass():
    records = _chain(3)
    result = verify_evidence_chain([records[0], records[2], records[1]])
    assert result.status is not ChainStatus.INTACT


def test_created_at_is_timezone_aware():
    record = EvidenceGenerator().generate(_context())
    assert record.created_at.tzinfo is not None
    assert record.created_at <= datetime.now(UTC)
