from __future__ import annotations

import csv
import io
import json
import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

from flask import Flask, Response, g, jsonify, render_template, request, send_file
from openpyxl import Workbook
from werkzeug.security import check_password_hash, generate_password_hash

APP_NAME = "Murisphere"
DB_PATH = os.getenv("MURISPHERE_DB", "murisphere.db")

app = Flask(__name__, static_folder="static", template_folder="templates")


@dataclass
class AuthContext:
    user_id: int
    email: str
    full_name: str
    role: str
    lab_id: int | None


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with open("schema.sql", "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    existing = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
    if existing:
        conn.close()
        return

    conn.execute(
        "INSERT INTO facilities (name, timezone, created_at) VALUES (?, ?, ?)",
        ("North Campus Vivarium", "America/New_York", now_iso()),
    )
    conn.execute(
        "INSERT INTO labs (name, pi_name, facility_id, created_at) VALUES (?, ?, 1, ?)",
        ("Neurogenetics Lab", "Dr. A. Rivera", now_iso()),
    )
    conn.execute(
        "INSERT INTO rooms (name, facility_id, capacity, created_at) VALUES (?, 1, 240, ?)",
        ("Room A1", now_iso()),
    )
    conn.execute(
        "INSERT INTO racks (name, room_id, capacity, created_at) VALUES (?, 1, 120, ?)",
        ("Rack R1", now_iso()),
    )
    conn.execute(
        "INSERT INTO iacuc_protocols (protocol_number, title, lab_id, expires_on, created_at) VALUES (?, ?, 1, ?, ?)",
        ("IACUC-2026-014", "Synaptic Development Cohort", "2026-12-31", now_iso()),
    )

    users = [
        ("admin@murisphere.local", "Admin User", "Admin", None, "admin1234"),
        ("tech@murisphere.local", "Tech One", "Technician", 1, "tech1234"),
        ("pi@murisphere.local", "Principal Investigator", "PI", 1, "pi1234"),
    ]
    for email, name, role, lab_id, pwd in users:
        conn.execute(
            "INSERT INTO users (email, full_name, role, lab_id, password_hash, is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (email, name, role, lab_id, generate_password_hash(pwd), now_iso()),
        )

    cages = [
        ("C-A1-001", "C57BL/6J", "WT/WT", "Breeding", "2026-01-12", 1, 2, 1, 1, 1),
        ("C-A1-002", "Ai14 x Cre", "+/tg", "Holding", "2026-02-01", 2, 3, 1, 1, 1),
    ]
    for cage_id, strain, genotype, status, dob, males, females, room_id, rack_id, lab_id in cages:
        conn.execute(
            """
            INSERT INTO cages (
                cage_code, strain, genotype_summary, breeding_status, dob,
                male_count, female_count, room_id, rack_id, lab_id, protocol_id,
                qr_token, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                cage_id,
                strain,
                genotype,
                status,
                dob,
                males,
                females,
                room_id,
                rack_id,
                lab_id,
                secrets.token_urlsafe(12),
                now_iso(),
                now_iso(),
            ),
        )

    conn.commit()
    conn.close()


def audit_log(actor_id: int | None, entity_type: str, entity_id: int | str, action: str, before: Any, after: Any) -> None:
    db().execute(
        """
        INSERT INTO audit_logs (actor_user_id, entity_type, entity_id, action, before_json, after_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_id,
            entity_type,
            str(entity_id),
            action,
            json.dumps(before, default=str) if before is not None else None,
            json.dumps(after, default=str) if after is not None else None,
            now_iso(),
        ),
    )
    db().commit()


def current_user() -> AuthContext | None:
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        return None
    row = db().execute(
        """
        SELECT u.id, u.email, u.full_name, u.role, u.lab_id
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now_iso()),
    ).fetchone()
    if not row:
        return None
    return AuthContext(
        user_id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        lab_id=row["lab_id"],
    )


def require_auth(roles: tuple[str, ...] | None = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if roles and user.role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            g.user = user
            return func(*args, **kwargs)

        return wrapper

    return decorator


def cage_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "cageCode": row["cage_code"],
        "strain": row["strain"],
        "genotypeSummary": row["genotype_summary"],
        "breedingStatus": row["breeding_status"],
        "dob": row["dob"],
        "maleCount": row["male_count"],
        "femaleCount": row["female_count"],
        "room": row["room_name"],
        "rack": row["rack_name"],
        "lab": row["lab_name"],
        "protocol": row["protocol_number"],
        "notes": row["notes"],
        "qrToken": row["qr_token"],
        "updatedAt": row["updated_at"],
    }


def simple_pdf(lines: list[str]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream_lines = ["BT", "/F1 10 Tf", "50 790 Td", "12 TL"]
    for line in lines:
        stream_lines.append(f"({esc(line)}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    content = "\n".join(stream_lines).encode("latin-1", errors="replace")

    objs = []
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objs.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n")
    objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objs.append(f"5 0 obj << /Length {len(content)} >> stream\n".encode("ascii") + content + b"\nendstream endobj\n")

    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objs:
        offsets.append(len(body))
        body += obj
    xref_start = len(body)
    xref = [f"xref\n0 {len(offsets)}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("ascii"))
    trailer = f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode("ascii")
    return body + b"".join(xref) + trailer


@app.route("/")
def index() -> str:
    return render_template("index.html", app_name=APP_NAME)


@app.route("/scan/<token>")
def scan_page(token: str) -> str:
    return render_template("scan.html", app_name=APP_NAME, scan_token=token)


@app.post("/api/auth/login")
def login() -> Response:
    payload = request.get_json(force=True)
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    row = db().execute(
        "SELECT id, email, full_name, role, lab_id, password_hash, is_active FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if not row or not row["is_active"] or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(UTC) + timedelta(hours=12)).isoformat()
    db().execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, row["id"], expires_at, now_iso()),
    )
    db().commit()

    return jsonify(
        {
            "token": token,
            "user": {
                "id": row["id"],
                "email": row["email"],
                "fullName": row["full_name"],
                "role": row["role"],
                "labId": row["lab_id"],
            },
            "appName": APP_NAME,
        }
    )


@app.post("/api/auth/logout")
@require_auth()
def logout() -> Response:
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    db().execute("DELETE FROM sessions WHERE token = ?", (token,))
    db().commit()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
@require_auth()
def me() -> Response:
    user = g.user
    return jsonify({"id": user.user_id, "email": user.email, "fullName": user.full_name, "role": user.role, "labId": user.lab_id})


@app.get("/api/cages")
@require_auth()
def list_cages() -> Response:
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    clauses = []
    params: list[Any] = []
    if q:
        clauses.append("(c.cage_code LIKE ? OR c.strain LIKE ? OR c.genotype_summary LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if status:
        clauses.append("c.breeding_status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db().execute(
        f"""
        SELECT c.*, r.name AS room_name, k.name AS rack_name, l.name AS lab_name, p.protocol_number
        FROM cages c
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        {where_sql}
        ORDER BY c.updated_at DESC
        LIMIT 500
        """,
        params,
    ).fetchall()
    return jsonify([cage_payload(row) for row in rows])


@app.get("/api/cages/<int:cage_id>")
@require_auth()
def get_cage(cage_id: int) -> Response:
    row = db().execute(
        """
        SELECT c.*, r.name AS room_name, k.name AS rack_name, l.name AS lab_name, p.protocol_number
        FROM cages c
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        WHERE c.id = ?
        """,
        (cage_id,),
    ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    animals = db().execute(
        "SELECT id, animal_code, sex, dob, genotype, status FROM animals WHERE cage_id = ? ORDER BY id DESC",
        (cage_id,),
    ).fetchall()
    history = db().execute(
        "SELECT actor_user_id, action, created_at FROM audit_logs WHERE entity_type = 'cage' AND entity_id = ? ORDER BY id DESC LIMIT 30",
        (str(cage_id),),
    ).fetchall()

    return jsonify(
        {
            "cage": cage_payload(row),
            "animals": [dict(r) for r in animals],
            "history": [dict(r) for r in history],
        }
    )


@app.patch("/api/cages/<int:cage_id>")
@require_auth(("Technician", "PI", "Admin"))
def update_cage(cage_id: int) -> Response:
    payload = request.get_json(force=True)
    row = db().execute("SELECT * FROM cages WHERE id = ?", (cage_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    allowed = {
        "maleCount": "male_count",
        "femaleCount": "female_count",
        "breedingStatus": "breeding_status",
        "notes": "notes",
        "genotypeSummary": "genotype_summary",
    }
    updates = {}
    for api_field, db_field in allowed.items():
        if api_field in payload:
            updates[db_field] = payload[api_field]

    if not updates:
        return jsonify({"error": "No changes supplied"}), 400

    before = dict(row)
    updates["updated_at"] = now_iso()
    set_sql = ", ".join([f"{k} = ?" for k in updates])
    params = list(updates.values()) + [cage_id]
    db().execute(f"UPDATE cages SET {set_sql} WHERE id = ?", params)
    db().commit()

    after = dict(db().execute("SELECT * FROM cages WHERE id = ?", (cage_id,)).fetchone())
    audit_log(g.user.user_id, "cage", cage_id, "update", before, after)
    return jsonify({"ok": True})


@app.post("/api/cages")
@require_auth(("PI", "Admin"))
def create_cage() -> Response:
    payload = request.get_json(force=True)
    cage_code = payload["cageCode"].strip()
    strain = payload.get("strain", "Unknown")
    genotype = payload.get("genotypeSummary", "Unknown")
    breeding_status = payload.get("breedingStatus", "Holding")
    dob = payload.get("dob")
    male_count = int(payload.get("maleCount", 0))
    female_count = int(payload.get("femaleCount", 0))
    room_id = int(payload.get("roomId", 1))
    rack_id = int(payload.get("rackId", 1))
    lab_id = int(payload.get("labId", g.user.lab_id or 1))
    protocol_id = int(payload.get("protocolId", 1))

    cur = db().execute(
        """
        INSERT INTO cages (
            cage_code, strain, genotype_summary, breeding_status, dob, male_count, female_count,
            room_id, rack_id, lab_id, protocol_id, qr_token, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cage_code,
            strain,
            genotype,
            breeding_status,
            dob,
            male_count,
            female_count,
            room_id,
            rack_id,
            lab_id,
            protocol_id,
            secrets.token_urlsafe(12),
            now_iso(),
            now_iso(),
        ),
    )
    db().commit()
    cage_id = cur.lastrowid
    audit_log(g.user.user_id, "cage", cage_id, "create", None, payload)
    return jsonify({"id": cage_id}), 201


@app.get("/api/scan/<code>")
@require_auth()
def scan_cage(code: str) -> Response:
    started = datetime.now(UTC)
    row = db().execute(
        """
        SELECT c.*, r.name AS room_name, k.name AS rack_name, l.name AS lab_name, p.protocol_number
        FROM cages c
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        WHERE c.cage_code = ? OR c.qr_token = ?
        """,
        (code, code),
    ).fetchone()
    if not row:
        return jsonify({"error": "Cage not found"}), 404
    elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return jsonify({"cage": cage_payload(row), "lookupMs": elapsed_ms})


@app.get("/api/public/scan/<token>")
def public_scan(token: str) -> Response:
    row = db().execute(
        """
        SELECT c.*, r.name AS room_name, k.name AS rack_name, l.name AS lab_name, p.protocol_number
        FROM cages c
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        WHERE c.qr_token = ?
        """,
        (token,),
    ).fetchone()
    if not row:
        return jsonify({"error": "Cage not found"}), 404
    return jsonify({"cage": cage_payload(row)})


@app.post("/api/cages/<int:cage_id>/wean")
@require_auth(("Technician", "PI", "Admin"))
def wean(cage_id: int) -> Response:
    payload = request.get_json(force=True)
    male = int(payload.get("male", 0))
    female = int(payload.get("female", 0))
    date = payload.get("date", datetime.now(UTC).date().isoformat())

    cur = db().execute(
        "INSERT INTO lifecycle_events (cage_id, event_type, details_json, event_date, created_by, created_at) VALUES (?, 'weaning', ?, ?, ?, ?)",
        (cage_id, json.dumps({"male": male, "female": female}), date, g.user.user_id, now_iso()),
    )
    db().execute(
        "UPDATE cages SET male_count = male_count + ?, female_count = female_count + ?, updated_at = ? WHERE id = ?",
        (male, female, now_iso(), cage_id),
    )
    db().commit()
    audit_log(g.user.user_id, "lifecycle_event", cur.lastrowid, "wean", None, {"cage_id": cage_id, "male": male, "female": female})
    return jsonify({"ok": True})


@app.post("/api/cages/<int:cage_id>/transfer")
@require_auth(("Technician", "PI", "Admin"))
def transfer(cage_id: int) -> Response:
    payload = request.get_json(force=True)
    target_room_id = int(payload["roomId"])
    target_rack_id = int(payload["rackId"])

    before = db().execute("SELECT room_id, rack_id FROM cages WHERE id = ?", (cage_id,)).fetchone()
    if not before:
        return jsonify({"error": "Not found"}), 404
    db().execute(
        "UPDATE cages SET room_id = ?, rack_id = ?, updated_at = ? WHERE id = ?",
        (target_room_id, target_rack_id, now_iso(), cage_id),
    )
    db().execute(
        "INSERT INTO lifecycle_events (cage_id, event_type, details_json, event_date, created_by, created_at) VALUES (?, 'transfer', ?, ?, ?, ?)",
        (
            cage_id,
            json.dumps({"fromRoom": before["room_id"], "fromRack": before["rack_id"], "toRoom": target_room_id, "toRack": target_rack_id}),
            datetime.now(UTC).date().isoformat(),
            g.user.user_id,
            now_iso(),
        ),
    )
    db().commit()
    audit_log(g.user.user_id, "cage", cage_id, "transfer", dict(before), {"room_id": target_room_id, "rack_id": target_rack_id})
    return jsonify({"ok": True})


@app.post("/api/cages/<int:cage_id>/note")
@require_auth(("Technician", "PI", "Admin"))
def add_note(cage_id: int) -> Response:
    payload = request.get_json(force=True)
    text = payload.get("text", "").strip()
    if not text:
        return jsonify({"error": "Note cannot be empty"}), 400
    db().execute(
        "INSERT INTO notes (entity_type, entity_id, text, created_by, created_at) VALUES ('cage', ?, ?, ?, ?)",
        (str(cage_id), text, g.user.user_id, now_iso()),
    )
    db().commit()
    audit_log(g.user.user_id, "cage", cage_id, "note", None, {"text": text})
    return jsonify({"ok": True})


@app.post("/api/litters")
@require_auth(("Technician", "PI", "Admin"))
def create_litter() -> Response:
    payload = request.get_json(force=True)
    cage_id = int(payload["cageId"])
    birth_date = payload["birthDate"]
    size = int(payload.get("size", 0))
    survived = int(payload.get("survived", size))

    cur = db().execute(
        "INSERT INTO litters (cage_id, birth_date, litter_size, survived_count, created_at) VALUES (?, ?, ?, ?, ?)",
        (cage_id, birth_date, size, survived, now_iso()),
    )
    litter_id = cur.lastrowid
    count_m = int(payload.get("male", 0))
    count_f = int(payload.get("female", 0))

    for i in range(count_m):
        db().execute(
            "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, created_at, updated_at) VALUES (?, 'M', ?, ?, ?, 'Active', ?, ?, ?, ?)",
            (f"M-{litter_id}-{i+1:03d}", birth_date, payload.get("strain", "Unknown"), payload.get("genotype", "Pending"), cage_id, litter_id, now_iso(), now_iso()),
        )
    for i in range(count_f):
        db().execute(
            "INSERT INTO animals (animal_code, sex, dob, strain, genotype, status, cage_id, litter_id, created_at, updated_at) VALUES (?, 'F', ?, ?, ?, 'Active', ?, ?, ?, ?)",
            (f"F-{litter_id}-{i+1:03d}", birth_date, payload.get("strain", "Unknown"), payload.get("genotype", "Pending"), cage_id, litter_id, now_iso(), now_iso()),
        )

    db().execute(
        "UPDATE cages SET male_count = male_count + ?, female_count = female_count + ?, updated_at = ? WHERE id = ?",
        (count_m, count_f, now_iso(), cage_id),
    )
    db().commit()

    audit_log(g.user.user_id, "litter", litter_id, "create", None, payload)
    return jsonify({"id": litter_id})


@app.post("/api/breeding/events")
@require_auth(("Technician", "PI", "Admin"))
def breeding_event() -> Response:
    payload = request.get_json(force=True)
    cur = db().execute(
        "INSERT INTO breeding_events (cage_id, event_type, event_date, details_json, assigned_to, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            payload["cageId"],
            payload["eventType"],
            payload["eventDate"],
            json.dumps(payload.get("details", {})),
            payload.get("assignedTo"),
            now_iso(),
        ),
    )
    db().commit()
    audit_log(g.user.user_id, "breeding_event", cur.lastrowid, "create", None, payload)
    return jsonify({"id": cur.lastrowid})


@app.get("/api/calendar")
@require_auth()
def calendar() -> Response:
    start = request.args.get("start", datetime.now(UTC).date().isoformat())
    end = request.args.get("end", (datetime.now(UTC).date() + timedelta(days=30)).isoformat())

    events = db().execute(
        """
        SELECT b.id, b.cage_id, c.cage_code, b.event_type, b.event_date, b.assigned_to, b.details_json
        FROM breeding_events b
        JOIN cages c ON b.cage_id = c.id
        WHERE b.event_date BETWEEN ? AND ?
        ORDER BY b.event_date ASC
        """,
        (start, end),
    ).fetchall()
    return jsonify([dict(e) for e in events])


@app.post("/api/genotyping/upload")
@require_auth(("PI", "Admin"))
def genotype_upload() -> Response:
    if "file" not in request.files:
        return jsonify({"error": "Upload a CSV file"}), 400
    f = request.files["file"]
    content = f.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    for row in reader:
        animal_code = row.get("animal_code")
        genotype = row.get("genotype_result")
        if not animal_code or not genotype:
            continue
        animal = db().execute("SELECT id, genotype FROM animals WHERE animal_code = ?", (animal_code,)).fetchone()
        if not animal:
            continue
        db().execute(
            "INSERT INTO genotype_results (animal_id, result, source, created_at) VALUES (?, ?, ?, ?)",
            (animal["id"], genotype, "CSV", now_iso()),
        )
        db().execute("UPDATE animals SET genotype = ?, updated_at = ? WHERE id = ?", (genotype, now_iso(), animal["id"]))
        inserted += 1
    db().commit()
    return jsonify({"updatedAnimals": inserted})


@app.get("/api/analytics/summary")
@require_auth()
def analytics_summary() -> Response:
    total_cages = db().execute("SELECT COUNT(*) AS c FROM cages").fetchone()["c"]
    total_animals = db().execute("SELECT COUNT(*) AS c FROM animals WHERE status = 'Active'").fetchone()["c"]
    sex = db().execute("SELECT sex, COUNT(*) AS c FROM animals WHERE status = 'Active' GROUP BY sex").fetchall()
    sex_map = {r["sex"]: r["c"] for r in sex}

    litters = db().execute("SELECT litter_size, survived_count FROM litters ORDER BY id DESC LIMIT 200").fetchall()
    survival = 0.0
    if litters:
        total_litter_size = sum(r["litter_size"] for r in litters)
        total_survived = sum(r["survived_count"] for r in litters)
        survival = round((total_survived / total_litter_size) * 100, 2) if total_litter_size else 0.0

    room_capacity = db().execute(
        """
        SELECT r.id, r.name, r.capacity, COUNT(c.id) AS occupied
        FROM rooms r
        LEFT JOIN cages c ON c.room_id = r.id
        GROUP BY r.id
        """
    ).fetchall()

    upcoming_tasks = db().execute(
        """
        SELECT b.event_type, b.event_date, c.cage_code
        FROM breeding_events b
        JOIN cages c ON b.cage_id = c.id
        WHERE b.event_date BETWEEN ? AND ?
        ORDER BY b.event_date ASC
        LIMIT 20
        """,
        (datetime.now(UTC).date().isoformat(), (datetime.now(UTC).date() + timedelta(days=14)).isoformat()),
    ).fetchall()

    return jsonify(
        {
            "totalCages": total_cages,
            "totalActiveAnimals": total_animals,
            "sexRatio": {"M": sex_map.get("M", 0), "F": sex_map.get("F", 0)},
            "pupSurvivalPct": survival,
            "roomCapacity": [dict(r) for r in room_capacity],
            "upcomingTasks": [dict(r) for r in upcoming_tasks],
        }
    )


@app.post("/api/forecast/demand")
@require_auth(("PI", "Admin"))
def forecast() -> Response:
    payload = request.get_json(force=True)
    needed_by = payload.get("neededBy")
    requested = int(payload.get("animalsNeeded", 0))
    active = db().execute("SELECT COUNT(*) AS c FROM animals WHERE status = 'Active'").fetchone()["c"]
    deficit = max(requested - active, 0)

    avg_litter_survival = db().execute(
        "SELECT AVG(CAST(survived_count AS FLOAT) / NULLIF(litter_size, 0)) AS v FROM litters"
    ).fetchone()["v"]
    avg_litter_survival = float(avg_litter_survival) if avg_litter_survival else 0.75
    expected_per_litter = max(int(round(6 * avg_litter_survival)), 1)

    litters_required = (deficit + expected_per_litter - 1) // expected_per_litter
    return jsonify(
        {
            "neededBy": needed_by,
            "requested": requested,
            "activeNow": active,
            "deficit": deficit,
            "estimatedLittersRequired": litters_required,
            "assumptions": {
                "baselinePupsPerLitter": 6,
                "avgSurvivalFraction": round(avg_litter_survival, 2),
            },
        }
    )


@app.post("/api/import/excel")
@require_auth(("Admin",))
def import_excel() -> Response:
    if "file" not in request.files:
        return jsonify({"error": "File missing"}), 400

    from openpyxl import load_workbook

    wb = load_workbook(request.files["file"], data_only=True)
    ws = wb.active

    created = 0
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        cage_code, strain, genotype, breeding_status, male, female = row[:6]
        if not cage_code:
            continue
        try:
            db().execute(
                """
                INSERT INTO cages (
                    cage_code, strain, genotype_summary, breeding_status, male_count, female_count,
                    room_id, rack_id, lab_id, protocol_id, qr_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 1, 1, ?, ?, ?)
                """,
                (
                    str(cage_code),
                    str(strain or "Unknown"),
                    str(genotype or "Unknown"),
                    str(breeding_status or "Holding"),
                    int(male or 0),
                    int(female or 0),
                    secrets.token_urlsafe(12),
                    now_iso(),
                    now_iso(),
                ),
            )
            created += 1
        except sqlite3.IntegrityError:
            app.logger.warning("Skipping duplicate cage code row %s", idx)
    db().commit()
    audit_log(g.user.user_id, "import", "excel", "bulk_import", None, {"created": created})
    return jsonify({"created": created})


@app.get("/api/reports/cages.csv")
@require_auth()
def report_cages_csv() -> Response:
    rows = db().execute(
        "SELECT cage_code, strain, genotype_summary, breeding_status, male_count, female_count, dob FROM cages ORDER BY cage_code"
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["cage_code", "strain", "genotype", "status", "male", "female", "dob"])
    for r in rows:
        writer.writerow([r["cage_code"], r["strain"], r["genotype_summary"], r["breeding_status"], r["male_count"], r["female_count"], r["dob"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=cages_report.csv"})


@app.get("/api/reports/cages.xlsx")
@require_auth()
def report_cages_xlsx() -> Response:
    rows = db().execute(
        "SELECT cage_code, strain, genotype_summary, breeding_status, male_count, female_count, dob FROM cages ORDER BY cage_code"
    ).fetchall()
    wb = Workbook()
    ws = wb.active
    ws.title = "Cages"
    ws.append(["cage_code", "strain", "genotype", "status", "male", "female", "dob"])
    for r in rows:
        ws.append([r["cage_code"], r["strain"], r["genotype_summary"], r["breeding_status"], r["male_count"], r["female_count"], r["dob"]])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(
        bio,
        as_attachment=True,
        download_name="cages_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/reports/cages.pdf")
@require_auth()
def report_cages_pdf() -> Response:
    rows = db().execute(
        "SELECT cage_code, strain, genotype_summary, breeding_status, male_count, female_count, dob FROM cages ORDER BY cage_code"
    ).fetchall()
    lines = [f"Murisphere Cage Report - generated {datetime.now(UTC).date().isoformat()}", ""]
    for r in rows:
        lines.append(
            f"{r['cage_code']} | {r['strain']} | {r['genotype_summary']} | {r['breeding_status']} | M:{r['male_count']} F:{r['female_count']} | DOB:{r['dob']}"
        )
    return Response(simple_pdf(lines), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=cages_report.pdf"})


@app.post("/api/cages/cards")
@require_auth()
def cage_cards() -> Response:
    payload = request.get_json(force=True)
    ids = payload.get("ids", [])
    if not ids:
        return jsonify({"error": "Provide at least one cage ID"}), 400
    placeholders = ",".join("?" for _ in ids)
    rows = db().execute(
        f"""
        SELECT c.id, c.cage_code, c.strain, c.genotype_summary, c.breeding_status, c.dob,
               c.male_count, c.female_count, l.name AS lab_name, p.protocol_number,
               r.name AS room_name, k.name AS rack_name, c.qr_token
        FROM cages c
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        WHERE c.id IN ({placeholders})
        """,
        ids,
    ).fetchall()

    cards = []
    for r in rows:
        cards.append(
            {
                "cageId": r["id"],
                "cageCode": r["cage_code"],
                "strain": r["strain"],
                "genotype": r["genotype_summary"],
                "piLab": r["lab_name"],
                "breedingStatus": r["breeding_status"],
                "dob": r["dob"],
                "animalCount": {"M": r["male_count"], "F": r["female_count"]},
                "protocol": r["protocol_number"],
                "location": f"{r['room_name']} / {r['rack_name']}",
                "qrValue": r["qr_token"],
                "scanUrl": f"/scan/{r['qr_token']}",
            }
        )
    return jsonify(cards)


@app.get("/api/compliance/protocol-alerts")
@require_auth()
def protocol_alerts() -> Response:
    cutoff = (datetime.now(UTC).date() + timedelta(days=45)).isoformat()
    rows = db().execute(
        "SELECT protocol_number, title, expires_on FROM iacuc_protocols WHERE expires_on <= ? ORDER BY expires_on ASC",
        (cutoff,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/facility/capacity")
@require_auth(("Admin", "PI"))
def facility_capacity() -> Response:
    rooms = db().execute(
        """
        SELECT r.id, r.name, r.capacity,
               COUNT(c.id) AS occupied,
               ROUND((COUNT(c.id) * 100.0) / NULLIF(r.capacity, 0), 2) AS utilization_pct
        FROM rooms r
        LEFT JOIN cages c ON c.room_id = r.id
        GROUP BY r.id
        ORDER BY utilization_pct DESC
        """
    ).fetchall()
    return jsonify([dict(r) for r in rooms])


@app.get("/api/audit")
@require_auth(("Admin", "PI"))
def audit_list() -> Response:
    rows = db().execute(
        """
        SELECT a.id, u.full_name AS actor, a.entity_type, a.entity_id, a.action, a.created_at
        FROM audit_logs a
        LEFT JOIN users u ON a.actor_user_id = u.id
        ORDER BY a.id DESC
        LIMIT 250
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
