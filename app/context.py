"""Shared dependencies and server-side template configuration."""

import logging
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.clients.keitaro import KeitaroClient
from app.config import Settings
from app.repositories.storage import Store
from app.services.access import AccessPolicy
from app.services.campaigns import CampaignService
from app.services.resources import ResourceService

settings = Settings()
frontend_root = Path(__file__).resolve().parent.parent / "frontend"
templates = Jinja2Templates(directory=frontend_root / "templates")
client = KeitaroClient(settings)
store = Store(settings.database_path)
service = CampaignService(client, store)
resource_service = ResourceService(client)
access_policy = AccessPolicy(settings)
logger = logging.getLogger(__name__)
