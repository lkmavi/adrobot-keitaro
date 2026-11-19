"""Keitaro resource management routes."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app import context as ctx
from app.clients.keitaro import KeitaroError

router = APIRouter()


@router.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request, campaign_id: int = 0) -> HTMLResponse:
    """Display resource creation forms."""
    return ctx.templates.TemplateResponse(
        request=request,
        name="resources.html",
        context={
            "campaign_id": max(campaign_id, 0),
            "settings_prefix": ctx.settings.campaign_prefix,
            "creation_rights": ctx.access_policy.creation_rights(),
        },
    )


@router.post("/resources", response_class=HTMLResponse)
async def create_resource(
    request: Request,
    kind: str = Form(),
    name: str = Form(),
    url: str = Form(""),
    campaign_id: int = Form(0),
) -> HTMLResponse:
    """Create a resource and render the result."""
    try:
        ctx.access_policy.require_create(kind)
        resource_id = await ctx.resource_service.create(kind, name, url)
        message = f"Ресурс создан в Keitaro: ID {resource_id}. Вернитесь и выберите его."
        return ctx.templates.TemplateResponse(
            request=request,
            name="resources.html",
            context={
                "campaign_id": max(campaign_id, 0),
                "settings_prefix": ctx.settings.campaign_prefix,
                "creation_rights": ctx.access_policy.creation_rights(),
                "message": message,
            },
        )
    except (ValueError, PermissionError, KeitaroError) as exc:
        if isinstance(exc, KeitaroError) and exc.status_code == 403:
            ctx.access_policy.deny(kind)
        ctx.logger.warning(
            "Resource creation failed: kind=%s",
            kind if kind in {"group", "domain", "source", "offer"} else "unknown",
        )
        return ctx.templates.TemplateResponse(
            request=request,
            name="resources.html",
            context={
                "campaign_id": max(campaign_id, 0),
                "settings_prefix": ctx.settings.campaign_prefix,
                "creation_rights": ctx.access_policy.creation_rights(),
                "error": str(exc),
            },
        )


RESOURCE_PATHS = {
    "group": "/groups?type=campaigns",
    "domain": "/domains",
    "source": "/traffic_sources",
    "offer": "/offers",
}


@router.get("/resources/options/{kind}")
async def resource_options(kind: str) -> JSONResponse:
    """Return the current options for a supported resource type."""
    if kind not in RESOURCE_PATHS:
        return JSONResponse({"error": "Неизвестный тип ресурса"}, status_code=400)
    try:
        resources = await ctx.client.request("GET", RESOURCE_PATHS[kind])
        options = [
            {"id": item["id"], "name": item.get("name", str(item["id"]))}
            for item in resources
            if kind != "group" or item.get("type") in (None, "campaigns")
        ]
        return JSONResponse({"options": options}, headers={"Cache-Control": "no-store"})
    except KeitaroError as exc:
        return JSONResponse({"error": str(exc)}, status_code=exc.status_code or 502)


@router.post("/resources/inline")
async def create_resource_inline(
    kind: str = Form(), name: str = Form(), url: str = Form("")
) -> JSONResponse:
    """Create a resource and return its ID for the inline form."""
    try:
        ctx.access_policy.require_create(kind)
        resource_id = await ctx.resource_service.create(kind, name, url)
        return JSONResponse({"id": resource_id})
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    except KeitaroError as exc:
        if exc.status_code == 403:
            ctx.access_policy.deny(kind)
        return JSONResponse({"error": str(exc)}, status_code=exc.status_code or 502)
