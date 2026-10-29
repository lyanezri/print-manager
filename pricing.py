"""Motor de precios, base de datos SQLite y lógica de cálculo para Print Manager."""

from __future__ import annotations

import copy
import io
import json
import math
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pypdf import PdfReader

DEFAULT_TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "America/Santiago"))

DEFAULT_CATALOG: dict[str, Any] = {
    "shop_name": "Centro de Impresiones Casa",
    "subtitle": "Calculadora rápida de impresiones, fotocopias y servicios",
    "currency_symbol": "$",
    "duplex_discount_per_page": 20,
    "duplex_charge_mode": "per_page_discount",
    "minimum_job_amount": 0,
    "rounding_step": 10,
    "print_modes": [
        {
            "id": "bn_print",
            "name": "Impresión Blanco y Negro",
            "short_name": "Imp. B/N",
            "icon": "printer",
            "accent": "slate",
            "tiers": [
                {"min_qty": 1, "max_qty": 9, "unit_price": 150},
                {"min_qty": 10, "max_qty": 49, "unit_price": 100},
                {"min_qty": 50, "max_qty": None, "unit_price": 80},
            ],
        },
        {
            "id": "bn_copy",
            "name": "Fotocopia Blanco y Negro",
            "short_name": "Copia B/N",
            "icon": "copy",
            "accent": "zinc",
            "tiers": [
                {"min_qty": 1, "max_qty": 9, "unit_price": 100},
                {"min_qty": 10, "max_qty": 49, "unit_price": 80},
                {"min_qty": 50, "max_qty": None, "unit_price": 60},
            ],
        },
        {
            "id": "color_normal",
            "name": "Impresión / Copia Color Normal",
            "short_name": "Color Texto/Normal",
            "icon": "palette",
            "accent": "indigo",
            "tiers": [
                {"min_qty": 1, "max_qty": 9, "unit_price": 300},
                {"min_qty": 10, "max_qty": 49, "unit_price": 250},
                {"min_qty": 50, "max_qty": None, "unit_price": 200},
            ],
        },
        {
            "id": "color_full",
            "name": "Impresión Color Alta Cobertura / Foto",
            "short_name": "Color Full / Imagen",
            "icon": "image",
            "accent": "rose",
            "tiers": [
                {"min_qty": 1, "max_qty": 9, "unit_price": 500},
                {"min_qty": 10, "max_qty": 49, "unit_price": 400},
                {"min_qty": 50, "max_qty": None, "unit_price": 350},
            ],
        },
    ],
    "paper_types": [
        {"id": "carta", "name": "Carta Normal (75g)", "short_name": "Carta", "extra_per_sheet": 0},
        {"id": "oficio", "name": "Oficio / Legal", "short_name": "Oficio", "extra_per_sheet": 30},
        {"id": "a4", "name": "A4 Normal", "short_name": "A4", "extra_per_sheet": 0},
        {"id": "opalina", "name": "Opalina / Cartulina Hilada", "short_name": "Opalina", "extra_per_sheet": 250},
        {"id": "foto_glossy", "name": "Papel Fotográfico Brillante", "short_name": "Papel Foto", "extra_per_sheet": 400},
        {"id": "adhesivo", "name": "Papel Adhesivo / Sticker", "short_name": "Adhesivo", "extra_per_sheet": 350},
    ],
    "extra_services": [
        {"id": "anillado_chico", "name": "Anillado (hasta 60 hojas)", "category": "Terminación", "unit_price": 1500, "icon": "book"},
        {"id": "anillado_grande", "name": "Anillado Grueso (61 a 150 hojas)", "category": "Terminación", "unit_price": 2200, "icon": "book"},
        {"id": "plastificado_carnet", "name": "Termolaminado / Plastificado Carnet", "category": "Plastificado", "unit_price": 800, "icon": "shield"},
        {"id": "plastificado_carta", "name": "Termolaminado Carta / Oficio", "category": "Plastificado", "unit_price": 1200, "icon": "shield"},
        {"id": "escaneo_pdf", "name": "Escaneo a PDF / Correo (por pág.)", "category": "Digital", "unit_price": 200, "icon": "scan"},
        {"id": "tramite_cert", "name": "Descarga Trámite / Certificado + Imp.", "category": "Trámites", "unit_price": 600, "icon": "file-check"},
        {"id": "carpeta_archivador", "name": "Carpeta / Funda Plástica", "category": "Insumos", "unit_price": 300, "icon": "folder"},
    ],
}


def now_local() -> datetime:
    return datetime.now(DEFAULT_TZ)


def round_to_step(amount: float, step: int) -> int:
    val = int(round(amount))
    if step <= 1:
        return max(0, val)
    return max(0, int(round(val / step) * step))


def resolve_tier_price(tiers: list[dict[str, Any]], total_pages: int) -> tuple[int, dict[str, Any]]:
    """Obtiene el precio unitario según la cantidad total de páginas y los tramos configurados."""
    qty = max(1, int(total_pages))
    sorted_tiers = sorted(tiers, key=lambda t: int(t.get("min_qty", 1)))
    chosen = sorted_tiers[0] if sorted_tiers else {"min_qty": 1, "max_qty": None, "unit_price": 100}
    for tier in sorted_tiers:
        min_q = int(tier.get("min_qty", 1))
        max_q = tier.get("max_qty")
        if qty >= min_q and (max_q is None or qty <= int(max_q)):
            chosen = tier
            break
        if qty >= min_q:
            chosen = tier
    return int(chosen.get("unit_price", 0)), chosen


def calculate_print_line(
    catalog: dict[str, Any],
    *,
    mode_id: str,
    paper_id: str = "carta",
    pages: int = 1,
    copies: int = 1,
    duplex: bool = False,
) -> dict[str, Any]:
    """Calcula el detalle exacto de una línea de impresión o fotocopia."""
    pages = max(1, min(int(pages), 50000))
    copies = max(1, min(int(copies), 5000))
    total_pages = pages * copies

    modes = {m["id"]: m for m in catalog.get("print_modes", [])}
    mode = modes.get(mode_id)
    if not mode:
        raise ValueError(f"Modo de impresión desconocido: {mode_id}")

    papers = {p["id"]: p for p in catalog.get("paper_types", [])}
    paper = papers.get(paper_id) or next(iter(papers.values()), {"id": "carta", "name": "Carta", "short_name": "Carta", "extra_per_sheet": 0})

    sheets_per_copy = math.ceil(pages / 2) if duplex else pages
    total_sheets = sheets_per_copy * copies

    base_unit_price, matched_tier = resolve_tier_price(mode.get("tiers", []), total_pages)
    duplex_discount = int(catalog.get("duplex_discount_per_page", 0)) if (duplex and pages > 1) else 0
    effective_page_price = max(10, base_unit_price - duplex_discount)

    paper_extra_per_sheet = int(paper.get("extra_per_sheet", 0))
    printing_subtotal = total_pages * effective_page_price
    paper_subtotal = total_sheets * paper_extra_per_sheet
    line_total = printing_subtotal + paper_subtotal

    tier_min = int(matched_tier.get("min_qty", 1))
    tier_max = matched_tier.get("max_qty")
    tier_label = f"{tier_min}+ págs." if tier_max is None else f"{tier_min} a {tier_max} págs."

    description_parts = [mode.get("short_name") or mode["name"]]
    if paper.get("short_name") and paper["id"] != "carta":
        description_parts.append(paper["short_name"])
    elif paper.get("short_name"):
        description_parts.append("Carta")
    if duplex:
        description_parts.append("Doble Faz")
    else:
        description_parts.append("Simple Faz")

    return {
        "kind": "print",
        "mode_id": mode["id"],
        "mode_name": mode["name"],
        "paper_id": paper["id"],
        "paper_name": paper["name"],
        "pages": pages,
        "copies": copies,
        "total_pages": total_pages,
        "duplex": bool(duplex),
        "total_sheets": total_sheets,
        "base_unit_price": base_unit_price,
        "duplex_discount_per_page": duplex_discount,
        "effective_page_price": effective_page_price,
        "paper_extra_per_sheet": paper_extra_per_sheet,
        "tier_label": tier_label,
        "tier_applied": tier_min > 1,
        "printing_subtotal": printing_subtotal,
        "paper_subtotal": paper_subtotal,
        "line_total": line_total,
        "label": " · ".join(description_parts),
    }


def calculate_service_line(
    catalog: dict[str, Any],
    *,
    service_id: str,
    quantity: int = 1,
    custom_name: str | None = None,
    custom_unit_price: int | None = None,
) -> dict[str, Any]:
    """Calcula una línea de servicio adicional o cargo personalizado."""
    quantity = max(1, min(int(quantity), 10000))
    if service_id == "custom":
        name = (custom_name or "Servicio / Cargo Extra").strip()[:100]
        unit_price = max(0, int(custom_unit_price or 0))
        category = "Personalizado"
    else:
        services = {s["id"]: s for s in catalog.get("extra_services", [])}
        svc = services.get(service_id)
        if not svc:
            raise ValueError(f"Servicio extra desconocido: {service_id}")
        name = svc["name"]
        unit_price = int(svc.get("unit_price", 0))
        category = svc.get("category", "Extra")

    line_total = quantity * unit_price
    return {
        "kind": "service",
        "service_id": service_id,
        "name": name,
        "category": category,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": line_total,
        "label": name,
    }


def calculate_order_quote(
    catalog: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    manual_discount: int = 0,
) -> dict[str, Any]:
    """Calcula una cotización completa combinando líneas de impresión y servicios."""
    calculated_items: list[dict[str, Any]] = []
    subtotal = 0
    total_pages = 0
    total_sheets = 0

    for raw in items:
        kind = raw.get("kind", "print")
        if kind == "print":
            line = calculate_print_line(
                catalog,
                mode_id=str(raw.get("mode_id", "bn_print")),
                paper_id=str(raw.get("paper_id", "carta")),
                pages=int(raw.get("pages", 1)),
                copies=int(raw.get("copies", 1)),
                duplex=bool(raw.get("duplex", False)),
            )
            total_pages += line["total_pages"]
            total_sheets += line["total_sheets"]
        else:
            line = calculate_service_line(
                catalog,
                service_id=str(raw.get("service_id", "custom")),
                quantity=int(raw.get("quantity", 1)),
                custom_name=raw.get("custom_name"),
                custom_unit_price=raw.get("custom_unit_price"),
            )
        subtotal += line["line_total"]
        calculated_items.append(line)

    discount = max(0, min(int(manual_discount or 0), subtotal))
    raw_total = max(0, subtotal - discount)
    rounding_step = int(catalog.get("rounding_step", 10))
    final_total = round_to_step(raw_total, rounding_step) if raw_total > 0 else 0

    min_job = int(catalog.get("minimum_job_amount", 0))
    minimum_applied = False
    if final_total > 0 and final_total < min_job:
        final_total = min_job
        minimum_applied = True

    return {
        "items": calculated_items,
        "subtotal": subtotal,
        "manual_discount": discount,
        "final_total": final_total,
        "total_pages": total_pages,
        "total_sheets": total_sheets,
        "minimum_applied": minimum_applied,
        "currency_symbol": catalog.get("currency_symbol", "$"),
    }


def inspect_uploaded_document(filename: str, content: bytes) -> dict[str, Any]:
    """Analiza un PDF o imagen subida en memoria y devuelve la cantidad de páginas."""
    clean_name = os.path.basename(filename or "documento").strip() or "documento"
    lower = clean_name.lower()
    if lower.endswith(".pdf") or content.startswith(b"%PDF"):
        reader = PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        doc_type = "PDF"
    elif lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")):
        page_count = 1
        doc_type = "Imagen"
    else:
        raise ValueError("Formato no soportado. Sube un archivo PDF o una imagen (JPG, PNG, WEBP).")

    return {
        "filename": clean_name,
        "doc_type": doc_type,
        "pages": max(1, page_count),
        "sheets_simplex": max(1, page_count),
        "sheets_duplex": math.ceil(max(1, page_count) / 2),
        "size_kb": round(len(content) / 1024, 1),
    }


def validate_and_sanitize_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida y normaliza un catálogo editable antes de guardarlo."""
    merged = copy.deepcopy(DEFAULT_CATALOG)
    if not isinstance(payload, dict):
        raise ValueError("El catálogo debe ser un objeto JSON.")

    if "shop_name" in payload:
        merged["shop_name"] = str(payload["shop_name"]).strip()[:80] or DEFAULT_CATALOG["shop_name"]
    if "subtitle" in payload:
        merged["subtitle"] = str(payload["subtitle"]).strip()[:140] or DEFAULT_CATALOG["subtitle"]
    if "currency_symbol" in payload:
        merged["currency_symbol"] = str(payload["currency_symbol"]).strip()[:5] or "$"
    if "duplex_discount_per_page" in payload:
        merged["duplex_discount_per_page"] = max(0, min(int(payload["duplex_discount_per_page"]), 5000))
    if "minimum_job_amount" in payload:
        merged["minimum_job_amount"] = max(0, min(int(payload["minimum_job_amount"]), 50000))
    if "rounding_step" in payload:
        step = int(payload["rounding_step"])
        merged["rounding_step"] = step if step in (1, 10, 50, 100) else 10

    if isinstance(payload.get("print_modes"), list) and payload["print_modes"]:
        clean_modes = []
        for m in payload["print_modes"]:
            if not isinstance(m, dict) or not m.get("id") or not m.get("name"):
                continue
            raw_tiers = m.get("tiers") or []
            clean_tiers = []
            for t in raw_tiers:
                min_q = max(1, int(t.get("min_qty", 1)))
                max_raw = t.get("max_qty")
                max_q = int(max_raw) if max_raw not in (None, "", 0) else None
                price = max(1, int(t.get("unit_price", 100)))
                clean_tiers.append({"min_qty": min_q, "max_qty": max_q, "unit_price": price})
            if not clean_tiers:
                clean_tiers = [{"min_qty": 1, "max_qty": None, "unit_price": 100}]
            clean_tiers.sort(key=lambda x: x["min_qty"])
            clean_modes.append(
                {
                    "id": str(m["id"]).strip()[:40],
                    "name": str(m["name"]).strip()[:80],
                    "short_name": str(m.get("short_name") or m["name"]).strip()[:35],
                    "icon": str(m.get("icon") or "printer").strip()[:25],
                    "accent": str(m.get("accent") or "slate").strip()[:20],
                    "tiers": clean_tiers,
                }
            )
        if clean_modes:
            merged["print_modes"] = clean_modes

    if isinstance(payload.get("paper_types"), list) and payload["paper_types"]:
        clean_papers = []
        for p in payload["paper_types"]:
            if not isinstance(p, dict) or not p.get("id") or not p.get("name"):
                continue
            clean_papers.append(
                {
                    "id": str(p["id"]).strip()[:40],
                    "name": str(p["name"]).strip()[:80],
                    "short_name": str(p.get("short_name") or p["name"]).strip()[:30],
                    "extra_per_sheet": max(0, int(p.get("extra_per_sheet", 0))),
                }
            )
        if clean_papers:
            merged["paper_types"] = clean_papers

    if isinstance(payload.get("extra_services"), list):
        clean_services = []
        for s in payload["extra_services"]:
            if not isinstance(s, dict) or not s.get("id") or not s.get("name"):
                continue
            clean_services.append(
                {
                    "id": str(s["id"]).strip()[:40],
                    "name": str(s["name"]).strip()[:80],
                    "category": str(s.get("category") or "Extra").strip()[:40],
                    "unit_price": max(0, int(s.get("unit_price", 0))),
                    "icon": str(s.get("icon") or "plus").strip()[:25],
                }
            )
        merged["extra_services"] = clean_services

    return merged


class PrintStore:
    """Almacenamiento SQLite en modo WAL para configuración de precios e historial de trabajos."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    customer_name TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    payment_method TEXT NOT NULL DEFAULT 'efectivo',
                    status TEXT NOT NULL DEFAULT 'paid',
                    subtotal INTEGER NOT NULL DEFAULT 0,
                    manual_discount INTEGER NOT NULL DEFAULT 0,
                    final_total INTEGER NOT NULL DEFAULT 0,
                    total_pages INTEGER NOT NULL DEFAULT 0,
                    total_sheets INTEGER NOT NULL DEFAULT 0,
                    items_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                """
            )
            cur = conn.execute("SELECT value_json FROM settings WHERE key = 'catalog'")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?)",
                    ("catalog", json.dumps(DEFAULT_CATALOG, ensure_ascii=False), now_local().isoformat()),
                )

    def get_catalog(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value_json FROM settings WHERE key = 'catalog'").fetchone()
            if not row:
                return copy.deepcopy(DEFAULT_CATALOG)
            try:
                loaded = json.loads(row["value_json"])
                return validate_and_sanitize_catalog(loaded)
            except Exception:
                return copy.deepcopy(DEFAULT_CATALOG)

    def save_catalog(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean = validate_and_sanitize_catalog(payload)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO settings (key, value_json, updated_at)
                VALUES ('catalog', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(clean, ensure_ascii=False), now_local().isoformat()),
            )
        return clean

    def reset_catalog(self) -> dict[str, Any]:
        return self.save_catalog(copy.deepcopy(DEFAULT_CATALOG))

    def record_job(
        self,
        *,
        items: list[dict[str, Any]],
        manual_discount: int = 0,
        customer_name: str = "",
        note: str = "",
        payment_method: str = "efectivo",
        status: str = "paid",
    ) -> dict[str, Any]:
        if not items:
            raise ValueError("El trabajo debe incluir al menos un ítem.")
        catalog = self.get_catalog()
        quote = calculate_order_quote(catalog, items, manual_discount=manual_discount)
        valid_status = status if status in ("paid", "pending") else "paid"
        valid_method = payment_method if payment_method in ("efectivo", "transferencia", "pendiente") else "efectivo"
        if valid_status == "pending":
            valid_method = "pendiente"

        created_at = now_local().isoformat()
        clean_customer = (customer_name or "").strip()[:80]
        clean_note = (note or "").strip()[:200]

        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    created_at, customer_name, note, payment_method, status,
                    subtotal, manual_discount, final_total, total_pages, total_sheets, items_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    clean_customer,
                    clean_note,
                    valid_method,
                    valid_status,
                    quote["subtotal"],
                    quote["manual_discount"],
                    quote["final_total"],
                    quote["total_pages"],
                    quote["total_sheets"],
                    json.dumps(quote["items"], ensure_ascii=False),
                ),
            )
            job_id = int(cur.lastrowid or 0)

        return {
            "id": job_id,
            "created_at": created_at,
            "customer_name": clean_customer,
            "note": clean_note,
            "payment_method": valid_method,
            "status": valid_status,
            **quote,
        }

    def update_job_status(self, job_id: int, *, status: str, payment_method: str | None = None) -> dict[str, Any] | None:
        if status not in ("paid", "pending"):
            raise ValueError("Estado inválido.")
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
            if not row:
                return None
            new_method = payment_method or row["payment_method"]
            if status == "paid" and new_method == "pendiente":
                new_method = "efectivo"
            elif status == "pending":
                new_method = "pendiente"
            conn.execute(
                "UPDATE jobs SET status = ?, payment_method = ? WHERE id = ?",
                (status, new_method, int(job_id)),
            )
            updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
            return self._row_to_dict(updated)

    def delete_job(self, job_id: int) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (int(job_id),))
            return cur.rowcount > 0

    def list_jobs(self, *, limit: int = 50, status_filter: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with closing(self._connect()) as conn:
            if status_filter in ("paid", "pending"):
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status_filter, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_dashboard_stats(self) -> dict[str, Any]:
        now = now_local()
        today_prefix = now.strftime("%Y-%m-%d")
        month_prefix = now.strftime("%Y-%m")
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        with closing(self._connect()) as conn:
            today_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'paid' THEN final_total ELSE 0 END), 0) AS paid_total,
                    COALESCE(SUM(CASE WHEN status = 'pending' THEN final_total ELSE 0 END), 0) AS pending_total,
                    COALESCE(SUM(total_pages), 0) AS pages,
                    COALESCE(SUM(total_sheets), 0) AS sheets,
                    COUNT(*) AS jobs_count
                FROM jobs
                WHERE substr(created_at, 1, 10) = ?
                """,
                (today_prefix,),
            ).fetchone()

            week_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'paid' THEN final_total ELSE 0 END), 0) AS paid_total,
                    COUNT(*) AS jobs_count
                FROM jobs
                WHERE created_at >= ?
                """,
                (week_start,),
            ).fetchone()

            month_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'paid' THEN final_total ELSE 0 END), 0) AS paid_total,
                    COALESCE(SUM(total_pages), 0) AS pages,
                    COALESCE(SUM(total_sheets), 0) AS sheets,
                    COUNT(*) AS jobs_count
                FROM jobs
                WHERE substr(created_at, 1, 7) = ?
                """,
                (month_prefix,),
            ).fetchone()

            pending_global = conn.execute(
                """
                SELECT
                    COALESCE(SUM(final_total), 0) AS total,
                    COUNT(*) AS count
                FROM jobs
                WHERE status = 'pending'
                """
            ).fetchone()

        return {
            "today": {
                "paid_total": int(today_row["paid_total"]),
                "pending_total": int(today_row["pending_total"]),
                "pages": int(today_row["pages"]),
                "sheets": int(today_row["sheets"]),
                "jobs_count": int(today_row["jobs_count"]),
            },
            "week": {
                "paid_total": int(week_row["paid_total"]),
                "jobs_count": int(week_row["jobs_count"]),
            },
            "month": {
                "paid_total": int(month_row["paid_total"]),
                "pages": int(month_row["pages"]),
                "sheets": int(month_row["sheets"]),
                "jobs_count": int(month_row["jobs_count"]),
            },
            "pending_overall": {
                "total": int(pending_global["total"]),
                "count": int(pending_global["count"]),
            },
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "created_at": row["created_at"],
            "customer_name": row["customer_name"],
            "note": row["note"],
            "payment_method": row["payment_method"],
            "status": row["status"],
            "subtotal": int(row["subtotal"]),
            "manual_discount": int(row["manual_discount"]),
            "final_total": int(row["final_total"]),
            "total_pages": int(row["total_pages"]),
            "total_sheets": int(row["total_sheets"]),
            "items": json.loads(row["items_json"]),
        }
