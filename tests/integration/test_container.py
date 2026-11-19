"""Tests for application behavior."""

import base64
import time
import urllib.error
import urllib.request

import pytest
from testcontainers.core.container import DockerContainer

from app.clients.keitaro import KeitaroClient
from app.config import Settings
from app.repositories.storage import Store
from app.services.campaigns import CampaignService

SERVER = """
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
state = {"id": 12, "name": "Offers", "offers": [{"offer_id": 1, "share": 100, "state": "active"}]}
class Handler(BaseHTTPRequestHandler):
 def reply(self, value):
  body = json.dumps(value).encode()
  self.send_response(200)
  self.send_header("Content-Type", "application/json")
  self.end_headers()
  self.wfile.write(body)
 def do_GET(self):
  if self.headers.get("Api-Key") != "integration-key":
   self.send_error(401); return
  if self.path.endswith("/campaigns/5/streams"): self.reply([state])
  elif self.path.endswith("/streams/12"): self.reply(state)
  else: self.reply({"id": 2})
 def do_PUT(self):
  data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
  state.update(data); self.reply(state)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
"""


@pytest.mark.integration
async def test_publish_against_container(tmp_path):
    code = base64.b64encode(SERVER.encode()).decode()
    command = f"python -u -c \"import base64;exec(base64.b64decode('{code}'))\""
    with (
        DockerContainer("python:3.12-slim")
        .with_exposed_ports(8080)
        .with_command(command) as container
    ):
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(8080))

        for _ in range(50):
            try:
                request = urllib.request.Request(
                    f"http://{host}:{port}/admin_api/v1/streams/12",
                    headers={"Api-Key": "integration-key"},
                )
                with urllib.request.urlopen(request, timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.2)
        else:
            pytest.fail("Тестовый контейнер не запустился")
        settings = Settings(
            keitaro_url=f"http://{host}:{port}", keitaro_api_key="integration-key", _env_file=None
        )
        service = CampaignService(KeitaroClient(settings), Store(str(tmp_path / "state.db")))
        await service.fetch(5)
        await service.edit(12, "add", 2)
        await service.publish(12)
        base, working = service.store.get(12)
        assert base == working
        assert [entry["share"] for entry in base["offers"]] == [50, 50]
