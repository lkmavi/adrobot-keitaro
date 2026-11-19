"""Tests for application behavior."""

from fastapi.testclient import TestClient

import app.context as context
import app.main as main


class FakeClient:
    async def request(self, method, path, **kwargs):
        if path.endswith("/streams"):
            return [{"id": 12, "name": "Offers", "offers": []}]
        return [{"id": 1, "name": "Example"}]


def test_pages_render(monkeypatch):
    monkeypatch.setattr(context, "client", FakeClient())
    with TestClient(main.app) as client:
        home = client.get("/")
        editor = client.get("/campaigns/5")
    assert home.status_code == 200
    assert "Example" in home.text
    assert editor.status_code == 200
    assert "Offers" in editor.text


def test_cross_origin_post_is_rejected():
    with TestClient(main.app) as client:
        response = client.post("/campaigns/5/fetch", headers={"Origin": "https://other.example"})
    assert response.status_code == 403


class FakeService:
    async def create(self, *args):
        if args[0] == "bad":
            raise ValueError("Неверное название")
        return 123

    async def fetch(self, campaign_id):
        if campaign_id == 99:
            raise ValueError("Есть черновик")

    async def edit(self, *args):
        if args[1] == "bad":
            raise ValueError("Неверное действие")

    async def publish(self, stream_id):
        return None


def test_create_form_success_and_failure(monkeypatch):
    monkeypatch.setattr(context, "client", FakeClient())
    monkeypatch.setattr(context, "service", FakeService())
    headers = {"Origin": "http://testserver"}
    data = {"name": "ok", "geo": "AU", "offer_id": 1, "domain_id": 1, "group_id": 1, "source_id": 1}
    with TestClient(main.app) as client:
        assert "123" in client.post("/campaigns", data=data, headers=headers).text
        assert (
            "Неверное название"
            in client.post("/campaigns", data={**data, "name": "bad"}, headers=headers).text
        )
        assert client.post("/campaigns", data={}, headers=headers).status_code == 422


def test_fetch_form(monkeypatch):
    monkeypatch.setattr(context, "client", FakeClient())
    monkeypatch.setattr(context, "service", FakeService())
    with TestClient(main.app) as client:
        assert (
            "Потоки загружены"
            in client.post("/campaigns/5/fetch", headers={"Origin": "http://testserver"}).text
        )
        assert (
            "Есть черновик"
            in client.post("/campaigns/99/fetch", headers={"Origin": "http://testserver"}).text
        )


def test_edit_form_checks_ownership(monkeypatch, tmp_path):
    from app.repositories.storage import Store

    store = Store(str(tmp_path / "web.db"))
    store.put(
        12,
        {"campaign_id": 5, "offers": [], "signature": []},
        {"campaign_id": 5, "offers": [], "signature": []},
    )
    monkeypatch.setattr(context, "store", store)
    monkeypatch.setattr(context, "client", FakeClient())
    monkeypatch.setattr(context, "service", FakeService())
    headers = {"Origin": "http://testserver"}
    with TestClient(main.app) as client:
        response = client.post(
            "/campaigns/5/streams/12",
            data={"action": "publish"},
            headers=headers,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert (
            "Поток не загружен"
            in client.post(
                "/campaigns/9/streams/12", data={"action": "publish"}, headers=headers
            ).text
        )
        assert (
            "Неверное действие"
            in client.post("/campaigns/5/streams/12", data={"action": "bad"}, headers=headers).text
        )


def test_api_failure_is_visible(monkeypatch):
    from app.clients.keitaro import KeitaroError

    class BrokenClient:
        async def request(self, method, path, **kwargs):
            raise KeitaroError("Трекер недоступен")

    monkeypatch.setattr(context, "client", BrokenClient())
    with TestClient(main.app) as client:
        assert "Трекер недоступен" in client.get("/").text
        assert "Трекер недоступен" in client.get("/campaigns/5").text


def test_editor_navigation():
    with TestClient(main.app) as client:
        page = client.get("/editor")
        assert page.status_code == 200
        assert "Откройте кампанию" in page.text
        response = client.get("/editor/open", params={"campaign_id": 42}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/campaigns/42"
        invalid = client.get("/editor/open", params={"campaign_id": 0}, follow_redirects=False)
        assert invalid.headers["location"] == "/editor"


def test_resource_page_and_form(monkeypatch):
    class FakeResourceService:
        async def create(self, kind, name, url):
            if name == "bad":
                raise ValueError("Некорректное название")
            return 42

    monkeypatch.setattr(context, "resource_service", FakeResourceService())
    with TestClient(main.app) as client:
        assert "/campaigns/5" in client.get("/resources?campaign_id=5").text
        headers = {"Origin": "http://testserver"}
        assert (
            "ID 42"
            in client.post("/resources", data={"kind": "group", "name": "ok"}, headers=headers).text
        )
        assert (
            "Некорректное название"
            in client.post(
                "/resources", data={"kind": "group", "name": "bad"}, headers=headers
            ).text
        )


def test_resource_options(monkeypatch):
    monkeypatch.setattr(context, "client", FakeClient())
    with TestClient(main.app) as client:
        response = client.get("/resources/options/group")
        assert response.json()["options"] == [{"id": 1, "name": "Example"}]
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/resources/options/unknown").status_code == 400


def test_inline_resource_creation(monkeypatch):
    class FakeResourceService:
        async def create(self, kind, name, url):
            if name == "bad":
                raise ValueError("Неверное имя")
            return 42

    monkeypatch.setattr(context, "resource_service", FakeResourceService())
    with TestClient(main.app) as client:
        headers = {"Origin": "http://testserver"}
        response = client.post(
            "/resources/inline", data={"kind": "group", "name": "ok"}, headers=headers
        )
        assert response.json() == {"id": 42}
        error = client.post(
            "/resources/inline", data={"kind": "group", "name": "bad"}, headers=headers
        )
        assert error.status_code == 400 and error.json()["error"] == "Неверное имя"


def test_inline_api_errors(monkeypatch):
    from app.clients.keitaro import KeitaroError

    class Broken:
        async def request(self, *args, **kwargs):
            raise KeitaroError("API недоступен")

        async def create(self, *args, **kwargs):
            raise KeitaroError("API недоступен")

    monkeypatch.setattr(context, "client", Broken())
    monkeypatch.setattr(context, "resource_service", Broken())
    with TestClient(main.app) as client:
        assert client.get("/resources/options/offer").status_code == 502
        response = client.post(
            "/resources/inline",
            data={"kind": "offer", "name": "x"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 502


def test_inline_forbidden_keeps_status(monkeypatch):
    from app.clients.keitaro import KeitaroError

    class Forbidden:
        async def create(self, *args, **kwargs):
            raise KeitaroError("Недостаточно прав", 403)

    monkeypatch.setattr(context, "resource_service", Forbidden())
    with TestClient(main.app) as client:
        response = client.post(
            "/resources/inline",
            data={"kind": "offer", "name": "test"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Недостаточно прав"


def test_restricted_offer_creation_is_hidden_and_blocked(monkeypatch):
    from app.config import Settings
    from app.services.access import AccessPolicy

    class MustNotRun:
        async def create(self, *args, **kwargs):
            raise AssertionError("Запрет должен проверяться до обращения в Keitaro")

    monkeypatch.setattr(context, "client", FakeClient())
    monkeypatch.setattr(context, "resource_service", MustNotRun())
    monkeypatch.setattr(
        context, "access_policy", AccessPolicy(Settings(offer_creation_enabled=False))
    )
    with TestClient(main.app) as client:
        home = client.get("/").text
        assert 'data-create-resource="offer"' not in home
        assert "Создание недоступно" in home
        assert "Создание недоступно" in client.get("/resources").text
        response = client.post(
            "/resources/inline",
            data={"kind": "offer", "name": "test"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 403
        assert "администратору" in response.json()["error"]


def test_request_log_does_not_include_query_or_request_body(monkeypatch, caplog):
    import logging

    monkeypatch.setattr(context, "client", FakeClient())
    with caplog.at_level(logging.INFO, logger="app.middleware"):
        with TestClient(main.app) as client:
            response = client.get("/?token=private-secret")
            assert response.status_code == 200
            assert client.get("/health").json() == {"status": "ok"}
    assert "HTTP request: method=GET" in caplog.text
    assert "private-secret" not in caplog.text
    assert "route=/health" not in caplog.text


def test_frontend_assets_are_served():
    with TestClient(main.app) as client:
        css = client.get("/static/style.css")
        script = client.get("/static/resources.js")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert script.status_code == 200 and "refreshResource" in script.text
