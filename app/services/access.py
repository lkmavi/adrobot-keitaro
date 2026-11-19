"""Known access restrictions without destructive permission probes."""

from app.config import Settings


class AccessPolicy:
    """Track configured restrictions and observed API denials."""

    def __init__(self, settings: Settings):
        self.settings = settings

        self.denied: set[str] = set()

    def can_create(self, kind: str) -> bool:
        """Return whether resource creation is not known to be restricted."""
        if kind == "offer" and not self.settings.offer_creation_enabled:
            return False
        return kind not in self.denied

    def deny(self, kind: str) -> None:
        """Remember an upstream access denial for the current process."""
        if kind in {"offer", "group", "domain", "source"}:
            self.denied.add(kind)

    def creation_rights(self) -> dict[str, bool]:
        """Return the current creation availability for each resource type."""
        return {kind: self.can_create(kind) for kind in ("offer", "group", "domain", "source")}

    def require_create(self, kind: str) -> None:
        """Reject creation when a restriction is already known."""
        if not self.can_create(kind):
            raise PermissionError(
                "Создание этого ресурса отключено: у текущего ключа нет подтверждённых прав. "
                "Обратитесь к администратору Keitaro или выберите существующий ресурс."
            )
