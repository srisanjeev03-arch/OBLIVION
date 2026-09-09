"""Auth and RBAC v1 schema migration (Separation of Duties columns).

Revision ID: 0002_auth_rbac
Revises: 0001_initial
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_auth_rbac"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add password_hash and last_authenticated_at to users if not present
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Add Separation of Duties fields to operations
    with op.batch_alter_table("operations") as batch_op:
        batch_op.add_column(sa.Column("requested_by", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("approved_by", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("executed_by", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("verified_by", sa.String(64), nullable=True))
        batch_op.create_index("ix_operations_requested_by", ["requested_by"])
        batch_op.create_index("ix_operations_approved_by", ["approved_by"])
        batch_op.create_index("ix_operations_executed_by", ["executed_by"])
        batch_op.create_index("ix_operations_verified_by", ["verified_by"])


def downgrade() -> None:
    with op.batch_alter_table("operations") as batch_op:
        batch_op.drop_index("ix_operations_verified_by")
        batch_op.drop_index("ix_operations_executed_by")
        batch_op.drop_index("ix_operations_approved_by")
        batch_op.drop_index("ix_operations_requested_by")
        batch_op.drop_column("verified_by")
        batch_op.drop_column("executed_by")
        batch_op.drop_column("approved_by")
        batch_op.drop_column("requested_by")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_authenticated_at")
        batch_op.drop_column("password_hash")
