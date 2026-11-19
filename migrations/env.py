"""Run Alembic revisions against the configured SQLite database."""

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from app.config import Settings

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Emit migration SQL using the database URL from application settings."""
    database_path = config.attributes.get("database_path") or Settings().database_path
    database_url = URL.create("sqlite", database=str(Path(database_path).resolve()))
    context.configure(url=database_url.render_as_string(hide_password=False), literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply revisions through a SQLite connection to the configured database."""
    database_path = config.attributes.get("database_path") or Settings().database_path
    database_path = Path(database_path).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = URL.create("sqlite", database=str(database_path))
    engine = create_engine(database_url)

    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None, render_as_batch=True)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
