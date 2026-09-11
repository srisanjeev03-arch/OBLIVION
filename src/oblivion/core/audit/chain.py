"""Verification of the audit chain - and the boundary it must not cross.

## Audit-chain integrity is not evidence integrity

These are two different claims and this module will not let them be confused.

``INTACT`` here means **the log of acts has not been altered since it was
written**: no entry was edited, none was removed from between the entries
supplied, and each entry names its predecessor with that predecessor's real
digest.

It says *nothing* about whether an erasure worked, whether residual data
remains, or whether a certificate is trustworthy. Those are evidence and
certificate questions, answered by ``core/evidence/record.py`` and
``certificate/verification.py`` against separate artefacts.

An intact audit chain around a failed operation is the normal, correct outcome:
the log faithfully records a failure. A reader that treated such a system as
"verified" would be making exactly the substitution this docstring forbids, so
:class:`AuditChainVerification` carries ``proves`` and ``does_not_prove`` and
states the limit in its own output rather than leaving it to a caller.

## What each status means

Two levels are reported. Every record gets an :class:`AuditLinkStatus` saying
what was established about *it*; the sequence gets one
:class:`AuditChainStatus`.

Mutation is checked before linkage, and that order is deliberate. A record
whose own content was edited will usually also fail its successor's link check,
and reporting "broken predecessor" against the successor would point the reader
at the wrong record. The edited entry is named as the edited one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .records import AuditRecord


class AuditLinkStatus(str, Enum):
    """What was established about one record."""

    #: Sequence 1, references no predecessor, own digest matches. There is no
    #: earlier history for it to be missing.
    VALID_GENESIS = "VALID_GENESIS"
    #: Own digest matches, and it names the immediately preceding record with
    #: that record's real digest.
    VALID_PREDECESSOR = "VALID_PREDECESSOR"
    #: It names a predecessor that was not supplied, or the numbering jumps.
    #: History is incomplete; on its own this is not proof of tampering.
    MISSING_PREDECESSOR = "MISSING_PREDECESSOR"
    #: It names the right predecessor but records a digest that does not match
    #: that predecessor's actual content: the earlier record was changed.
    BROKEN_PREDECESSOR = "BROKEN_PREDECESSOR"
    #: The record's stored digest does not match a recomputation over its own
    #: content. This entry was edited after it was written.
    MUTATED_EVENT = "MUTATED_EVENT"


class AuditChainStatus(str, Enum):
    """The verdict over the supplied sequence.

    The same three words the evidence chain uses, with the same meanings, so
    this system has one integrity vocabulary rather than two that almost agree.
    """

    INTACT = "INTACT"
    BROKEN = "BROKEN"
    #: Nothing about history could be established - an empty log, or a window
    #: that does not begin at the genesis record.
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class StoredAuditRecord:
    """A record as it came back from storage, with the digest storage held.

    The two halves are kept apart on purpose. Detecting a mutated event means
    comparing what was *recorded* at append time against a recomputation over
    what is *there now*; a design that recomputed the digest on load and then
    compared it against itself would always agree and would detect nothing.
    """

    record: AuditRecord
    stored_digest: str


@dataclass(frozen=True)
class AuditLinkResult:
    audit_id: str
    sequence: int
    status: AuditLinkStatus
    detail: str

    @property
    def ok(self) -> bool:
        return self.status in (
            AuditLinkStatus.VALID_GENESIS,
            AuditLinkStatus.VALID_PREDECESSOR,
        )


@dataclass(frozen=True)
class AuditChainVerification:
    """The result of verifying a sequence of audit records."""

    status: AuditChainStatus
    checked: int
    reason: str
    links: tuple[AuditLinkResult, ...] = ()
    first_invalid_audit_id: str | None = None
    #: Rows written before this build's chaining existed. They carry no digest,
    #: so nothing can be established about them either way. They are excluded
    #: from the verdict and counted here rather than quietly omitted: a reader
    #: must be able to see that part of the log sits outside the guarantee.
    records_predating_chain: int = 0

    @property
    def intact(self) -> bool:
        return self.status is AuditChainStatus.INTACT

    @property
    def proves(self) -> tuple[str, ...]:
        """What an ``INTACT`` result actually establishes, and only that."""
        if self.status is not AuditChainStatus.INTACT:
            return ()
        return (
            "The audit records supplied have not been edited since they were written.",
            "No record was removed from between the records supplied.",
            "Each record names its predecessor with that predecessor's real digest.",
        )

    @property
    def does_not_prove(self) -> tuple[str, ...]:
        """Claims this verification never supports, whatever its status.

        Carried in the result itself so a caller rendering it cannot quietly
        widen the claim by leaving the limits out.
        """
        base = (
            "That any erasure succeeded, or that any target is unrecoverable.",
            "That the evidence records referenced by these entries are intact - "
            "evidence integrity is a separate check against the evidence chain.",
            "That any certificate is trustworthy.",
            "That acts performed outside this application were recorded at all.",
        )
        if self.records_predating_chain:
            return (
                *base,
                (
                    f"That the {self.records_predating_chain} record(s) written before "
                    "this build's chaining existed are intact - they carry no digest "
                    "and are outside this verification entirely."
                ),
            )
        return base


def _verify_one(
    entry: StoredAuditRecord,
    previous: StoredAuditRecord | None,
) -> AuditLinkResult:
    record = entry.record

    # 1. Own integrity, before anything about neighbours.
    recomputed = record.digest()
    if recomputed != entry.stored_digest:
        return AuditLinkResult(
            record.audit_id,
            record.sequence,
            AuditLinkStatus.MUTATED_EVENT,
            (
                f"Record {record.audit_id} was written with digest "
                f"{entry.stored_digest[:16]}... but its stored content now hashes to "
                f"{recomputed[:16]}.... The entry was modified after it was written."
            ),
        )

    # 2. Genesis.
    if previous is None:
        if record.is_genesis:
            return AuditLinkResult(
                record.audit_id,
                record.sequence,
                AuditLinkStatus.VALID_GENESIS,
                "The first record of the log, referencing no predecessor.",
            )
        return AuditLinkResult(
            record.audit_id,
            record.sequence,
            AuditLinkStatus.MISSING_PREDECESSOR,
            (
                f"Record {record.audit_id} references predecessor "
                f"{record.previous_audit_id!r}, which was not supplied. History "
                "before this point could not be established."
            ),
        )

    prior = previous.record

    # 3. Does it name the record that actually precedes it?
    if record.previous_audit_id != prior.audit_id:
        return AuditLinkResult(
            record.audit_id,
            record.sequence,
            AuditLinkStatus.MISSING_PREDECESSOR,
            (
                f"Record {record.audit_id} names predecessor "
                f"{record.previous_audit_id!r}, but the preceding record supplied is "
                f"{prior.audit_id!r}. At least one record is missing between them."
            ),
        )

    # 4. Contiguity. A gap in the numbering means entries were removed, even
    #    when the surviving links were rewritten to look continuous.
    if record.sequence != prior.sequence + 1:
        return AuditLinkResult(
            record.audit_id,
            record.sequence,
            AuditLinkStatus.MISSING_PREDECESSOR,
            (
                f"Record {record.audit_id} is at sequence {record.sequence}, but the "
                f"record before it is at {prior.sequence}. The numbering is not "
                "contiguous, so entries are missing."
            ),
        )

    # 5. Does the digest it recorded for its predecessor match that
    #    predecessor's real content?
    actual = prior.digest()
    if record.previous_audit_digest != actual:
        return AuditLinkResult(
            record.audit_id,
            record.sequence,
            AuditLinkStatus.BROKEN_PREDECESSOR,
            (
                f"Record {record.audit_id} recorded predecessor digest "
                f"{str(record.previous_audit_digest)[:16]}..., but {prior.audit_id} "
                f"actually hashes to {actual[:16]}.... The earlier record was "
                "modified or replaced."
            ),
        )

    return AuditLinkResult(
        record.audit_id,
        record.sequence,
        AuditLinkStatus.VALID_PREDECESSOR,
        f"Linked to {prior.audit_id} with a matching digest.",
    )


def verify_audit_chain(entries: Sequence[StoredAuditRecord]) -> AuditChainVerification:
    """Verify audit records, oldest first.

    An empty log is ``UNVERIFIABLE``, never ``INTACT``: there is nothing that
    could have been intact, and answering "verified" for an empty log would
    make deleting the whole log look like a clean result.

    A window that does not begin at sequence 1 is also ``UNVERIFIABLE`` even
    when every link inside it holds. The window is internally consistent, which
    is worth reporting, but it cannot speak for the history before it, and the
    reason says exactly that.
    """
    if not entries:
        return AuditChainVerification(
            AuditChainStatus.UNVERIFIABLE,
            0,
            (
                "No audit records were supplied, so nothing about the log could be "
                "established. An empty log is not an intact one."
            ),
        )

    links: list[AuditLinkResult] = []
    previous: StoredAuditRecord | None = None
    first_invalid: str | None = None

    for entry in entries:
        result = _verify_one(entry, previous)
        links.append(result)
        if not result.ok and first_invalid is None:
            first_invalid = result.audit_id
        previous = entry

    tuple_links = tuple(links)

    mutated = [r for r in tuple_links if r.status is AuditLinkStatus.MUTATED_EVENT]
    broken = [r for r in tuple_links if r.status is AuditLinkStatus.BROKEN_PREDECESSOR]

    # Mutation and a broken predecessor link are positive findings of tampering.
    if mutated or broken:
        first = mutated[0] if mutated else broken[0]
        return AuditChainVerification(
            AuditChainStatus.BROKEN,
            len(tuple_links),
            (
                f"{len(mutated)} record(s) were modified after being written and "
                f"{len(broken)} record(s) record a predecessor digest that does not "
                f"match. First affected: {first.audit_id}."
            ),
            tuple_links,
            first_invalid,
        )

    # A missing predecessor on the very first entry means a partial window was
    # supplied. That is a limit of the question asked, not evidence of tampering.
    head_incomplete = tuple_links[0].status is AuditLinkStatus.MISSING_PREDECESSOR
    interior_missing = [
        r for r in tuple_links[1:] if r.status is AuditLinkStatus.MISSING_PREDECESSOR
    ]

    if interior_missing:
        return AuditChainVerification(
            AuditChainStatus.BROKEN,
            len(tuple_links),
            (
                f"{len(interior_missing)} record(s) do not follow the record before "
                "them; entries were removed from the middle of the log. First "
                f"affected: {interior_missing[0].audit_id}."
            ),
            tuple_links,
            first_invalid,
        )

    if head_incomplete:
        return AuditChainVerification(
            AuditChainStatus.UNVERIFIABLE,
            len(tuple_links),
            (
                f"The {len(tuple_links)} record(s) supplied are internally consistent, "
                "but the sequence does not begin at the genesis record, so the history "
                "before it could not be verified."
            ),
            tuple_links,
            tuple_links[0].audit_id,
        )

    return AuditChainVerification(
        AuditChainStatus.INTACT,
        len(tuple_links),
        f"{len(tuple_links)} record(s) form an unbroken chain from the genesis record.",
        tuple_links,
    )


__all__ = [
    "AuditChainStatus",
    "AuditChainVerification",
    "AuditLinkResult",
    "AuditLinkStatus",
    "StoredAuditRecord",
    "verify_audit_chain",
]
