"""Request logging and form origin validation."""

import logging
import time
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next: Any) -> Response:
    """Log request outcomes without headers, bodies, or query parameters."""
    started = time.monotonic()
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        logger.exception("Request failed: exception_type=%s", type(exc).__name__)
        raise

    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    if route_path not in {"/health", "/static"}:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        log = (
            logger.error
            if response.status_code >= 500
            else (logger.warning if response.status_code >= 400 else logger.info)
        )
        log(
            "HTTP request: method=%s route=%s status=%s duration_ms=%s",
            request.method,
            route_path,
            response.status_code,
            elapsed_ms,
        )
    return response


async def protect_local_forms(request: Request, call_next: Any) -> Any:
    """Reject state-changing form submissions from another origin."""
    if request.method == "POST":
        origin = request.headers.get("origin", "")
        expected = str(request.base_url).rstrip("/")
        if origin != expected:
            logger.warning("Form submission rejected by origin check: route=%s", request.url.path)
            return HTMLResponse("Недопустимый источник запроса", status_code=403)

    return await call_next(request)
