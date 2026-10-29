"""Tests unitarios deterministas para Print Manager (motor de precios, PDF, DB y API)."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from pricing import (
    DEFAULT_CATALOG,
    PrintStore,
    calculate_order_quote,
    calculate_print_line,
    calculate_service_line,
    inspect_uploaded_document,
    resolve_tier_price,
    round_to_step,
    validate_and_sanitize_catalog,
)
from webapp import create_app


def _make_sample_pdf(num_pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class PricingEngineTests(unittest.TestCase):
    def test_resolve_tier_price_by_quantity(self) -> None:
        tiers = DEFAULT_CATALOG["print_modes"][0]["tiers"]
        p1, _ = resolve_tier_price(tiers, 1)
        p10, _ = resolve_tier_price(tiers, 10)
        p60, _ = resolve_tier_price(tiers, 60)
        self.assertEqual(p1, 150)
        self.assertEqual(p10, 100)
        self.assertEqual(p60, 80)

    def test_calculate_print_line_simplex_and_duplex(self) -> None:
        simplex = calculate_print_line(
            DEFAULT_CATALOG,
            mode_id="bn_print",
            paper_id="carta",
            pages=11,
            copies=1,
            duplex=False,
        )
        self.assertEqual(simplex["total_pages"], 11)
        self.assertEqual(simplex["total_sheets"], 11)
        self.assertEqual(simplex["effective_page_price"], 100)
        self.assertEqual(simplex["line_total"], 1100)

        duplex = calculate_print_line(
            DEFAULT_CATALOG,
            mode_id="bn_print",
            paper_id="carta",
            pages=11,
            copies=1,
            duplex=True,
        )
        self.assertEqual(duplex["total_pages"], 11)
        self.assertEqual(duplex["total_sheets"], 6)
        self.assertEqual(duplex["effective_page_price"], 80)
        self.assertEqual(duplex["line_total"], 880)

    def test_calculate_print_line_with_special_paper(self) -> None:
        line = calculate_print_line(
            DEFAULT_CATALOG,
            mode_id="color_full",
            paper_id="foto_glossy",
            pages=2,
            copies=3,
            duplex=False,
        )
        # 6 páginas totales -> tramo 1-9 ($500) + $400/hoja * 6 hojas = 3000 + 2400 = 5400
        self.assertEqual(line["total_pages"], 6)
        self.assertEqual(line["total_sheets"], 6)
        self.assertEqual(line["line_total"], 5400)

    def test_calculate_service_line_and_custom(self) -> None:
        anillado = calculate_service_line(DEFAULT_CATALOG, service_id="anillado_chico", quantity=2)
        self.assertEqual(anillado["line_total"], 3000)

        custom = calculate_service_line(
            DEFAULT_CATALOG,
            service_id="custom",
            quantity=1,
            custom_name="Currículum",
            custom_unit_price=1500,
        )
        self.assertEqual(custom["name"], "Currículum")
        self.assertEqual(custom["line_total"], 1500)

    def test_calculate_order_quote_with_discount(self) -> None:
        quote = calculate_order_quote(
            DEFAULT_CATALOG,
            items=[
                {"kind": "print", "mode_id": "bn_copy", "paper_id": "carta", "pages": 10, "copies": 1, "duplex": False},
                {"kind": "service", "service_id": "carpeta_archivador", "quantity": 1},
            ],
            manual_discount=100,
        )
        # 10 copias B/N a $80 = 800 + carpeta $300 = 1100 - 100 desc = 1000
        self.assertEqual(quote["subtotal"], 1100)
        self.assertEqual(quote["final_total"], 1000)
        self.assertEqual(quote["total_pages"], 10)
        self.assertEqual(quote["total_sheets"], 10)

    def test_inspect_uploaded_pdf_and_image(self) -> None:
        pdf_bytes = _make_sample_pdf(7)
        info = inspect_uploaded_document("tarea_colegio.pdf", pdf_bytes)
        self.assertEqual(info["pages"], 7)
        self.assertEqual(info["sheets_simplex"], 7)
        self.assertEqual(info["sheets_duplex"], 4)

        img_info = inspect_uploaded_document("carnet.jpg", b"\xff\xd8\xff\xe0fakejpeg")
        self.assertEqual(img_info["pages"], 1)
        self.assertEqual(img_info["doc_type"], "Imagen")

    def test_round_to_step_and_catalog_validation(self) -> None:
        self.assertEqual(round_to_step(144, 10), 140)
        self.assertEqual(round_to_step(146, 10), 150)
        clean = validate_and_sanitize_catalog({"shop_name": "Imprenta Familiar", "duplex_discount_per_page": 30})
        self.assertEqual(clean["shop_name"], "Imprenta Familiar")
        self.assertEqual(clean["duplex_discount_per_page"], 30)


class WebAppAndStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_prints.db"
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_healthz_and_index(self) -> None:
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

        html = self.client.get("/")
        self.assertEqual(html.status_code, 200)
        self.assertIn("Centro de Impresiones Casa", html.text)

    def test_create_update_and_delete_job_flow(self) -> None:
        payload = {
            "items": [
                {"kind": "print", "mode_id": "bn_print", "paper_id": "carta", "pages": 20, "copies": 1, "duplex": True},
                {"kind": "service", "service_id": "anillado_chico", "quantity": 1},
            ],
            "manual_discount": 0,
            "customer_name": "Vecina Marta",
            "note": "Entregar en la tarde",
            "payment_method": "pendiente",
            "status": "pending",
        }
        create_res = self.client.post("/api/jobs", json=payload)
        self.assertEqual(create_res.status_code, 200)
        data = create_res.json()
        job_id = data["job"]["id"]
        # 20 págs B/N (tramo 10-49 = $100 - $20 duplex = $80) * 20 = 1600 + anillado 1500 = 3100
        self.assertEqual(data["job"]["final_total"], 3100)
        self.assertEqual(data["stats"]["pending_overall"]["total"], 3100)

        patch_res = self.client.patch(
            f"/api/jobs/{job_id}",
            json={"status": "paid", "payment_method": "transferencia"},
        )
        self.assertEqual(patch_res.status_code, 200)
        patched = patch_res.json()
        self.assertEqual(patched["job"]["status"], "paid")
        self.assertEqual(patched["stats"]["today"]["paid_total"], 3100)
        self.assertEqual(patched["stats"]["pending_overall"]["total"], 0)

        del_res = self.client.delete(f"/api/jobs/{job_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["stats"]["today"]["paid_total"], 0)

    def test_catalog_update_and_reset_endpoints(self) -> None:
        cat = self.client.get("/api/catalog").json()
        cat["shop_name"] = "Copias Casa Luis"
        put_res = self.client.put("/api/catalog", json=cat)
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.json()["catalog"]["shop_name"], "Copias Casa Luis")

        reset_res = self.client.post("/api/catalog/reset")
        self.assertEqual(reset_res.status_code, 200)
        self.assertEqual(reset_res.json()["catalog"]["shop_name"], DEFAULT_CATALOG["shop_name"])

    def test_inspect_file_endpoint_pdf(self) -> None:
        pdf_bytes = _make_sample_pdf(5)
        res = self.client.post(
            "/api/inspect-file",
            files={"file": ("guia.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(res.status_code, 200)
        doc = res.json()["document"]
        self.assertEqual(doc["pages"], 5)
        self.assertEqual(doc["sheets_duplex"], 3)


if __name__ == "__main__":
    unittest.main()
