"""SQLAlchemy 2.x engine, session, and Base setup."""
import os
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


class Base(DeclarativeBase):
    """Declarative base for all Oblivion models."""


_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker[Session]] = None


def get_database_url() -> str:
    """Returns the database URL. Defaults to SQLite file."""
    url = os.environ.get("OBLIVION_DATABASE_URL")
    if url:
        return url
    db_path = os.environ.get("OBLIVION_DATABASE_PATH", "oblivion.db")
    return f"sqlite:///{db_path}"


def get_engine() -> Engine:
    """Returns the global SQLAlchemy engine, creating it if needed."""
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args: dict[str, object] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Returns the global session factory, creating it if needed."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def reset_engine() -> None:
    """Disposes the current engine (useful for tests)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def init_db() -> None:
    """Creates all tables. Used for tests and initial setup."""
    from oblivion.persistence.models import (  # noqa: F401  (ensure models are registered)
        UserModel, RoleModel, PermissionModel, RolePermissionModel, SessionModel,
        TargetModel, OperationModel, OperationEventModel,
        BaselineModel, RecoveryTestModel, ResidualFindingModel, AssuranceResultModel,
        EvidenceRecordModel, CertificateModel,
        AuditEventModel,
    )
    Base.metadata.create_all(bind=get_engine())
