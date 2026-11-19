"""Persist stream baselines and editable drafts independently of Keitaro."""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.repositories.migrations import upgrade_database

logger = logging.getLogger(__name__)


class Store:
    """Store each stream's published baseline beside its current working copy.

    Keeping both snapshots lets the service detect local edits and upstream
    changes before replacing a stream in Keitaro.
    """

    def __init__(self, path: str):
        """Apply pending schema upgrades before opening the draft store."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        self.path = path
        upgrade_database(path)
        logger.info("Draft storage initialized: database=%s", path)

    def get(self, stream_id: int) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Return ``(baseline, working_copy)`` or ``None`` when no draft exists."""
        logger.debug("Draft lookup started: stream_id=%s", stream_id)
        try:
            with closing(sqlite3.connect(self.path)) as db, db:
                row = db.execute(
                    "SELECT base, working FROM drafts WHERE stream_id = ?", (stream_id,)
                ).fetchone()

            result = (json.loads(row[0]), json.loads(row[1])) if row else None
            logger.debug("Draft lookup completed: stream_id=%s found=%s", stream_id, bool(result))
            return result
        except (sqlite3.Error, json.JSONDecodeError):
            logger.exception("Draft lookup failed: stream_id=%s", stream_id)
            raise

    def put(self, stream_id: int, base: dict[str, Any], working: dict[str, Any]) -> None:
        """Atomically replace both snapshots so they cannot become inconsistent."""
        logger.debug("Draft save started: stream_id=%s", stream_id)
        try:
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute(
                    "INSERT OR REPLACE INTO drafts (stream_id, base, working) VALUES (?, ?, ?)",
                    (
                        stream_id,
                        json.dumps(base, ensure_ascii=False),
                        json.dumps(working, ensure_ascii=False),
                    ),
                )
            logger.debug("Draft save completed: stream_id=%s", stream_id)
        except (sqlite3.Error, TypeError, ValueError):
            logger.exception("Draft save failed: stream_id=%s", stream_id)
            raise
