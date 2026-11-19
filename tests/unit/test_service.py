"""Tests for application behavior."""

import json

import httpx
import pytest

from app.clients.keitaro import KeitaroClient
from app.config import Settings
from app.repositories.storage import Store
from app.services.campaigns import CampaignService, PartialCreationError


def make_service(tmp_path, handler):
    settings = Settings(
        keitaro_url="https://tracker.test", keitaro_api_key="secret", _env_file=None
    )
    return CampaignService(
        KeitaroClient(settings, httpx.MockTransport(handler)), Store(str(tmp_path / "test.db"))
    )


async def test_create_campaign_and_streams(tmp_path):
    calls = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"id": 42})

    service = make_service(tmp_path, handler)
    assert await service.create("test_lkmavi_demo", "au", 2, 3, 4, 5) == 42
    assert calls[1][2]["name"] == "test_lkmavi_demo"
    assert calls[2][2]["filters"][0]["payload"] == ["AU"]
    assert calls[3][2]["offers"][0]["share"] == 100


async def test_partial_creation_reports_id(tmp_path):
    def handler(request):
        if request.url.path.endswith("/streams"):
            return httpx.Response(500)
        return httpx.Response(200, json={"id": 42})

    service = make_service(tmp_path, handler)
    with pytest.raises(PartialCreationError, match="42"):
        await service.create("demo", "AU", 2, 3, 4, 5)


async def test_draft_cancel_and_conflict(tmp_path):
    state = {
        "id": 7,
        "name": "Offers",
        "offers": [{"offer_id": 1, "share": 100, "state": "active"}],
    }
    writes = []

    def handler(request):
        if request.method == "PUT":
            writes.append(request)
        if request.url.path.endswith("/campaigns/5/streams"):
            return httpx.Response(200, json=[state])
        return httpx.Response(200, json=state)

    service = make_service(tmp_path, handler)
    await service.fetch(5)
    await service.edit(7, "add", 2)
    assert [x["share"] for x in service.store.get(7)[1]["offers"]] == [50, 50]
    state["offers"][0]["share"] = 90
    with pytest.raises(ValueError, match="изменился"):
        await service.publish(7)
    assert not writes
    await service.edit(7, "cancel")
    assert service.store.get(7)[0] == service.store.get(7)[1]


@pytest.mark.parametrize(
    ("name", "geo", "offer_id", "domain", "group", "source"),
    [
        (" ", "AU", 1, 1, 1, 1),
        ("test", "A", 1, 1, 1, 1),
        ("test", "РУ", 1, 1, 1, 1),
        ("test", "A1", 1, 1, 1, 1),
        ("test", "AU", 0, 1, 1, 1),
        ("test", "AU", 1, -1, 1, 1),
    ],
)
async def test_create_validation_without_network(
    tmp_path, name, geo, offer_id, domain, group, source
):
    def handler(request):
        pytest.fail("Некорректные данные не должны отправляться в API")

    service = make_service(tmp_path, handler)
    with pytest.raises(ValueError):
        await service.create(name, geo, offer_id, domain, group, source)


def stream_handler(state):
    def handler(request):
        if request.url.path.endswith("/campaigns/5/streams"):
            return httpx.Response(200, json=[state])
        return httpx.Response(200, json=state)

    return handler


async def test_fetch_archives_removed_and_preserves_pins(tmp_path):
    state = {
        "id": 7,
        "name": "Offers",
        "offers": [{"offer_id": 1, "share": 50}, {"offer_id": 2, "share": 50}],
    }
    service = make_service(tmp_path, stream_handler(state))
    await service.fetch(5)
    base, _ = service.store.get(7)
    base["offers"][0]["pinned"] = True
    service.store.put(7, base, base)
    state["offers"] = [{"offer_id": 1, "share": 100}]
    await service.fetch(5)
    offers = service.store.get(7)[0]["offers"]
    assert offers[0]["pinned"] is True
    assert offers[1]["removed"] is True and offers[1]["share"] == 0


async def test_fetch_does_not_overwrite_draft(tmp_path):
    state = {"id": 7, "offers": [{"offer_id": 1, "share": 100}]}
    service = make_service(tmp_path, stream_handler(state))
    await service.fetch(5)
    await service.edit(7, "add", 2)
    before = service.store.get(7)
    with pytest.raises(ValueError, match="опубликуйте или отмените"):
        await service.fetch(5)
    assert service.store.get(7) == before


@pytest.mark.parametrize(
    ("action", "offer_id", "share"),
    [("add", 1, 0), ("remove", 99, 0), ("unknown", 1, 0), ("pin", 1, 101)],
)
async def test_invalid_edits_preserve_draft(tmp_path, action, offer_id, share):
    state = {"id": 7, "offers": [{"offer_id": 1, "share": 100}]}
    service = make_service(tmp_path, stream_handler(state))
    await service.fetch(5)
    before = service.store.get(7)
    with pytest.raises(ValueError):
        await service.edit(7, action, offer_id, share)
    assert service.store.get(7) == before


async def test_remove_restore_and_cancel(tmp_path):
    state = {"id": 7, "offers": [{"offer_id": 1, "share": 50}, {"offer_id": 2, "share": 50}]}
    service = make_service(tmp_path, stream_handler(state))
    await service.fetch(5)
    await service.edit(7, "remove", 1)
    assert [item["share"] for item in service.store.get(7)[1]["offers"]] == [0, 100]
    await service.edit(7, "restore", 1)
    assert [item["share"] for item in service.store.get(7)[1]["offers"]] == [50, 50]
    await service.edit(7, "cancel")
    assert service.store.get(7)[0] == service.store.get(7)[1]


async def test_unknown_stream(tmp_path):
    service = make_service(tmp_path, lambda request: pytest.fail("Неожиданный запрос"))
    with pytest.raises(ValueError, match="загрузите"):
        await service.edit(999, "remove", 1)
    with pytest.raises(ValueError, match="загрузите"):
        await service.publish(999)


async def test_publish_empty_does_not_write(tmp_path):
    state = {"id": 7, "offers": [{"offer_id": 1, "share": 100}]}
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(
            200, json=[state] if request.url.path.endswith("/campaigns/5/streams") else state
        )

    service = make_service(tmp_path, handler)
    await service.fetch(5)
    await service.edit(7, "remove", 1)
    with pytest.raises(ValueError, match="без активных"):
        await service.publish(7)
    assert "PUT" not in calls


async def test_publish_verifies_remote_result(tmp_path):
    state = {"id": 7, "offers": [{"offer_id": 1, "share": 100}]}
    service = make_service(tmp_path, stream_handler(state))
    await service.fetch(5)
    await service.edit(7, "add", 2)
    from app.clients.keitaro import KeitaroError

    with pytest.raises(KeitaroError, match="неожиданные данные"):
        await service.publish(7)
    base, working = service.store.get(7)
    assert base != working


async def test_unpin_rebalances(tmp_path):
    state = {"id": 7, "offers": [{"offer_id": 1, "share": 25}, {"offer_id": 2, "share": 75}]}
    service = make_service(tmp_path, stream_handler(state))
    await service.fetch(5)
    await service.edit(7, "pin", 1, 25)
    await service.edit(7, "unpin", 1)
    assert [item["share"] for item in service.store.get(7)[1]["offers"]] == [50, 50]


@pytest.mark.parametrize("name", ["test_lkmavi_", "test_lkmavi_   "])
async def test_prefix_without_name_is_rejected(tmp_path, name):
    service = make_service(tmp_path, lambda request: pytest.fail("Неожиданный запрос"))
    with pytest.raises(ValueError, match="после префикса"):
        await service.create(name, "AU", 1, 1, 1, 1)
