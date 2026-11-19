"""Tests for application behavior."""

import httpx
import pytest

from app.clients.keitaro import KeitaroClient
from app.config import Settings
from app.services.resources import ResourceService


def make_resource_service(handler):
    settings = Settings(
        keitaro_url="https://example.test",
        keitaro_api_key="test",
        campaign_prefix="test_lkmavi_",
        _env_file=None,
    )
    return ResourceService(KeitaroClient(settings, httpx.MockTransport(handler)))


@pytest.mark.parametrize(
    ("kind", "name", "url", "endpoint", "expected"),
    [
        ("group", "my group", "", "/groups", {"name": "test_lkmavi_my_group", "type": "campaigns"}),
        (
            "group",
            "test_lkmavi_group",
            "",
            "/groups",
            {"name": "test_lkmavi_group", "type": "campaigns"},
        ),
        ("domain", "Example.com", "", "/domains", {"name": "example.com"}),
        ("source", "Source", "", "/traffic_sources", {"name": "Source"}),
        (
            "offer",
            "Offer",
            "https://example.com/",
            "/offers",
            {
                "name": "Offer",
                "offer_type": "external",
                "action_type": "http",
                "action_payload": "https://example.com/",
            },
        ),
    ],
)
async def test_create_resource(kind, name, url, endpoint, expected):
    import json

    def handler(request):
        assert request.url.path.endswith(endpoint)
        assert json.loads(request.content) == expected
        return httpx.Response(200, json={"id": 42})

    assert await make_resource_service(handler).create(kind, name, url) == 42


@pytest.mark.parametrize(
    ("kind", "name", "url"),
    [
        ("other", "x", ""),
        ("group", "test_lkmavi_", ""),
        ("source", " ", ""),
        ("domain", "https://example.com", ""),
        ("domain", "127.0.0.1", ""),
        ("domain", "-example.com", ""),
        ("offer", "offer", "file:///tmp/x"),
        ("offer", "offer", "https://user:password@example.com/"),
    ],
)
async def test_invalid_resource_never_sends_request(kind, name, url):
    def handler(request):
        pytest.fail("Некорректные данные не должны отправляться")

    with pytest.raises(ValueError):
        await make_resource_service(handler).create(kind, name, url)
