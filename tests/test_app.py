from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta

from openpyxl import Workbook

import app as appmod


class AppIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = appmod.DB_PATH
        appmod.DB_PATH = f"{self._tmp.name}/test_murisphere.db"
        appmod.init_db()
        appmod.app.config.update(TESTING=True)
        self.client = appmod.app.test_client()

    def tearDown(self) -> None:
        appmod.DB_PATH = self._old_db
        self._tmp.cleanup()

    def login(self, email: str, password: str) -> str:
        res = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200)
        return res.get_json()["token"]

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_auth_login_and_me(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")
        me = self.client.get("/api/auth/me", headers=self.auth_headers(token))
        self.assertEqual(me.status_code, 200)
        payload = me.get_json()
        self.assertEqual(payload["email"], "admin@murisphere.local")
        self.assertEqual(payload["role"], "Admin")

        unauth = self.client.get("/api/auth/me")
        self.assertEqual(unauth.status_code, 401)

    def test_scan_edit_workflow_updates_and_audits(self) -> None:
        token = self.login("tech@murisphere.local", "tech1234")
        cages = self.client.get("/api/cages", headers=self.auth_headers(token)).get_json()
        self.assertTrue(cages)
        first = cages[0]

        scan = self.client.get(f"/api/scan/{first['cageCode']}", headers=self.auth_headers(token))
        self.assertEqual(scan.status_code, 200)
        scan_payload = scan.get_json()
        self.assertEqual(scan_payload["cage"]["id"], first["id"])

        patch = self.client.patch(
            f"/api/cages/{first['id']}",
            headers=self.auth_headers(token),
            json={
                "maleCount": first["maleCount"] + 1,
                "femaleCount": first["femaleCount"] + 2,
                "breedingStatus": "Holding",
                "notes": "Updated from test",
            },
        )
        self.assertEqual(patch.status_code, 200)

        detail = self.client.get(f"/api/cages/{first['id']}", headers=self.auth_headers(token)).get_json()
        cage = detail["cage"]
        self.assertEqual(cage["maleCount"], first["maleCount"] + 1)
        self.assertEqual(cage["femaleCount"], first["femaleCount"] + 2)
        self.assertEqual(cage["breedingStatus"], "Holding")
        self.assertTrue(any(item["action"] == "update" for item in detail["history"]))

    def test_rbac_on_create_cage(self) -> None:
        tech = self.login("tech@murisphere.local", "tech1234")
        admin = self.login("admin@murisphere.local", "admin1234")

        payload = {
            "cageCode": "C-NEW-001",
            "strain": "C57BL/6J",
            "genotypeSummary": "WT/WT",
            "breedingStatus": "Holding",
            "maleCount": 1,
            "femaleCount": 1,
            "roomId": 1,
            "rackId": 1,
            "labId": 1,
            "protocolId": 1,
        }

        forbidden = self.client.post("/api/cages", headers=self.auth_headers(tech), json=payload)
        self.assertEqual(forbidden.status_code, 403)

        created = self.client.post("/api/cages", headers=self.auth_headers(admin), json=payload)
        self.assertEqual(created.status_code, 201)

    def test_cards_and_public_scan(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")
        cages = self.client.get("/api/cages", headers=self.auth_headers(token)).get_json()

        cards = self.client.post("/api/cages/cards", headers=self.auth_headers(token), json={"ids": [cages[0]["id"]]})
        self.assertEqual(cards.status_code, 200)
        card = cards.get_json()[0]
        self.assertTrue(card["scanUrl"].startswith("/scan/"))
        self.assertTrue(card["qrValue"])

        public_scan = self.client.get(f"/api/public/scan/{card['qrValue']}")
        self.assertEqual(public_scan.status_code, 200)
        self.assertEqual(public_scan.get_json()["cage"]["cageCode"], card["cageCode"])

        scan_page = self.client.get(card["scanUrl"])
        self.assertEqual(scan_page.status_code, 200)
        self.assertIn(b"Loading Cage Info", scan_page.data)

    def test_breeding_calendar_forecast_and_analytics(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")

        event_date = (date.today() + timedelta(days=2)).isoformat()
        event = self.client.post(
            "/api/breeding/events",
            headers=self.auth_headers(token),
            json={"cageId": 1, "eventType": "plug_check", "eventDate": event_date},
        )
        self.assertEqual(event.status_code, 200)

        cal = self.client.get("/api/calendar", headers=self.auth_headers(token))
        self.assertEqual(cal.status_code, 200)
        self.assertTrue(any(item["event_type"] == "plug_check" for item in cal.get_json()))

        forecast = self.client.post(
            "/api/forecast/demand",
            headers=self.auth_headers(token),
            json={"neededBy": (date.today() + timedelta(days=30)).isoformat(), "animalsNeeded": 120},
        )
        self.assertEqual(forecast.status_code, 200)
        f = forecast.get_json()
        self.assertEqual(f["requested"], 120)
        self.assertIn("estimatedLittersRequired", f)

        analytics = self.client.get("/api/analytics/summary", headers=self.auth_headers(token))
        self.assertEqual(analytics.status_code, 200)
        self.assertGreaterEqual(analytics.get_json()["totalCages"], 2)

    def test_reports_imports_genotyping_facility_audit(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")

        csv_res = self.client.get("/api/reports/cages.csv", headers=self.auth_headers(token))
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res.content_type)

        xlsx_res = self.client.get("/api/reports/cages.xlsx", headers=self.auth_headers(token))
        self.assertEqual(xlsx_res.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xlsx_res.content_type)

        pdf_res = self.client.get("/api/reports/cages.pdf", headers=self.auth_headers(token))
        self.assertEqual(pdf_res.status_code, 200)
        self.assertIn("application/pdf", pdf_res.content_type)
        self.assertTrue(pdf_res.data.startswith(b"%PDF-"))

        with sqlite3.connect(appmod.DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'Pending', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                (
                    "A-GENO-001",
                    date.today().isoformat(),
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

        genotype_csv = io.BytesIO(b"animal_code,genotype_result\nA-GENO-001,fl/fl\n")
        geno = self.client.post(
            "/api/genotyping/upload",
            headers=self.auth_headers(token),
            data={"file": (genotype_csv, "genotyping.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(geno.status_code, 200)
        self.assertEqual(geno.get_json()["updatedAnimals"], 1)

        wb = Workbook()
        ws = wb.active
        ws.append(["cage_code", "strain", "genotype", "breeding_status", "male", "female"])
        ws.append(["C-IMPORT-001", "BALB/c", "WT/WT", "Holding", 1, 2])
        xlsx_file = io.BytesIO()
        wb.save(xlsx_file)
        xlsx_file.seek(0)

        imp = self.client.post(
            "/api/import/excel",
            headers=self.auth_headers(token),
            data={"file": (xlsx_file, "import.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(imp.status_code, 200)
        self.assertGreaterEqual(imp.get_json()["created"], 1)

        compliance = self.client.get("/api/compliance/protocol-alerts", headers=self.auth_headers(token))
        self.assertEqual(compliance.status_code, 200)

        facility = self.client.get("/api/facility/capacity", headers=self.auth_headers(token))
        self.assertEqual(facility.status_code, 200)

        audit = self.client.get("/api/audit", headers=self.auth_headers(token))
        self.assertEqual(audit.status_code, 200)
        self.assertIsInstance(audit.get_json(), list)


if __name__ == "__main__":
    unittest.main()
