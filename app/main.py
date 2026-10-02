"""HTTP layer for the grid asset register.

Run locally:  uvicorn app.main:app --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import (
    AssetCreate,
    AssetOut,
    AssetStatus,
    AssetType,
    Outage,
    OutageCreate,
    OutageResolve,
    StatusUpdate,
)
from .service import ConflictError, GridService, NotFoundError, RuleViolationError

STATIC_DIR = Path(__file__).parent / "static"


def create_app(service: GridService | None = None) -> FastAPI:
    """App factory: every test gets a fresh, isolated service."""
    svc = service or GridService()
    app = FastAPI(title="Grid Asset Register", version="1.0.0")

    # ---------- consistent error format ----------

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            location = [str(part) for part in err["loc"] if part not in ("body", "query", "path")]
            message = err["msg"].removeprefix("Value error, ")
            errors.append({"field": ".".join(location) or "request", "message": message})
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation failed", "errors": errors},
        )

    @app.exception_handler(NotFoundError)
    async def on_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def on_conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RuleViolationError)
    async def on_rule_violation(_: Request, exc: RuleViolationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc), "errors": []})

    # ---------- routes ----------

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/assets", response_model=list[AssetOut])
    def list_assets(type: AssetType | None = None, status: AssetStatus | None = None):
        return [AssetOut.from_asset(a) for a in svc.list_assets(type, status)]

    @app.post("/api/assets", response_model=AssetOut, status_code=201)
    def create_asset(payload: AssetCreate):
        return AssetOut.from_asset(svc.create_asset(payload))

    # Declared before /{asset_id} so "geojson" is not parsed as an id
    @app.get("/api/assets/geojson")
    def assets_geojson() -> JSONResponse:
        return JSONResponse(svc.to_geojson(), media_type="application/geo+json")

    @app.get("/api/assets/{asset_id}", response_model=AssetOut)
    def get_asset(asset_id: int):
        return AssetOut.from_asset(svc.get_asset(asset_id))

    @app.patch("/api/assets/{asset_id}/status", response_model=AssetOut)
    def update_status(asset_id: int, payload: StatusUpdate):
        return AssetOut.from_asset(svc.set_status(asset_id, payload.status))

    @app.delete("/api/assets/{asset_id}", status_code=204)
    def delete_asset(asset_id: int) -> Response:
        svc.delete_asset(asset_id)
        return Response(status_code=204)

    @app.get("/api/outages", response_model=list[Outage])
    def list_outages(open_only: bool = False):
        return svc.list_outages(open_only)

    @app.post("/api/outages", response_model=Outage, status_code=201)
    def report_outage(payload: OutageCreate):
        return svc.report_outage(payload)

    @app.patch("/api/outages/{outage_id}/resolve", response_model=Outage)
    def resolve_outage(outage_id: int, payload: OutageResolve):
        return svc.resolve_outage(outage_id, payload.resolved_at)

    # ---------- UI ----------

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
