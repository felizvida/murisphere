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

import importlib
import os
import time
import unittest
from pathlib import Path

import storage_postgres


DB_URL = os.getenv("MURISPHERE_DATABASE_URL", "").strip()
DB_DIALECT = os.getenv("MURISPHERE_DB_DIALECT", "").strip().lower()

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:
    psycopg = None
    dict_row = None


@unittest.skipUnless(DB_DIALECT == "postgres" and DB_URL and psycopg is not None and dict_row is not None, "PostgreSQL integration env not configured")
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.appmod = importlib.import_module("app")
        cls.storage = importlib.import_module("storage")

    def setUp(self) -> None:
        deadline = time.time() + 15
        while True:
            try:
                with psycopg.connect(DB_URL, autocommit=True) as conn:
                    conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
                    conn.execute("CREATE SCHEMA public")
                return
            except psycopg.OperationalError:
                if time.time() >= deadline:
                    raise
                time.sleep(0.5)

    def auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def login(self, client, email: str, password: str) -> str:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["token"]

    def test_init_db_bootstraps_seed_data_on_postgres(self) -> None:
        self.appmod.init_db()
        with psycopg.connect(DB_URL, row_factory=dict_row) as conn:
            user_count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            cage_count = conn.execute("SELECT COUNT(*) AS n FROM cages").fetchone()["n"]
            tables = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN ('users', 'cages', 'labs')
                """
            ).fetchone()["n"]
        self.assertGreaterEqual(user_count, 3)
        self.assertGreaterEqual(cage_count, 2)
        self.assertEqual(tables, 3)

    def test_init_db_upgrades_legacy_postgres_schema_missing_handoff_sla_table(self) -> None:
        schema = Path("schema_postgres.sql").read_text(encoding="utf-8")
        handoff_block = """CREATE TABLE IF NOT EXISTS project_handoff_slas (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL UNIQUE,
    assigned_max_days INTEGER NOT NULL DEFAULT 2,
    shipped_max_days INTEGER NOT NULL DEFAULT 5,
    repeat_breach_threshold INTEGER NOT NULL DEFAULT 2,
    updated_by INTEGER,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(updated_by) REFERENCES users(id)
);

"""
        legacy_schema = schema.replace(handoff_block, "")
        legacy_schema = legacy_schema.replace(
            "CREATE INDEX IF NOT EXISTS idx_project_handoff_slas_project ON project_handoff_slas(project_id);\n",
            "",
        )

        with psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row) as conn:
            for statement in storage_postgres.split_sql_statements(legacy_schema):
                conn.execute(statement)
            before = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'project_handoff_slas'
                """
            ).fetchone()["n"]
        self.assertEqual(before, 0)

        self.appmod.init_db()

        with psycopg.connect(DB_URL, row_factory=dict_row) as conn:
            table_count = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'project_handoff_slas'
                """
            ).fetchone()["n"]
            column_rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'project_handoff_slas'
                ORDER BY ordinal_position
                """
            ).fetchall()
            user_count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        self.assertEqual(table_count, 1)
        self.assertGreaterEqual(user_count, 3)
        self.assertEqual(
            [row["column_name"] for row in column_rows],
            [
                "id",
                "project_id",
                "assigned_max_days",
                "shipped_max_days",
                "repeat_breach_threshold",
                "updated_by",
                "updated_at",
            ],
        )

        self.appmod.app.config.update(TESTING=True)
        client = self.appmod.app.test_client()
        admin = self.login(client, "admin@murisphere.local", "admin1234")
        project = client.post(
            "/api/projects",
            headers=self.auth_headers(admin),
            json={
                "projectCode": f"PG-UPGRADE-{int(time.time() * 1000)}",
                "title": "Postgres Upgrade Migration Project",
                "labId": 1,
                "status": "Active",
                "targetAnimals": 12,
            },
        )
        self.assertEqual(project.status_code, 201)
        project_id = project.get_json()["id"]
        update = client.put(
            f"/api/projects/{project_id}/handoff-sla",
            headers=self.auth_headers(admin),
            json={"assignedMaxDays": 3, "shippedMaxDays": 4, "repeatBreachThreshold": 2},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["assignedMaxDays"], 3)

    def test_storage_wrapper_supports_qmark_queries_and_lastrowid(self) -> None:
        self.appmod.init_db()
        conn = self.storage.connect(DB_URL)
        try:
            cur = conn.execute(
                "INSERT INTO notes (entity_type, entity_id, text, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                ("integration", "1", "postgres-bridge", 1, self.appmod.now_iso()),
            )
            note_id = cur.lastrowid
            row = conn.execute("SELECT id, text FROM notes WHERE id = ?", (note_id,)).fetchone()
        finally:
            conn.rollback()
            conn.close()
        self.assertIsInstance(note_id, int)
        self.assertGreater(note_id, 0)
        self.assertEqual(row["text"], "postgres-bridge")

    def test_auth_and_cage_listing_workflow_on_postgres(self) -> None:
        self.appmod.init_db()
        self.appmod.app.config.update(TESTING=True)
        client = self.appmod.app.test_client()

        token = self.login(client, "admin@murisphere.local", "admin1234")
        headers = self.auth_headers(token)

        health = client.get("/api/system/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["storage"], "postgres")

        cages = client.get("/api/cages", headers=headers)
        self.assertEqual(cages.status_code, 200)
        cage_rows = cages.get_json()
        self.assertGreaterEqual(len(cage_rows), 1)

        cards = client.post("/api/cages/cards", headers=headers, json={"ids": [cage_rows[0]["id"]]})
        self.assertEqual(cards.status_code, 200)
        card = cards.get_json()[0]
        self.assertIn("qrValue", card)
        self.assertIn("projects", card)

    def test_billing_and_chargeback_workflow_on_postgres(self) -> None:
        self.appmod.init_db()
        self.appmod.app.config.update(TESTING=True)
        client = self.appmod.app.test_client()

        admin = self.login(client, "admin@murisphere.local", "admin1234")
        pi = self.login(client, "pi@murisphere.local", "pi1234")

        create_rule = client.post(
            "/api/billing/rules",
            headers=self.auth_headers(admin),
            json={"labId": 1, "lineType": "per_diem", "rate": 1.35},
        )
        self.assertEqual(create_rule.status_code, 201)
        self.assertGreater(create_rule.get_json()["id"], 0)

        rules = client.get("/api/billing/rules", headers=self.auth_headers(pi))
        self.assertEqual(rules.status_code, 200)
        self.assertTrue(rules.get_json())

        chargeback = client.get(
            "/api/facility/chargeback?periodDays=30&ratePerCageDay=1.0",
            headers=self.auth_headers(admin),
        )
        self.assertEqual(chargeback.status_code, 200)
        self.assertTrue(any(row["estimatedCharge"] > 0 for row in chargeback.get_json()))

        run = client.post(
            "/api/billing/run",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(run.status_code, 200)
        self.assertGreater(run.get_json()["entriesUpserted"], 0)

        statements = client.get(
            "/api/billing/statements.csv?periodStart=2026-03-01&periodEnd=2026-03-31",
            headers=self.auth_headers(admin),
        )
        self.assertEqual(statements.status_code, 200)
        self.assertIn("text/csv", statements.content_type)
        self.assertIn("period_start", statements.get_data(as_text=True))

        close = client.post(
            "/api/billing/close-period",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.get_json()["status"], "closed")

        rerun = client.post(
            "/api/billing/run",
            headers=self.auth_headers(admin),
            json={"periodStart": "2026-03-01", "periodEnd": "2026-03-31"},
        )
        self.assertEqual(rerun.status_code, 409)

    def test_alert_dispatch_and_stream_workflow_on_postgres(self) -> None:
        self.appmod.init_db()
        self.appmod.app.config.update(TESTING=True)
        client = self.appmod.app.test_client()

        admin = self.login(client, "admin@murisphere.local", "admin1234")
        headers = self.auth_headers(admin)

        overdue_task = client.post(
            "/api/tasks/assign",
            headers=headers,
            json={"taskType": "plug_check", "cageId": 1, "dueOn": "2020-01-01", "assignedTo": 2},
        )
        self.assertEqual(overdue_task.status_code, 201)

        feed = client.get("/api/alerts/feed?status=active", headers=headers)
        self.assertEqual(feed.status_code, 200)
        alerts = feed.get_json()
        self.assertTrue(alerts)
        alert_id = alerts[0]["id"]

        ack = client.post(f"/api/alerts/{alert_id}/ack", headers=headers)
        self.assertEqual(ack.status_code, 200)

        acked = client.get("/api/alerts/feed?status=acknowledged", headers=headers)
        self.assertEqual(acked.status_code, 200)
        self.assertTrue(any(row["id"] == alert_id for row in acked.get_json()))

        channel = client.post(
            "/api/notifications/channels",
            headers=headers,
            json={"channelType": "in_app", "labId": 1, "minSeverity": "low"},
        )
        self.assertEqual(channel.status_code, 201)

        mortality = client.post(
            "/api/cages/1/mortality",
            headers=headers,
            json={"male": 1, "cause": "found dead", "necropsyRequired": True},
        )
        self.assertEqual(mortality.status_code, 201)

        dispatch = client.post("/api/alerts/dispatch", headers=headers)
        self.assertEqual(dispatch.status_code, 200)
        payload = dispatch.get_json()
        self.assertGreaterEqual(payload["alerts"], 1)
        self.assertGreaterEqual(payload["simulated"], 1)

        stream = client.get("/api/alerts/stream?once=1", headers=headers)
        self.assertEqual(stream.status_code, 200)
        self.assertIn("text/event-stream", stream.content_type)
        self.assertIn(b"event: alerts", stream.data)

    def test_planner_scenario_project_evaluation_workflow_on_postgres(self) -> None:
        self.appmod.init_db()
        self.appmod.app.config.update(TESTING=True)
        client = self.appmod.app.test_client()

        admin = self.login(client, "admin@murisphere.local", "admin1234")
        headers = self.auth_headers(admin)

        create_project = client.post(
            "/api/projects",
            headers=headers,
            json={
                "projectCode": f"PG-PLAN-{int(time.time() * 1000)}",
                "title": "Postgres Planner Validation Project",
                "labId": 1,
                "status": "Active",
                "targetAnimals": 320,
            },
        )
        self.assertEqual(create_project.status_code, 201)
        project_id = create_project.get_json()["id"]

        projects = client.get("/api/projects", headers=headers)
        self.assertEqual(projects.status_code, 200)
        project_rows = projects.get_json()
        self.assertTrue(any(row["id"] == project_id for row in project_rows))
        project = next(row for row in project_rows if row["id"] == project_id)

        scenario = client.post(
            "/api/planner/scenarios",
            headers=headers,
            json={
                "name": "Postgres demand plan",
                "labId": project["lab_id"],
                "targetAnimals": 300,
                "maxNewCages": 20,
                "neededBy": "2026-09-01",
            },
        )
        self.assertEqual(scenario.status_code, 201)
        scenario_id = scenario.get_json()["id"]

        add_projects = client.post(
            f"/api/planner/scenarios/{scenario_id}/projects",
            headers=headers,
            json={"projects": [{"projectId": project["id"], "animalsNeeded": 320, "priority": 1}]},
        )
        self.assertEqual(add_projects.status_code, 200)
        self.assertGreaterEqual(add_projects.get_json()["upserted"], 1)

        scenario_list = client.get("/api/planner/scenarios", headers=headers)
        self.assertEqual(scenario_list.status_code, 200)
        self.assertTrue(any(row["id"] == scenario_id for row in scenario_list.get_json()))

        evaluate = client.post(f"/api/planner/scenarios/{scenario_id}/evaluate", headers=headers)
        self.assertEqual(evaluate.status_code, 200)
        evaluation = evaluate.get_json()
        self.assertIn("projectedDeficit", evaluation)
        self.assertIn(evaluation["riskLevel"], {"low", "medium", "high"})

        plans = client.get(f"/api/planner/scenarios/{scenario_id}/plans", headers=headers)
        self.assertEqual(plans.status_code, 200)
        plan_rows = plans.get_json()
        self.assertTrue(plan_rows)
        self.assertEqual(plan_rows[0]["projected_deficit"], evaluation["projectedDeficit"])
