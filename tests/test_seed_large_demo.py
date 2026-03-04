from __future__ import annotations

import sqlite3
import tempfile
import unittest

import seed_large_demo as seed


class SeedLargeDemoTests(unittest.TestCase):
    def test_large_demo_seed_creates_expected_scale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/seed_demo.db"
            with open(db_path, "w", encoding="utf-8"):
                pass

            old_db = seed.DB_PATH
            seed.DB_PATH = db_path
            try:
                seed.main()
            finally:
                seed.DB_PATH = old_db

            conn = sqlite3.connect(db_path)
            labs = conn.execute("SELECT COUNT(*) FROM labs").fetchone()[0]
            cages = conn.execute("SELECT COUNT(*) FROM cages").fetchone()[0]
            projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

            proj_min, proj_max = conn.execute(
                "SELECT MIN(c), MAX(c) FROM (SELECT lab_id, COUNT(*) c FROM projects GROUP BY lab_id)"
            ).fetchone()
            cage_min, cage_max = conn.execute(
                "SELECT MIN(c), MAX(c) FROM (SELECT lab_id, COUNT(*) c FROM cages GROUP BY lab_id)"
            ).fetchone()
            tiers = dict(conn.execute("SELECT size_tier, COUNT(*) FROM lab_profiles GROUP BY size_tier").fetchall())
            conn.close()

            self.assertEqual(labs, 20)
            self.assertEqual(cages, 3000)
            self.assertGreaterEqual(projects, 40)
            self.assertGreaterEqual(proj_min, 2)
            self.assertLessEqual(proj_max, 6)
            self.assertGreaterEqual(cage_min, 35)
            self.assertGreater(cage_max, cage_min)
            self.assertGreater(tiers.get("small", 0), 0)
            self.assertGreater(tiers.get("medium", 0), 0)
            self.assertGreater(tiers.get("large", 0), 0)


if __name__ == "__main__":
    unittest.main()
