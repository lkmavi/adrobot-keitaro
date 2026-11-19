"""Structured logging configuration."""

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from app.config import Settings


class JsonLogFormatter(logging.Formatter):
    """Format an application log record as a single JSON line."""

    def __init__(self, service_name: str):
        super().__init__()

        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record as a JSON object on one line."""
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    """Configure application logging and optional rotating JSON output."""
    log_format = (
        f"%(asctime)s %(levelname)s service={settings.service_name} "
        "logger=%(name)s function=%(funcName)s %(message)s"
    )
    logging.basicConfig(level=logging.INFO, format=log_format)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if settings.log_file:
        handler = RotatingFileHandler(
            settings.log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(JsonLogFormatter(settings.service_name))
        app_logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
