"""FastAPI application: routes, validation, and error handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .errors import FigmaExporterError, InputValidationError, UpstreamError
from .exporters.ai import ai_export
from .exporters.image import image_export
from .exporters.pixel import pixel_export
from .exporters.structured import structured_export
from .figma_client import FigmaClient
from .models import (
    AIExportRequest,
    PixelExportRequest,
    StructuredExportRequest,
    TreeRequest,
)
from .tree import build_path_map, simplify_tree

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _client(request: Request, token: str | None) -> FigmaClient:
    settings: Settings = request.app.state.settings
    return FigmaClient(
        token or settings.figma_token,
        settings=settings,
        transport=request.app.state.figma_transport,
    )


def _enforce_selection_limit(node_ids: list[str], settings: Settings) -> None:
    if len(node_ids) > settings.max_selected_ids:
        raise InputValidationError(
            f"Too many node ids: {len(node_ids)} (limit {settings.max_selected_ids})."
        )


def create_app(
    *,
    settings: Settings | None = None,
    figma_transport: httpx.BaseTransport | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Figma → HTML/CSS/JSON exporter", version="1.0.0")
    app.state.settings = settings
    app.state.figma_transport = figma_transport

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(FigmaExporterError)
    async def _handle_app_error(_: Request, exc: FigmaExporterError) -> JSONResponse:
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        message = "Invalid request."
        if errors:
            first = errors[0]
            loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
            message = f"{loc}: {first.get('msg')}" if loc else str(first.get("msg"))
        return JSONResponse({"error": message}, status_code=400)

    @app.middleware("http")
    async def _limit_body(request: Request, call_next: Any) -> Any:
        if request.url.path != "/api/image/export":
            raw = request.headers.get("content-length")
            if raw and raw.isdigit() and int(raw) > settings.request_body_limit_bytes:
                return JSONResponse({"error": "Request body too large."}, status_code=413)
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        page = STATIC_DIR / "index.html"
        if not page.is_file():
            return HTMLResponse("<h1>Figma exporter</h1>")
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.post("/api/figma/tree")
    def figma_tree(req: TreeRequest, request: Request) -> dict[str, Any]:
        with _client(request, req.token) as client:
            data = client.get_file(req.file_key)
        document = data.get("document")
        if not document:
            raise UpstreamError("Figma response has no 'document' field.")
        return {"tree": simplify_tree(document), "idToPath": build_path_map(document)}

    @app.post("/api/figma/export/structured")
    def export_structured(req: StructuredExportRequest, request: Request) -> dict[str, Any]:
        _enforce_selection_limit(req.node_ids, settings)
        with _client(request, req.token) as client:
            file_data = client.get_file(req.file_key)
            return structured_export(
                file_data,
                req.node_ids,
                label_full_path=req.label_full_path,
                normalize=req.normalize,
                client=client,
                file_key=req.file_key,
            )

    @app.post("/api/figma/export/pixel")
    def export_pixel(req: PixelExportRequest, request: Request) -> dict[str, Any]:
        _enforce_selection_limit(req.node_ids, settings)
        with _client(request, req.token) as client:
            file_data = client.get_file(req.file_key)
            return pixel_export(
                file_data,
                req.node_ids,
                client=client,
                file_key=req.file_key,
                fmt=req.format,
                scale=req.scale,
                normalize=req.normalize,
            )

    @app.post("/api/figma/export/ai")
    def export_ai(req: AIExportRequest, request: Request) -> dict[str, Any]:
        _enforce_selection_limit(req.node_ids, settings)
        with _client(request, req.token) as client:
            file_data = client.get_file(req.file_key)
            return ai_export(
                file_data,
                req.node_ids,
                client=client,
                file_key=req.file_key,
                openai_api_key=settings.openai_api_key,
                model=req.model or settings.openai_default_model,
                normalize=req.normalize,
                max_images=req.max_images,
                max_text_chars_per_node=req.max_text_chars_per_node,
                max_output_tokens=settings.openai_max_output_tokens,
            )

    @app.post("/api/image/export")
    async def export_image(
        image: UploadFile = File(...),
        model: str = Form(default=""),
    ) -> dict[str, Any]:
        data = await image.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise InputValidationError(f"Image exceeds the {settings.max_upload_bytes}-byte limit.")
        return await run_in_threadpool(
            image_export,
            data,
            image.content_type or "application/octet-stream",
            openai_api_key=settings.openai_api_key,
            model=model or settings.openai_default_model,
            max_output_tokens=settings.openai_max_output_tokens,
        )

    return app


app = create_app()
