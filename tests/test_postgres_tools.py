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

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import app as appmod
import generate_postgres_schema
import postgres_export_bundle
import postgres_readiness_audit
import storage
import storage_postgres
import storage_sqlite


class PostgresToolingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = appmod.DB_PATH
        self._old_attachment_dir = appmod.ATTACHMENT_DIR
        appmod.DB_PATH = f"{self._tmp.name}/test_murisphere.db"
        appmod.ATTACHMENT_DIR = Path(self._tmp.name) / "uploads"
        appmod.init_db()

    def tearDown(self) -> None:
        appmod.DB_PATH = self._old_db
        appmod.ATTACHMENT_DIR = self._old_attachment_dir
        self._tmp.cleanup()

    def test_postgres_export_bundle_writes_manifest_and_table_files(self) -> None:
        out_dir = Path(self._tmp.name) / "bundle"
        manifest = postgres_export_bundle.export_bundle(Path(appmod.DB_PATH), out_dir)

        self.assertEqual(manifest["sourceEngine"], "sqlite")
        self.assertEqual(manifest["targetEngine"], "postgresql")
        self.assertGreater(manifest["tableCount"], 0)
        self.assertTrue((out_dir / "manifest.json").exists())
        self.assertTrue((out_dir / "schema-sqlite.sql").exists())
        self.assertTrue((out_dir / "README.txt").exists())

        tables = {table["name"]: table for table in manifest["tables"]}
        self.assertIn("cages", tables)
        self.assertIn("users", tables)
        self.assertTrue((out_dir / tables["cages"]["file"]).exists())

        first_cage_line = (out_dir / tables["cages"]["file"]).read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("cage_code", json.loads(first_cage_line))

    def test_postgres_readiness_audit_flags_known_sqlite_patterns(self) -> None:
        report = postgres_readiness_audit.build_report()
        self.assertTrue(report["ok"])
        findings = {item["id"]: item for item in report["findings"]}
        self.assertEqual(findings["sqlite_driver"]["count"], 0)
        self.assertEqual(findings["autoincrement"]["count"], 0)
        self.assertEqual(findings["sqlite_schema_pragma"]["count"], 0)
        self.assertEqual(findings["insert_or_replace"]["count"], 0)

    def test_storage_helpers_generate_portable_sql_shapes(self) -> None:
        upsert_sql = storage.sql_upsert(
            "billing_reviews",
            ["period_start", "period_end", "lab_id", "review_status"],
            ["period_start", "period_end", "lab_id"],
            ["review_status"],
        )
        self.assertIn("ON CONFLICT", upsert_sql)
        self.assertNotIn("INSERT OR REPLACE", upsert_sql)
        self.assertIn("GROUP_CONCAT", storage_sqlite.sql_list_agg("pj.project_code"))

    def test_storage_translates_qmark_placeholders_for_postgres(self) -> None:
        translated = storage_postgres.translate_qmark_sql("SELECT * FROM cages WHERE cage_code = ? AND notes <> '?'")
        self.assertEqual(translated, "SELECT * FROM cages WHERE cage_code = %s AND notes <> '?'")

    def test_postgres_schema_generation_matches_committed_schema(self) -> None:
        source = Path("schema.sql").read_text(encoding="utf-8")
        committed = Path("schema_postgres.sql").read_text(encoding="utf-8")
        generated = generate_postgres_schema.translate_schema(source)
        self.assertEqual(committed, generated)
        self.assertNotIn("PRAGMA", committed)
        self.assertNotIn("AUTOINCREMENT", committed)
        self.assertIn("SERIAL PRIMARY KEY", committed)

    def test_postgres_connect_uses_psycopg_when_dialect_is_postgres(self) -> None:
        fake_cursor = mock.Mock()
        fake_cursor.fetchone.return_value = {"id": 41}
        fake_conn = mock.Mock()
        fake_conn.cursor.return_value = fake_cursor
        fake_psycopg = mock.Mock()
        fake_psycopg.connect.return_value = fake_conn

        with mock.patch.dict(os.environ, {"MURISPHERE_DB_DIALECT": "postgres"}, clear=False):
            with mock.patch.object(storage, "DATABASE_DIALECT", "postgres"):
                with mock.patch.object(storage_postgres, "psycopg", fake_psycopg):
                    with mock.patch.object(storage_postgres, "dict_row", object()):
                        conn = storage.connect("postgresql://demo")
                        cur = conn.execute("INSERT INTO cages (cage_code) VALUES (?)", ("C-1",))

        fake_psycopg.connect.assert_called_once()
        fake_cursor.execute.assert_called_once_with("INSERT INTO cages (cage_code) VALUES (%s) RETURNING id", ("C-1",))
        self.assertEqual(cur.lastrowid, 41)

    def test_split_sql_statements_ignores_semicolons_inside_comments(self) -> None:
        script = """/*
 * Licensed under the Apache License, Version 2.0 (the "License");
 */
-- Generated from schema.sql by generate_postgres_schema.py
CREATE TABLE demo (id SERIAL PRIMARY KEY);
INSERT INTO demo (id) VALUES (1);
"""
        statements = storage_postgres.split_sql_statements(script)
        self.assertEqual(
            statements,
            [
                """/*
 * Licensed under the Apache License, Version 2.0 (the "License");
 */
-- Generated from schema.sql by generate_postgres_schema.py
CREATE TABLE demo (id SERIAL PRIMARY KEY)""",
                "INSERT INTO demo (id) VALUES (1)",
            ],
        )

    def test_app_selects_postgres_schema_when_postgres_dialect_is_active(self) -> None:
        with mock.patch.object(storage, "DATABASE_DIALECT", "postgres"):
            self.assertEqual(appmod.schema_path(), "schema_postgres.sql")

    def test_project_handoff_sla_migration_sql_is_postgres_safe(self) -> None:
        class FakeConn:
            def __init__(self) -> None:
                self.executed: list[str] = []

            def execute(self, sql: str, _params=None):
                self.executed.append(sql)
                return mock.Mock()

            def executescript(self, script: str) -> None:
                self.executed.append(script)

        fake_conn = FakeConn()

        def fake_columns(_conn, table: str) -> list[str]:
            if table == "litters":
                return ["id", "weaned_on"]
            if table == "project_cohort_closeouts":
                return ["id", "outcome_code"]
            if table == "project_handoff_slas":
                return []
            return ["id"]

        with mock.patch.object(storage, "DATABASE_DIALECT", "postgres"):
            with mock.patch.object(appmod.storage, "table_columns", side_effect=fake_columns):
                appmod._apply_schema_migrations(fake_conn)

        executed_sql = "\n".join(fake_conn.executed)
        self.assertIn("CREATE TABLE IF NOT EXISTS project_handoff_slas", executed_sql)
        self.assertIn("SERIAL PRIMARY KEY", executed_sql)
        self.assertNotIn("AUTOINCREMENT", executed_sql)
