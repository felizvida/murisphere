from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def inject_demo_alert_conditions(db_path: Path, target_cages: int = 60) -> dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    cages = conn.execute(
        """
        SELECT c.id, c.protocol_id, c.lab_id
        FROM cages c
        JOIN iacuc_protocols p ON p.id = c.protocol_id
        ORDER BY c.id ASC
        LIMIT ?
        """,
        (max(target_cages, 1),),
    ).fetchall()
    if not cages:
        conn.close()
        raise RuntimeError("No cages available to inject alert conditions")

    admin_user = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    actor_id = int(admin_user["id"]) if admin_user else 1
    run_at = now_iso()

    protocol_ids = sorted({int(row["protocol_id"]) for row in cages if row["protocol_id"] is not None})
    if protocol_ids:
        placeholders = ", ".join(["?"] * len(protocol_ids))
        conn.execute(
            f"UPDATE iacuc_protocols SET expires_on = '2020-01-01' WHERE id IN ({placeholders})",
            protocol_ids,
        )

    task_rows = 0
    deviation_rows = 0
    mortality_rows = 0
    vet_rows = 0

    for idx, cage in enumerate(cages):
        cage_id = int(cage["id"])
        protocol_id = int(cage["protocol_id"] or 0)
        lab_id = int(cage["lab_id"] or 0)

        conn.execute(
            """
            INSERT INTO task_assignments (task_type, cage_id, due_on, assigned_to, required_qualification, status, created_by, created_at)
            VALUES (?, ?, '2020-01-01', ?, NULL, 'pending', ?, ?)
            """,
            ("plug_check" if idx % 2 == 0 else "wean", cage_id, actor_id, actor_id, run_at),
        )
        task_rows += 1

        conn.execute(
            """
            INSERT INTO protocol_deviations (protocol_id, cage_id, reported_by, reported_at, severity, summary, capa_plan, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                protocol_id,
                cage_id,
                actor_id,
                run_at,
                "high" if idx % 3 == 0 else "moderate",
                f"Injected alert deviation for cage {cage_id}",
                "Review, reconcile, and document corrective action.",
            ),
        )
        deviation_rows += 1

        if idx % 2 == 0:
            conn.execute(
                """
                INSERT INTO mortality_records (
                    animal_id, cage_id, protocol_id, count_male, count_female, cause, found_at,
                    reported_by, necropsy_required, necropsy_status, notes
                ) VALUES (NULL, ?, ?, 1, 0, 'found dead', ?, ?, 1, 'pending', ?)
                """,
                (cage_id, protocol_id, run_at, actor_id, "Injected necropsy pending fixture"),
            )
            mortality_rows += 1

        conn.execute(
            """
            INSERT INTO vet_cases (cage_id, animal_id, lab_id, case_status, severity, opened_at, closed_at, opened_by, notes)
            VALUES (?, NULL, ?, 'open', ?, ?, NULL, ?, ?)
            """,
            (
                cage_id,
                lab_id,
                "high" if idx % 4 == 0 else "moderate",
                run_at,
                actor_id,
                "Injected open vet case fixture",
            ),
        )
        vet_rows += 1

    conn.commit()
    conn.close()

    return {
        "db": str(db_path),
        "cagesTouched": len(cages),
        "expiredProtocols": len(protocol_ids),
        "tasksInserted": task_rows,
        "deviationsInserted": deviation_rows,
        "mortalityInserted": mortality_rows,
        "vetCasesInserted": vet_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject deterministic alert-triggering records into a Murisphere SQLite demo database.")
    parser.add_argument("--db", default=os.getenv("MURISPHERE_DB", "murisphere.db"), help="Path to the SQLite database.")
    parser.add_argument("--target-cages", type=int, default=60, help="How many cages to enrich with alert-triggering records.")
    parser.add_argument(
        "--output-json",
        default="docs/test_reports/ALERT_FIXTURE_RESULT.json",
        help="Where to write the machine-readable result summary.",
    )
    args = parser.parse_args()

    result = inject_demo_alert_conditions(Path(args.db), target_cages=max(1, args.target_cages))
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("Alert condition injection complete")
    for key, value in result.items():
        print(f"{key}={value}")
    print(f"json={output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
