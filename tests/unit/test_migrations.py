"""Verify new database creation and safe adoption of legacy SQLite schemas."""

import sqlite3
from contextlib import closing

import pytest

from app.repositories.migrations import upgrade_database


def test_upgrade_creates_schema_and_is_idempotent(tmp_path):
    """Create the draft schema once and record its revision across repeat runs."""
    database_path = str(tmp_path / "nested" / "fresh.sqlite3")

    upgrade_database(database_path)
    upgrade_database(database_path)

    with closing(sqlite3.connect(database_path)) as database, database:
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master")}
        columns = {row[1] for row in database.execute("PRAGMA table_info(drafts)")}
        revision = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert "drafts" in tables
    assert columns == {"stream_id", "base", "working"}
    assert revision == "0001_create_drafts"


def test_upgrade_adopts_legacy_drafts_without_losing_data(tmp_path):
    """Register the pre-migration schema and retain previously saved drafts."""
    database_path = str(tmp_path / "legacy.sqlite3")
    with closing(sqlite3.connect(database_path)) as database, database:
        database.execute(
            "CREATE TABLE drafts "
            "(stream_id INTEGER PRIMARY KEY, base TEXT NOT NULL, working TEXT NOT NULL)"
        )
        database.execute(
            "INSERT INTO drafts VALUES (?, ?, ?)",
            (42, '{"name":"Legacy"}', '{"offers":[]}'),
        )

    upgrade_database(database_path)

    with closing(sqlite3.connect(database_path)) as database, database:
        draft = database.execute(
            "SELECT base, working FROM drafts WHERE stream_id = ?", (42,)
        ).fetchone()
        revision = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert draft == ('{"name":"Legacy"}', '{"offers":[]}')
    assert revision == "0001_create_drafts"


def test_upgrade_rejects_incompatible_legacy_table(tmp_path):
    """Fail clearly rather than silently reinterpreting an unknown table shape."""
    database_path = str(tmp_path / "incompatible.sqlite3")
    with closing(sqlite3.connect(database_path)) as database, database:
        database.execute("CREATE TABLE drafts (id INTEGER PRIMARY KEY)")

    with pytest.raises(RuntimeError, match="does not match the expected schema"):
        upgrade_database(database_path)
