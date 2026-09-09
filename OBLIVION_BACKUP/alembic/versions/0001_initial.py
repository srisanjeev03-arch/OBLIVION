"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(255)),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(255)),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("role_id", sa.String(64), sa.ForeignKey("roles.id"), nullable=False, index=True),
        sa.Column("permission_id", sa.String(64), sa.ForeignKey("permissions.id"), index=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), index=True),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("token_hash", sa.String(128)),
    )

    op.create_table(
        "targets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("path", sa.String(1024), nullable=False, index=True),
        sa.Column("canonical_path", sa.String(1024), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("file_count", sa.Integer()),
        sa.Column("total_size", sa.Integer()),
        sa.Column("sha256", sa.String(64), index=True),
        sa.Column("storage_profile_id", sa.String(64), index=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "operations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("target_id", sa.String(64), sa.ForeignKey("targets.id"), nullable=False, index=True),
        sa.Column("mode", sa.String(64), nullable=False),
        sa.Column("policy_id", sa.String(64), index=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="CREATED"),
        sa.Column("actor_id", sa.String(64), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("warnings", sa.Text()),
    )
    op.create_index("ix_operations_state", "operations", ["state"])

    op.create_table(
        "operation_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("from_state", sa.String(32)),
        sa.Column("to_state", sa.String(32)),
        sa.Column("payload", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_operation_events_op_seq", "operation_events", ["operation_id", "sequence"])

    op.create_table(
        "baselines",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, index=True),
        sa.Column("target_id", sa.String(64), sa.ForeignKey("targets.id"), nullable=False, index=True),
        sa.Column("file_inventory", sa.Text()),
        sa.Column("hashes", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "recovery_tests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, index=True),
        sa.Column("result_status", sa.String(32), nullable=False, index=True),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "residual_findings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, index=True),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("artifact_path", sa.String(1024)),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_residual_findings_severity", "residual_findings", ["severity"])

    op.create_table(
        "assurance_results",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("reasons", sa.Text()),
        sa.Column("limitations", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, index=True),
        sa.Column("evidence_digest", sa.String(64), nullable=False, index=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "certificates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), sa.ForeignKey("operations.id"), nullable=False, index=True),
        sa.Column("evidence_id", sa.String(64), sa.ForeignKey("evidence_records.id"), index=True),
        sa.Column("certificate_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("signing_algorithm", sa.String(32), nullable=False, server_default="Ed25519"),
        sa.Column("key_id", sa.String(128)),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text()),
        sa.Column("limitations", sa.Text()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_certificates_operation", "certificates", ["operation_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(64), index=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("operation_id", sa.String(64), index=True),
        sa.Column("target_id", sa.String(64), index=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("safe_metadata", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_actor_time", "audit_events", ["actor_id", "created_at"])
    op.create_index("ix_audit_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    for table in [
        "audit_events", "certificates", "evidence_records", "assurance_results",
        "residual_findings", "recovery_tests", "baselines", "operation_events",
        "operations", "targets", "sessions", "role_permissions",
        "permissions", "roles", "users",
    ]:
        op.drop_table(table)
