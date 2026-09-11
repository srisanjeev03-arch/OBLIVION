"""Alembic environment script."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from oblivion.persistence.database import Base, get_database_url  # noqa: E402
from oblivion.persistence.models import (  # noqa: E402,F401
    UserModel, RoleModel, PermissionModel, RolePermissionModel, SessionModel,
    TargetModel, OperationModel, OperationEventModel,
    BaselineModel, RecoveryTestModel, ResidualFindingModel, AssuranceResultModel,
    EvidenceRecordModel, CertificateModel,
    AuditEventModel,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The application decides which database this is, not alembic.ini.
#
# alembic.ini hardcodes `sqlite:///oblivion.db`, so before this every migration
# ran against whatever file happened to sit in the working directory, whatever
# OBLIVION_DATABASE_URL said. Two consequences, both bad: a deployment that
# configured its database by environment variable would have migrations
# silently applied to a different one, and a migration could not be exercised
# against a throwaway database at all - which is how they stayed untested.
#
# `get_database_url()` is the same resolver the application uses, so there is
# one answer to "which database" rather than two that usually agree.
config.set_main_option("sqlalchemy.url", get_database_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
