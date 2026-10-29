"""Aplicación web FastAPI para el Gestor y Calculadora de Impresiones Casa."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from pricing import (
    PrintStore,
    calculate_order_quote,
    inspect_uploaded_document,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("PRINT_DATA_DIR", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "prints.db"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB máximo para conteo de páginas

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class QuoteRequest(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    manual_discount: int = 0


class JobCreateRequest(BaseModel):
    items: list[dict[str, Any]]
    manual_discount: int = 0
    customer_name: str = ""
    note: str = ""
    payment_method: str = "efectivo"
    status: str = "paid"


class JobStatusUpdateRequest(BaseModel):
    status: str
    payment_method: str | None = None


def create_app(db_path: str | Path | None = None) -> FastAPI:
    store = PrintStore(db_path or DB_PATH)
    application = FastAPI(
        title="Print Manager Casa",
        description="Calculadora y gestor de impresiones, fotocopias y servicios",
        version="1.0.0",
    )
    application.state.store = store

    @application.get("/healthz")
    def healthz() -> dict[str, Any]:
        catalog = store.get_catalog()
        return {"ok": True, "shop_name": catalog.get("shop_name", "Print Manager")}

    @application.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        catalog = store.get_catalog()
        stats = store.get_dashboard_stats()
        recent_jobs = store.list_jobs(limit=30)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "catalog": catalog,
                "stats": stats,
                "recent_jobs": recent_jobs,
            },
        )

    @application.get("/api/bootstrap")
    def get_bootstrap() -> dict[str, Any]:
        return {
            "catalog": store.get_catalog(),
            "stats": store.get_dashboard_stats(),
            "jobs": store.list_jobs(limit=40),
        }

    @application.get("/api/catalog")
    def get_catalog() -> dict[str, Any]:
        return store.get_catalog()

    @application.put("/api/catalog")
    def update_catalog(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            saved = store.save_catalog(payload)
            return {"ok": True, "catalog": saved}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/catalog/reset")
    def reset_catalog() -> dict[str, Any]:
        saved = store.reset_catalog()
        return {"ok": True, "catalog": saved}

    @application.post("/api/quote")
    def quote_order(req: QuoteRequest) -> dict[str, Any]:
        catalog = store.get_catalog()
        try:
            return calculate_order_quote(
                catalog,
                req.items,
                manual_discount=req.manual_discount,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/inspect-file")
    async def inspect_file(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="El archivo supera el límite de 25 MB.",
            )
        try:
            info = inspect_uploaded_document(file.filename or "documento.pdf", content)
            return {"ok": True, "document": info}
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"No se pudo leer el archivo: {exc}",
            ) from exc

    @application.get("/api/jobs")
    def list_jobs(limit: int = 50, status: str | None = None) -> dict[str, Any]:
        return {
            "jobs": store.list_jobs(limit=limit, status_filter=status),
            "stats": store.get_dashboard_stats(),
        }

    @application.post("/api/jobs")
    def create_job(req: JobCreateRequest) -> dict[str, Any]:
        try:
            job = store.record_job(
                items=req.items,
                manual_discount=req.manual_discount,
                customer_name=req.customer_name,
                note=req.note,
                payment_method=req.payment_method,
                status=req.status,
            )
            return {
                "ok": True,
                "job": job,
                "stats": store.get_dashboard_stats(),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.patch("/api/jobs/{job_id}")
    def update_job(job_id: int, req: JobStatusUpdateRequest) -> dict[str, Any]:
        try:
            updated = store.update_job_status(
                job_id,
                status=req.status,
                payment_method=req.payment_method,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
        return {
            "ok": True,
            "job": updated,
            "stats": store.get_dashboard_stats(),
        }

    @application.delete("/api/jobs/{job_id}")
    def remove_job(job_id: int) -> JSONResponse:
        deleted = store.delete_job(job_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
        return JSONResponse(
            {
                "ok": True,
                "stats": store.get_dashboard_stats(),
            }
        )

    return application


app = create_app()
