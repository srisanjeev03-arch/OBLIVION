"""Phase 23: evidence chain linkage and certificate verification bindings.

Every column added here is nullable. Existing rows keep their values and simply
have no Phase 23 bindings, which the verifier reports as absent fields rather
than treating as tampering - a legacy certificate is judged, not destroyed.

Revision ID: 0003_phase23_evidence_certificate
Revises: 0002_auth_rbac
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_phase23_evidence_certificate"
down_revision = "0002_auth_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evidence_records") as batch_op:
        # Which canonical byte form produced evidence_digest. Without it a future
        # codec change would silently reinterpret an existing digest.
        batch_op.add_column(
            sa.Column("canonicalization_version", sa.String(32), nullable=True)
        )
        # Chain linkage: both set together, or neither.
        batch_op.add_column(sa.Column("previous_evidence_id", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("previous_evidence_digest", sa.String(64), nullable=True)
        )
        batch_op.create_index("ix_evidence_records_previous", ["previous_evidence_id"])

    with op.batch_alter_table("certificates") as batch_op:
        batch_op.add_column(
            sa.Column("canonicalization_version", sa.String(32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("evidence_schema_version", sa.String(32), nullable=True)
        )
        # What the certificate is about, so a verifier can compare it against an
        # independently supplied expectation.
        batch_op.add_column(sa.Column("target_identity", sa.String(1024), nullable=True))
        batch_op.add_column(sa.Column("method", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("result", sa.String(32), nullable=True))
        # The signer identity a TrustStore is keyed by. Confers nothing alone.
        batch_op.add_column(sa.Column("signer_id", sa.String(128), nullable=True))
        batch_op.create_index("ix_certificates_signer", ["signer_id"])


def downgrade() -> None:
    with op.batch_alter_table("certificates") as batch_op:
        batch_op.drop_index("ix_certificates_signer")
        batch_op.drop_column("signer_id")
        batch_op.drop_column("result")
        batch_op.drop_column("method")
        batch_op.drop_column("target_identity")
        batch_op.drop_column("evidence_schema_version")
        batch_op.drop_column("canonicalization_version")

    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.drop_index("ix_evidence_records_previous")
        batch_op.drop_column("previous_evidence_digest")
        batch_op.drop_column("previous_evidence_id")
        batch_op.drop_column("canonicalization_version")
