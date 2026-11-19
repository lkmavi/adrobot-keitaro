"""SQLite storage for stream drafts and published snapshots."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class Store:
    """Persist stream snapshots and drafts in SQLite."""

    def __init__(self, path: str):
        """Initialize the SQLite database and its schema."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        self.path = path

        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS drafts "
                "(stream_id INTEGER PRIMARY KEY, base TEXT NOT NULL, working TEXT NOT NULL)"
            )

    def get(self, stream_id: int) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Return the published snapshot and draft for a stream, if present."""
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute(
                "SELECT base, working FROM drafts WHERE stream_id = ?", (stream_id,)
            ).fetchone()

        return (json.loads(row[0]), json.loads(row[1])) if row else None

    def put(self, stream_id: int, base: dict[str, Any], working: dict[str, Any]) -> None:
        """Persist a stream snapshot and draft in a single transaction."""
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO drafts (stream_id, base, working) VALUES (?, ?, ?)",
                (
                    stream_id,
                    json.dumps(base, ensure_ascii=False),
                    json.dumps(working, ensure_ascii=False),
                ),
            )
