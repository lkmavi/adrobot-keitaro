"""Tests for application behavior."""

from app.repositories.storage import Store


def test_storage_persists_and_replaces(tmp_path):
    path = str(tmp_path / "nested" / "state.db")
    store = Store(path)
    assert store.get(1) is None
    store.put(1, {"name": "Поток"}, {"items": [1]})
    store.put(1, {"name": "Поток"}, {"items": [2]})
    store.put(2, {"name": "Другой"}, {})
    reopened = Store(path)
    assert reopened.get(1) == ({"name": "Поток"}, {"items": [2]})
    assert reopened.get(2) == ({"name": "Другой"}, {})
