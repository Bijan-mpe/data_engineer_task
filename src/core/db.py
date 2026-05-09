"""
Database engine, session factory, and session lifecycle helpers.

Two session shapes are provided for different callers:
  get_session()    — plain generator for FastAPI Depends(); FastAPI manages teardown.
  session_scope()  — @contextmanager for pipeline and script code that uses `with`.

Both implement the same commit-on-success / rollback-on-exception contract.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import settings

engine = create_engine(
    URL.create(
        drivername="postgresql",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    ),
    pool_pre_ping=True,
)
SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Shared declarative base — all ORM models must inherit from this."""

    pass


def get_session() -> Generator[Session, None, None]:
    """
    Plain generator dependency for FastAPI.

    Usage:
        @router.get("/")
        def endpoint(session: Session = Depends(get_session)):
            ...
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context-manager wrapper for pipeline and script code.

    Usage:
        with session_scope() as session:
            session.add(record)
    """
    yield from get_session()
