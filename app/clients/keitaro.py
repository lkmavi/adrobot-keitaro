"""HTTP client for the Keitaro Admin API."""

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class KeitaroError(Exception):
    """A sanitized API error with an optional upstream HTTP status."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class KeitaroClient:
    """Send authenticated requests to the Keitaro Admin API."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        """Initialize the client with settings and an optional test transport."""
        self.settings = settings

        self.transport = transport

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send an Admin API request and translate upstream failures."""
        if not self.settings.keitaro_url or not self.settings.keitaro_api_key:
            logger.error("Keitaro request rejected: API URL or API key is not configured")
            raise KeitaroError("Укажите KEITARO_URL и KEITARO_API_KEY в .env")

        base = self.settings.keitaro_url.rstrip("/") + "/admin_api/v1"
        logger.debug(
            "Keitaro request started: method=%s endpoint=%s", method, path.split("?", 1)[0]
        )
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.keitaro_timeout, transport=self.transport
            ) as client:
                response = await client.request(
                    method,
                    base + path,
                    headers={"Api-Key": self.settings.keitaro_api_key},
                    **kwargs,
                )

                logger.debug(
                    "Keitaro response received: method=%s status=%s", method, response.status_code
                )
                response.raise_for_status()

                return response.json() if response.content else None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            log = logger.error if status >= 500 else logger.warning
            log(
                "Keitaro request failed: method=%s endpoint=%s status=%s",
                method,
                path.split("?", 1)[0],
                status,
            )

            if status == 403:
                raise KeitaroError(
                    "Keitaro отклонил операцию (HTTP 403): у текущего ключа или пользователя "
                    "недостаточно прав. Проверьте права доступа в Keitaro.",
                    status,
                ) from exc
            raise KeitaroError(f"Keitaro вернул HTTP {status}", status) from exc
        except (httpx.RequestError, ValueError) as exc:
            logger.error(
                "Keitaro connection or response format error: "
                "method=%s endpoint=%s exception_type=%s",
                method,
                path.split("?", 1)[0],
                type(exc).__name__,
            )
            raise KeitaroError("Нет ответа Keitaro или ответ имеет неверный формат") from exc
