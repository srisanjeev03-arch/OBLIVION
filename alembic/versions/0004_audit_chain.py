"""Audit log: tamper-evident chaining and server-derived actor provenance.

Every column added here is nullable, and ``sequence`` defaults to 0. Rows
written by the previous revision therefore survive the upgrade unchanged - they
simply carry no digest and no link.

That is deliberate and is *not* a silent downgrade of the guarantee. A legacy
row has ``digest = NULL``, and ``core/audit/log.py`` refuses to append on top of
a tail with no digest rather than fabricating a link to it. Verification
likewise reports such rows as unverifiable rather than intact: the chain begins
where real digests begin, and history before that point is stated as
unestablished rather than quietly vouched for.

Back-filling digests over legacy rows was considered and rejected. Computing a
digest now, over content that was never hashed at the time, would manufacture
exactly the evidence of integrity that does not exist - the one thing an audit
log must never do.

Revision ID: 0004_audit_chain
Revises: 0003_phase23_evidence_certificate
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_audit_chain"
down_revision = "0003_phase23_evidence_certificate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        # Position in the log. 1-based and contiguous for rows this revision
        # writes; 0 for pre-existing rows, which is how they are recognised.
        batch_op.add_column(
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0")
        )

        # Actor provenance. Without `actor_source`, "system" and an
        # authenticated principal are two strings in one column and a reader
        # cannot tell a proven identity from an asserted one.
        batch_op.add_column(sa.Column("actor_role", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("actor_source", sa.String(32), nullable=True))

        # References to the artefacts an act produced. References, not copies:
        # the audit log points at evidence, it does not restate it.
        batch_op.add_column(sa.Column("evidence_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("certificate_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=True))

        # The canonical ISO-8601 instant that was hashed, stored as text so it
        # round-trips byte for byte. A DateTime column under SQLite drops the
        # timezone, which would change the hashed representation on reload and
        # report every honest row as mutated.
        batch_op.add_column(sa.Column("occurred_at", sa.String(64), nullable=True))

        batch_op.add_column(sa.Column("schema_version", sa.String(32), nullable=True))
        batch_op.add_column(
            sa.Column("canonicalization_version", sa.String(32), nullable=True)
        )

        # The digest as computed at append time, and the link to the
        # predecessor. Verification recomputes from stored content and compares
        # against `digest`, so this column must never be rewritten.
        batch_op.add_column(sa.Column("digest", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("previous_audit_id", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("previous_audit_digest", sa.String(64), nullable=True)
        )

        batch_op.create_index("ix_audit_events_evidence_id", ["evidence_id"])
        batch_op.create_index("ix_audit_events_certificate_id", ["certificate_id"])
        batch_op.create_index("ix_audit_events_occurred_at", ["occurred_at"])

    # Unique, so two concurrent appends cannot both claim one position: the
    # loser's insert fails and it retries against the new tail instead of
    # forking history.
    op.create_index("ix_audit_sequence", "audit_events", ["sequence"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_audit_sequence", table_name="audit_events")
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_events_occurred_at")
        batch_op.drop_index("ix_audit_events_certificate_id")
        batch_op.drop_index("ix_audit_events_evidence_id")
        batch_op.drop_column("previous_audit_digest")
        batch_op.drop_column("previous_audit_id")
        batch_op.drop_column("digest")
        batch_op.drop_column("canonicalization_version")
        batch_op.drop_column("schema_version")
        batch_op.drop_column("occurred_at")
        batch_op.drop_column("summary")
        batch_op.drop_column("certificate_id")
        batch_op.drop_column("evidence_id")
        batch_op.drop_column("actor_source")
        batch_op.drop_column("actor_role")
        batch_op.drop_column("sequence")
