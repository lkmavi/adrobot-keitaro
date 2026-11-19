"""Known access restrictions without destructive permission probes."""

import logging

from app.config import Settings

logger = logging.getLogger(__name__)


class AccessPolicy:
    """Track configured restrictions and observed API denials."""

    def __init__(self, settings: Settings):
        self.settings = settings

        self.denied: set[str] = set()

    def can_create(self, kind: str) -> bool:
        """Return whether resource creation is not known to be restricted."""
        allowed = not (kind == "offer" and not self.settings.offer_creation_enabled)
        allowed = allowed and kind not in self.denied
        logger.debug("Resource permission checked: kind=%s allowed=%s", kind, allowed)
        return allowed

    def deny(self, kind: str) -> None:
        """Remember an upstream access denial for the current process."""
        if kind in {"offer", "group", "domain", "source"}:
            self.denied.add(kind)
            logger.info("Resource creation permission denied upstream: kind=%s", kind)

    def creation_rights(self) -> dict[str, bool]:
        """Return the current creation availability for each resource type."""
        return {kind: self.can_create(kind) for kind in ("offer", "group", "domain", "source")}

    def require_create(self, kind: str) -> None:
        """Reject creation when a restriction is already known."""
        if not self.can_create(kind):
            logger.warning("Resource creation blocked by access policy: kind=%s", kind)
            raise PermissionError(
                "Создание этого ресурса отключено: у текущего ключа нет подтверждённых прав. "
                "Обратитесь к администратору Keitaro или выберите существующий ресурс."
            )
