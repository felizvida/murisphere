from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import alert_coverage_verifier as verifier
import app as appmod
import seed_alert_conditions


class SeedAlertConditionsTests(unittest.TestCase):
    def test_injected_conditions_produce_alert_rich_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "alert-fixture.db"
            old_db = appmod.DB_PATH
            try:
                appmod.DB_PATH = str(db_path)
                appmod.init_db()
                result = seed_alert_conditions.inject_demo_alert_conditions(db_path, target_cages=2)
            finally:
                appmod.DB_PATH = old_db

            self.assertEqual(result["cagesTouched"], 2)
            self.assertGreaterEqual(result["tasksInserted"], 2)
            self.assertGreaterEqual(result["deviationsInserted"], 2)
            verification = verifier.verify_alert_coverage(
                db_path=db_path,
                min_total_alerts=5,
                min_distinct_cages=2,
                required_categories=[
                    "protocol_expired",
                    "task_overdue",
                    "deviation_open",
                    "necropsy_pending",
                    "vet_open",
                ],
            )
            self.assertTrue(verification["ok"])


if __name__ == "__main__":
    unittest.main()
