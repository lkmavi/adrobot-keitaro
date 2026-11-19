"""Campaign creation and stream editing use cases."""

import logging
from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.clients.keitaro import KeitaroClient, KeitaroError
from app.repositories.storage import Store
from app.services.weights import redistribute

logger = logging.getLogger(__name__)


class PartialCreationError(Exception):
    """Report a campaign created without all required streams."""


def remote_signature(stream: dict[str, Any]) -> list[tuple[int, int, str]]:
    """Return a stable representation of the upstream offer assignments."""
    return sorted(
        (int(item["offer_id"]), int(item.get("share", 0)), item.get("state", "active"))
        for item in stream.get("offers", [])
    )


class CampaignService:
    """Coordinate campaign creation and stream editing."""

    def __init__(self, client: KeitaroClient, store: Store):
        """Initialize the campaign service with its dependencies."""
        self.client = client
        self.store = store

    async def create(
        self, name: str, geo: str, offer_id: int, domain: int, group: int, source: int
    ) -> int:
        """Create a campaign and its GEO and offer streams."""
        logger.debug("Campaign creation started: geo=%s", geo.strip().upper())
        name, geo = name.strip(), geo.strip().upper()

        if (
            not name
            or len(geo) != 2
            or not geo.isascii()
            or not geo.isalpha()
            or min(offer_id, domain, group, source) <= 0
        ):
            logger.warning("Campaign creation validation failed: reason=invalid_input")
            raise ValueError("Укажите название, двухбуквенный GEO и корректные ID")

        prefix = self.client.settings.campaign_prefix

        suffix = name[len(prefix) :].strip() if name.startswith(prefix) else name

        if not suffix:
            logger.warning("Campaign creation validation failed: reason=empty_name_suffix")
            raise ValueError("Введите название кампании после префикса")

        name = prefix + suffix

        await self.client.request("GET", f"/offers/{offer_id}")

        campaign = await self.client.request(
            "POST",
            "/campaigns",
            json={
                "name": name,
                "alias": uuid4().hex[:12],
                "type": "position",
                "domain_id": domain,
                "group_id": str(group),
                "traffic_source_id": source,
            },
        )

        campaign_id = int(campaign["id"])
        logger.info("Campaign created: campaign_id=%s", campaign_id)
        try:
            await self.client.request(
                "POST",
                "/streams",
                json={
                    "campaign_id": campaign_id,
                    "name": "GEO → Google",
                    "type": "regular",
                    "position": 1,
                    "schema": "redirect",
                    "action_type": "http",
                    "action_payload": self.client.settings.redirect_url,
                    "filters": [{"name": "country", "mode": "accept", "payload": [geo]}],
                },
            )

            await self.client.request(
                "POST",
                "/streams",
                json={
                    "campaign_id": campaign_id,
                    "name": "Offers",
                    "type": "default",
                    "position": 2,
                    "schema": "landings",
                    "action_type": "http",
                    "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
                },
            )
        except KeitaroError as exc:
            logger.error("Campaign partially created: campaign_id=%s", campaign_id)

            raise PartialCreationError(
                f"Кампания {campaign_id} создана частично. Проверьте её в Keitaro: {exc}"
            ) from exc

        return campaign_id

    async def fetch(self, campaign_id: int) -> list[dict[str, Any]]:
        """Refresh streams while preserving previously archived offers."""
        logger.debug("Fetching streams: campaign_id=%s", campaign_id)

        streams = await self.client.request("GET", f"/campaigns/{campaign_id}/streams")

        for stream in streams:
            existing = self.store.get(int(stream["id"]))
            if existing and existing[0] != existing[1]:
                logger.warning(
                    "Campaign refresh blocked by pending draft: campaign_id=%s stream_id=%s",
                    campaign_id,
                    stream["id"],
                )
                raise ValueError("Сначала опубликуйте или отмените изменения потока")
        for stream in streams:
            current = self.store.get(int(stream["id"]))

            old = {int(x["offer_id"]): x for x in current[0]["offers"]} if current else {}

            entries = []
            for item in stream.get("offers", []):
                oid = int(item["offer_id"])
                entries.append(
                    {
                        "offer_id": oid,
                        "share": int(item.get("share", 0)),
                        "pinned": old.get(oid, {}).get("pinned", False),
                        "removed": False,
                        "state": item.get("state", "active"),
                    }
                )

            present = {entry["offer_id"] for entry in entries}
            entries.extend(
                {**item, "removed": True, "share": 0, "pinned": False}
                for oid, item in old.items()
                if oid not in present
            )

            snapshot = {
                "campaign_id": campaign_id,
                "name": stream.get("name", "Поток"),
                "offers": entries,
                "signature": remote_signature(stream),
            }

            snapshot["signature"] = [list(item) for item in snapshot["signature"]]
            self.store.put(int(stream["id"]), snapshot, deepcopy(snapshot))

        return streams

    async def edit(self, stream_id: int, action: str, offer_id: int = 0, share: int = 0) -> None:
        """Apply an offer action to the local stream draft."""
        current = self.store.get(stream_id)
        if not current:
            logger.warning("Stream edit rejected: stream_id=%s reason=draft_not_loaded", stream_id)
            raise ValueError("Сначала загрузите потоки кампании")
        base, working = current
        offers = working["offers"]
        item = next((x for x in offers if x["offer_id"] == offer_id), None)
        if action == "cancel":
            self.store.put(stream_id, base, deepcopy(base))
            logger.info("Draft cancelled: stream_id=%s", stream_id)
            return
        if action == "add":
            if item:
                raise ValueError("Оффер уже есть в списке: восстановите его из архива")
            await self.client.request("GET", f"/offers/{offer_id}")
            offers.append(
                {
                    "offer_id": offer_id,
                    "share": 0,
                    "pinned": False,
                    "removed": False,
                    "state": "active",
                }
            )
        elif not item:
            raise ValueError("Оффер не найден в этом потоке")
        elif action == "remove":
            item.update(removed=True, pinned=False, share=0)
        elif action == "restore":
            item.update(removed=False, pinned=False)
        elif action == "pin":
            item.update(pinned=True, share=share)
        elif action == "unpin":
            item["pinned"] = False
        else:
            raise ValueError("Неизвестное действие")

        working["offers"] = redistribute(offers)
        self.store.put(stream_id, base, working)
        logger.debug("Draft updated: stream_id=%s action=%s", stream_id, action)

    async def publish(self, stream_id: int) -> None:
        """Publish a draft after checking for upstream changes."""
        current = self.store.get(stream_id)
        if not current:
            logger.warning(
                "Stream publish rejected: stream_id=%s reason=draft_not_loaded", stream_id
            )
            raise ValueError("Сначала загрузите потоки кампании")
        base, working = current
        remote = await self.client.request("GET", f"/streams/{stream_id}")
        if [list(x) for x in remote_signature(remote)] != base["signature"]:
            logger.warning("Stream publish rejected: stream_id=%s reason=remote_changed", stream_id)
            raise ValueError(
                "Поток изменился в Keitaro. Отмените черновик и загрузите потоки снова"
            )
        logger.debug("Snapshot checked before publish: stream_id=%s", stream_id)

        offers = [
            {"offer_id": x["offer_id"], "share": x["share"], "state": x["state"]}
            for x in working["offers"]
            if not x["removed"]
        ]
        if not offers:
            logger.warning(
                "Stream publish rejected: stream_id=%s reason=no_active_offers", stream_id
            )
            raise ValueError("Нельзя опубликовать поток без активных офферов")
        await self.client.request("PUT", f"/streams/{stream_id}", json={"offers": offers})

        saved = await self.client.request("GET", f"/streams/{stream_id}")
        expected = sorted((x["offer_id"], x["share"], x["state"]) for x in offers)
        if remote_signature(saved) != expected:
            logger.error("Stream publish verification failed: stream_id=%s", stream_id)
            raise KeitaroError(
                "Keitaro вернул неожиданные данные после сохранения; проверьте поток"
            )
        working["signature"] = [list(x) for x in remote_signature(saved)]
        self.store.put(stream_id, working, deepcopy(working))
        logger.info("Stream published: stream_id=%s", stream_id)
