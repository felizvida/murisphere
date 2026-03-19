from __future__ import annotations

import importlib
import os
import time
import unittest


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

        login = client.post("/api/auth/login", json={"email": "admin@murisphere.local", "password": "admin1234"})
        self.assertEqual(login.status_code, 200)
        token = login.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

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
        self.assertIn("projectCodes", card)
