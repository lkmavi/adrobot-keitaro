"""Apply versioned SQLite schema changes through Alembic."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def upgrade_database(database_path: str) -> None:
    """Apply all pending revisions to the configured database file."""
    logger.info("Database migration started")
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_path"] = database_path
    config.attributes["configure_logger"] = False

    try:
        command.upgrade(config, "head")
    except Exception:
        logger.exception("Database migration failed")
        raise

    logger.info("Database migration completed")
