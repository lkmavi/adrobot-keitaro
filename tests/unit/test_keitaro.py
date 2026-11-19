"""Tests for application behavior."""

import httpx
import pytest

from app.clients.keitaro import KeitaroClient, KeitaroError
from app.config import Settings


def client_for(handler):
    settings = Settings(
        keitaro_url="https://example.test/", keitaro_api_key="secret", _env_file=None
    )
    return KeitaroClient(settings, httpx.MockTransport(handler))


async def test_request_uses_api_header():
    def handler(request):
        assert str(request.url) == "https://example.test/admin_api/v1/offers"
        assert request.headers["Api-Key"] == "secret"
        return httpx.Response(200, json=[{"id": 1}])

    assert await client_for(handler).request("GET", "/offers") == [{"id": 1}]


async def test_empty_response():
    assert await client_for(lambda request: httpx.Response(204)).request("DELETE", "/x") is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
async def test_http_failure_hides_response_body(status):
    client = client_for(lambda request: httpx.Response(status, text="secret"))
    with pytest.raises(KeitaroError) as error:
        await client.request("GET", "/offers")
    assert str(status) in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("failure", ["network", "invalid_json"])
async def test_network_and_invalid_json(failure):
    def handler(request):
        if failure == "network":
            raise httpx.ConnectError("secret", request=request)
        return httpx.Response(200, text="not json")

    with pytest.raises(KeitaroError, match="Нет ответа") as error:
        await client_for(handler).request("GET", "/offers")
    assert "secret" not in str(error.value)


async def test_missing_credentials():
    settings = Settings(keitaro_url="", keitaro_api_key="", _env_file=None)
    with pytest.raises(KeitaroError, match="KEITARO_URL"):
        await KeitaroClient(settings).request("GET", "/offers")


async def test_forbidden_reports_permissions_and_status():
    client = client_for(lambda request: httpx.Response(403, text="private details"))
    with pytest.raises(KeitaroError, match="недостаточно прав") as error:
        await client.request("POST", "/offers")
    assert error.value.status_code == 403
    assert "private details" not in str(error.value)
