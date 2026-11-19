"""Creation of supported Keitaro resources."""

import ipaddress
import logging
import re
from urllib.parse import urlsplit

from app.clients.keitaro import KeitaroClient

logger = logging.getLogger(__name__)


class ResourceService:
    """Validate and create supported Keitaro resources."""

    def __init__(self, client: KeitaroClient):
        self.client = client

    async def create(self, kind: str, name: str, url: str = "") -> int:
        """Validate and create a supported resource in Keitaro."""
        logger.debug("Resource creation started: kind=%s", kind)
        name = name.strip()
        if not name or kind not in {"group", "domain", "source", "offer"}:
            logger.warning(
                "Resource creation validation failed: kind=%s reason=invalid_kind_or_name", kind
            )
            raise ValueError("Укажите корректный тип и название ресурса")
        if kind == "group":
            prefix = self.client.settings.campaign_prefix
            suffix = name[len(prefix) :] if name.startswith(prefix) else name
            suffix = re.sub(r"\s+", "_", suffix.strip())
            if not suffix:
                logger.warning(
                    "Resource creation validation failed: kind=group reason=empty_suffix"
                )
                raise ValueError("Введите название группы после префикса")
            payload = {"name": prefix + suffix, "type": "campaigns"}
            path = "/groups"
        elif kind == "domain":
            domain = name.lower().rstrip(".")
            labels = domain.split(".")
            if len(labels) < 2 or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
            ):
                logger.warning(
                    "Resource creation validation failed: kind=domain reason=invalid_domain"
                )
                raise ValueError("Введите имя домена без схемы, пути и порта")
            try:
                ipaddress.ip_address(domain)
            except ValueError:
                pass
            else:
                logger.warning("Resource creation validation failed: kind=domain reason=ip_address")
                raise ValueError("Укажите доменное имя, а не IP-адрес")
            path, payload = "/domains", {"name": domain}
        elif kind == "source":
            path, payload = "/traffic_sources", {"name": name}
        else:
            target = urlsplit(url.strip())
            if target.scheme not in {"http", "https"} or not target.hostname or target.username:
                logger.warning("Resource creation validation failed: kind=offer reason=invalid_url")
                raise ValueError("Укажите корректный HTTP или HTTPS URL оффера")
            path, payload = (
                "/offers",
                {
                    "name": name,
                    "offer_type": "external",
                    "action_type": "http",
                    "action_payload": url.strip(),
                },
            )

        result = await self.client.request("POST", path, json=payload)
        resource_id = int(result["id"])
        logger.info("Resource created: kind=%s id=%s", kind, resource_id)
        return resource_id
