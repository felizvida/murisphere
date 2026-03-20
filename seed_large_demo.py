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

import os
import random
import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

DB_PATH = os.getenv("MURISPHERE_DB", "murisphere.db")
TOTAL_LABS = 20
TOTAL_CAGES = 3000
SEED = 20260304


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ensure_support_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_id INTEGER NOT NULL,
            project_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            target_animals INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lab_id) REFERENCES labs(id)
        );

        CREATE TABLE IF NOT EXISTS project_cages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            cage_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL,
            UNIQUE(project_id, cage_id),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(cage_id) REFERENCES cages(id)
        );

        CREATE TABLE IF NOT EXISTS lab_profiles (
            lab_id INTEGER PRIMARY KEY,
            size_tier TEXT NOT NULL,
            staff_count INTEGER NOT NULL,
            expected_cage_load INTEGER NOT NULL,
            active_project_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(lab_id) REFERENCES labs(id)
        );
        """
    )


def clear_operational_data(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM genotype_results;
        DELETE FROM breeding_events;
        DELETE FROM lifecycle_events;
        DELETE FROM animals;
        DELETE FROM litters;
        DELETE FROM project_cages;
        DELETE FROM cages;
        DELETE FROM notes;
        DELETE FROM audit_logs;
        DELETE FROM projects;
        DELETE FROM lab_profiles;
        """
    )


def ensure_facilities_rooms_racks(conn: sqlite3.Connection) -> list[int]:
    existing = conn.execute("SELECT id FROM facilities ORDER BY id").fetchall()
    if not existing:
        facilities = [
            ("North Campus Vivarium", "America/New_York", now_iso()),
            ("South Campus Barrier Facility", "America/New_York", now_iso()),
            ("Translational Animal Center", "America/New_York", now_iso()),
        ]
        conn.executemany("INSERT INTO facilities (name, timezone, created_at) VALUES (?, ?, ?)", facilities)

    facility_ids = [r[0] for r in conn.execute("SELECT id FROM facilities ORDER BY id").fetchall()]

    room_count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    rack_count = conn.execute("SELECT COUNT(*) FROM racks").fetchone()[0]
    if room_count == 0 or rack_count == 0:
        for fid in facility_ids:
            for ri in range(1, 7):
                room_name = f"F{fid}-Room-{ri:02d}"
                conn.execute(
                    "INSERT INTO rooms (name, facility_id, capacity, created_at) VALUES (?, ?, ?, ?)",
                    (room_name, fid, 400, now_iso()),
                )
                room_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for ki in range(1, 11):
                    conn.execute(
                        "INSERT INTO racks (name, room_id, capacity, created_at) VALUES (?, ?, ?, ?)",
                        (f"R{ri:02d}-{ki:02d}", room_id, 80, now_iso()),
                    )

    return facility_ids


def ensure_labs(conn: sqlite3.Connection, facility_ids: list[int]) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    existing_count = conn.execute("SELECT COUNT(*) FROM labs").fetchone()[0]
    lab_names = [
        "Neurogenetics Lab",
        "Synaptic Circuits Group",
        "Developmental Signaling Unit",
        "Cancer Models Core",
        "Metabolic Disease Program",
        "Behavioral Neuroscience Team",
        "Immunology Animal Platform",
        "Aging Biology Lab",
        "Stem Cell Dynamics Group",
        "Genome Editing Hub",
        "Cortex Plasticity Lab",
        "Cardio Translational Models",
        "Renal Physiology Unit",
        "Retina Function Group",
        "Microbiome Host Lab",
        "Pain Mechanisms Program",
        "Rare Disease Models",
        "Regenerative Medicine Lab",
        "Molecular Pathology Group",
        "Systems Neurobiology Unit",
    ]

    for i in range(existing_count, TOTAL_LABS):
        name = lab_names[i]
        pi = f"Dr. PI {i+1:02d}"
        fid = facility_ids[i % len(facility_ids)]
        conn.execute(
            "INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, ?, ?)",
            (name, pi, fid, now_iso()),
        )

    labs = conn.execute("SELECT id, name, facility_id FROM labs ORDER BY id LIMIT ?", (TOTAL_LABS,)).fetchall()
    return labs


def ensure_protocols_projects(conn: sqlite3.Connection, labs: list[sqlite3.Row], rng: random.Random) -> tuple[dict[int, list[int]], dict[int, list[int]], dict[int, dict[str, int | str]]]:
    protocols_by_lab: dict[int, list[int]] = defaultdict(list)
    projects_by_lab: dict[int, list[int]] = defaultdict(list)
    profile_map: dict[int, dict[str, int | str]] = {}

    size_tiers = ["small"] * 8 + ["medium"] * 8 + ["large"] * 4
    rng.shuffle(size_tiers)

    for idx, lab in enumerate(labs):
        lab_id = lab["id"]
        tier = size_tiers[idx]
        if tier == "small":
            staff = rng.randint(3, 6)
            pcount = rng.randint(2, 3)
            expected = rng.randint(60, 110)
            prot_count = 1
        elif tier == "medium":
            staff = rng.randint(7, 13)
            pcount = rng.randint(3, 5)
            expected = rng.randint(120, 210)
            prot_count = 2
        else:
            staff = rng.randint(14, 24)
            pcount = rng.randint(4, 6)
            expected = rng.randint(220, 420)
            prot_count = 3

        profile_map[lab_id] = {
            "size_tier": tier,
            "staff_count": staff,
            "active_project_count": pcount,
            "expected_cage_load": expected,
        }

        for p in range(prot_count):
            proto = f"IACUC-2026-{lab_id:02d}{p+1:02d}"
            expires = (date.today() + timedelta(days=120 + rng.randint(0, 220))).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO iacuc_protocols (protocol_number, title, lab_id, expires_on, created_at) VALUES (?, ?, ?, ?, ?)",
                (proto, f"{lab['name']} Protocol {p+1}", lab_id, expires, now_iso()),
            )

        prot_ids = [r[0] for r in conn.execute("SELECT id FROM iacuc_protocols WHERE lab_id = ? ORDER BY id", (lab_id,)).fetchall()]
        protocols_by_lab[lab_id] = prot_ids

        for p in range(pcount):
            code = f"L{lab_id:02d}-PRJ-{p+1:02d}"
            status = "Active" if p < max(1, pcount - 1) else "Planning"
            target_animals = rng.randint(80, 900)
            conn.execute(
                "INSERT INTO projects (lab_id, project_code, title, status, target_animals, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (lab_id, code, f"{lab['name']} Project {p+1}", status, target_animals, now_iso()),
            )

        project_ids = [r[0] for r in conn.execute("SELECT id FROM projects WHERE lab_id = ? ORDER BY id", (lab_id,)).fetchall()]
        projects_by_lab[lab_id] = project_ids

        conn.execute(
            "INSERT INTO lab_profiles (lab_id, size_tier, staff_count, expected_cage_load, active_project_count, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (lab_id, tier, staff, expected, pcount, now_iso()),
        )

    return protocols_by_lab, projects_by_lab, profile_map


def cage_distribution(labs: list[sqlite3.Row], profile_map: dict[int, dict[str, int | str]], total: int) -> dict[int, int]:
    weight = {}
    for lab in labs:
        lab_id = lab["id"]
        tier = profile_map[lab_id]["size_tier"]
        weight[lab_id] = 1.0 if tier == "small" else 2.1 if tier == "medium" else 4.2

    raw = {lab_id: int(weight[lab_id] * 100) for lab_id in weight}
    alloc = {lab_id: max(35, raw[lab_id]) for lab_id in raw}
    current = sum(alloc.values())

    while current < total:
        for lab_id in sorted(weight, key=lambda k: weight[k], reverse=True):
            if current >= total:
                break
            alloc[lab_id] += 1
            current += 1

    while current > total:
        for lab_id in sorted(weight, key=lambda k: weight[k]):
            if current <= total:
                break
            if alloc[lab_id] > 35:
                alloc[lab_id] -= 1
                current -= 1

    return alloc


def insert_cages_and_links(
    conn: sqlite3.Connection,
    labs: list[sqlite3.Row],
    protocols_by_lab: dict[int, list[int]],
    projects_by_lab: dict[int, list[int]],
    counts: dict[int, int],
    rng: random.Random,
) -> None:
    strains = ["C57BL/6J", "BALB/c", "NOD", "129S1", "Ai14 x Cre", "FVB/N", "Rosa26-LSL"]
    genotypes = ["WT/WT", "+/tg", "fl/fl", "Cre/+", "+/+", "tg/tg", "Pending"]
    statuses = ["Breeding", "Holding", "Timed Mating", "Wean Pending"]

    rooms_by_fac: dict[int, list[int]] = defaultdict(list)
    racks_by_room: dict[int, list[int]] = defaultdict(list)

    for room_id, fid in conn.execute("SELECT id, facility_id FROM rooms").fetchall():
        rooms_by_fac[fid].append(room_id)
    for rack_id, room_id in conn.execute("SELECT id, room_id FROM racks").fetchall():
        racks_by_room[room_id].append(rack_id)

    cage_rows = []
    cage_map = []  # (lab_id, project_id)
    created_at = now_iso()

    for lab in labs:
        lab_id = lab["id"]
        facility_id = lab["facility_id"]
        protocols = protocols_by_lab[lab_id]
        projects = projects_by_lab[lab_id]
        rooms = rooms_by_fac[facility_id]

        for i in range(1, counts[lab_id] + 1):
            room_id = rooms[(i - 1) % len(rooms)]
            racks = racks_by_room[room_id]
            rack_id = racks[rng.randint(0, len(racks) - 1)]

            dob = (date.today() - timedelta(days=rng.randint(20, 420))).isoformat()
            m = rng.randint(0, 4)
            f = rng.randint(0, 6)
            cage_code = f"F{facility_id}-L{lab_id:02d}-C{i:04d}"
            protocol_id = protocols[rng.randint(0, len(protocols) - 1)]
            project_id = projects[rng.randint(0, len(projects) - 1)]

            cage_rows.append(
                (
                    cage_code,
                    strains[rng.randint(0, len(strains) - 1)],
                    genotypes[rng.randint(0, len(genotypes) - 1)],
                    statuses[rng.randint(0, len(statuses) - 1)],
                    dob,
                    m,
                    f,
                    room_id,
                    rack_id,
                    lab_id,
                    protocol_id,
                    f"tok_{facility_id}_{lab_id}_{i:04d}_{rng.randint(1000, 9999)}",
                    created_at,
                    created_at,
                )
            )
            cage_map.append((lab_id, project_id))

    conn.executemany(
        """
        INSERT INTO cages (
            cage_code, strain, genotype_summary, breeding_status, dob, male_count, female_count,
            room_id, rack_id, lab_id, protocol_id, qr_token, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        cage_rows,
    )

    cage_ids = [r[0] for r in conn.execute("SELECT id FROM cages ORDER BY id").fetchall()]
    links = []
    for idx, cage_id in enumerate(cage_ids):
        _lab_id, project_id = cage_map[idx]
        links.append((project_id, cage_id, created_at))

    conn.executemany(
        "INSERT INTO project_cages (project_id, cage_id, assigned_at) VALUES (?, ?, ?)",
        links,
    )


def print_summary(conn: sqlite3.Connection) -> None:
    labs = conn.execute("SELECT COUNT(*) FROM labs").fetchone()[0]
    cages = conn.execute("SELECT COUNT(*) FROM cages").fetchone()[0]
    projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    by_size = conn.execute(
        "SELECT size_tier, COUNT(*) FROM lab_profiles GROUP BY size_tier ORDER BY size_tier"
    ).fetchall()

    print(f"labs={labs}")
    print(f"cages={cages}")
    print(f"projects={projects}")
    print("lab_size_distribution=" + ", ".join([f"{row[0]}:{row[1]}" for row in by_size]))


def main() -> None:
    if not Path(DB_PATH).exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Start app once to initialize schema, then rerun.")

    rng = random.Random(SEED)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    ensure_support_tables(conn)
    clear_operational_data(conn)
    facility_ids = ensure_facilities_rooms_racks(conn)
    labs = ensure_labs(conn, facility_ids)
    protocols_by_lab, projects_by_lab, profile_map = ensure_protocols_projects(conn, labs, rng)
    counts = cage_distribution(labs, profile_map, TOTAL_CAGES)
    insert_cages_and_links(conn, labs, protocols_by_lab, projects_by_lab, counts, rng)

    conn.commit()
    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
