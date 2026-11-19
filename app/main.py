"""FastAPI application assembly."""

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import context
from app.logging_config import configure_logging
from app.middleware import log_requests, protect_local_forms
from app.routes import campaigns, resources

configure_logging(context.settings)
logger = logging.getLogger(__name__)

app = FastAPI(title="Adrobot • Keitaro")
app.mount("/static", StaticFiles(directory=context.frontend_root / "static"), name="static")

app.include_router(campaigns.router)
app.include_router(resources.router)

app.middleware("http")(log_requests)
app.middleware("http")(protect_local_forms)
logger.info("Application configured: service=%s", context.settings.service_name)
