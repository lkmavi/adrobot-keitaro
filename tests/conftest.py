"""Tests for application behavior."""

import os
import tempfile

_test_dir = tempfile.TemporaryDirectory(prefix="adrobot-tests-")

os.environ["KEITARO_URL"] = "http://test.invalid"
os.environ["KEITARO_API_KEY"] = "test-only-key"
os.environ["DATABASE_PATH"] = os.path.join(_test_dir.name, "app.sqlite3")


os.environ["OFFER_CREATION_ENABLED"] = "true"
