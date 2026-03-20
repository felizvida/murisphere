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

import argparse
import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def severity_from_deviation(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    return "high" if value in {"high", "major", "critical"} else "medium"


def severity_from_vet(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    return "high" if value in {"high", "critical"} else "medium"


def verify_alert_coverage(
    db_path: Path,
    min_total_alerts: int,
    min_distinct_cages: int,
    required_categories: list[str],
    ensure_schema: bool = False,
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "ok": False,
            "error": f"Database not found: {db_path}",
            "db_path": str(db_path),
        }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if ensure_schema:
        schema_path = Path("schema.sql")
        if schema_path.exists():
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.commit()

    today = date.today().isoformat()
    categories: dict[str, int] = {
        "protocol_expired": 0,
        "task_overdue": 0,
        "deviation_open": 0,
        "necropsy_pending": 0,
        "vet_open": 0,
    }
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    distinct_cages: set[int] = set()
    missing_tables: list[str] = []
    notes: list[str] = []

    # 1) Expired protocol cages => high severity
    if table_exists(conn, "cages") and table_exists(conn, "iacuc_protocols"):
        rows = conn.execute(
            """
            SELECT c.id AS cage_id
            FROM cages c
            JOIN iacuc_protocols p ON p.id = c.protocol_id
            WHERE p.expires_on < ?
            """,
            (today,),
        ).fetchall()
        categories["protocol_expired"] = len(rows)
        severity_counts["high"] += len(rows)
        distinct_cages.update(int(r["cage_id"]) for r in rows if r["cage_id"] is not None)
    else:
        missing_tables.extend([t for t in ("cages", "iacuc_protocols") if not table_exists(conn, t)])

    # 2) Overdue tasks => medium severity
    if table_exists(conn, "task_assignments") and table_exists(conn, "cages"):
        rows = conn.execute(
            """
            SELECT t.id AS task_id, t.cage_id
            FROM task_assignments t
            JOIN cages c ON c.id = t.cage_id
            WHERE t.status IN ('pending', 'in_progress')
              AND t.due_on < ?
            """,
            (today,),
        ).fetchall()
        categories["task_overdue"] = len(rows)
        severity_counts["medium"] += len(rows)
        distinct_cages.update(int(r["cage_id"]) for r in rows if r["cage_id"] is not None)
    else:
        missing_tables.extend([t for t in ("task_assignments",) if not table_exists(conn, t)])

    # 3) Open deviations => severity from deviation.severity
    if table_exists(conn, "protocol_deviations"):
        rows = conn.execute(
            """
            SELECT id, cage_id, severity
            FROM protocol_deviations
            WHERE status IN ('open', 'under_review')
            """
        ).fetchall()
        categories["deviation_open"] = len(rows)
        for r in rows:
            sev = severity_from_deviation(r["severity"])
            severity_counts[sev] += 1
            if r["cage_id"] is not None:
                distinct_cages.add(int(r["cage_id"]))
    else:
        missing_tables.append("protocol_deviations")

    # 4) Necropsy pending => high severity
    if table_exists(conn, "mortality_records"):
        rows = conn.execute(
            """
            SELECT id, cage_id
            FROM mortality_records
            WHERE necropsy_status = 'pending'
            """
        ).fetchall()
        categories["necropsy_pending"] = len(rows)
        severity_counts["high"] += len(rows)
        distinct_cages.update(int(r["cage_id"]) for r in rows if r["cage_id"] is not None)
    else:
        missing_tables.append("mortality_records")

    # 5) Open vet cases => severity from vet_cases.severity
    if table_exists(conn, "vet_cases"):
        rows = conn.execute(
            """
            SELECT id, cage_id, severity
            FROM vet_cases
            WHERE case_status = 'open'
            """
        ).fetchall()
        categories["vet_open"] = len(rows)
        for r in rows:
            sev = severity_from_vet(r["severity"])
            severity_counts[sev] += 1
            if r["cage_id"] is not None:
                distinct_cages.add(int(r["cage_id"]))
    else:
        missing_tables.append("vet_cases")

    conn.close()

    missing_tables = sorted(set(missing_tables))
    total_alerts = sum(categories.values())
    required_missing = [c for c in required_categories if categories.get(c, 0) <= 0]
    failed_checks: list[str] = []

    if missing_tables:
        failed_checks.append(f"Missing required tables: {', '.join(missing_tables)}")
    if total_alerts < min_total_alerts:
        failed_checks.append(f"Total alert candidates too low: {total_alerts} < {min_total_alerts}")
    if len(distinct_cages) < min_distinct_cages:
        failed_checks.append(f"Distinct cages with alerts too low: {len(distinct_cages)} < {min_distinct_cages}")
    if required_missing:
        failed_checks.append(f"Missing required alert categories: {', '.join(required_missing)}")
    if severity_counts["high"] <= 0:
        failed_checks.append("No high-severity alert candidates found")
    if severity_counts["medium"] <= 0:
        failed_checks.append("No medium-severity alert candidates found")

    if not failed_checks:
        notes.append("Synthetic dataset demonstrates broad, multi-category alert pressure.")
    else:
        notes.append("Synthetic dataset does not currently satisfy broad alert coverage expectations.")

    return {
        "ok": not failed_checks,
        "db_path": str(db_path),
        "today": today,
        "thresholds": {
            "min_total_alerts": min_total_alerts,
            "min_distinct_cages": min_distinct_cages,
            "required_categories": required_categories,
        },
        "summary": {
            "total_alert_candidates": total_alerts,
            "distinct_cages_with_alerts": len(distinct_cages),
            "category_counts": categories,
            "severity_counts": severity_counts,
        },
        "failed_checks": failed_checks,
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify synthesized demo data triggers a wide range of alert conditions."
    )
    parser.add_argument(
        "--db",
        default=os.getenv("MURISPHERE_DB", "murisphere.db"),
        help="Path to Murisphere SQLite database (default: env MURISPHERE_DB or murisphere.db).",
    )
    parser.add_argument("--min-total-alerts", type=int, default=100, help="Minimum total alert candidates expected.")
    parser.add_argument(
        "--min-distinct-cages",
        type=int,
        default=50,
        help="Minimum distinct cages that should have alert candidates.",
    )
    parser.add_argument(
        "--required-categories",
        default="protocol_expired,task_overdue,deviation_open,necropsy_pending,vet_open",
        help="Comma-separated required alert categories.",
    )
    parser.add_argument(
        "--output-json",
        default="docs/test_reports/ALERT_COVERAGE_RESULT.json",
        help="Where to write machine-readable result JSON.",
    )
    parser.add_argument(
        "--ensure-schema",
        action="store_true",
        help="Apply local schema.sql before verification (safe additive migration).",
    )
    args = parser.parse_args()

    required_categories = [x.strip() for x in args.required_categories.split(",") if x.strip()]
    result = verify_alert_coverage(
        db_path=Path(args.db),
        min_total_alerts=max(0, args.min_total_alerts),
        min_distinct_cages=max(0, args.min_distinct_cages),
        required_categories=required_categories,
        ensure_schema=bool(args.ensure_schema),
    )

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("Alert coverage verification complete")
    print(f"ok={result['ok']}")
    print(f"db={result['db_path']}")
    print(f"total_alert_candidates={result['summary']['total_alert_candidates']}")
    print(f"distinct_cages_with_alerts={result['summary']['distinct_cages_with_alerts']}")
    print(
        "category_counts="
        + ", ".join([f"{k}:{v}" for k, v in result["summary"]["category_counts"].items()])
    )
    print(
        "severity_counts="
        + ", ".join([f"{k}:{v}" for k, v in result["summary"]["severity_counts"].items()])
    )
    if result["failed_checks"]:
        print("failed_checks=" + " | ".join(result["failed_checks"]))
    print(f"json={output_path.resolve()}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
