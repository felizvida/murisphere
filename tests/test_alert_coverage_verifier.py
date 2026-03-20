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

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import alert_coverage_verifier as verifier


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AlertCoverageVerifierTests(unittest.TestCase):
    def test_fails_when_no_alert_conditions_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "empty_alerts.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript(Path("schema.sql").read_text(encoding="utf-8"))
            conn.commit()
            conn.close()

            result = verifier.verify_alert_coverage(
                db_path=db_path,
                min_total_alerts=5,
                min_distinct_cages=2,
                required_categories=["protocol_expired", "task_overdue"],
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["summary"]["total_alert_candidates"], 0)
            self.assertTrue(result["failed_checks"])

    def test_passes_with_all_alert_categories_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "alert_rich.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            conn.executescript(Path("schema.sql").read_text(encoding="utf-8"))

            conn.execute("INSERT INTO facilities (name, timezone, created_at) VALUES (?, ?, ?)", ("F1", "America/New_York", now_iso()))
            conn.execute("INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, 1, ?)", ("L1", "PI", now_iso()))
            conn.execute("INSERT INTO rooms (name, facility_id, capacity, created_at) VALUES (?, 1, 100, ?)", ("R1", now_iso()))
            conn.execute("INSERT INTO racks (name, room_id, capacity, created_at) VALUES (?, 1, 100, ?)", ("K1", now_iso()))
            conn.execute(
                "INSERT INTO users (email, full_name, role, lab_id, password_hash, is_active, created_at) VALUES (?, ?, 'Admin', 1, ?, 1, ?)",
                ("admin@test.local", "Admin", "hash", now_iso()),
            )
            conn.execute(
                "INSERT INTO iacuc_protocols (protocol_number, title, lab_id, expires_on, created_at) VALUES (?, ?, 1, ?, ?)",
                ("IACUC-1", "P1", "2020-01-01", now_iso()),
            )
            conn.execute(
                """
                INSERT INTO cages (
                    cage_code, strain, genotype_summary, breeding_status, dob, male_count, female_count,
                    room_id, rack_id, lab_id, protocol_id, qr_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 1, 1, ?, ?, ?)
                """,
                ("C-1", "C57BL/6J", "WT/WT", "Holding", "2025-01-01", 2, 2, "tok_c1", now_iso(), now_iso()),
            )
            conn.execute(
                """
                INSERT INTO cages (
                    cage_code, strain, genotype_summary, breeding_status, dob, male_count, female_count,
                    room_id, rack_id, lab_id, protocol_id, qr_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 1, 1, ?, ?, ?)
                """,
                ("C-2", "C57BL/6J", "WT/WT", "Holding", "2025-01-01", 2, 2, "tok_c2", now_iso(), now_iso()),
            )
            conn.execute(
                "INSERT INTO task_assignments (task_type, cage_id, due_on, assigned_to, required_qualification, status, created_by, created_at) VALUES (?, 1, ?, 1, NULL, 'pending', 1, ?)",
                ("plug_check", "2020-01-01", now_iso()),
            )
            conn.execute(
                """
                INSERT INTO protocol_deviations (
                    protocol_id, cage_id, reported_by, reported_at, severity, summary, capa_plan, status
                ) VALUES (1, 1, 1, ?, 'high', 'deviation', 'capa', 'open')
                """,
                (now_iso(),),
            )
            conn.execute(
                """
                INSERT INTO mortality_records (
                    animal_id, cage_id, protocol_id, count_male, count_female, cause, found_at,
                    reported_by, necropsy_required, necropsy_status, notes
                ) VALUES (NULL, 2, 1, 1, 0, 'found dead', ?, 1, 1, 'pending', 'note')
                """,
                (now_iso(),),
            )
            conn.execute(
                """
                INSERT INTO vet_cases (
                    cage_id, animal_id, lab_id, case_status, severity, opened_at, closed_at, opened_by, notes
                ) VALUES (2, NULL, 1, 'open', 'moderate', ?, NULL, 1, 'monitor')
                """,
                (now_iso(),),
            )
            conn.commit()
            conn.close()

            result = verifier.verify_alert_coverage(
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

            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["summary"]["total_alert_candidates"], 5)
            self.assertGreaterEqual(result["summary"]["distinct_cages_with_alerts"], 2)
            self.assertEqual(result["summary"]["category_counts"]["protocol_expired"], 2)
            self.assertEqual(result["summary"]["category_counts"]["task_overdue"], 1)
            self.assertEqual(result["summary"]["category_counts"]["deviation_open"], 1)
            self.assertEqual(result["summary"]["category_counts"]["necropsy_pending"], 1)
            self.assertEqual(result["summary"]["category_counts"]["vet_open"], 1)


if __name__ == "__main__":
    unittest.main()
