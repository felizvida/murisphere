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
import json
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
        self.assertIn('data-tab="dashboard"', body)
        self.assertIn('data-tab="scan"', body)
        self.assertIn('id="scanBtn"', body)
        self.assertIn('id="printCardsBtn"', body)
        self.assertIn('id="plannerScenarioForm"', body)
        self.assertIn('id="sampleCreateForm"', body)
        self.assertIn('id="cohortInsights"', body)
        self.assertIn('href="/chat/"', body)

    def test_chat_route_serves_console_ui(self) -> None:
        redirect_res = self.client.get("/chat", follow_redirects=False)
        self.assertEqual(redirect_res.status_code, 308)
        self.assertEqual(redirect_res.headers["Location"], "/chat/")

        page = self.client.get("/chat/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn('id="chatForm"', body)
        self.assertIn('id="chatTranscript"', body)
        self.assertIn('id="dailyBriefingBtn"', body)
        self.assertIn('id="technicianChecklistBtn"', body)
        self.assertIn('id="managerChecklistBtn"', body)
        self.assertIn('id="clearConversationBtn"', body)
        self.assertIn('id="logoutBtn"', body)
        self.assertIn("/docs/first-principles-rethink", body)
        self.assertIn('href="/"', body)

    def test_learning_routes_serve_tutorial_assets(self) -> None:
        redirect_res = self.client.get("/learn", follow_redirects=False)
        self.assertEqual(redirect_res.status_code, 308)
        self.assertEqual(redirect_res.headers["Location"], "/learn/")

        page = self.client.get("/learn/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn("Murisphere Role-Based Tutorial", body)
        self.assertIn("Role 1: Technician", body)
        self.assertIn("Role 2: Facility Manager", body)
        self.assertIn("Role 3: Researcher / PI", body)
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

    def test_first_principles_rethink_route_serves_markdown(self) -> None:
        page = self.client.get("/docs/first-principles-rethink")
        self.assertEqual(page.status_code, 200)
        self.assertIn("text/markdown", page.content_type)
        body = page.data.decode("utf-8")
        self.assertIn("Two Active Product Lines", body)
        self.assertIn("Technician: What They Care About Daily", body)
        self.assertIn("Animal Facility Manager", body)

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
        self.assertIn("/?scanToken=${encodeURIComponent(token)}", body)
        self.assertIn("/chat/?scanToken=${encodeURIComponent(token)}", body)
        self.assertIn("/room/?scanToken=${encodeURIComponent(token)}", body)

    def test_room_mode_page_and_phone_pass_workflow(self) -> None:
        token = self.login("tech@murisphere.local", "tech1234")
        page = self.client.get("/room/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn("Room Mode", body)
        self.assertIn('id="startPassBtn"', body)
        self.assertIn("/static/room.js", body)

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            tech_id = conn.execute("SELECT id FROM users WHERE email = 'tech@murisphere.local'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO task_assignments (task_type, cage_id, due_on, assigned_to, status, created_by, created_at)
                VALUES ('wean', 1, ?, ?, 'pending', ?, ?)
                """,
                ((date.today() - timedelta(days=1)).isoformat(), tech_id, tech_id, now),
            )
            conn.execute(
                """
                INSERT INTO litters (cage_id, birth_date, litter_size, survived_count, weaned_on, created_at)
                VALUES (1, ?, 6, 5, NULL, ?)
                """,
                ((date.today() - timedelta(days=24)).isoformat(), now),
            )
            conn.commit()

        summary = self.client.get("/api/room-mode/summary", headers=self.auth_headers(token))
        self.assertEqual(summary.status_code, 200)
        summary_payload = summary.get_json()
        self.assertTrue(summary_payload["rooms"])
        self.assertEqual(summary_payload["selectedRoom"]["id"], 1)
        self.assertGreaterEqual(summary_payload["stats"]["queueCount"], 1)
        self.assertTrue(any(item["cageCode"] == "C-A1-001" for item in summary_payload["actionQueue"]))

        start = self.client.post(
            "/api/room-mode/pass/start",
            headers=self.auth_headers(token),
            json={"roomId": 1},
        )
        self.assertEqual(start.status_code, 201)
        pass_id = start.get_json()["id"]

        detail = self.client.get("/api/room-mode/cage/C-A1-001", headers=self.auth_headers(token))
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()
        self.assertEqual(detail_payload["cage"]["cageCode"], "C-A1-001")
        self.assertIn(detail_payload["tier"], {"ACTION", "STOP", "WATCH", "INFO"})
        self.assertTrue(detail_payload["primaryActions"])
        self.assertTrue(detail_payload["weaningDue"])

        scan = self.client.post(
            f"/api/room-mode/pass/{pass_id}/scan",
            headers=self.auth_headers(token),
            json={"code": "C-A1-001", "maleCount": 1, "femaleCount": 2, "breedingStatus": "Breeding"},
        )
        self.assertEqual(scan.status_code, 200)
        scan_payload = scan.get_json()
        self.assertFalse(scan_payload["outOfRoom"])
        self.assertEqual(scan_payload["summary"]["scannedCages"], 1)

        complete = self.client.post(
            f"/api/room-mode/pass/{pass_id}/complete",
            headers=self.auth_headers(token),
            json={"notes": "Room pass complete"},
        )
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.get_json()["summary"]["status"], "completed")

    def test_room_mode_frontend_contract(self) -> None:
        template = Path("templates/room.html").read_text(encoding="utf-8")
        script = Path("static/room.js").read_text(encoding="utf-8")
        combined = template + script
        for required in [
            'id="roomList"',
            'id="scanForm"',
            'id="actionQueue"',
            'id="cageDetail"',
            'id="completePassBtn"',
        ]:
            self.assertIn(required, combined)
        self.assertIn("/api/room-mode/summary", script)
        self.assertIn("/api/room-mode/pass/start", script)
        self.assertIn("/api/room-mode/cage/", script)

    def test_frontend_handles_session_expiry_contract(self) -> None:
        workspace_js = Path("static/app.js").read_text(encoding="utf-8")
        chat_js = Path("static/chat.js").read_text(encoding="utf-8")
        self.assertIn("function handleSessionExpired(", workspace_js)
        self.assertIn("function handleBackgroundError(", workspace_js)
        self.assertIn('await api("/api/auth/me"', workspace_js)
        self.assertIn("handleSessionExpired();", workspace_js)
        self.assertIn("function handleSessionExpired(", chat_js)
        self.assertIn("err.status = res.status", chat_js)
        self.assertIn("if (err && Number(err.status) === 401)", chat_js)
        self.assertIn('await api("/api/auth/me"', chat_js)
        self.assertIn("handleSessionExpired();", chat_js)

    def test_frontend_chat_contract(self) -> None:
        js = Path("static/chat.js").read_text(encoding="utf-8")
        self.assertIn('api("/api/chat"', js)
        self.assertIn('el("chatForm").addEventListener("submit"', js)
        self.assertIn('el("dailyBriefingBtn").addEventListener("click"', js)
        self.assertIn('el("technicianChecklistBtn").addEventListener("click"', js)
        self.assertIn('el("managerChecklistBtn").addEventListener("click"', js)
        self.assertIn('el("clearConversationBtn").addEventListener("click"', js)
        self.assertIn('el("logoutBtn").addEventListener("click"', js)
        self.assertIn("function rememberPendingScanFromUrl()", js)
        self.assertIn("function consumePendingScan()", js)
        self.assertIn("data-chat-prompt", js)
        self.assertIn("function appendAssistantReply(", js)
        self.assertIn("function renderCard(", js)
        self.assertIn('await api("/api/auth/me"', js)
        self.assertIn('await sendChat(`Open cage ${pendingScan}`', js)

    def test_frontend_workspace_contract(self) -> None:
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("function activateTab(", js)
        self.assertIn('el("plannerScenarioForm").addEventListener("submit"', js)
        self.assertIn('el("downloadProviderTemplateBtn").addEventListener("click"', js)
        self.assertIn('await openPendingScanIfAny()', js)
        self.assertIn('loadActiveAlertFeed().catch((err) => handleBackgroundError(err, "Background alert refresh failed"))', js)

    def test_chat_api_supports_daily_brief_and_write_workflow(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")
        cages = self.client.get("/api/cages", headers=self.auth_headers(token)).get_json()
        cage_code = cages[0]["cageCode"]

        welcome = self.client.post("/api/chat", headers=self.auth_headers(token), json={"message": ""})
        self.assertEqual(welcome.status_code, 200)
        welcome_payload = welcome.get_json()
        self.assertEqual(welcome_payload["intent"], "welcome")
        self.assertTrue(welcome_payload["cards"])
        self.assertIn("First-principles rethink", json.dumps(welcome_payload))

        brief = self.client.post("/api/chat", headers=self.auth_headers(token), json={"message": "What needs attention today?"})
        self.assertEqual(brief.status_code, 200)
        brief_payload = brief.get_json()
        self.assertEqual(brief_payload["intent"], "today")
        self.assertTrue(any(card["kind"] == "stats" for card in brief_payload["cards"]))

        cage = self.client.post("/api/chat", headers=self.auth_headers(token), json={"message": f"Open cage {cage_code}"})
        self.assertEqual(cage.status_code, 200)
        cage_payload = cage.get_json()
        self.assertEqual(cage_payload["intent"], "cage_detail")
        self.assertTrue(any(card["kind"] == "cage" for card in cage_payload["cards"]))

        update = self.client.post(
            "/api/chat",
            headers=self.auth_headers(token),
            json={"message": f"Update cage {cage_code} males=2 females=3 status=Holding note=chat updated"},
        )
        self.assertEqual(update.status_code, 200)
        update_payload = update.get_json()
        self.assertEqual(update_payload["intent"], "cage_updated")

        detail = self.client.get(f"/api/scan/{cage_code}", headers=self.auth_headers(token))
        self.assertEqual(detail.status_code, 200)
        cage_after = detail.get_json()["cage"]
        self.assertEqual(cage_after["maleCount"], 2)
        self.assertEqual(cage_after["femaleCount"], 3)
        self.assertEqual(cage_after["breedingStatus"], "Holding")

        note = self.client.post(
            "/api/chat",
            headers=self.auth_headers(token),
            json={"message": f"Note cage {cage_code}: observed stable nesting"},
        )
        self.assertEqual(note.status_code, 200)
        self.assertEqual(note.get_json()["intent"], "cage_note_saved")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            row = conn.execute(
                "SELECT text FROM notes WHERE entity_type = 'cage' AND entity_id = (SELECT id FROM cages WHERE cage_code = ?) ORDER BY id DESC LIMIT 1",
                (cage_code,),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "observed stable nesting")

    def test_chat_can_prepare_printable_cage_card(self) -> None:
        token = self.login("tech@murisphere.local", "tech1234")
        cages = self.client.get("/api/cages", headers=self.auth_headers(token))
        self.assertEqual(cages.status_code, 200)
        cage_payload = cages.get_json()
        self.assertTrue(cage_payload)
        cage = cage_payload[0]
        cage_code = cage["cageCode"]
        cage_id = cage["id"]

        print_reply = self.client.post(
            "/api/chat",
            headers=self.auth_headers(token),
            json={"message": f"Print cage card for {cage_code}"},
        )
        self.assertEqual(print_reply.status_code, 200)
        payload = print_reply.get_json()
        self.assertEqual(payload["intent"], "print_card")
        payload_json = json.dumps(payload)
        self.assertIn("Open print view", payload_json)
        self.assertIn(f"/print/cards?ids={cage_id}", payload_json)

        print_page = self.client.get(f"/print/cards?ids={cage_id}", headers=self.auth_headers(token))
        self.assertEqual(print_page.status_code, 200)
        body = print_page.data.decode("utf-8")
        self.assertIn("window.print()", body)
        self.assertIn("/api/assets/qrcode.png?v=", body)
        self.assertIn(f"Cage {cage_code}", body)

    def test_chat_supports_genotype_ready_and_stalled_handoff_prompts(self) -> None:
        token = self.login("pi@murisphere.local", "pi1234")

        ready = self.client.post(
            "/api/chat",
            headers=self.auth_headers(token),
            json={"message": "Show genotype-ready animals"},
        )
        self.assertEqual(ready.status_code, 200)
        ready_payload = ready.get_json()
        self.assertEqual(ready_payload["intent"], "genotype_ready")
        self.assertTrue(any(card["kind"] == "stats" for card in ready_payload["cards"]))
        self.assertTrue(any(card["title"] == "Project readiness" for card in ready_payload["cards"]))

        stalled = self.client.post(
            "/api/chat",
            headers=self.auth_headers(token),
            json={"message": "Show stalled cohort handoffs"},
        )
        self.assertEqual(stalled.status_code, 200)
        stalled_payload = stalled.get_json()
        self.assertEqual(stalled_payload["intent"], "stalled_handoffs")
        self.assertTrue(any(card["kind"] == "stats" for card in stalled_payload["cards"]))
        self.assertTrue(any(card["title"] == "Stalled handoffs" for card in stalled_payload["cards"]))

    def test_chat_supports_first_principles_role_workflows(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                """
                INSERT INTO litters (cage_id, birth_date, litter_size, survived_count, weaned_on, created_at)
                VALUES (1, ?, 6, 5, NULL, ?)
                """,
                ((date.today() - timedelta(days=24)).isoformat(), now),
            )
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES ('CHAT-RESERVE-001', 'M', ?, 'C57BL/6J', 'Cre/+', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                (date.today().isoformat(), now, now),
            )
            animal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        project = self.client.post(
            "/api/projects",
            headers=self.auth_headers(admin),
            json={"labId": 1, "projectCode": "PRJ-CHAT-001", "title": "Chat Reservation", "status": "active", "targetAnimals": 1},
        )
        self.assertEqual(project.status_code, 201)

        request_res = self.client.post(
            "/api/requests",
            headers=self.auth_headers(admin),
            json={"labId": 1, "requestType": "room_support", "details": {"room": "Room A1"}},
        )
        self.assertEqual(request_res.status_code, 201)
        stale_request_time = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        with sqlite3.connect(appmod.DB_PATH) as conn:
            conn.execute(
                "UPDATE facility_requests SET created_at = ?, updated_at = ? WHERE id = ?",
                (stale_request_time, stale_request_time, request_res.get_json()["id"]),
            )
            conn.commit()

        sample = self.client.post(
            "/api/samples",
            headers=self.auth_headers(tech),
            json={"animalId": animal_id, "sampleType": "ear", "sampleCode": "CHAT-SMP-001", "provider": "Transnetyx", "status": "resulted"},
        )
        self.assertEqual(sample.status_code, 201)

        mortality = self.client.post(
            "/api/cages/1/mortality",
            headers=self.auth_headers(admin),
            json={"male": 1, "female": 0, "cause": "found dead", "necropsyRequired": True},
        )
        self.assertEqual(mortality.status_code, 201)

        cages = self.client.get("/api/cages", headers=self.auth_headers(admin)).get_json()
        room_name = cages[0]["room"]

        prompt_expectations = [
            (tech, "What needs weaning this week?", "weaning_queue"),
            (admin, "Show mortality follow-up", "mortality_followup"),
            (admin, f"Generate cage cards for {room_name}", "print_room_cards"),
            (admin, "Which labs are above expected load?", "load_pressure"),
            (admin, "What requests breached SLA?", "request_sla"),
            (tech, "Show recent sample results", "sample_results"),
            (admin, "Generate a project closeout report", "project_closeout_report"),
            (admin, "Reserve 1 matching animal for project PRJ-CHAT-001", "reserve_matching"),
        ]
        for token, prompt, intent in prompt_expectations:
            with self.subTest(prompt=prompt):
                res = self.client.post("/api/chat", headers=self.auth_headers(token), json={"message": prompt})
                self.assertEqual(res.status_code, 200)
                payload = res.get_json()
                self.assertEqual(payload["intent"], intent)
                self.assertTrue(payload["cards"])

        assignments = self.client.get(f"/api/projects/{project.get_json()['id']}/assignments", headers=self.auth_headers(tech))
        self.assertEqual(assignments.status_code, 200)
        self.assertTrue(any(row["animal_code"] == "CHAT-RESERVE-001" for row in assignments.get_json()))

    def test_cage_card_batch_order_is_preserved(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")
        cages = self.client.get("/api/cages", headers=self.auth_headers(token)).get_json()
        ordered_ids = [cages[1]["id"], cages[0]["id"]]
        cards = self.client.post("/api/cages/cards", headers=self.auth_headers(token), json={"ids": ordered_ids})
        self.assertEqual(cards.status_code, 200)
        payload = cards.get_json()
        self.assertEqual([card["cageId"] for card in payload], ordered_ids)

    def test_cage_card_endpoints_reject_invalid_ids(self) -> None:
        token = self.login("admin@murisphere.local", "admin1234")

        bad_json = self.client.post("/api/cages/cards", headers=self.auth_headers(token), json={"ids": ["abc"]})
        self.assertEqual(bad_json.status_code, 400)
        self.assertIn("Cage IDs must be integers", bad_json.get_json()["error"])

        bad_print = self.client.get("/print/cards?ids=1,abc", headers=self.auth_headers(token))
        self.assertEqual(bad_print.status_code, 400)
        self.assertIn("Cage IDs must be integers", bad_print.get_json()["error"])

    def test_chat_api_respects_role_scope_for_facility_views(self) -> None:
        tech = self.login("tech@murisphere.local", "tech1234")
        tech_res = self.client.post("/api/chat", headers=self.auth_headers(tech), json={"message": "Show room utilization"})
        self.assertEqual(tech_res.status_code, 200)
        self.assertEqual(tech_res.get_json()["intent"], "facility_forbidden")

        admin = self.login("admin@murisphere.local", "admin1234")
        admin_res = self.client.post("/api/chat", headers=self.auth_headers(admin), json={"message": "Show room utilization"})
        self.assertEqual(admin_res.status_code, 200)
        payload = admin_res.get_json()
        self.assertEqual(payload["intent"], "facility")
        self.assertTrue(any(card["kind"] == "table" for card in payload["cards"]))

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
        analytics_payload = analytics.get_json()
        self.assertGreaterEqual(analytics_payload["totalCages"], 2)
        self.assertIn("cohortFlow", analytics_payload)
        self.assertIn("cohortLabs", analytics_payload)
        self.assertIn("cohortCompletion", analytics_payload)
        self.assertIn("stalledCohortAssignments", analytics_payload)
        self.assertIn("repeatBreachProjects", analytics_payload)
        self.assertIn("cohortCloseouts", analytics_payload)

        handoffs = self.client.get("/api/analytics/cohort-handoffs", headers=self.auth_headers(token))
        self.assertEqual(handoffs.status_code, 200)
        handoff_payload = handoffs.get_json()
        self.assertIn("taxonomy", handoff_payload)
        self.assertIn("stalledAgeBuckets", handoff_payload)
        self.assertIn("recentCloseouts", handoff_payload)
        self.assertIn("repeatBreachProjects", handoff_payload)

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

        closeout_csv = self.client.get("/api/reports/cohort-closeouts.csv", headers=self.auth_headers(token))
        self.assertEqual(closeout_csv.status_code, 200)
        self.assertIn("text/csv", closeout_csv.content_type)

        closeout_pdf = self.client.get("/api/reports/cohort-closeouts.pdf", headers=self.auth_headers(token))
        self.assertEqual(closeout_pdf.status_code, 200)
        self.assertIn("application/pdf", closeout_pdf.content_type)
        self.assertTrue(closeout_pdf.data.startswith(b"%PDF-"))

        stalled_csv = self.client.get("/api/reports/stalled-handoffs.csv", headers=self.auth_headers(token))
        self.assertEqual(stalled_csv.status_code, 200)
        self.assertIn("text/csv", stalled_csv.content_type)

        stalled_pdf = self.client.get("/api/reports/stalled-handoffs.pdf", headers=self.auth_headers(token))
        self.assertEqual(stalled_pdf.status_code, 200)
        self.assertIn("application/pdf", stalled_pdf.content_type)
        self.assertTrue(stalled_pdf.data.startswith(b"%PDF-"))

        cookie_closeout_csv = self.client.get("/api/reports/cohort-closeouts.csv")
        self.assertEqual(cookie_closeout_csv.status_code, 200)
        self.assertIn("text/csv", cookie_closeout_csv.content_type)

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

    def test_protocol_alerts_are_lab_scoped(self) -> None:
        tech = self.login("tech@murisphere.local", "tech1234")
        admin = self.login("admin@murisphere.local", "admin1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, ?, ?)",
                ("Scoped Protocol Lab", "Dr. Scoped", 1, now),
            )
            other_lab_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO iacuc_protocols (protocol_number, title, lab_id, expires_on, created_at) VALUES (?, ?, ?, ?, ?)",
                ("IACUC-OTHER-001", "Other Lab Protocol", other_lab_id, "2020-01-01", now),
            )
            conn.commit()

        tech_alerts = self.client.get("/api/compliance/protocol-alerts", headers=self.auth_headers(tech))
        self.assertEqual(tech_alerts.status_code, 200)
        tech_numbers = {row["protocol_number"] for row in tech_alerts.get_json()}
        self.assertNotIn("IACUC-OTHER-001", tech_numbers)

        admin_alerts = self.client.get("/api/compliance/protocol-alerts", headers=self.auth_headers(admin))
        self.assertEqual(admin_alerts.status_code, 200)
        admin_numbers = {row["protocol_number"] for row in admin_alerts.get_json()}
        self.assertIn("IACUC-OTHER-001", admin_numbers)

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

    def test_pending_scan_storage_contract(self) -> None:
        workspace_src = Path("static/app.js").read_text(encoding="utf-8")
        chat_src = Path("static/chat.js").read_text(encoding="utf-8")
        self.assertIn('const PENDING_SCAN_KEY = "murisphere_pending_scan"', workspace_src)
        self.assertIn("function readPendingScanToken()", workspace_src)
        self.assertIn("async function openPendingScanIfAny()", workspace_src)
        self.assertIn("localStorage.setItem(PENDING_SCAN_KEY, fromUrl)", workspace_src)
        self.assertIn('params.delete("scanToken")', workspace_src)
        self.assertIn("window.history.replaceState({}, \"\", nextUrl)", workspace_src)
        self.assertIn('const PENDING_SCAN_KEY = "murisphere_pending_scan"', chat_src)
        self.assertIn("function rememberPendingScanFromUrl()", chat_src)
        self.assertIn("function consumePendingScan()", chat_src)
        self.assertIn("localStorage.setItem(PENDING_SCAN_KEY, scanToken)", chat_src)

    def test_chat_panels_present_in_ui(self) -> None:
        page = self.client.get("/chat/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertIn('id="chatTranscript"', body)
        self.assertIn('id="quickPromptStrip"', body)
        self.assertIn('id="chatForm"', body)
        self.assertIn('id="sendChatBtn"', body)
        self.assertIn('id="managerChecklistBtn"', body)
        self.assertIn('id="dailyBriefingBtn"', body)

        js = Path("static/chat.js").read_text(encoding="utf-8")
        self.assertIn("function renderCard(", js)
        self.assertIn("function appendAssistantReply(", js)
        self.assertIn("function updatePromptStrip(", js)

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

    def test_genotyping_dashboard_provider_template_and_csv_import(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'WT/WT', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("IMPORT-SIRE-001", date.today().isoformat(), now, now),
            )
            sire_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        sample = self.client.post(
            "/api/samples",
            headers=self.auth_headers(tech),
            json={"animalId": sire_id, "sampleType": "tail", "sampleCode": "SMP-IMPORT-001", "provider": "Transnetyx"},
        )
        self.assertEqual(sample.status_code, 201)
        sample_id = sample.get_json()["id"]

        order = self.client.post(
            "/api/genotyping/orders",
            headers=self.auth_headers(tech),
            json={"provider": "Transnetyx", "sampleIds": [sample_id], "markerPanel": "Cre Panel"},
        )
        self.assertEqual(order.status_code, 201)
        order_id = order.get_json()["id"]
        order_ref = order.get_json()["orderRef"]

        template = self.client.get(f"/api/genotyping/orders/{order_id}/provider-template.csv", headers=self.auth_headers(tech))
        self.assertEqual(template.status_code, 200)
        self.assertIn("text/csv", template.content_type)
        self.assertIn(order_ref, template.data.decode("utf-8"))
        self.assertIn("SMP-IMPORT-001", template.data.decode("utf-8"))

        import_res = self.client.post(
            f"/api/genotyping/orders/{order_id}/import-results",
            headers=self.auth_headers(admin),
            data={
                "status": "closed",
                "file": (
                    io.BytesIO(b"sample_code,result,marker_panel\nSMP-IMPORT-001,Cre/+,Cre Panel\n"),
                    "provider_results.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(import_res.status_code, 200)
        self.assertEqual(import_res.get_json()["updatedAnimals"], 1)

        detail = self.client.get(f"/api/genotyping/orders/{order_id}", headers=self.auth_headers(tech))
        self.assertEqual(detail.status_code, 200)
        payload = detail.get_json()
        self.assertEqual(payload["order"]["status"], "closed")
        self.assertEqual(payload["items"][0]["result"], "Cre/+")
        self.assertEqual(payload["items"][0]["sample_status"], "resulted")
        self.assertEqual(payload["reconciliation"]["summary"]["completionPct"], 100.0)
        self.assertEqual(payload["reconciliation"]["summary"]["resultedItems"], 1)

        reconciliation = self.client.get(f"/api/genotyping/orders/{order_id}/reconciliation", headers=self.auth_headers(tech))
        self.assertEqual(reconciliation.status_code, 200)
        self.assertEqual(reconciliation.get_json()["items"][0]["workflowState"], "resulted")

        sample_events = self.client.get(f"/api/samples/{sample_id}/events", headers=self.auth_headers(tech))
        self.assertEqual(sample_events.status_code, 200)
        self.assertTrue(any(event["event_type"] == "resulted" for event in sample_events.get_json()))

        genotype_history = self.client.get(f"/api/animals/{sire_id}/genotypes", headers=self.auth_headers(tech))
        self.assertEqual(genotype_history.status_code, 200)
        self.assertEqual(genotype_history.get_json()[0]["result"], "Cre/+")

        dashboard = self.client.get("/api/genotyping/dashboard", headers=self.auth_headers(tech))
        self.assertEqual(dashboard.status_code, 200)
        dashboard_payload = dashboard.get_json()
        self.assertTrue(any(row["label"] == "resulted" and row["value"] >= 1 for row in dashboard_payload["sampleStatus"]))
        self.assertTrue(any(row["label"] == "closed" and row["value"] >= 1 for row in dashboard_payload["orderStatus"]))
        self.assertTrue(any(row["provider"] == "Transnetyx" for row in dashboard_payload["providers"]))

    def test_provider_presets_and_cohort_assignment_views(self) -> None:
        admin = self.login("admin@murisphere.local", "admin1234")
        tech = self.login("tech@murisphere.local", "tech1234")

        project = self.client.post(
            "/api/projects",
            headers=self.auth_headers(admin),
            json={"labId": 1, "projectCode": "PRJ-GENO-001", "title": "Cohort Assignment", "status": "active", "targetAnimals": 6},
        )
        self.assertEqual(project.status_code, 201)
        project_id = project.get_json()["id"]

        assigned = self.client.post(
            f"/api/projects/{project_id}/assign-cages",
            headers=self.auth_headers(admin),
            json={"cageIds": [1]},
        )
        self.assertEqual(assigned.status_code, 200)

        template_create = self.client.post(
            "/api/genotyping/target-templates",
            headers=self.auth_headers(admin),
            json={
                "labId": 1,
                "name": "Cre Expansion",
                "description": "Reusable Cre-positive cohort template",
                "targets": [{"genotypePattern": "Cre/+", "targetCount": 3, "priority": 1}],
            },
        )
        self.assertEqual(template_create.status_code, 201)
        template_id = template_create.get_json()["id"]

        templates = self.client.get("/api/genotyping/target-templates", headers=self.auth_headers(tech))
        self.assertEqual(templates.status_code, 200)
        template_payload = templates.get_json()
        self.assertTrue(any(row["source"] == "preset" and row["presetKey"] == "balanced-pilot" for row in template_payload))
        self.assertTrue(any(row["source"] == "custom" and row["id"] == template_id for row in template_payload))

        targets = self.client.post(
            f"/api/projects/{project_id}/apply-target-template",
            headers=self.auth_headers(admin),
            json={"templateId": template_id},
        )
        self.assertEqual(targets.status_code, 200)
        listed_targets = self.client.get(f"/api/projects/{project_id}/genotype-targets", headers=self.auth_headers(tech))
        self.assertEqual(listed_targets.status_code, 200)
        self.assertEqual(listed_targets.get_json()[0]["genotype_pattern"], "Cre/+")

        preset_project = self.client.post(
            "/api/projects",
            headers=self.auth_headers(admin),
            json={"labId": 1, "projectCode": "PRJ-TPL-002", "title": "Template Applied", "status": "active", "targetAnimals": 0},
        )
        self.assertEqual(preset_project.status_code, 201)
        preset_project_id = preset_project.get_json()["id"]
        preset_apply = self.client.post(
            f"/api/projects/{preset_project_id}/apply-target-template",
            headers=self.auth_headers(admin),
            json={"presetKey": "balanced-pilot"},
        )
        self.assertEqual(preset_apply.status_code, 200)
        preset_targets = self.client.get(f"/api/projects/{preset_project_id}/genotype-targets", headers=self.auth_headers(tech))
        self.assertEqual(preset_targets.status_code, 200)
        self.assertEqual(len(preset_targets.get_json()), 2)

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute("UPDATE cages SET male_count = 1, female_count = 1 WHERE id = 1")
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'Cre/+', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("COHORT-SIRE-001", date.today().isoformat(), now, now),
            )
            sire_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'F', ?, 'C57BL/6J', 'fl/+', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("COHORT-DAM-001", date.today().isoformat(), now, now),
            )
            dam_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        pair = self.client.post(
            "/api/breeding/pairs",
            headers=self.auth_headers(tech),
            json={"sireId": sire_id, "damId": dam_id, "cageId": 1, "notes": "cohort planning pair"},
        )
        self.assertEqual(pair.status_code, 201)

        providers = self.client.get("/api/genotyping/providers", headers=self.auth_headers(tech))
        self.assertEqual(providers.status_code, 200)
        provider_payload = providers.get_json()
        self.assertTrue(any(row["name"] == "Charles River" for row in provider_payload))
        self.assertTrue(any("tube_id" in row["exportColumns"] for row in provider_payload if row["name"] == "Charles River"))

        sample = self.client.post(
            "/api/samples",
            headers=self.auth_headers(tech),
            json={"animalId": sire_id, "sampleType": "ear", "sampleCode": "CR-TUBE-001", "provider": "Charles River"},
        )
        self.assertEqual(sample.status_code, 201)
        sample_id = sample.get_json()["id"]

        order = self.client.post(
            "/api/genotyping/orders",
            headers=self.auth_headers(tech),
            json={"provider": "Charles River", "projectId": project_id, "sampleIds": [sample_id], "markerPanel": "Mouse Line Verification"},
        )
        self.assertEqual(order.status_code, 201)
        order_id = order.get_json()["id"]

        template = self.client.get(f"/api/genotyping/orders/{order_id}/provider-template.csv", headers=self.auth_headers(tech))
        self.assertEqual(template.status_code, 200)
        template_text = template.data.decode("utf-8")
        self.assertIn("tube_id", template_text.splitlines()[0])
        self.assertIn("panel_name", template_text.splitlines()[0])
        self.assertIn("CR-TUBE-001", template_text)

        import_res = self.client.post(
            f"/api/genotyping/orders/{order_id}/import-results",
            headers=self.auth_headers(admin),
            data={
                "status": "received",
                "file": (
                    io.BytesIO(b"tube_id,result,panel_name\nCR-TUBE-001,Cre/+,Mouse Line Verification\n"),
                    "charles_river_results.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(import_res.status_code, 200)
        self.assertEqual(import_res.get_json()["updatedAnimals"], 1)

        reserve = self.client.post(
            f"/api/projects/{project_id}/reserve-animals",
            headers=self.auth_headers(admin),
            json={"animalIds": [sire_id]},
        )
        self.assertEqual(reserve.status_code, 200)
        self.assertEqual(reserve.get_json()["reserved"], 1)
        mismatch = self.client.post(
            f"/api/projects/{project_id}/reserve-animals",
            headers=self.auth_headers(admin),
            json={"animalIds": [dam_id]},
        )
        self.assertEqual(mismatch.status_code, 200)
        self.assertEqual(mismatch.get_json()["reserved"], 0)
        self.assertEqual(mismatch.get_json()["conflicts"][0]["reason"], "target_mismatch")
        assignments = self.client.get(f"/api/projects/{project_id}/assignments", headers=self.auth_headers(tech))
        self.assertEqual(assignments.status_code, 200)
        self.assertEqual(assignments.get_json()[0]["animal_code"], "COHORT-SIRE-001")

        status_update = self.client.post(
            f"/api/projects/{project_id}/assignment-status",
            headers=self.auth_headers(admin),
            json={"animalIds": [sire_id], "status": "assigned"},
        )
        self.assertEqual(status_update.status_code, 200)
        self.assertEqual(status_update.get_json()["updated"], 1)

        default_sla = self.client.get(f"/api/projects/{project_id}/handoff-sla", headers=self.auth_headers(tech))
        self.assertEqual(default_sla.status_code, 200)
        self.assertEqual(default_sla.get_json()["assignedMaxDays"], 2)
        self.assertEqual(default_sla.get_json()["source"], "default")

        custom_sla = self.client.put(
            f"/api/projects/{project_id}/handoff-sla",
            headers=self.auth_headers(admin),
            json={"assignedMaxDays": 3, "shippedMaxDays": 2, "repeatBreachThreshold": 1},
        )
        self.assertEqual(custom_sla.status_code, 200)
        self.assertEqual(custom_sla.get_json()["assignedMaxDays"], 3)
        self.assertEqual(custom_sla.get_json()["repeatBreachThreshold"], 1)
        self.assertEqual(custom_sla.get_json()["source"], "custom")

        second_sla = self.client.put(
            f"/api/projects/{project_id}/handoff-sla",
            headers=self.auth_headers(admin),
            json={"assignedMaxDays": 3, "shippedMaxDays": 3, "repeatBreachThreshold": 1},
        )
        self.assertEqual(second_sla.status_code, 200)
        self.assertEqual(second_sla.get_json()["shippedMaxDays"], 3)
        with sqlite3.connect(appmod.DB_PATH) as conn:
            handoff_rows = conn.execute("SELECT COUNT(*) FROM project_handoff_slas WHERE project_id = ?", (project_id,)).fetchone()[0]
        self.assertEqual(handoff_rows, 1)

        timeline = self.client.get(f"/api/projects/{project_id}/assignment-timeline", headers=self.auth_headers(tech))
        self.assertEqual(timeline.status_code, 200)
        timeline_payload = timeline.get_json()
        self.assertEqual(timeline_payload["statusCounts"]["assigned"], 1)
        self.assertTrue(any(row["toStatus"] == "assigned" and row["animalCode"] == "COHORT-SIRE-001" for row in timeline_payload["events"]))
        self.assertEqual(timeline_payload["completion"]["completedAnimals"], 0)

        consumed_update = self.client.post(
            f"/api/projects/{project_id}/assignment-status",
            headers=self.auth_headers(admin),
            json={"animalIds": [sire_id], "status": "consumed"},
        )
        self.assertEqual(consumed_update.status_code, 200)
        self.assertEqual(consumed_update.get_json()["updated"], 1)

        consumed_timeline = self.client.get(f"/api/projects/{project_id}/assignment-timeline", headers=self.auth_headers(tech))
        self.assertEqual(consumed_timeline.status_code, 200)
        consumed_payload = consumed_timeline.get_json()
        self.assertEqual(consumed_payload["completion"]["completedAnimals"], 1)
        self.assertEqual(consumed_payload["completion"]["state"], "in_progress")
        self.assertTrue(any(row["key"] == "consumed" and row["value"] == 1 for row in consumed_payload["dispositionFlow"]))

        closeout = self.client.post(
            f"/api/projects/{project_id}/closeouts",
            headers=self.auth_headers(admin),
            json={
                "status": "partial",
                "outcomeCode": "partial_data",
                "completedAnimals": 1,
                "summary": "Pilot imaging cohort completed for the first subject.",
                "notes": "Initial microscopy run completed; waiting for second animal.",
            },
        )
        self.assertEqual(closeout.status_code, 201)
        closeout_id = closeout.get_json()["id"]
        closeout_attachment = self.client.post(
            "/api/attachments",
            headers=self.auth_headers(admin),
            data={
                "entityType": "project_closeout",
                "entityId": str(closeout_id),
                "file": (io.BytesIO(b"closeout attachment"), "closeout.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(closeout_attachment.status_code, 201)
        closeouts = self.client.get(f"/api/projects/{project_id}/closeouts", headers=self.auth_headers(tech))
        self.assertEqual(closeouts.status_code, 200)
        closeout_payload = closeouts.get_json()
        self.assertEqual(closeout_payload[0]["summary"], "Pilot imaging cohort completed for the first subject.")
        self.assertEqual(closeout_payload[0]["outcome_code"], "partial_data")
        self.assertEqual(closeout_payload[0]["outcome_label"], "Partial Data")
        self.assertEqual(closeout_payload[0]["attachment_count"], 1)
        self.assertEqual(closeout_payload[0]["attachments"][0]["filename"], "closeout.txt")
        filtered_closeouts = self.client.get(
            f"/api/projects/{project_id}/closeouts?outcomeCode=partial_data",
            headers=self.auth_headers(tech),
        )
        self.assertEqual(filtered_closeouts.status_code, 200)
        self.assertEqual(len(filtered_closeouts.get_json()), 1)
        filtered_empty = self.client.get(
            f"/api/projects/{project_id}/closeouts?outcomeCode=met_goal",
            headers=self.auth_headers(tech),
        )
        self.assertEqual(filtered_empty.status_code, 200)
        self.assertEqual(filtered_empty.get_json(), [])

        cohorts = self.client.get("/api/genotyping/cohorts", headers=self.auth_headers(tech))
        self.assertEqual(cohorts.status_code, 200)
        cohort_payload = cohorts.get_json()
        self.assertTrue(any(row["projectCode"] == "PRJ-GENO-001" and row["matchedReadyAnimals"] >= 1 for row in cohort_payload["projects"]))
        self.assertTrue(any(row["animalCode"] == "COHORT-SIRE-001" for row in cohort_payload["readyAnimals"]))
        project_row = next(row for row in cohort_payload["projects"] if row["projectCode"] == "PRJ-GENO-001")
        self.assertEqual(project_row["targetRules"][0]["genotypePattern"], "Cre/+")
        self.assertTrue(any(item["key"] == "consumed" and item["value"] >= 1 for item in project_row["statusFlow"]))
        self.assertTrue(cohort_payload["breederSignals"])
        self.assertIn("signal", cohort_payload["breederSignals"][0])

        release = self.client.post(
            f"/api/projects/{project_id}/release-animals",
            headers=self.auth_headers(admin),
            json={"animalIds": [sire_id]},
        )
        self.assertEqual(release.status_code, 200)
        self.assertEqual(release.get_json()["released"], 1)
        released_timeline = self.client.get(f"/api/projects/{project_id}/assignment-timeline", headers=self.auth_headers(tech))
        self.assertEqual(released_timeline.status_code, 200)
        self.assertGreaterEqual(released_timeline.get_json()["statusCounts"]["released"], 1)
        self.assertEqual(released_timeline.get_json()["completion"]["completedAnimals"], 1)

        with sqlite3.connect(appmod.DB_PATH) as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                """
                INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at)
                VALUES (?, 'M', ?, 'C57BL/6J', 'Cre/+', 'Active', 1, NULL, NULL, NULL, ?, ?)
                """,
                ("COHORT-STALLED-001", date.today().isoformat(), now, now),
            )
            stalled_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        reserve_stalled = self.client.post(
            f"/api/projects/{project_id}/reserve-animals",
            headers=self.auth_headers(admin),
            json={"animalIds": [stalled_id]},
        )
        self.assertEqual(reserve_stalled.status_code, 200)
        status_stalled = self.client.post(
            f"/api/projects/{project_id}/assignment-status",
            headers=self.auth_headers(admin),
            json={"animalIds": [stalled_id], "status": "assigned"},
        )
        self.assertEqual(status_stalled.status_code, 200)
        with sqlite3.connect(appmod.DB_PATH) as conn:
            aged = (datetime.now(UTC) - timedelta(days=4)).isoformat()
            conn.execute("UPDATE project_animal_assignments SET assigned_at = ? WHERE animal_id = ?", (aged, stalled_id))
            conn.commit()
        alert_feed = self.client.get("/api/alerts/feed?status=active", headers=self.auth_headers(admin))
        self.assertEqual(alert_feed.status_code, 200)
        stalled_alert = next(row for row in alert_feed.get_json() if row["category"] == "cohort" and "COHORT-STALLED-001" in row["message"])
        self.assertEqual(stalled_alert["severity"], "low")
        self.assertEqual(stalled_alert["meta"]["thresholdDays"], 3)
        self.assertEqual(stalled_alert["meta"]["overdueDays"], 1)
        repeat_alert = next(row for row in alert_feed.get_json() if row["title"] == "Project Handoff SLA Repeatedly Breached")
        self.assertEqual(repeat_alert["meta"]["projectCode"], "PRJ-GENO-001")
        self.assertEqual(repeat_alert["meta"]["repeatBreachThreshold"], 1)

        handoff_analytics = self.client.get("/api/analytics/cohort-handoffs?outcomeCode=partial_data", headers=self.auth_headers(admin))
        self.assertEqual(handoff_analytics.status_code, 200)
        analytics_payload = handoff_analytics.get_json()
        self.assertEqual(analytics_payload["recentCloseouts"][0]["outcomeCode"], "partial_data")
        self.assertTrue(any(row["label"] == "2-4d" and row["value"] >= 1 for row in analytics_payload["stalledAgeBuckets"]))
        self.assertTrue(any(row["labName"] == "Neurogenetics Lab" for row in analytics_payload["stalledByLab"]))
        self.assertTrue(any(row["projectCode"] == "PRJ-GENO-001" and row["breachCount"] >= 1 for row in analytics_payload["repeatBreachProjects"]))

        closeout_report = self.client.get(
            "/api/reports/cohort-closeouts.csv?outcomeCode=partial_data",
            headers=self.auth_headers(admin),
        )
        self.assertEqual(closeout_report.status_code, 200)
        closeout_report_text = closeout_report.data.decode("utf-8")
        self.assertIn("PRJ-GENO-001", closeout_report_text)
        self.assertIn("Partial Data", closeout_report_text)

        stalled_report = self.client.get("/api/reports/stalled-handoffs.csv", headers=self.auth_headers(admin))
        self.assertEqual(stalled_report.status_code, 200)
        stalled_report_text = stalled_report.data.decode("utf-8")
        self.assertIn("COHORT-STALLED-001", stalled_report_text)
        self.assertIn(",3,1,low,1,", stalled_report_text)


if __name__ == "__main__":
    unittest.main()
