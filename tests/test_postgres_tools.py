from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import app as appmod
import postgres_export_bundle
import postgres_readiness_audit


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
        self.assertFalse(report["ok"])
        findings = {item["id"]: item for item in report["findings"]}
        self.assertGreater(findings["sqlite_driver"]["count"], 0)
        self.assertGreater(findings["autoincrement"]["count"], 0)
