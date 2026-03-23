# Copyright 2026 Murisphere Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import UTC, date, datetime, timedelta

from openpyxl import Workbook

import app as appmod


class AppIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = appmod.DB_PATH
        self._old_attachment_dir = appmod.ATTACHMENT_DIR
        appmod.DB_PATH = f"{self._tmp.name}/test_murisphere.db"
        appmod.ATTACHMENT_DIR = Path(self._tmp.name) / "uploads"
        appmod.init_db()
        appmod.reset_rate_limit_state()
        appmod.app.config.update(TESTING=True)
        self.client = appmod.app.test_client()

    def tearDown(self) -> None:
        appmod.reset_rate_limit_state()
        appmod.DB_PATH = self._old_db
        appmod.ATTACHMENT_DIR = self._old_attachment_dir
        self._tmp.cleanup()

    def login(self, email: str, password: str) -> str:
        res = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200)
        return res.get_json()["token"]

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_auth_login_and_me(self) -> None:
        unauth = self.client.get("/api/auth/me")
        self.assertEqual(unauth.status_code, 401)

        token = self.login("admin@murisphere.local", "admin1234")
        me = self.client.get("/api/auth/me", headers=self.auth_headers(token))
        self.assertEqual(me.status_code, 200)
        payload = me.get_json()
        self.assertEqual(payload["email"], "admin@murisphere.local")
        self.assertEqual(payload["role"], "Admin")

    def test_system_health_reports_runtime_contract(self) -> None:
        res = self.client.get("/api/system/health")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["app"], "Murisphere")
        self.assertIn("version", payload)
        self.assertIn("runtimeMode", payload)
        self.assertEqual(payload["storage"], "sqlite")

    def test_login_rate_limit_blocks_repeated_failures(self) -> None:
        old_cfg = (
            appmod.LOGIN_RATE_LIMIT_MAX_FAILURES,
            appmod.LOGIN_RATE_LIMIT_WINDOW_SEC,
            appmod.LOGIN_RATE_LIMIT_BLOCK_SEC,
        )
        try:
            appmod.LOGIN_RATE_LIMIT_MAX_FAILURES = 3
            appmod.LOGIN_RATE_LIMIT_WINDOW_SEC = 60
            appmod.LOGIN_RATE_LIMIT_BLOCK_SEC = 60
            appmod.reset_rate_limit_state()

            for _ in range(2):
                bad = self.client.post("/api/auth/login", json={"email": "admin@murisphere.local", "password": "wrong"})
                self.assertEqual(bad.status_code, 401)

            blocked = self.client.post("/api/auth/login", json={"email": "admin@murisphere.local", "password": "wrong"})
            self.assertEqual(blocked.status_code, 429)
            self.assertIn("retryAfterSec", blocked.get_json())

            still_blocked = self.client.post("/api/auth/login", json={"email": "admin@murisphere.local", "password": "admin1234"})
            self.assertEqual(still_blocked.status_code, 429)
        finally:
            (
                appmod.LOGIN_RATE_LIMIT_MAX_FAILURES,
                appmod.LOGIN_RATE_LIMIT_WINDOW_SEC,
                appmod.LOGIN_RATE_LIMIT_BLOCK_SEC,
            ) = old_cfg
            appmod.reset_rate_limit_state()

    def test_public_scan_rate_limit(self) -> None:
        old_cfg = (
            appmod.PUBLIC_SCAN_RATE_LIMIT_MAX,
            appmod.PUBLIC_SCAN_RATE_LIMIT_WINDOW_SEC,
        )
        try:
            appmod.PUBLIC_SCAN_RATE_LIMIT_MAX = 2
            appmod.PUBLIC_SCAN_RATE_LIMIT_WINDOW_SEC = 60
            appmod.reset_rate_limit_state()

            token = self.login("admin@murisphere.local", "admin1234")
            cages = self.client.get("/api/cages", headers=self.auth_headers(token)).get_json()
            cards = self.client.post("/api/cages/cards", headers=self.auth_headers(token), json={"ids": [cages[0]["id"]]})
            card = cards.get_json()[0]

            ok1 = self.client.get(f"/api/public/scan/{card['qrValue']}")
            ok2 = self.client.get(f"/api/public/scan/{card['qrValue']}")
            blocked = self.client.get(f"/api/public/scan/{card['qrValue']}")

            self.assertEqual(ok1.status_code, 200)
            self.assertEqual(ok2.status_code, 200)
            self.assertEqual(blocked.status_code, 429)
            self.assertIn("retryAfterSec", blocked.get_json())
        finally:
            appmod.PUBLIC_SCAN_RATE_LIMIT_MAX, appmod.PUBLIC_SCAN_RATE_LIMIT_WINDOW_SEC = old_cfg
            appmod.reset_rate_limit_state()

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
        self.assertIn("groupOwner", card)
        self.assertIn("groupName", card)
        self.assertIn("protocolDescription", card)
        self.assertIn("projects", card)
        self.assertIn("animals", card)
        self.assertIn("litters", card)
        self.assertIsInstance(card["projects"], list)
        self.assertIsInstance(card["animals"], list)
        self.assertIsInstance(card["litters"], list)
        if card["litters"]:
            self.assertIn("dow", card["litters"][0])

        public_scan = self.client.get(f"/api/public/scan/{card['qrValue']}")
        self.assertEqual(public_scan.status_code, 200)
        public_cage = public_scan.get_json()["cage"]
        self.assertEqual(public_cage["cageCode"], card["cageCode"])
        self.assertIn("genotypeSummary", public_cage)
        self.assertIn("dob", public_cage)
        self.assertIn("protocol", public_cage)

        scan_page = self.client.get(card["scanUrl"])
        self.assertEqual(scan_page.status_code, 200)
        self.assertIn(b"Loading Cage Info", scan_page.data)

        qr = self.client.get(f"/api/assets/qrcode.png?v=https://example.org{card['scanUrl']}")
        self.assertEqual(qr.status_code, 200)
        self.assertIn("image/png", qr.content_type)
        self.assertTrue(qr.data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(qr.data), 300)

        barcode = self.client.get(f"/api/assets/barcode.svg?v={card['cageCode']}")
        self.assertEqual(barcode.status_code, 200)
        self.assertIn("image/svg+xml", barcode.content_type)
        self.assertIn(b"<svg", barcode.data)

    def test_litter_dow_is_exposed_on_cage_card_and_set_by_wean(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")
        litter_birth = (date.today() - timedelta(days=21)).isoformat()
        created = self.client.post(
            "/api/litters",
            headers=self.auth_headers(token),
            json={"cageId": 1, "birthDate": litter_birth, "size": 4, "survived": 3, "male": 1, "female": 2},
        )
        self.assertEqual(created.status_code, 200)
        litter_id = created.get_json()["id"]

        cards_before = self.client.post("/api/cages/cards", headers=self.auth_headers(token), json={"ids": [1]}).get_json()
        litter_before = next((l for l in cards_before[0]["litters"] if l["litterId"] == litter_id), None)
        self.assertIsNotNone(litter_before)
        self.assertIn("dow", litter_before)
        self.assertIsNone(litter_before["dow"])

        dow_date = date.today().isoformat()
        wean = self.client.post(
            "/api/cages/1/wean",
            headers=self.auth_headers(token),
            json={"male": 0, "female": 0, "litterId": litter_id, "date": dow_date},
        )
        self.assertEqual(wean.status_code, 200)

        cards_after = self.client.post("/api/cages/cards", headers=self.auth_headers(token), json={"ids": [1]}).get_json()
        litter_after = next((l for l in cards_after[0]["litters"] if l["litterId"] == litter_id), None)
        self.assertIsNotNone(litter_after)
        self.assertEqual(litter_after["dow"], dow_date)

    def test_index_uses_local_card_rendering_assets(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertNotIn("cdn.jsdelivr.net/npm/qrcode", body)
        self.assertNotIn("cdn.jsdelivr.net/npm/jsbarcode", body)
        self.assertIn('id="dashboardLearning"', body)
        self.assertIn('id="plannerScenarioForm"', body)
        self.assertIn('id="loadPlannerBtn"', body)
        self.assertIn('id="sampleCreateForm"', body)
        self.assertIn('id="loadSamplesBtn"', body)
        self.assertIn('id="genotypingCallbackForm"', body)

    def test_learning_routes_serve_tutorial_assets(self) -> None:
        redirect_res = self.client.get("/learn", follow_redirects=False)
        self.assertEqual(redirect_res.status_code, 308)
        self.assertEqual(redirect_res.headers["Location"], "/learn/")

        page = self.client.get("/learn/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn("self-paced learning", body)
        self.assertIn("tutorial.css", body)
        self.assertIn("assets/cage_card_complete.svg", body)

        css = self.client.get("/learn/tutorial.css")
        self.assertEqual(css.status_code, 200)
        self.assertIn("text/css", css.content_type)
        self.assertIn(b":root", css.data)

        asset = self.client.get("/learn/assets/cage_card_complete.svg")
        self.assertEqual(asset.status_code, 200)
        self.assertIn("image/svg+xml", asset.content_type)
        self.assertIn(b"<svg", asset.data)

        pdf = self.client.get("/learn/user_training_tutorial.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("application/pdf", pdf.content_type)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))

    def test_learning_overview_reports_scope_and_seeded_examples(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")

        initial = self.client.get("/api/learning/overview", headers=self.auth_headers(token))
        self.assertEqual(initial.status_code, 200)
        payload = initial.get_json()
        self.assertEqual(payload["tutorialUrl"], "/learn/")
        self.assertEqual(payload["tutorialPdfUrl"], "/learn/user_training_tutorial.pdf")
        self.assertEqual(len(payload["modules"]), 7)
        self.assertFalse(payload["tutorialReady"])
        self.assertEqual(payload["counts"]["animals"], 0)
        self.assertIsNone(payload["examples"]["pedigreeAnimal"])

        project = self.client.post(
            "/api/projects",
            headers=self.auth_headers(token),
            json={"labId": 1, "projectCode": "PRJ-LEARN-001", "title": "Learning Cohort", "status": "active", "targetAnimals": 24},
        )
        self.assertEqual(project.status_code, 201)
        project_id = project.get_json()["id"]

        litter = self.client.post(
            "/api/litters",
            headers=self.auth_headers(token),
            json={"cageId": 1, "birthDate": date.today().isoformat(), "size": 4, "survived": 4, "male": 2, "female": 2},
        )
        self.assertEqual(litter.status_code, 200)
        litter_id = litter.get_json()["id"]

        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(appmod.DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("LEARN-SIRE-001", date.today().isoformat(), now, now),
            )
            sire_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'F', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("LEARN-DAM-001", date.today().isoformat(), now, now),
            )
            dam_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'Cre/+', 'Active', 1, ?, ?, ?, ?, ?)
                """,
                ("LEARN-PUP-001", date.today().isoformat(), litter_id, sire_id, dam_id, now, now),
            )
            pup_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        sample = self.client.post(
            "/api/samples",
            headers=self.auth_headers(token),
            json={
                "animalId": pup_id,
                "sampleType": "tail",
                "sampleCode": "SMP-LEARN-001",
                "status": "received",
                "provider": "Transnetyx",
            },
        )
        self.assertEqual(sample.status_code, 201)

        scenario = self.client.post(
            "/api/planner/scenarios",
            headers=self.auth_headers(token),
            json={"labId": 1, "name": "Learning Planner Scenario", "neededBy": "2026-04-15", "targetAnimals": 20, "maxNewCages": 4},
        )
        self.assertEqual(scenario.status_code, 201)

        attach = self.client.post(
            f"/api/planner/scenarios/{scenario.get_json()['id']}/projects",
            headers=self.auth_headers(token),
            json={"projects": [{"projectId": project_id, "animalsNeeded": 20, "priority": 1}]},
        )
        self.assertEqual(attach.status_code, 200)

        learned = self.client.get("/api/learning/overview", headers=self.auth_headers(token))
        self.assertEqual(learned.status_code, 200)
        enriched = learned.get_json()
        self.assertTrue(enriched["workflowAvailability"]["breedingPedigree"])
        self.assertTrue(enriched["workflowAvailability"]["sampleGenotyping"])
        self.assertTrue(enriched["workflowAvailability"]["planner"])
        self.assertTrue(enriched["workflowAvailability"]["projects"])
        self.assertTrue(enriched["tutorialReady"])
        self.assertEqual(enriched["examples"]["project"]["project_code"], "PRJ-LEARN-001")
        self.assertEqual(enriched["examples"]["pedigreeAnimal"]["animal_code"], "LEARN-PUP-001")
        self.assertEqual(enriched["examples"]["sample"]["sample_code"], "SMP-LEARN-001")
        self.assertEqual(enriched["examples"]["plannerScenario"]["name"], "Learning Planner Scenario")

    def test_planner_detail_and_recommendation_workflow(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")

        project = self.client.post(
            "/api/projects",
            headers=self.auth_headers(token),
            json={"labId": 1, "projectCode": "PRJ-PLAN-001", "title": "Planner Demand", "status": "active", "targetAnimals": 30},
        )
        self.assertEqual(project.status_code, 201)
        project_id = project.get_json()["id"]

        scenario = self.client.post(
            "/api/planner/scenarios",
            headers=self.auth_headers(token),
            json={"labId": 1, "name": "Planner Console Scenario", "neededBy": "2026-04-20", "targetAnimals": 30, "maxNewCages": 3},
        )
        self.assertEqual(scenario.status_code, 201)
        scenario_id = scenario.get_json()["id"]

        attach = self.client.post(
            f"/api/planner/scenarios/{scenario_id}/projects",
            headers=self.auth_headers(token),
            json={"projects": [{"projectId": project_id, "animalsNeeded": 30, "priority": 1}]},
        )
        self.assertEqual(attach.status_code, 200)

        detail = self.client.get(f"/api/planner/scenarios/{scenario_id}", headers=self.auth_headers(token))
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()
        self.assertEqual(detail_payload["scenario"]["name"], "Planner Console Scenario")
        self.assertEqual(detail_payload["projects"][0]["project_code"], "PRJ-PLAN-001")
        self.assertIn("lab_name", detail_payload["scenario"])

        evaluate = self.client.post(f"/api/planner/scenarios/{scenario_id}/evaluate", headers=self.auth_headers(token))
        self.assertEqual(evaluate.status_code, 200)
        self.assertIn("riskLevel", evaluate.get_json())

        plans = self.client.get(f"/api/planner/scenarios/{scenario_id}/plans", headers=self.auth_headers(token))
        self.assertEqual(plans.status_code, 200)
        self.assertTrue(plans.get_json())

        recs = self.client.get("/api/recommendations?status=open", headers=self.auth_headers(token))
        self.assertEqual(recs.status_code, 200)
        self.assertTrue(isinstance(recs.get_json(), list))

        outcomes = self.client.get("/api/recommendations/outcomes", headers=self.auth_headers(token))
        self.assertEqual(outcomes.status_code, 200)
        self.assertTrue(isinstance(outcomes.get_json(), list))

    def test_scan_template_escapes_public_fields(self) -> None:
        page = self.client.get("/scan/test-token-123")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn("const esc = (value)", body)
        self.assertIn("${esc(c.strain)}", body)
        self.assertIn("${esc(c.genotypeSummary)}", body)
        self.assertIn("${esc(c.protocol || \"N/A\")}", body)
        self.assertIn("${esc(e.message)}", body)

    def test_frontend_handles_session_expiry_contract(self) -> None:
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("function handleSessionExpired(", js)
        self.assertIn("function handleBackgroundError(", js)
        self.assertIn("err.status = res.status", js)
        self.assertIn("if (err && Number(err.status) === 401)", js)
        self.assertIn("loadActiveAlertFeed().catch((err) => handleBackgroundError(err", js)

    def test_frontend_learning_and_planner_contract(self) -> None:
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("const LEARNING_PROGRESS_KEY =", js)
        self.assertIn('el("plannerScenarioForm").addEventListener("submit"', js)
        self.assertIn('el("generateRecommendationsBtn").addEventListener("click"', js)
        self.assertIn('api("/api/planner/scenarios"', js)
        self.assertIn('data-learning-toggle-module', js)
        self.assertIn('el("sampleCreateForm").addEventListener("submit"', js)
        self.assertIn('el("genotypingOrderForm").addEventListener("submit"', js)
        self.assertIn('el("genotypingCallbackForm").addEventListener("submit"', js)
        self.assertIn('inspectGenotypingOrder(orderId)', js)
        self.assertIn('"/api/genotyping/orders"', js)
        self.assertIn('"/api/genotyping/orders/callback"', js)

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

    def test_project_management_assignment_and_scope(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        create = self.client.post(
            "/api/projects",
            headers=self.auth_headers(admin),
            json={"labId": 1, "projectCode": "PRJ-NG-001", "title": "Neuro Cohort", "status": "active", "targetAnimals": 120},
        )
        self.assertEqual(create.status_code, 201)
        project_id = create.get_json()["id"]

        cages = self.client.get("/api/cages", headers=self.auth_headers(admin)).get_json()
        assign = self.client.post(
            f"/api/projects/{project_id}/assign-cages",
            headers=self.auth_headers(admin),
            json={"cageIds": [cages[0]["id"], cages[1]["id"]]},
        )
        self.assertEqual(assign.status_code, 200)
        self.assertEqual(assign.get_json()["assigned"], 2)

        plist = self.client.get("/api/projects", headers=self.auth_headers(admin))
        self.assertEqual(plist.status_code, 200)
        self.assertTrue(any(p["project_code"] == "PRJ-NG-001" for p in plist.get_json()))

        pcages = self.client.get(f"/api/projects/{project_id}/cages", headers=self.auth_headers(admin))
        self.assertEqual(pcages.status_code, 200)
        self.assertEqual(len(pcages.get_json()), 2)

        search_by_project_code = self.client.get("/api/cages?q=PRJ-NG-001", headers=self.auth_headers(admin))
        self.assertEqual(search_by_project_code.status_code, 200)
        self.assertGreaterEqual(len(search_by_project_code.get_json()), 2)
        self.assertTrue(all("projectCodes" in c for c in search_by_project_code.get_json()))

        search_by_project_title = self.client.get("/api/cages?q=Neuro Cohort", headers=self.auth_headers(admin))
        self.assertEqual(search_by_project_title.status_code, 200)
        self.assertGreaterEqual(len(search_by_project_title.get_json()), 2)

        forbidden = self.client.post(
            "/api/projects",
            headers=self.auth_headers(tech),
            json={"labId": 1, "projectCode": "PRJ-TECH-001", "title": "Should Fail"},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_bulk_actions_and_quota_tracking(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO lab_profiles (lab_id, size_tier, staff_count, expected_cage_load, active_project_count, updated_at) VALUES (1, 'medium', 6, 20, 2, ?)",
                (now,),
            )
            conn.commit()

        cages = self.client.get("/api/cages", headers=self.auth_headers(admin)).get_json()
        ids = [cages[0]["id"], cages[1]["id"]]

        retire = self.client.post(
            "/api/cages/bulk-actions",
            headers=self.auth_headers(admin),
            json={"action": "retire_breeders", "cageIds": ids, "reason": "non-productive"},
        )
        self.assertEqual(retire.status_code, 200)
        self.assertEqual(retire.get_json()["updated"], 2)

        updated_cage = self.client.get(f"/api/cages/{ids[0]}", headers=self.auth_headers(admin)).get_json()["cage"]
        self.assertEqual(updated_cage["breedingStatus"], "Retired")

        transfer = self.client.post(
            "/api/cages/bulk-actions",
            headers=self.auth_headers(admin),
            json={"action": "transfer", "cageIds": ids, "roomId": 1, "rackId": 1},
        )
        self.assertEqual(transfer.status_code, 200)
        self.assertEqual(transfer.get_json()["updated"], 2)

        quotas = self.client.get("/api/facility/quotas", headers=self.auth_headers(admin))
        self.assertEqual(quotas.status_code, 200)
        payload = quotas.get_json()
        self.assertTrue(payload)
        self.assertTrue(any(row["labId"] == 1 for row in payload))

    def test_advanced_analytics_and_operational_endpoints(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")

        # Seed lineage and litter/genotype records
        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.row_factory = sqlite3.Row
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'M', ?, 'C57BL/6J', 'fl/+','Active',1,NULL,NULL,NULL,?,?)",
                ("SIRE-001", date.today().isoformat(), now, now),
            )
            sire_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'F', ?, 'C57BL/6J', '+/+','Active',1,NULL,NULL,NULL,?,?)",
                ("DAM-001", date.today().isoformat(), now, now),
            )
            dam_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO litters (cage_id, birth_date, litter_size, survived_count, created_at) VALUES (1, ?, 4, 3, ?)",
                (date.today().isoformat(), now),
            )
            litter_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'M', ?, 'C57BL/6J', 'fl/+','Active',1,?,?,?,?,?)",
                ("PUP-001", date.today().isoformat(), litter_id, sire_id, dam_id, now, now),
            )
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'F', ?, 'C57BL/6J', '+/+','Active',1,?,?,?,?,?)",
                ("PUP-002", date.today().isoformat(), litter_id, sire_id, dam_id, now, now),
            )
            conn.commit()

        animals = self.client.get("/api/animals?q=PUP-001", headers=self.auth_headers(admin))
        self.assertEqual(animals.status_code, 200)
        pup_id = animals.get_json()[0]["id"]

        pedigree = self.client.get(f"/api/animals/{pup_id}/pedigree?generations=2", headers=self.auth_headers(admin))
        self.assertEqual(pedigree.status_code, 200)
        pdata = pedigree.get_json()
        self.assertGreaterEqual(len(pdata["nodes"]), 3)
        self.assertTrue(any(e["relation"] == "sire" for e in pdata["edges"]))

        productivity = self.client.get("/api/breeding/productivity", headers=self.auth_headers(admin))
        self.assertEqual(productivity.status_code, 200)
        self.assertTrue(isinstance(productivity.get_json(), list))

        non_productive = self.client.get("/api/breeding/non-productive?staleDays=0", headers=self.auth_headers(admin))
        self.assertEqual(non_productive.status_code, 200)

        reminders = self.client.get("/api/tasks/reminders?windowDays=30", headers=self.auth_headers(admin))
        self.assertEqual(reminders.status_code, 200)

        mendelian = self.client.get("/api/genotyping/mendelian", headers=self.auth_headers(admin))
        self.assertEqual(mendelian.status_code, 200)
        self.assertTrue(isinstance(mendelian.get_json(), list))

        alerts = self.client.get("/api/genotyping/alerts?threshold=0.1", headers=self.auth_headers(admin))
        self.assertEqual(alerts.status_code, 200)

        space = self.client.get("/api/forecast/cage-space?days=30", headers=self.auth_headers(admin))
        self.assertEqual(space.status_code, 200)
        self.assertIn("rooms", space.get_json())

        consolidation = self.client.get("/api/forecast/consolidation?maxAnimals=5", headers=self.auth_headers(admin))
        self.assertEqual(consolidation.status_code, 200)

        facilities = self.client.get("/api/facilities", headers=self.auth_headers(admin))
        self.assertEqual(facilities.status_code, 200)
        self.assertTrue(facilities.get_json())

        chargeback = self.client.get("/api/facility/chargeback?periodDays=30&ratePerCageDay=1.0", headers=self.auth_headers(admin))
        self.assertEqual(chargeback.status_code, 200)
        self.assertTrue(chargeback.get_json())

        breeder_csv = self.client.get("/api/reports/breeder-productivity.csv", headers=self.auth_headers(admin))
        self.assertEqual(breeder_csv.status_code, 200)
        self.assertIn("text/csv", breeder_csv.content_type)

        survival_csv = self.client.get("/api/reports/survival.csv", headers=self.auth_headers(admin))
        self.assertEqual(survival_csv.status_code, 200)
        self.assertIn("text/csv", survival_csv.content_type)

        protocol_csv = self.client.get("/api/reports/protocol-usage.csv", headers=self.auth_headers(admin))
        self.assertEqual(protocol_csv.status_code, 200)
        self.assertIn("text/csv", protocol_csv.content_type)

    def test_protocol_expiry_hard_stop(self) -> None:
        tech = self.login("tech@murisphere.local", "tech1234")
        admin = self.login("admin@murisphere.local", "admin1234")
        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO iacuc_protocols (protocol_number, title, lab_id, expires_on, created_at) VALUES (?, ?, ?, ?, ?)",
                ("IACUC-EXPIRED-1", "Expired Protocol", 1, "2020-01-01", now),
            )
            protocol_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("UPDATE cages SET protocol_id = ? WHERE id = 1", (protocol_id,))
            conn.commit()

        blocked = self.client.patch("/api/cages/1", headers=self.auth_headers(tech), json={"notes": "should fail"})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "PROTOCOL_EXPIRED")

        # Restore valid protocol for further actions in this test
        with sqlite3.connect(appmod.DB_PATH) as conn:
            conn.execute("UPDATE cages SET protocol_id = 1 WHERE id = 1")
            conn.commit()

        ok = self.client.patch("/api/cages/1", headers=self.auth_headers(admin), json={"notes": "ok now"})
        self.assertEqual(ok.status_code, 200)

    def test_billing_engine_and_requests_and_exports(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        pi = self.login("pi@murisphere.local", "pi1234")

        rule = self.client.post(
            "/api/billing/rules",
            headers=self.auth_headers(admin),
            json={"labId": 1, "lineType": "per_diem", "rate": 1.25},
        )
        self.assertEqual(rule.status_code, 201)

        rules = self.client.get("/api/billing/rules", headers=self.auth_headers(pi))
        self.assertEqual(rules.status_code, 200)
        self.assertTrue(rules.get_json())

        run = self.client.post(
            "/api/billing/run",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(run.status_code, 200)
        self.assertGreater(run.get_json()["entriesUpserted"], 0)

        # rerun-safe upsert
        rerun = self.client.post(
            "/api/billing/run",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(rerun.status_code, 200)

        statement = self.client.get(
            "/api/billing/statements.csv?periodStart=2026-03-01&periodEnd=2026-03-31",
            headers=self.auth_headers(admin),
        )
        self.assertEqual(statement.status_code, 200)
        self.assertIn("text/csv", statement.content_type)

        close = self.client.post(
            "/api/billing/close-period",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(close.status_code, 200)

        after_close = self.client.post(
            "/api/billing/run",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(after_close.status_code, 409)

        req = self.client.post(
            "/api/requests",
            headers=self.auth_headers(pi),
            json={"requestType": "animal_order", "details": {"count": 12, "strain": "C57BL/6J"}},
        )
        self.assertEqual(req.status_code, 201)
        req_id = req.get_json()["id"]

        reqs = self.client.get("/api/requests", headers=self.auth_headers(pi))
        self.assertEqual(reqs.status_code, 200)
        self.assertTrue(reqs.get_json())

        status = self.client.post(
            f"/api/requests/{req_id}/status",
            headers=self.auth_headers(admin),
            json={"status": "approved"},
        )
        self.assertEqual(status.status_code, 200)

        sla = self.client.get("/api/operations/sla", headers=self.auth_headers(admin))
        self.assertEqual(sla.status_code, 200)

        bench = self.client.get("/api/facility/benchmark", headers=self.auth_headers(admin))
        self.assertEqual(bench.status_code, 200)
        self.assertTrue(bench.get_json())

        job = self.client.post(
            "/api/integrations/export-jobs",
            headers=self.auth_headers(admin),
            json={"jobType": "daily_census", "payload": {"format": "csv"}},
        )
        self.assertEqual(job.status_code, 201)
        job_id = job.get_json()["id"]

        run_job = self.client.post(f"/api/integrations/export-jobs/{job_id}/run", headers=self.auth_headers(admin))
        self.assertEqual(run_job.status_code, 200)

        jobs = self.client.get("/api/integrations/export-jobs", headers=self.auth_headers(admin))
        self.assertEqual(jobs.status_code, 200)
        self.assertTrue(any(j["id"] == job_id for j in jobs.get_json()))

    def test_missing_feature_parity_modules_end_to_end(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        # Census session workflow
        sess = self.client.post("/api/census/sessions", headers=self.auth_headers(tech), json={"roomId": 1, "notes": "AM census"})
        self.assertEqual(sess.status_code, 201)
        session_id = sess.get_json()["id"]

        scan = self.client.post(
            f"/api/census/sessions/{session_id}/scan",
            headers=self.auth_headers(tech),
            json={"code": "C-A1-001", "maleCount": 1, "femaleCount": 2, "breedingStatus": "Breeding"},
        )
        self.assertEqual(scan.status_code, 200)

        get_session = self.client.get(f"/api/census/sessions/{session_id}", headers=self.auth_headers(tech))
        self.assertEqual(get_session.status_code, 200)
        self.assertEqual(len(get_session.get_json()["scans"]), 1)

        done = self.client.post(f"/api/census/sessions/{session_id}/complete", headers=self.auth_headers(tech), json={"notes": "done"})
        self.assertEqual(done.status_code, 200)

        # Order lifecycle
        order = self.client.post(
            "/api/orders",
            headers=self.auth_headers(tech),
            json={"quantity": 5, "vendor": "JAX", "strain": "C57BL/6J", "sex": "F"},
        )
        self.assertEqual(order.status_code, 201)
        order_id = order.get_json()["id"]

        promote = self.client.post(
            f"/api/orders/{order_id}/status",
            headers=self.auth_headers(admin),
            json={"status": "ordered"},
        )
        self.assertEqual(promote.status_code, 200)

        orders = self.client.get("/api/orders", headers=self.auth_headers(admin))
        self.assertEqual(orders.status_code, 200)
        self.assertTrue(any(o["id"] == order_id for o in orders.get_json()))

        # Protocol lifecycle versions
        pver = self.client.post(
            "/api/protocols/1/versions",
            headers=self.auth_headers(admin),
            json={"title": "Protocol v2", "details": {"change": "new endpoint"}},
        )
        self.assertEqual(pver.status_code, 201)
        pvers = self.client.get("/api/protocols/1/versions", headers=self.auth_headers(admin))
        self.assertEqual(pvers.status_code, 200)
        self.assertTrue(pvers.get_json())

        # Billing depth
        adj = self.client.post(
            "/api/billing/adjustments",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31", "labId": 1, "amount": -12.5, "reason": "manual correction"},
        )
        self.assertEqual(adj.status_code, 201)
        review = self.client.post(
            "/api/billing/review",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31", "labId": 1, "reviewStatus": "approved", "note": "looks good"},
        )
        self.assertEqual(review.status_code, 200)
        rate_model = self.client.get("/api/billing/rate-model?laborPerDay=0.5&housingPerDay=0.3&overheadPerDay=0.2&marginPct=20", headers=self.auth_headers(admin))
        self.assertEqual(rate_model.status_code, 200)
        self.assertIn("recommendedPerDiemRate", rate_model.get_json())

        # Vet care and treatment
        case = self.client.post(
            "/api/vet/cases",
            headers=self.auth_headers(tech),
            json={"cageId": 1, "severity": "moderate", "notes": "monitor coat condition"},
        )
        self.assertEqual(case.status_code, 201)
        case_id = case.get_json()["id"]
        tx = self.client.post(
            f"/api/vet/cases/{case_id}/treatments",
            headers=self.auth_headers(tech),
            json={"treatmentName": "Supportive care", "scheduleRule": "daily", "nextDueOn": date.today().isoformat()},
        )
        self.assertEqual(tx.status_code, 201)
        cases = self.client.get("/api/vet/cases", headers=self.auth_headers(admin))
        self.assertEqual(cases.status_code, 200)
        self.assertTrue(any(c["id"] == case_id for c in cases.get_json()))

        # Qualification-aware task assignment
        self.client.post(
            "/api/staff/qualifications",
            headers=self.auth_headers(admin),
            json={"userId": 2, "qualificationCode": "Q-WEAN"},
        )
        tgood = self.client.post(
            "/api/tasks/assign",
            headers=self.auth_headers(admin),
            json={"taskType": "wean", "cageId": 1, "dueOn": date.today().isoformat(), "assignedTo": 2, "requiredQualification": "Q-WEAN"},
        )
        self.assertEqual(tgood.status_code, 201)
        tbad = self.client.post(
            "/api/tasks/assign",
            headers=self.auth_headers(admin),
            json={"taskType": "special", "cageId": 1, "dueOn": date.today().isoformat(), "assignedTo": 2, "requiredQualification": "Q-NONEXIST"},
        )
        self.assertEqual(tbad.status_code, 409)

        # Attachments and e-signature
        file_data = io.BytesIO(b"clinical note attachment")
        up = self.client.post(
            "/api/attachments",
            headers=self.auth_headers(tech),
            data={"entityType": "vet_case", "entityId": str(case_id), "file": (file_data, "note.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(up.status_code, 201)
        att_id = up.get_json()["id"]
        alist = self.client.get(f"/api/attachments?entityType=vet_case&entityId={case_id}", headers=self.auth_headers(tech))
        self.assertEqual(alist.status_code, 200)
        self.assertTrue(alist.get_json())
        dl = self.client.get(f"/api/attachments/{att_id}/download", headers=self.auth_headers(tech))
        self.assertEqual(dl.status_code, 200)
        dl.close()

        sign_fail = self.client.post(
            "/api/sign",
            headers=self.auth_headers(tech),
            json={"entityType": "animal_order", "entityId": order_id, "action": "approve", "password": "wrong"},
        )
        self.assertEqual(sign_fail.status_code, 403)
        sign_ok = self.client.post(
            "/api/sign",
            headers=self.auth_headers(tech),
            json={"entityType": "animal_order", "entityId": order_id, "action": "approve", "password": "tech1234"},
        )
        self.assertEqual(sign_ok.status_code, 200)
        self.assertIn("signatureHash", sign_ok.get_json())

        # Real export dispatch path: invalid target should fail
        ejob = self.client.post(
            "/api/integrations/export-jobs",
            headers=self.auth_headers(admin),
            json={"jobType": "lims_sync", "targetUrl": "https://example.invalid/ingest", "payload": {"kind": "census"}},
        )
        self.assertEqual(ejob.status_code, 201)
        erun = self.client.post(f"/api/integrations/export-jobs/{ejob.get_json()['id']}/run", headers=self.auth_headers(admin))
        self.assertEqual(erun.status_code, 502)

    def test_export_job_scope_isolation_for_pi(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        pi_lab1 = self.login("pi@murisphere.local", "pi1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, ?, ?)",
                ("Lab Two", "Dr. Two", 1, now),
            )
            lab2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO users (email, full_name, role, lab_id, password_hash, is_active, created_at) VALUES (?, ?, 'PI', ?, ?, 1, ?)",
                ("pi2@murisphere.local", "PI Two", lab2, appmod.generate_password_hash("pi2pass"), now),
            )
            conn.commit()
        pi_lab2 = self.login("pi2@murisphere.local", "pi2pass")

        j1 = self.client.post(
            "/api/integrations/export-jobs",
            headers=self.auth_headers(pi_lab1),
            json={"jobType": "lab1_job", "payload": {}},
        )
        self.assertEqual(j1.status_code, 201)
        j2 = self.client.post(
            "/api/integrations/export-jobs",
            headers=self.auth_headers(pi_lab2),
            json={"jobType": "lab2_job", "payload": {}},
        )
        self.assertEqual(j2.status_code, 201)
        lab2_job_id = j2.get_json()["id"]

        listed = self.client.get("/api/integrations/export-jobs", headers=self.auth_headers(pi_lab1))
        self.assertEqual(listed.status_code, 200)
        job_types = {row["job_type"] for row in listed.get_json()}
        self.assertIn("lab1_job", job_types)
        self.assertNotIn("lab2_job", job_types)

        forbidden_run = self.client.post(f"/api/integrations/export-jobs/{lab2_job_id}/run", headers=self.auth_headers(pi_lab1))
        self.assertIn(forbidden_run.status_code, (403, 404))

        # Admin can still see all
        listed_admin = self.client.get("/api/integrations/export-jobs", headers=self.auth_headers(admin))
        self.assertEqual(listed_admin.status_code, 200)
        admin_types = {row["job_type"] for row in listed_admin.get_json()}
        self.assertIn("lab1_job", admin_types)
        self.assertIn("lab2_job", admin_types)

    def test_pedigree_does_not_leak_cross_lab_ancestors(self) -> None:
        tech = self.login("tech@murisphere.local", "tech1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, ?, ?)",
                ("Hidden Lab", "Dr. Hidden", 1, now),
            )
            hidden_lab = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO cages (
                    cage_code, strain, genotype_summary, breeding_status, dob, male_count, female_count,
                    room_id, rack_id, lab_id, protocol_id, qr_token, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "C-HIDDEN-001",
                    "BALB/c",
                    "WT/WT",
                    "Holding",
                    date.today().isoformat(),
                    1,
                    1,
                    1,
                    1,
                    hidden_lab,
                    1,
                    "tok_hidden_001",
                    "",
                    now,
                    now,
                ),
            )
            hidden_cage = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'M', ?, 'BALB/c', 'WT/WT', 'Active', ?, NULL, NULL, NULL, ?, ?)",
                ("A-HIDDEN-SIRE", date.today().isoformat(), hidden_cage, now, now),
            )
            hidden_sire = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'F', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, NULL, NULL, ?, ?)",
                ("A-LAB1-DAM", date.today().isoformat(), now, now),
            )
            dam_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at) VALUES (?, 'M', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, ?, ?, ?, ?)",
                ("A-LAB1-CHILD", date.today().isoformat(), hidden_sire, dam_id, now, now),
            )
            child_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        pedigree = self.client.get(f"/api/animals/{child_id}/pedigree?generations=3", headers=self.auth_headers(tech))
        self.assertEqual(pedigree.status_code, 200)
        node_codes = {n["animal_code"] for n in pedigree.get_json()["nodes"]}
        self.assertIn("A-LAB1-CHILD", node_codes)
        self.assertIn("A-LAB1-DAM", node_codes)
        self.assertNotIn("A-HIDDEN-SIRE", node_codes)

    def test_billing_run_rejects_invalid_dates(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        bad = self.client.post(
            "/api/billing/run",
            headers=self.auth_headers(admin),
            json={"periodStart": "not-a-date", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(bad.status_code, 400)

    def test_offline_queue_storage_is_user_scoped(self) -> None:
        src = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("function mutationQueueKey()", src)
        self.assertIn("state.user?.id", src)

    def test_visualization_panels_present_in_ui(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn('id="pedigreeViz"', body)
        self.assertIn('id="cageVisuals"', body)
        self.assertIn('id="breedingVisuals"', body)
        self.assertIn('id="analyticsVisuals"', body)
        self.assertIn('id="complianceVisuals"', body)

        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("renderPedigreeGraph", js)
        self.assertIn("renderAnalyticsVisuals", js)
        self.assertIn("renderCageVisuals", js)

    def test_technician_cannot_access_other_lab_cage(self) -> None:
        tech_token = self.login("tech@murisphere.local", "tech1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, ?, ?)",
                ("Other Lab", "Dr. Other", 1, now),
            )
            other_lab_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO cages (
                    cage_code, strain, genotype_summary, breeding_status, dob, male_count, female_count,
                    room_id, rack_id, lab_id, protocol_id, qr_token, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "C-OTHER-001",
                    "BALB/c",
                    "WT/WT",
                    "Holding",
                    date.today().isoformat(),
                    1,
                    1,
                    1,
                    1,
                    other_lab_id,
                    1,
                    "tok_other_001",
                    "other lab cage",
                    now,
                    now,
                ),
            )
            conn.commit()

        # Should not be visible in list
        cages = self.client.get("/api/cages", headers=self.auth_headers(tech_token)).get_json()
        self.assertFalse(any(c["cageCode"] == "C-OTHER-001" for c in cages))

        # Should not be scannable or editable by another lab's technician
        scan = self.client.get("/api/scan/C-OTHER-001", headers=self.auth_headers(tech_token))
        self.assertEqual(scan.status_code, 404)

        other = self.client.get("/api/public/scan/tok_other_001")
        self.assertEqual(other.status_code, 200)
        other_id = other.get_json()["cage"]["id"]

        edit = self.client.patch(
            f"/api/cages/{other_id}",
            headers=self.auth_headers(tech_token),
            json={"notes": "attempted cross-lab edit"},
        )
        self.assertEqual(edit.status_code, 404)

    def test_quarantine_and_mortality_workflows(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        intake = self.client.post(
            "/api/quarantine/intakes",
            headers=self.auth_headers(tech),
            json={
                "labId": 1,
                "cageId": 1,
                "vendor": "JAX",
                "strain": "C57BL/6J",
                "sex": "F",
                "quantity": 10,
                "arrivalDate": date.today().isoformat(),
                "quarantineEndOn": date.today().isoformat(),
                "notes": "incoming shipment",
            },
        )
        self.assertEqual(intake.status_code, 201)
        intake_id = intake.get_json()["id"]

        promote = self.client.post(
            f"/api/quarantine/intakes/{intake_id}/status",
            headers=self.auth_headers(admin),
            json={"status": "in_quarantine"},
        )
        self.assertEqual(promote.status_code, 200)

        qlist = self.client.get("/api/quarantine/intakes?status=in_quarantine", headers=self.auth_headers(admin))
        self.assertEqual(qlist.status_code, 200)
        self.assertTrue(any(i["id"] == intake_id for i in qlist.get_json()))

        qalerts = self.client.get("/api/compliance/quarantine-alerts", headers=self.auth_headers(admin))
        self.assertEqual(qalerts.status_code, 200)
        self.assertTrue(any(i["id"] == intake_id for i in qalerts.get_json()))

        mortality = self.client.post(
            "/api/cages/1/mortality",
            headers=self.auth_headers(tech),
            json={"male": 1, "female": 0, "cause": "found dead", "necropsyRequired": True, "notes": "flag for pathology"},
        )
        self.assertEqual(mortality.status_code, 201)
        mortality_id = mortality.get_json()["id"]

        mlist = self.client.get("/api/mortality?necropsyStatus=pending", headers=self.auth_headers(admin))
        self.assertEqual(mlist.status_code, 200)
        self.assertTrue(any(m["id"] == mortality_id for m in mlist.get_json()))

        complete_necropsy = self.client.post(
            f"/api/mortality/{mortality_id}/necropsy",
            headers=self.auth_headers(admin),
            json={"status": "completed"},
        )
        self.assertEqual(complete_necropsy.status_code, 200)

        mortality_csv = self.client.get("/api/reports/mortality.csv", headers=self.auth_headers(admin))
        self.assertEqual(mortality_csv.status_code, 200)
        self.assertIn("text/csv", mortality_csv.content_type)

    def test_alert_feed_ack_and_dispatch_channels(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")

        overdue_task = self.client.post(
            "/api/tasks/assign",
            headers=self.auth_headers(admin),
            json={"taskType": "plug_check", "cageId": 1, "dueOn": "2020-01-01", "assignedTo": 2},
        )
        self.assertEqual(overdue_task.status_code, 201)

        feed = self.client.get("/api/alerts/feed?status=active", headers=self.auth_headers(admin))
        self.assertEqual(feed.status_code, 200)
        alerts = feed.get_json()
        self.assertTrue(alerts)
        alert_id = alerts[0]["id"]

        ack = self.client.post(f"/api/alerts/{alert_id}/ack", headers=self.auth_headers(admin))
        self.assertEqual(ack.status_code, 200)

        acked_feed = self.client.get("/api/alerts/feed?status=acknowledged", headers=self.auth_headers(admin))
        self.assertEqual(acked_feed.status_code, 200)
        self.assertTrue(any(a["id"] == alert_id for a in acked_feed.get_json()))

        channel = self.client.post(
            "/api/notifications/channels",
            headers=self.auth_headers(admin),
            json={"channelType": "in_app", "labId": 1, "minSeverity": "low"},
        )
        self.assertEqual(channel.status_code, 201)

        mortality = self.client.post(
            "/api/cages/1/mortality",
            headers=self.auth_headers(admin),
            json={"male": 1, "cause": "found dead", "necropsyRequired": True},
        )
        self.assertEqual(mortality.status_code, 201)

        dispatch = self.client.post("/api/alerts/dispatch", headers=self.auth_headers(admin))
        self.assertEqual(dispatch.status_code, 200)
        self.assertGreaterEqual(dispatch.get_json()["simulated"], 1)

    def test_new_feature_workflows_end_to_end(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute("UPDATE cages SET male_count = 0, female_count = 1 WHERE id = 1")
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("PAIR-SIRE-001", date.today().isoformat(), now, now),
            )
            sire_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'F', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("PAIR-DAM-001", date.today().isoformat(), now, now),
            )
            dam_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        pair = self.client.post(
            "/api/breeding/pairs",
            headers=self.auth_headers(tech),
            json={"sireId": sire_id, "damId": dam_id, "cageId": 1, "notes": "timed pairing"},
        )
        self.assertEqual(pair.status_code, 201)
        pair_id = pair.get_json()["id"]

        with sqlite3.connect(appmod.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO litters (cage_id, birth_date, litter_size, survived_count, created_at) VALUES (1, ?, 6, 5, ?)",
                (date.today().isoformat(), datetime.now(UTC).isoformat()),
            )
            conn.commit()

        pair_prod = self.client.get(f"/api/breeding/pairs/{pair_id}/productivity", headers=self.auth_headers(tech))
        self.assertEqual(pair_prod.status_code, 200)
        self.assertGreaterEqual(pair_prod.get_json()["litterCount"], 1)

        pause_pair = self.client.post(
            f"/api/breeding/pairs/{pair_id}/status",
            headers=self.auth_headers(tech),
            json={"status": "paused", "notes": "temporary hold"},
        )
        self.assertEqual(pause_pair.status_code, 200)
        pair_list = self.client.get("/api/breeding/pairs?status=paused", headers=self.auth_headers(tech))
        self.assertEqual(pair_list.status_code, 200)
        self.assertTrue(any(p["id"] == pair_id for p in pair_list.get_json()))

        tag = self.client.post(
            f"/api/animals/{sire_id}/tags",
            headers=self.auth_headers(tech),
            json={"tagType": "ear_tag", "tagValue": "E-001"},
        )
        self.assertEqual(tag.status_code, 201)
        tags = self.client.get(f"/api/animals/{sire_id}/tags", headers=self.auth_headers(tech))
        self.assertEqual(tags.status_code, 200)
        self.assertTrue(any(t["tag_value"] == "E-001" for t in tags.get_json()))

        sample = self.client.post(
            "/api/samples",
            headers=self.auth_headers(tech),
            json={"animalId": sire_id, "sampleType": "tail", "sampleCode": "SMP-001", "provider": "Transnetyx"},
        )
        self.assertEqual(sample.status_code, 201)
        sample_id = sample.get_json()["id"]
        sample_list = self.client.get("/api/samples", headers=self.auth_headers(tech))
        self.assertEqual(sample_list.status_code, 200)
        self.assertTrue(any(row["id"] == sample_id and row["animal_id"] == sire_id and row["cage_id"] == 1 for row in sample_list.get_json()))
        sample_status = self.client.post(
            f"/api/samples/{sample_id}/status",
            headers=self.auth_headers(tech),
            json={"status": "shipped", "trackingNumber": "TRACK-001"},
        )
        self.assertEqual(sample_status.status_code, 200)
        sample_events = self.client.get(f"/api/samples/{sample_id}/events", headers=self.auth_headers(tech))
        self.assertEqual(sample_events.status_code, 200)
        self.assertGreaterEqual(len(sample_events.get_json()), 2)
        genotype_history_before = self.client.get(f"/api/animals/{sire_id}/genotypes", headers=self.auth_headers(tech))
        self.assertEqual(genotype_history_before.status_code, 200)
        self.assertEqual(genotype_history_before.get_json(), [])

        order = self.client.post(
            "/api/genotyping/orders",
            headers=self.auth_headers(tech),
            json={"provider": "Transnetyx", "sampleIds": [sample_id], "markerPanel": "Cre Panel"},
        )
        self.assertEqual(order.status_code, 201)
        order_id = order.get_json()["id"]
        order_ref = order.get_json()["orderRef"]
        order_detail = self.client.get(f"/api/genotyping/orders/{order_id}", headers=self.auth_headers(tech))
        self.assertEqual(order_detail.status_code, 200)
        self.assertEqual(order_detail.get_json()["order"]["order_ref"], order_ref)
        self.assertEqual(order_detail.get_json()["items"][0]["sample_code"], "SMP-001")
        submit = self.client.post(f"/api/genotyping/orders/{order_id}/submit", headers=self.auth_headers(tech))
        self.assertEqual(submit.status_code, 200)
        callback = self.client.post(
            "/api/genotyping/orders/callback",
            headers={"X-Provider-Token": "dev-callback-token"},
            json={"orderRef": order_ref, "status": "received", "results": [{"sampleCode": "SMP-001", "result": "fl/+", "markerPanel": "Cre Panel"}]},
        )
        self.assertEqual(callback.status_code, 200)
        self.assertEqual(callback.get_json()["updatedAnimals"], 1)
        genotype_history_after = self.client.get(f"/api/animals/{sire_id}/genotypes", headers=self.auth_headers(tech))
        self.assertEqual(genotype_history_after.status_code, 200)
        self.assertEqual(genotype_history_after.get_json()[0]["result"], "fl/+")
        animals = self.client.get("/api/animals?q=PAIR-SIRE-001", headers=self.auth_headers(tech))
        self.assertEqual(animals.status_code, 200)
        self.assertEqual(animals.get_json()[0]["genotype"], "fl/+")

        rec_gen = self.client.post("/api/recommendations/generate", headers=self.auth_headers(admin))
        self.assertEqual(rec_gen.status_code, 200)
        recs = self.client.get("/api/recommendations?status=open", headers=self.auth_headers(admin))
        self.assertEqual(recs.status_code, 200)
        self.assertTrue(recs.get_json())
        rec_id = recs.get_json()[0]["id"]
        rec_decision = self.client.post(
            f"/api/recommendations/{rec_id}/decision",
            headers=self.auth_headers(admin),
            json={"decision": "adjusted", "adjustment": {"targetRoom": "Room A1"}, "note": "move next week"},
        )
        self.assertEqual(rec_decision.status_code, 200)
        outcomes = self.client.get("/api/recommendations/outcomes", headers=self.auth_headers(admin))
        self.assertEqual(outcomes.status_code, 200)
        self.assertTrue(any(o["status"] == "adjusted" for o in outcomes.get_json()))

        scenario = self.client.post(
            "/api/planner/scenarios",
            headers=self.auth_headers(admin),
            json={"name": "Q2 demand", "labId": 1, "targetAnimals": 300, "maxNewCages": 20, "neededBy": "2026-09-01"},
        )
        self.assertEqual(scenario.status_code, 201)
        scenario_id = scenario.get_json()["id"]
        scenario_list = self.client.get("/api/planner/scenarios", headers=self.auth_headers(admin))
        self.assertEqual(scenario_list.status_code, 200)
        self.assertTrue(any(s["id"] == scenario_id for s in scenario_list.get_json()))
        eval_res = self.client.post(f"/api/planner/scenarios/{scenario_id}/evaluate", headers=self.auth_headers(admin))
        self.assertEqual(eval_res.status_code, 200)
        self.assertIn("projectedDeficit", eval_res.get_json())
        plans = self.client.get(f"/api/planner/scenarios/{scenario_id}/plans", headers=self.auth_headers(admin))
        self.assertEqual(plans.status_code, 200)
        self.assertTrue(plans.get_json())

        stream = self.client.get("/api/alerts/stream?once=1", headers=self.auth_headers(admin))
        self.assertEqual(stream.status_code, 200)
        self.assertIn("text/event-stream", stream.content_type)
        self.assertIn(b"event: alerts", stream.data)


if __name__ == "__main__":
    unittest.main()
