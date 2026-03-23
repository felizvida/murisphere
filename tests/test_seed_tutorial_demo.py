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

import tempfile
import unittest
from pathlib import Path

import alert_coverage_verifier as verifier
import seed_tutorial_demo


class SeedTutorialDemoTests(unittest.TestCase):
    def test_tutorial_demo_populates_learning_ready_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "training_demo.db"
            result = seed_tutorial_demo.create_tutorial_demo(db_path, force=True)

            self.assertEqual(result["base"]["labs"], 20)
            self.assertEqual(result["base"]["cages"], 3000)
            self.assertGreaterEqual(result["enriched"]["animals"], 150)
            self.assertGreaterEqual(result["enriched"]["litters"], 20)
            self.assertGreaterEqual(result["enriched"]["breedingPairs"], 20)
            self.assertGreaterEqual(result["enriched"]["sampleRecords"], 10)
            self.assertGreaterEqual(result["enriched"]["plannerScenarios"], 4)

            verification = verifier.verify_alert_coverage(
                db_path=db_path,
                min_total_alerts=20,
                min_distinct_cages=10,
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
