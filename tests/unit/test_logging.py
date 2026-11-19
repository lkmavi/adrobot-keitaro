"""Tests for application behavior."""

import json
import logging

from app.logging_config import JsonLogFormatter


def test_json_formatter_contains_code_location_and_escapes_lines():
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="/tmp/example.py",
        lineno=42,
        msg="Action %s\nnext",
        args=("done",),
        exc_info=None,
        func="example_function",
    )
    formatted = JsonLogFormatter("adrobot").format(record)
    payload = json.loads(formatted)
    assert "\n" not in formatted
    assert payload["service"] == "adrobot"
    assert payload["logger"] == "app.test"
    assert payload["function"] == "example_function"
    assert payload["line"] == 42
    assert payload["level"] == "INFO"
    assert payload["message"] == "Action done\nnext"
