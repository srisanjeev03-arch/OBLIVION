"""Target identity: bind an approved operation to the object that was approved.

Adds ``targets.volume_serial`` and ``targets.file_id``, both nullable.

Why nullable, and why nothing is back-filled
--------------------------------------------
A row written before this revision records no identity, and none can honestly be
invented for it now: the object it described may since have been replaced, so a
value computed today would assert a continuity that was never observed. That is
the same reasoning the audit-chain revision used for digests, and the same answer
- record absence, and make absence fail closed.

Callers must therefore treat a NULL identity as *identity not established* and
refuse the destructive step, never as *identity matches*. A target analysed
after this revision carries its identity and can be executed against; a legacy
target must be re-analysed first. Refusing a legitimate operation is recoverable;
erasing a substituted object is not.

The columns are also NULL on any host where the identity is not observable at all
(``_get_file_id`` and ``get_volume_serial`` are Windows-only), which the same
fail-closed rule covers without a special case.

Revision ID: 0005_target_identity
Revises: 0004_audit_chain
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_target_identity"
down_revision = "0004_audit_chain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("targets", sa.Column("volume_serial", sa.String(length=64), nullable=True))
    op.add_column("targets", sa.Column("file_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("targets", "file_id")
    op.drop_column("targets", "volume_serial")
