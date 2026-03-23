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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from random import Random
from typing import Any

import app as appmod
import seed_alert_conditions
import seed_large_demo

DEFAULT_DB_PATH = Path("training_demo.db")
TRAINING_SEED = 20260323


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_reset_path(db_path: Path, force: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        if force or db_path.name == DEFAULT_DB_PATH.name:
            db_path.unlink()
        else:
            raise RuntimeError(
                f"{db_path} already exists. Re-run with --force to overwrite it, or use the default training db path."
            )
    db_path.touch()


def _bootstrap_base_demo(db_path: Path) -> dict[str, Any]:
    original_db = appmod.DB_PATH
    original_dialect = os.environ.pop("MURISPHERE_DB_DIALECT", None)
    original_url = os.environ.pop("MURISPHERE_DATABASE_URL", None)
    try:
        appmod.DB_PATH = str(db_path)
        appmod.init_db()
        return seed_large_demo.seed_database(str(db_path))
    finally:
        appmod.DB_PATH = original_db
        if original_dialect is not None:
            os.environ["MURISPHERE_DB_DIALECT"] = original_dialect
        if original_url is not None:
            os.environ["MURISPHERE_DATABASE_URL"] = original_url


def _clear_training_only_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM sample_events;
        DELETE FROM sample_records;
        DELETE FROM animal_tags;
        DELETE FROM breeding_pairs;
        DELETE FROM breeding_events;
        DELETE FROM genotype_results;
        DELETE FROM planner_plans;
        DELETE FROM planner_scenario_projects;
        DELETE FROM planner_scenarios;
        DELETE FROM animals;
        DELETE FROM litters;
        """
    )


def _insert_animal(
    conn: sqlite3.Connection,
    *,
    animal_code: str,
    sex: str,
    dob: str,
    strain: str,
    genotype: str,
    cage_id: int,
    litter_id: int | None,
    sire_id: int | None,
    dam_id: int | None,
    status: str = "Active",
) -> int:
    stamp = now_iso()
    cur = conn.execute(
        """
        INSERT INTO animals (
            animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, sire_id, dam_id, stamp, stamp),
    )
    return int(cur.lastrowid)


def _insert_pair_training_data(conn: sqlite3.Connection, rng: Random) -> dict[str, int]:
    cages = conn.execute(
        """
        SELECT id, cage_code, strain, genotype_summary, breeding_status, lab_id
        FROM cages
        WHERE male_count >= 1 AND female_count >= 1
        ORDER BY
            CASE breeding_status
                WHEN 'Breeding' THEN 1
                WHEN 'Wean Pending' THEN 2
                WHEN 'Timed Mating' THEN 3
                WHEN 'Holding' THEN 4
                ELSE 5
            END,
            id
        LIMIT 48
        """
    ).fetchall()
    if not cages:
        return {"animals": 0, "litters": 0, "pairs": 0, "samples": 0, "scenarios": 0}

    trainer_id = conn.execute("SELECT id FROM users WHERE role = 'Technician' ORDER BY id LIMIT 1").fetchone()[0]
    sample_statuses = ["collected", "shipped", "received", "resulted"]

    animal_count = 0
    litter_count = 0
    pair_count = 0
    sample_count = 0

    for idx, row in enumerate(cages):
        cage_id = int(row["id"])
        cage_code = str(row["cage_code"])
        strain = str(row["strain"])
        genotype = str(row["genotype_summary"] or "Pending")
        status = str(row["breeding_status"])
        today = date.today()

        sire_id = _insert_animal(
            conn,
            animal_code=f"{cage_code}-SIRE",
            sex="M",
            dob=(today - timedelta(days=140 + (idx % 30))).isoformat(),
            strain=strain,
            genotype=genotype,
            cage_id=cage_id,
            litter_id=None,
            sire_id=None,
            dam_id=None,
        )
        dam_id = _insert_animal(
            conn,
            animal_code=f"{cage_code}-DAM",
            sex="F",
            dob=(today - timedelta(days=132 + (idx % 25))).isoformat(),
            strain=strain,
            genotype=genotype,
            cage_id=cage_id,
            litter_id=None,
            sire_id=None,
            dam_id=None,
        )
        animal_count += 2

        pair_status = "active" if status in {"Breeding", "Timed Mating", "Wean Pending"} else "paused"
        pair_started = (today - timedelta(days=28 + idx)).isoformat()
        conn.execute(
            """
            INSERT INTO breeding_pairs (sire_id, dam_id, cage_id, lab_id, status, started_on, notes, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sire_id,
                dam_id,
                cage_id,
                int(row["lab_id"]),
                pair_status,
                pair_started,
                "Tutorial seed pair for self-paced learning",
                trainer_id,
                now_iso(),
                now_iso(),
            ),
        )
        pair_count += 1

        conn.execute(
            """
            INSERT INTO breeding_events (cage_id, event_type, event_date, details_json, assigned_to, created_at)
            VALUES (?, 'timed_mating', ?, ?, ?, ?)
            """,
            (
                cage_id,
                pair_started,
                json.dumps({"seeded": True, "objective": "tutorial"}),
                trainer_id,
                now_iso(),
            ),
        )
        conn.execute(
            """
            INSERT INTO breeding_events (cage_id, event_type, event_date, details_json, assigned_to, created_at)
            VALUES (?, 'plug_check', ?, ?, ?, ?)
            """,
            (
                cage_id,
                (today - timedelta(days=24 + idx)).isoformat(),
                json.dumps({"seeded": True, "result": "positive" if idx % 2 == 0 else "negative"}),
                trainer_id,
                now_iso(),
            ),
        )

        if idx >= 30 and status == "Holding":
            conn.execute(
                "UPDATE cages SET male_count = 1, female_count = 1, updated_at = ? WHERE id = ?",
                (now_iso(), cage_id),
            )
            continue

        birth_date = today - timedelta(days=16 + (idx % 5))
        litter_size = 5 + (idx % 3)
        survived = litter_size - (1 if idx % 4 == 0 else 0)
        weaned_on = (birth_date + timedelta(days=21)).isoformat() if status == "Wean Pending" else None
        cur = conn.execute(
            """
            INSERT INTO litters (cage_id, birth_date, litter_size, survived_count, weaned_on, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cage_id, birth_date.isoformat(), litter_size, survived, weaned_on, now_iso()),
        )
        litter_id = int(cur.lastrowid)
        litter_count += 1

        conn.execute(
            """
            INSERT INTO breeding_events (cage_id, event_type, event_date, details_json, assigned_to, created_at)
            VALUES (?, 'litter_birth', ?, ?, ?, ?)
            """,
            (
                cage_id,
                birth_date.isoformat(),
                json.dumps({"litterId": litter_id, "born": litter_size, "survived": survived}),
                trainer_id,
                now_iso(),
            ),
        )

        male_pups = survived // 2
        female_pups = survived - male_pups
        conn.execute(
            "UPDATE cages SET male_count = ?, female_count = ?, updated_at = ? WHERE id = ?",
            (1 + male_pups, 1 + female_pups, now_iso(), cage_id),
        )

        created_pups: list[int] = []
        for pup_idx in range(survived):
            sex = "M" if pup_idx < male_pups else "F"
            pup_id = _insert_animal(
                conn,
                animal_code=f"{cage_code}-P{pup_idx + 1:02d}",
                sex=sex,
                dob=birth_date.isoformat(),
                strain=strain,
                genotype=rng.choice(["WT/WT", "+/+", "Cre/+", "fl/+", genotype]),
                cage_id=cage_id,
                litter_id=litter_id,
                sire_id=sire_id,
                dam_id=dam_id,
            )
            created_pups.append(pup_id)
            animal_count += 1

            if pup_idx < 2:
                conn.execute(
                    """
                    INSERT INTO animal_tags (animal_id, tag_type, tag_value, is_active, applied_on, applied_by)
                    VALUES (?, 'ear_tag', ?, 1, ?, ?)
                    """,
                    (pup_id, f"ET-{idx + 1:02d}-{pup_idx + 1:02d}", now_iso(), trainer_id),
                )

        if created_pups:
            sample_status = sample_statuses[idx % len(sample_statuses)]
            first_pup = created_pups[0]
            cur = conn.execute(
                """
                INSERT INTO sample_records (
                    animal_id, cage_id, sample_type, sample_code, provider, status, tracking_number, collected_on, collected_by, notes
                ) VALUES (?, ?, 'tail', ?, 'Transnetyx', ?, ?, ?, ?, ?)
                """,
                (
                    first_pup,
                    cage_id,
                    f"SMP-{idx + 1:04d}",
                    sample_status,
                    f"TRK-{1000 + idx}",
                    (birth_date + timedelta(days=7)).isoformat(),
                    trainer_id,
                    "Tutorial seed sample for chain-of-custody practice",
                ),
            )
            sample_id = int(cur.lastrowid)
            sample_count += 1

            event_types = ["collected", "shipped", "received", "resulted"]
            for event_idx, event_type in enumerate(event_types[: event_types.index(sample_status) + 1]):
                conn.execute(
                    """
                    INSERT INTO sample_events (sample_id, event_type, event_time, actor_user_id, details_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        sample_id,
                        event_type,
                        (birth_date + timedelta(days=7 + event_idx)).isoformat(),
                        trainer_id,
                        json.dumps({"seeded": True}),
                    ),
                )

            if sample_status == "resulted":
                conn.execute(
                    """
                    INSERT INTO genotype_results (animal_id, result, source, created_at)
                    VALUES (?, ?, 'tutorial_seed', ?)
                    """,
                    (first_pup, rng.choice(["WT/WT", "Cre/+", "fl/+"]), now_iso()),
                )

    return {
        "animals": animal_count,
        "litters": litter_count,
        "pairs": pair_count,
        "samples": sample_count,
    }


def _insert_planner_examples(conn: sqlite3.Connection) -> int:
    admin_id = conn.execute("SELECT id FROM users WHERE role = 'Admin' ORDER BY id LIMIT 1").fetchone()[0]
    labs = conn.execute(
        """
        SELECT l.id, l.name
        FROM labs l
        ORDER BY l.id
        LIMIT 6
        """
    ).fetchall()

    scenario_count = 0
    for idx, lab in enumerate(labs):
        needed_by = (date.today() + timedelta(days=21 + idx * 7)).isoformat()
        target_animals = 120 + idx * 40
        max_new_cages = 10 + idx * 2
        cur = conn.execute(
            """
            INSERT INTO planner_scenarios (lab_id, name, needed_by, target_animals, max_new_cages, assumptions_json, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?)
            """,
            (
                int(lab["id"]),
                f"{lab['name']} Cohort Plan",
                needed_by,
                target_animals,
                max_new_cages,
                json.dumps({"targetSex": "balanced", "purpose": "self-paced tutorial"}),
                admin_id,
                now_iso(),
                now_iso(),
            ),
        )
        scenario_id = int(cur.lastrowid)

        projects = conn.execute(
            "SELECT id FROM projects WHERE lab_id = ? ORDER BY id LIMIT 2",
            (int(lab["id"]),),
        ).fetchall()
        for priority, project in enumerate(projects, start=1):
            conn.execute(
                """
                INSERT INTO planner_scenario_projects (scenario_id, project_id, animals_needed, priority)
                VALUES (?, ?, ?, ?)
                """,
                (scenario_id, int(project["id"]), target_animals // max(len(projects), 1), priority),
            )

        deficit = max(0, target_animals - (60 + idx * 10))
        risk = "high" if deficit > 120 else "medium" if deficit > 40 else "low"
        conn.execute(
            """
            INSERT INTO planner_plans (scenario_id, estimated_litters, estimated_cages, projected_deficit, risk_level, recommendation_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                max(1, (deficit + 3) // 4),
                max_new_cages,
                deficit,
                risk,
                json.dumps({"action": "scale breeders", "seeded": True}),
                now_iso(),
            ),
        )
        scenario_count += 1

    return scenario_count


def create_tutorial_demo(db_path: Path, *, force: bool = False) -> dict[str, Any]:
    _safe_reset_path(db_path, force=force)
    base = _bootstrap_base_demo(db_path)

    rng = Random(TRAINING_SEED)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _clear_training_only_tables(conn)
    advanced = _insert_pair_training_data(conn, rng)
    advanced["scenarios"] = _insert_planner_examples(conn)
    conn.commit()
    conn.close()

    alerts = seed_alert_conditions.inject_demo_alert_conditions(db_path, target_cages=80)

    conn = sqlite3.connect(str(db_path))
    enriched = {
        "animals": conn.execute("SELECT COUNT(*) FROM animals").fetchone()[0],
        "litters": conn.execute("SELECT COUNT(*) FROM litters").fetchone()[0],
        "breedingPairs": conn.execute("SELECT COUNT(*) FROM breeding_pairs").fetchone()[0],
        "sampleRecords": conn.execute("SELECT COUNT(*) FROM sample_records").fetchone()[0],
        "plannerScenarios": conn.execute("SELECT COUNT(*) FROM planner_scenarios").fetchone()[0],
        "alertingTasks": conn.execute("SELECT COUNT(*) FROM task_assignments").fetchone()[0],
    }
    conn.close()

    return {
        "db": str(db_path),
        "base": base,
        "advanced": advanced,
        "alerts": alerts,
        "enriched": enriched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a tutorial-ready Murisphere demo database with scale, alerts, and learner-friendly workflow data.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path to create/reset.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting an existing non-default database file.")
    parser.add_argument(
        "--output-json",
        default="docs/test_reports/TUTORIAL_DEMO_SEED_RESULT.json",
        help="Path for a machine-readable result summary.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    result = create_tutorial_demo(db_path, force=args.force)
    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("Tutorial-ready demo created")
    print(f"db={db_path}")
    print(json.dumps(result["base"], sort_keys=True))
    print(json.dumps(result["enriched"], sort_keys=True))
    print(f"json={out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
