"""Campaign creation and stream editor routes."""

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import context as ctx
from app.clients.keitaro import KeitaroError
from app.services.campaigns import PartialCreationError

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return the process health status without calling Keitaro."""
    return {"status": "ok"}


async def render_home(request: Request, message: str = "", error: str = "") -> HTMLResponse:
    """Render campaign creation with current Keitaro resources."""
    data: dict[str, Any] = {"domains": [], "groups": [], "sources": [], "offers": []}
    try:
        for key, path in (
            ("domains", "/domains"),
            ("groups", "/groups?type=campaigns"),
            ("sources", "/traffic_sources"),
            ("offers", "/offers"),
        ):
            data[key] = await ctx.client.request("GET", path)

        data["groups"] = [x for x in data["groups"] if x.get("type") in (None, "campaigns")]
    except KeitaroError as exc:
        error = error or str(exc)

    return ctx.templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            **data,
            "message": message,
            "error": error,
            "prefix": ctx.settings.campaign_prefix,
            "redirect_url": ctx.settings.redirect_url,
            "creation_rights": ctx.access_policy.creation_rights(),
        },
    )


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Display the campaign creation page."""
    return await render_home(request, message=request.query_params.get("message", ""))


@router.get("/editor", response_class=HTMLResponse)
async def editor_start(request: Request) -> HTMLResponse:
    """Display the campaign lookup page."""
    return ctx.templates.TemplateResponse(request=request, name="editor_start.html", context={})


@router.get("/editor/open")
async def open_editor(campaign_id: int) -> RedirectResponse:
    """Redirect to the editor for a valid campaign ID."""
    if campaign_id <= 0:
        return RedirectResponse("/editor", status_code=303)
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)


@router.post("/campaigns", response_class=HTMLResponse)
async def create_campaign(
    request: Request,
    name: str = Form(),
    geo: str = Form(),
    offer_id: int = Form(),
    domain_id: int = Form(),
    group_id: int = Form(),
    source_id: int = Form(),
) -> HTMLResponse:
    """Create a campaign from a validated form submission."""
    try:
        campaign_id = await ctx.service.create(name, geo, offer_id, domain_id, group_id, source_id)
        return await render_home(request, message=f"Кампания {campaign_id} создана")
    except (KeitaroError, PartialCreationError, ValueError) as exc:
        return await render_home(request, error=str(exc))


async def render_editor(
    request: Request, campaign_id: int, error: str = "", message: str = ""
) -> HTMLResponse:
    """Render streams, offer names, and their saved drafts."""
    try:
        streams = await ctx.client.request("GET", f"/campaigns/{campaign_id}/streams")
        offers = await ctx.client.request("GET", "/offers")
        names = {int(x["id"]): x.get("name", str(x["id"])) for x in offers}
        rows = [
            {
                "id": int(s["id"]),
                "name": s.get("name", "Поток"),
                "draft": ctx.store.get(int(s["id"])),
            }
            for s in streams
        ]
    except KeitaroError as exc:
        rows, names, error = [], {}, str(exc)
    return ctx.templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={
            "campaign_id": campaign_id,
            "creation_rights": ctx.access_policy.creation_rights(),
            "streams": rows,
            "names": names,
            "offers": offers if not error else [],
            "error": error,
            "message": message,
        },
    )


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def editor(request: Request, campaign_id: int) -> HTMLResponse:
    """Display the stream editor for a campaign."""
    ctx.logger.info("Campaign editor opened: campaign_id=%s", campaign_id)
    return await render_editor(request, campaign_id)


@router.post("/campaigns/{campaign_id}/fetch", response_class=HTMLResponse)
async def fetch(request: Request, campaign_id: int) -> HTMLResponse:
    """Refresh the local stream snapshots from Keitaro."""
    try:
        await ctx.service.fetch(campaign_id)
        return await render_editor(request, campaign_id, message="Потоки загружены")
    except (KeitaroError, ValueError) as exc:
        return await render_editor(request, campaign_id, error=str(exc))


@router.post("/campaigns/{campaign_id}/streams/{stream_id}", response_class=HTMLResponse)
async def edit_stream(
    request: Request,
    campaign_id: int,
    stream_id: int,
    action: str = Form(),
    offer_id: int = Form(0),
    share: int = Form(0),
) -> Response:
    """Update, cancel, or publish a campaign stream draft."""
    try:
        current = ctx.store.get(stream_id)
        if not current or current[0]["campaign_id"] != campaign_id:
            raise ValueError("Поток не загружен для этой кампании")
        if action == "publish":
            await ctx.service.publish(stream_id)
        else:
            await ctx.service.edit(stream_id, action, offer_id, share)

        return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)
    except (KeitaroError, ValueError) as exc:
        return await render_editor(request, campaign_id, error=str(exc))
