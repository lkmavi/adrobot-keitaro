"""Track configured and observed API restrictions without probing by mutation."""

import logging

from app.config import Settings

logger = logging.getLogger(__name__)


class AccessPolicy:
    """Keep conservative resource-creation rights for the current process.

    A resource kind is disabled after an upstream 403 because the API does not
    provide a safe, read-only permission check for these creation operations.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        self.denied: set[str] = set()

    def can_create(self, kind: str) -> bool:
        """Return false for configured restrictions or previously observed 403s."""
        allowed = not (kind == "offer" and not self.settings.offer_creation_enabled)
        allowed = allowed and kind not in self.denied
        logger.debug("Resource permission checked: kind=%s allowed=%s", kind, allowed)
        return allowed

    def deny(self, kind: str) -> None:
        """Remember a recognized resource denial for subsequent UI requests."""
        if kind in {"offer", "group", "domain", "source"}:
            self.denied.add(kind)
            logger.info("Resource creation permission denied upstream: kind=%s", kind)

    def creation_rights(self) -> dict[str, bool]:
        """Build the resource-to-availability mapping consumed by templates."""
        return {kind: self.can_create(kind) for kind in ("offer", "group", "domain", "source")}

    def require_create(self, kind: str) -> None:
        """Raise a readable permission error before a known-forbidden API call."""
        if not self.can_create(kind):
            logger.warning("Resource creation blocked by access policy: kind=%s", kind)
            raise PermissionError(
                "Создание этого ресурса отключено: у текущего ключа нет подтверждённых прав. "
                "Обратитесь к администратору Keitaro или выберите существующий ресурс."
            )
