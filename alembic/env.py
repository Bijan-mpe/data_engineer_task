"""Alembic migration environment.

Reads the database URL from application settings so migration commands
use the same connection as the running application.

src.models.orm is imported explicitly so all ORM classes are registered
with Base.metadata before Alembic inspects it for autogeneration.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import src.models.orm  # noqa: F401 — registers all ORM classes with Base.metadata
from alembic import context
from src.core.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Return the database URL from the module-level settings singleton."""
    from src.core.config import settings

    return settings.database_url


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without a live DB connection."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live DB connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
