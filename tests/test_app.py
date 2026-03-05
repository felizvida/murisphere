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
        unauth = self.client.get("/api/auth/me")
        self.assertEqual(unauth.status_code, 401)

        token = self.login("admin@murisphere.local", "admin1234")
        me = self.client.get("/api/auth/me", headers=self.auth_headers(token))
        self.assertEqual(me.status_code, 200)
        payload = me.get_json()
        self.assertEqual(payload["email"], "admin@murisphere.local")
        self.assertEqual(payload["role"], "Admin")

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

        qr = self.client.get(f"/api/assets/qrcode.png?v=https://example.org{card['scanUrl']}")
        self.assertEqual(qr.status_code, 200)
        self.assertIn("image/png", qr.content_type)
        self.assertTrue(qr.data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(qr.data), 300)

        barcode = self.client.get(f"/api/assets/barcode.svg?v={card['cageCode']}")
        self.assertEqual(barcode.status_code, 200)
        self.assertIn("image/svg+xml", barcode.content_type)
        self.assertIn(b"<svg", barcode.data)

    def test_index_uses_local_card_rendering_assets(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode("utf-8")
        self.assertNotIn("cdn.jsdelivr.net/npm/qrcode", body)
        self.assertNotIn("cdn.jsdelivr.net/npm/jsbarcode", body)

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


if __name__ == "__main__":
    unittest.main()
