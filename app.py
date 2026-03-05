from __future__ import annotations

import csv
import hashlib
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
import qrcode
from barcode import Code128
from barcode.writer import SVGWriter

APP_NAME = "Murisphere"
DB_PATH = os.getenv("MURISPHERE_DB", "murisphere.db")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MURISPHERE_MAX_UPLOAD_BYTES", "5242880"))


@dataclass
class AuthContext:
    user_id: int
    email: str
    full_name: str
    role: str
    lab_id: int | None


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        token = request.cookies.get("murisphere_session", "").strip()
    if not token:
        return None
    row = db().execute(
        """
        SELECT u.id, u.email, u.full_name, u.role, u.lab_id
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token_digest(token), now_iso()),
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


def is_admin(user: AuthContext) -> bool:
    return user.role == "Admin"


def ensure_cage_scope(cage_id: int, user: AuthContext) -> sqlite3.Row | None:
    if is_admin(user):
        return db().execute("SELECT * FROM cages WHERE id = ?", (cage_id,)).fetchone()
    if user.lab_id is None:
        return None
    return db().execute("SELECT * FROM cages WHERE id = ? AND lab_id = ?", (cage_id, user.lab_id)).fetchone()


def ensure_project_scope(project_id: int, user: AuthContext) -> sqlite3.Row | None:
    if is_admin(user):
        return db().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if user.lab_id is None:
        return None
    return db().execute("SELECT * FROM projects WHERE id = ? AND lab_id = ?", (project_id, user.lab_id)).fetchone()


def cage_protocol_expired(cage_id: int) -> tuple[bool, str | None]:
    row = db().execute(
        """
        SELECT p.protocol_number, p.expires_on
        FROM cages c
        LEFT JOIN iacuc_protocols p ON p.id = c.protocol_id
        WHERE c.id = ?
        """,
        (cage_id,),
    ).fetchone()
    if not row or not row["expires_on"]:
        return False, None
    expired = row["expires_on"] < datetime.now(UTC).date().isoformat()
    if not expired:
        return False, None
    return True, f"Protocol {row['protocol_number']} expired on {row['expires_on']}"


def require_nonexpired_protocol(cage_id: int) -> Response | None:
    expired, msg = cage_protocol_expired(cage_id)
    if expired:
        return jsonify({"error": msg, "code": "PROTOCOL_EXPIRED"}), 409
    return None


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


@app.errorhandler(413)
def too_large(_err: Exception) -> Response:
    return jsonify({"error": "Upload too large"}), 413


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
        (token_digest(token), row["id"], expires_at, now_iso()),
    )
    db().commit()

    resp = jsonify(
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
    resp.set_cookie(
        "murisphere_session",
        token,
        httponly=True,
        secure=os.getenv("MURISPHERE_COOKIE_SECURE", "0") == "1",
        samesite="Lax",
        max_age=12 * 60 * 60,
    )
    return resp


@app.post("/api/auth/logout")
@require_auth()
def logout() -> Response:
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        token = request.cookies.get("murisphere_session", "").strip()
    if token:
        db().execute("DELETE FROM sessions WHERE token = ?", (token_digest(token),))
    db().commit()
    resp = jsonify({"ok": True})
    resp.delete_cookie("murisphere_session")
    return resp


@app.get("/api/auth/me")
@require_auth()
def me() -> Response:
    user = g.user
    return jsonify({"id": user.user_id, "email": user.email, "fullName": user.full_name, "role": user.role, "labId": user.lab_id})


@app.get("/api/projects")
@require_auth()
def list_projects() -> Response:
    params: tuple[Any, ...] = ()
    query = """
        SELECT p.id, p.lab_id, p.project_code, p.title, p.status, p.target_animals, p.created_at,
               l.name AS lab_name,
               COUNT(pc.cage_id) AS assigned_cages
        FROM projects p
        JOIN labs l ON l.id = p.lab_id
        LEFT JOIN project_cages pc ON pc.project_id = p.id
    """
    if not is_admin(g.user):
        query += " WHERE p.lab_id = ? "
        params = (g.user.lab_id,)
    query += " GROUP BY p.id ORDER BY p.created_at DESC LIMIT 500"
    rows = db().execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/projects")
@require_auth(("PI", "Admin"))
def create_project() -> Response:
    payload = request.get_json(force=True)
    project_code = str(payload.get("projectCode", "")).strip()
    title = str(payload.get("title", "")).strip()
    if not project_code or not title:
        return jsonify({"error": "projectCode and title are required"}), 400
    status = str(payload.get("status", "active")).strip() or "active"
    target_animals = int(payload.get("targetAnimals", 0))
    if target_animals < 0:
        return jsonify({"error": "targetAnimals cannot be negative"}), 400

    lab_id = int(payload.get("labId", g.user.lab_id or 1))
    if not is_admin(g.user) and g.user.lab_id != lab_id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        cur = db().execute(
            "INSERT INTO projects (lab_id, project_code, title, status, target_animals, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (lab_id, project_code, title, status, target_animals, now_iso()),
        )
        db().commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "projectCode must be unique"}), 409

    project_id = cur.lastrowid
    audit_log(g.user.user_id, "project", project_id, "create", None, payload)
    return jsonify({"id": project_id}), 201


@app.patch("/api/projects/<int:project_id>")
@require_auth(("PI", "Admin"))
def update_project(project_id: int) -> Response:
    payload = request.get_json(force=True)
    row = ensure_project_scope(project_id, g.user)
    if not row:
        return jsonify({"error": "Not found"}), 404

    allowed = {
        "title": "title",
        "status": "status",
        "targetAnimals": "target_animals",
    }
    updates = {}
    for api_field, db_field in allowed.items():
        if api_field in payload:
            updates[db_field] = payload[api_field]
    if "target_animals" in updates and int(updates["target_animals"]) < 0:
        return jsonify({"error": "targetAnimals cannot be negative"}), 400
    if not updates:
        return jsonify({"error": "No changes supplied"}), 400

    before = dict(row)
    set_sql = ", ".join([f"{k} = ?" for k in updates])
    params = list(updates.values()) + [project_id]
    db().execute(f"UPDATE projects SET {set_sql} WHERE id = ?", params)
    db().commit()
    after = dict(db().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
    audit_log(g.user.user_id, "project", project_id, "update", before, after)
    return jsonify({"ok": True})


@app.get("/api/projects/<int:project_id>/cages")
@require_auth()
def project_cages(project_id: int) -> Response:
    project = ensure_project_scope(project_id, g.user)
    if not project:
        return jsonify({"error": "Not found"}), 404
    rows = db().execute(
        """
        SELECT c.id, c.cage_code, c.strain, c.genotype_summary, c.breeding_status, c.male_count, c.female_count
        FROM project_cages pc
        JOIN cages c ON c.id = pc.cage_id
        WHERE pc.project_id = ?
        ORDER BY c.cage_code
        """,
        (project_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/projects/<int:project_id>/assign-cages")
@require_auth(("PI", "Admin"))
def assign_project_cages(project_id: int) -> Response:
    project = ensure_project_scope(project_id, g.user)
    if not project:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(force=True)
    cage_ids = payload.get("cageIds", [])
    if not cage_ids:
        return jsonify({"error": "Provide cageIds"}), 400

    assigned = 0
    for raw_id in cage_ids:
        cage_id = int(raw_id)
        cage = ensure_cage_scope(cage_id, g.user)
        if not cage:
            continue
        if int(cage["lab_id"]) != int(project["lab_id"]):
            continue
        try:
            db().execute(
                "INSERT INTO project_cages (project_id, cage_id, assigned_at) VALUES (?, ?, ?)",
                (project_id, cage_id, now_iso()),
            )
            assigned += 1
        except sqlite3.IntegrityError:
            continue
    db().commit()
    audit_log(g.user.user_id, "project", project_id, "assign_cages", None, {"cageIds": cage_ids, "assigned": assigned})
    return jsonify({"assigned": assigned})


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
    if not is_admin(g.user):
        clauses.append("c.lab_id = ?")
        params.append(g.user.lab_id)

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
    scope_clause = "" if is_admin(g.user) else "AND c.lab_id = ?"
    params: list[Any] = [cage_id]
    if not is_admin(g.user):
        params.append(g.user.lab_id)
    row = db().execute(
        """
        SELECT c.*, r.name AS room_name, k.name AS rack_name, l.name AS lab_name, p.protocol_number
        FROM cages c
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        WHERE c.id = ?
        """
        + scope_clause,
        params,
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
    row = ensure_cage_scope(cage_id, g.user)
    if not row:
        return jsonify({"error": "Not found"}), 404
    blocked = require_nonexpired_protocol(cage_id)
    if blocked:
        return blocked

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

    if "male_count" in updates and int(updates["male_count"]) < 0:
        return jsonify({"error": "maleCount cannot be negative"}), 400
    if "female_count" in updates and int(updates["female_count"]) < 0:
        return jsonify({"error": "femaleCount cannot be negative"}), 400

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
    if male_count < 0 or female_count < 0:
        return jsonify({"error": "Counts cannot be negative"}), 400
    room_id = int(payload.get("roomId", 1))
    rack_id = int(payload.get("rackId", 1))
    lab_id = int(payload.get("labId", g.user.lab_id or 1))
    if not is_admin(g.user) and g.user.lab_id != lab_id:
        return jsonify({"error": "Forbidden"}), 403
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
    scope_clause = "" if is_admin(g.user) else " AND c.lab_id = ?"
    params: list[Any] = [code, code]
    if not is_admin(g.user):
        params.append(g.user.lab_id)
    row = db().execute(
        """
        SELECT c.*, r.name AS room_name, k.name AS rack_name, l.name AS lab_name, p.protocol_number
        FROM cages c
        LEFT JOIN rooms r ON c.room_id = r.id
        LEFT JOIN racks k ON c.rack_id = k.id
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN iacuc_protocols p ON c.protocol_id = p.id
        WHERE (c.cage_code = ? OR c.qr_token = ?)
        """
        + scope_clause
        + """
        """,
        params,
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
    return jsonify(
        {
            "cage": {
                "id": row["id"],
                "cageCode": row["cage_code"],
                "strain": row["strain"],
                "breedingStatus": row["breeding_status"],
                "maleCount": row["male_count"],
                "femaleCount": row["female_count"],
                "room": row["room_name"],
                "rack": row["rack_name"],
                "lab": row["lab_name"],
                "updatedAt": row["updated_at"],
            }
        }
    )


@app.get("/api/assets/qrcode.png")
def qrcode_asset() -> Response:
    value = request.args.get("v", "").strip()
    if not value:
        return jsonify({"error": "Missing query parameter: v"}), 400
    if len(value) > 2048:
        return jsonify({"error": "Value too long"}), 400

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0f2027", back_color="#ffffff")
    bio = io.BytesIO()
    image.save(bio, format="PNG")
    bio.seek(0)
    return send_file(bio, mimetype="image/png")


@app.get("/api/assets/barcode.svg")
def barcode_asset() -> Response:
    value = request.args.get("v", "").strip()
    if not value:
        return jsonify({"error": "Missing query parameter: v"}), 400
    if len(value) > 80:
        return jsonify({"error": "Value too long"}), 400

    code = Code128(value, writer=SVGWriter())
    svg_payload = code.render(
        writer_options={
            "module_width": 0.28,
            "module_height": 14.0,
            "quiet_zone": 1.0,
            "font_size": 8,
            "text_distance": 1.0,
            "write_text": True,
        }
    )
    return Response(svg_payload, mimetype="image/svg+xml")


@app.post("/api/cages/<int:cage_id>/wean")
@require_auth(("Technician", "PI", "Admin"))
def wean(cage_id: int) -> Response:
    payload = request.get_json(force=True)
    male = int(payload.get("male", 0))
    female = int(payload.get("female", 0))
    date = payload.get("date", datetime.now(UTC).date().isoformat())
    if male < 0 or female < 0:
        return jsonify({"error": "Counts cannot be negative"}), 400
    if not ensure_cage_scope(cage_id, g.user):
        return jsonify({"error": "Not found"}), 404
    blocked = require_nonexpired_protocol(cage_id)
    if blocked:
        return blocked

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

    scoped = ensure_cage_scope(cage_id, g.user)
    if not scoped:
        return jsonify({"error": "Not found"}), 404
    blocked = require_nonexpired_protocol(cage_id)
    if blocked:
        return blocked
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
    if not ensure_cage_scope(cage_id, g.user):
        return jsonify({"error": "Not found"}), 404
    blocked = require_nonexpired_protocol(cage_id)
    if blocked:
        return blocked
    if not text:
        return jsonify({"error": "Note cannot be empty"}), 400
    db().execute(
        "INSERT INTO notes (entity_type, entity_id, text, created_by, created_at) VALUES ('cage', ?, ?, ?, ?)",
        (str(cage_id), text, g.user.user_id, now_iso()),
    )
    db().commit()
    audit_log(g.user.user_id, "cage", cage_id, "note", None, {"text": text})
    return jsonify({"ok": True})


@app.post("/api/cages/bulk-actions")
@require_auth(("PI", "Admin"))
def bulk_cage_actions() -> Response:
    payload = request.get_json(force=True)
    action = str(payload.get("action", "")).strip()
    cage_ids = payload.get("cageIds", [])
    if action not in {"retire_breeders", "transfer"}:
        return jsonify({"error": "Unsupported action"}), 400
    if not cage_ids:
        return jsonify({"error": "Provide cageIds"}), 400

    updated = 0
    if action == "retire_breeders":
        for raw_id in cage_ids:
            cage_id = int(raw_id)
            row = ensure_cage_scope(cage_id, g.user)
            if not row:
                continue
            blocked = require_nonexpired_protocol(cage_id)
            if blocked:
                continue
            before = dict(row)
            db().execute(
                "UPDATE cages SET breeding_status = 'Retired', updated_at = ? WHERE id = ?",
                (now_iso(), cage_id),
            )
            db().execute(
                "INSERT INTO lifecycle_events (cage_id, event_type, details_json, event_date, created_by, created_at) VALUES (?, 'retire', ?, ?, ?, ?)",
                (cage_id, json.dumps({"reason": payload.get("reason", "bulk_retire")}), datetime.now(UTC).date().isoformat(), g.user.user_id, now_iso()),
            )
            updated += 1
            audit_log(g.user.user_id, "cage", cage_id, "retire", before, {"breeding_status": "Retired"})
    else:
        room_id = int(payload.get("roomId", 0))
        rack_id = int(payload.get("rackId", 0))
        if room_id <= 0 or rack_id <= 0:
            return jsonify({"error": "roomId and rackId are required for transfer"}), 400
        for raw_id in cage_ids:
            cage_id = int(raw_id)
            row = ensure_cage_scope(cage_id, g.user)
            if not row:
                continue
            blocked = require_nonexpired_protocol(cage_id)
            if blocked:
                continue
            before = {"room_id": row["room_id"], "rack_id": row["rack_id"]}
            db().execute(
                "UPDATE cages SET room_id = ?, rack_id = ?, updated_at = ? WHERE id = ?",
                (room_id, rack_id, now_iso(), cage_id),
            )
            db().execute(
                "INSERT INTO lifecycle_events (cage_id, event_type, details_json, event_date, created_by, created_at) VALUES (?, 'transfer', ?, ?, ?, ?)",
                (
                    cage_id,
                    json.dumps({"fromRoom": row["room_id"], "fromRack": row["rack_id"], "toRoom": room_id, "toRack": rack_id}),
                    datetime.now(UTC).date().isoformat(),
                    g.user.user_id,
                    now_iso(),
                ),
            )
            updated += 1
            audit_log(g.user.user_id, "cage", cage_id, "transfer", before, {"room_id": room_id, "rack_id": rack_id})
    db().commit()
    return jsonify({"updated": updated})


@app.post("/api/litters")
@require_auth(("Technician", "PI", "Admin"))
def create_litter() -> Response:
    payload = request.get_json(force=True)
    cage_id = int(payload["cageId"])
    birth_date = payload["birthDate"]
    size = int(payload.get("size", 0))
    survived = int(payload.get("survived", size))
    if size < 0 or survived < 0:
        return jsonify({"error": "Litter counts cannot be negative"}), 400
    if not ensure_cage_scope(cage_id, g.user):
        return jsonify({"error": "Not found"}), 404
    blocked = require_nonexpired_protocol(cage_id)
    if blocked:
        return blocked

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
    cage_id = int(payload["cageId"])
    if not ensure_cage_scope(cage_id, g.user):
        return jsonify({"error": "Not found"}), 404
    blocked = require_nonexpired_protocol(cage_id)
    if blocked:
        return blocked
    cur = db().execute(
        "INSERT INTO breeding_events (cage_id, event_type, event_date, details_json, assigned_to, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            cage_id,
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

    scope_clause = ""
    params: list[Any] = [start, end]
    if not is_admin(g.user):
        scope_clause = " AND c.lab_id = ?"
        params.append(g.user.lab_id)
    events = db().execute(
        """
        SELECT b.id, b.cage_id, c.cage_code, b.event_type, b.event_date, b.assigned_to, b.details_json
        FROM breeding_events b
        JOIN cages c ON b.cage_id = c.id
        WHERE b.event_date BETWEEN ? AND ?
        """
        + scope_clause
        + """
        ORDER BY b.event_date ASC
        """,
        params,
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
        if not is_admin(g.user):
            scoped = db().execute(
                """
                SELECT a.id
                FROM animals a
                JOIN cages c ON c.id = a.cage_id
                WHERE a.id = ? AND c.lab_id = ?
                """,
                (animal["id"], g.user.lab_id),
            ).fetchone()
            if not scoped:
                continue
        db().execute(
            "INSERT INTO genotype_results (animal_id, result, source, created_at) VALUES (?, ?, ?, ?)",
            (animal["id"], genotype, "CSV", now_iso()),
        )
        db().execute("UPDATE animals SET genotype = ?, updated_at = ? WHERE id = ?", (genotype, now_iso(), animal["id"]))
        inserted += 1
    db().commit()
    return jsonify({"updatedAnimals": inserted})


@app.get("/api/animals")
@require_auth()
def list_animals() -> Response:
    q = request.args.get("q", "").strip()
    sex = request.args.get("sex", "").strip()
    status = request.args.get("status", "").strip()
    genotype = request.args.get("genotype", "").strip()

    clauses = ["1 = 1"]
    params: list[Any] = []
    if q:
        clauses.append("(a.animal_code LIKE ? OR a.strain LIKE ? OR COALESCE(a.genotype, '') LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if sex:
        clauses.append("a.sex = ?")
        params.append(sex)
    if status:
        clauses.append("a.status = ?")
        params.append(status)
    if genotype:
        clauses.append("COALESCE(a.genotype, '') LIKE ?")
        params.append(f"%{genotype}%")
    if not is_admin(g.user):
        clauses.append("c.lab_id = ?")
        params.append(g.user.lab_id)

    rows = db().execute(
        f"""
        SELECT a.id, a.animal_code, a.sex, a.dob, a.strain, a.genotype, a.status, a.cage_id, c.cage_code
        FROM animals a
        LEFT JOIN cages c ON c.id = a.cage_id
        WHERE {' AND '.join(clauses)}
        ORDER BY a.id DESC
        LIMIT 1000
        """,
        params,
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/animals/<int:animal_id>/pedigree")
@require_auth()
def animal_pedigree(animal_id: int) -> Response:
    generations = max(1, min(int(request.args.get("generations", 3)), 6))
    root = db().execute(
        """
        SELECT a.id, a.animal_code, a.sex, a.dob, a.strain, a.genotype, a.status, a.sire_id, a.dam_id
        FROM animals a
        LEFT JOIN cages c ON c.id = a.cage_id
        WHERE a.id = ?
        """
        + ("" if is_admin(g.user) else " AND c.lab_id = ? "),
        (animal_id,) if is_admin(g.user) else (animal_id, g.user.lab_id),
    ).fetchone()
    if not root:
        return jsonify({"error": "Not found"}), 404

    queue: list[tuple[int, int]] = [(animal_id, 0)]
    seen: set[int] = set()
    nodes: dict[int, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    while queue:
        aid, depth = queue.pop(0)
        if aid in seen or depth > generations:
            continue
        seen.add(aid)
        row = db().execute(
            "SELECT id, animal_code, sex, dob, strain, genotype, status, sire_id, dam_id FROM animals WHERE id = ?",
            (aid,),
        ).fetchone()
        if not row:
            continue
        nodes[aid] = dict(row)
        if depth == generations:
            continue
        for rel, pid in (("sire", row["sire_id"]), ("dam", row["dam_id"])):
            if pid:
                edges.append({"from": aid, "to": pid, "relation": rel})
                queue.append((int(pid), depth + 1))

    return jsonify({"rootId": animal_id, "generations": generations, "nodes": list(nodes.values()), "edges": edges})


@app.get("/api/breeding/productivity")
@require_auth()
def breeding_productivity() -> Response:
    min_litters = int(request.args.get("minLitters", 0))
    scope = ""
    params: list[Any] = []
    if not is_admin(g.user):
        scope = " WHERE c.lab_id = ? "
        params.append(g.user.lab_id)

    rows = db().execute(
        f"""
        SELECT c.id AS cage_id, c.cage_code, c.breeding_status,
               COUNT(l.id) AS litter_count,
               COALESCE(AVG(l.survived_count), 0) AS avg_survived,
               MAX(l.birth_date) AS last_litter_date
        FROM cages c
        LEFT JOIN litters l ON l.cage_id = c.id
        {scope}
        GROUP BY c.id
        HAVING COUNT(l.id) >= ?
        ORDER BY litter_count DESC, avg_survived DESC
        LIMIT 500
        """,
        params + [min_litters],
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/breeding/non-productive")
@require_auth()
def breeding_non_productive() -> Response:
    stale_days = int(request.args.get("staleDays", 45))
    cutoff = (datetime.now(UTC).date() - timedelta(days=stale_days)).isoformat()

    params: list[Any] = []
    scope = ""
    if not is_admin(g.user):
        scope = " AND c.lab_id = ? "
        params.append(g.user.lab_id)
    params.append(cutoff)
    rows = db().execute(
        """
        SELECT c.id AS cage_id, c.cage_code, c.breeding_status, MAX(l.birth_date) AS last_litter_date, COUNT(l.id) AS litter_count
        FROM cages c
        LEFT JOIN litters l ON l.cage_id = c.id
        WHERE c.breeding_status IN ('Breeding', 'Timed Mating', 'Holding')
        """
        + scope
        + """
        GROUP BY c.id
        HAVING (MAX(l.birth_date) IS NULL OR MAX(l.birth_date) < ?)
        ORDER BY last_litter_date ASC
        LIMIT 500
        """,
        params,
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/tasks/reminders")
@require_auth()
def task_reminders() -> Response:
    window_days = int(request.args.get("windowDays", 14))
    today = datetime.now(UTC).date().isoformat()
    horizon = (datetime.now(UTC).date() + timedelta(days=window_days)).isoformat()
    params: list[Any] = [today, horizon]
    scope = ""
    if not is_admin(g.user):
        scope = " AND c.lab_id = ? "
        params.append(g.user.lab_id)
    rows = db().execute(
        """
        SELECT b.id, b.event_type, b.event_date, b.cage_id, c.cage_code, b.assigned_to, u.full_name AS assignee
        FROM breeding_events b
        JOIN cages c ON c.id = b.cage_id
        LEFT JOIN users u ON u.id = b.assigned_to
        WHERE b.event_date <= ?
          AND b.event_date >= ?
        """
        + scope
        + """
        ORDER BY b.event_date ASC
        LIMIT 500
        """,
        [horizon, today] + ([g.user.lab_id] if not is_admin(g.user) else []),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["overdue"] = d["event_date"] < today
        out.append(d)
    return jsonify(out)


@app.get("/api/genotyping/mendelian")
@require_auth()
def mendelian_tracking() -> Response:
    scope = ""
    params: list[Any] = []
    if not is_admin(g.user):
        scope = " AND c.lab_id = ? "
        params.append(g.user.lab_id)

    rows = db().execute(
        """
        SELECT l.id AS litter_id, l.birth_date, c.cage_code, a.genotype, COUNT(a.id) AS n
        FROM litters l
        JOIN cages c ON c.id = l.cage_id
        LEFT JOIN animals a ON a.litter_id = l.id
        WHERE 1 = 1
        """
        + scope
        + """
        GROUP BY l.id, a.genotype
        ORDER BY l.birth_date DESC
        LIMIT 2000
        """,
        params,
    ).fetchall()

    by_litter: dict[int, dict[str, Any]] = {}
    for r in rows:
        lid = r["litter_id"]
        if lid not in by_litter:
            by_litter[lid] = {
                "litterId": lid,
                "birthDate": r["birth_date"],
                "cageCode": r["cage_code"],
                "observed": {},
            }
        gkey = r["genotype"] or "Unknown"
        by_litter[lid]["observed"][gkey] = int(r["n"])

    result = []
    for payload in by_litter.values():
        observed = payload["observed"]
        total = sum(observed.values())
        if total <= 0:
            continue
        expected = {k: round(1.0 / len(observed), 4) for k in observed.keys()}
        observed_ratio = {k: round(v / total, 4) for k, v in observed.items()}
        payload["expectedRatio"] = expected
        payload["observedRatio"] = observed_ratio
        payload["totalGenotyped"] = total
        result.append(payload)
    return jsonify(result)


@app.get("/api/genotyping/alerts")
@require_auth()
def genotyping_alerts() -> Response:
    threshold = float(request.args.get("threshold", 0.25))
    tracked = mendelian_tracking().get_json()
    alerts = []
    for row in tracked:
        max_dev = 0.0
        for gkey, exp in row["expectedRatio"].items():
            obs = row["observedRatio"].get(gkey, 0.0)
            max_dev = max(max_dev, abs(obs - exp))
        if max_dev >= threshold:
            alerts.append(
                {
                    "litterId": row["litterId"],
                    "cageCode": row["cageCode"],
                    "birthDate": row["birthDate"],
                    "maxDeviation": round(max_dev, 4),
                    "threshold": threshold,
                }
            )
    return jsonify(alerts)


@app.get("/api/forecast/cage-space")
@require_auth(("PI", "Admin"))
def forecast_cage_space() -> Response:
    days = int(request.args.get("days", 30))
    if is_admin(g.user):
        rooms = db().execute(
            """
            SELECT r.id, r.name, r.capacity, COUNT(c.id) AS occupied
            FROM rooms r
            LEFT JOIN cages c ON c.room_id = r.id
            GROUP BY r.id
            """
        ).fetchall()
        created_recent = db().execute(
            "SELECT COUNT(*) AS c FROM cages WHERE created_at >= ?",
            ((datetime.now(UTC) - timedelta(days=30)).isoformat(),),
        ).fetchone()["c"]
    else:
        rooms = db().execute(
            """
            SELECT r.id, r.name, r.capacity, SUM(CASE WHEN c.lab_id = ? THEN 1 ELSE 0 END) AS occupied
            FROM rooms r
            LEFT JOIN cages c ON c.room_id = r.id
            GROUP BY r.id
            """,
            (g.user.lab_id,),
        ).fetchall()
        created_recent = db().execute(
            "SELECT COUNT(*) AS c FROM cages WHERE created_at >= ? AND lab_id = ?",
            ((datetime.now(UTC) - timedelta(days=30)).isoformat(), g.user.lab_id),
        ).fetchone()["c"]

    retire_recent = db().execute(
        """
        SELECT COUNT(*) AS c
        FROM lifecycle_events le
        JOIN cages c ON c.id = le.cage_id
        WHERE le.event_type = 'retire' AND le.created_at >= ?
        """
        + ("" if is_admin(g.user) else " AND c.lab_id = ? "),
        ((datetime.now(UTC) - timedelta(days=30)).isoformat(),)
        if is_admin(g.user)
        else ((datetime.now(UTC) - timedelta(days=30)).isoformat(), g.user.lab_id),
    ).fetchone()["c"]

    net_per_day = (created_recent - retire_recent) / 30.0
    out = []
    for r in rooms:
        projected = int(round(r["occupied"] + net_per_day * days))
        out.append(
            {
                "roomId": r["id"],
                "roomName": r["name"],
                "capacity": r["capacity"],
                "occupiedNow": r["occupied"],
                "projectedOccupied": projected,
                "projectedUtilizationPct": round((projected * 100.0) / r["capacity"], 2) if r["capacity"] else None,
            }
        )
    return jsonify({"days": days, "netCageDeltaPerDay": round(net_per_day, 3), "rooms": out})


@app.get("/api/forecast/consolidation")
@require_auth(("PI", "Admin"))
def forecast_consolidation() -> Response:
    max_animals = int(request.args.get("maxAnimals", 2))
    scope = ""
    params: list[Any] = [max_animals]
    if not is_admin(g.user):
        scope = " AND c.lab_id = ? "
        params.append(g.user.lab_id)
    rows = db().execute(
        """
        SELECT c.id, c.cage_code, c.strain, c.genotype_summary, c.room_id, c.rack_id, (c.male_count + c.female_count) AS total_animals
        FROM cages c
        WHERE c.breeding_status = 'Holding'
          AND (c.male_count + c.female_count) <= ?
        """
        + scope
        + """
        ORDER BY c.room_id, c.strain, c.genotype_summary, total_animals ASC
        LIMIT 2000
        """,
        params,
    ).fetchall()

    grouped: dict[tuple[Any, ...], list[sqlite3.Row]] = {}
    for r in rows:
        key = (r["room_id"], r["strain"], r["genotype_summary"])
        grouped.setdefault(key, []).append(r)

    recommendations = []
    for key, candidates in grouped.items():
        while len(candidates) >= 2:
            a = candidates.pop(0)
            b = candidates.pop(0)
            recommendations.append(
                {
                    "roomId": key[0],
                    "strain": key[1],
                    "genotype": key[2],
                    "fromCages": [a["cage_code"], b["cage_code"]],
                    "combinedAnimals": int(a["total_animals"]) + int(b["total_animals"]),
                }
            )
    return jsonify(recommendations)


@app.get("/api/analytics/summary")
@require_auth()
def analytics_summary() -> Response:
    if is_admin(g.user):
        total_cages = db().execute("SELECT COUNT(*) AS c FROM cages").fetchone()["c"]
        total_animals = db().execute("SELECT COUNT(*) AS c FROM animals WHERE status = 'Active'").fetchone()["c"]
        sex = db().execute("SELECT sex, COUNT(*) AS c FROM animals WHERE status = 'Active' GROUP BY sex").fetchall()
    else:
        total_cages = db().execute("SELECT COUNT(*) AS c FROM cages WHERE lab_id = ?", (g.user.lab_id,)).fetchone()["c"]
        total_animals = db().execute(
            """
            SELECT COUNT(*) AS c
            FROM animals a
            JOIN cages c ON c.id = a.cage_id
            WHERE a.status = 'Active' AND c.lab_id = ?
            """,
            (g.user.lab_id,),
        ).fetchone()["c"]
        sex = db().execute(
            """
            SELECT a.sex, COUNT(*) AS c
            FROM animals a
            JOIN cages c ON c.id = a.cage_id
            WHERE a.status = 'Active' AND c.lab_id = ?
            GROUP BY a.sex
            """,
            (g.user.lab_id,),
        ).fetchall()
    sex_map = {r["sex"]: r["c"] for r in sex}

    litters = db().execute("SELECT litter_size, survived_count FROM litters ORDER BY id DESC LIMIT 200").fetchall()
    survival = 0.0
    if litters:
        total_litter_size = sum(r["litter_size"] for r in litters)
        total_survived = sum(r["survived_count"] for r in litters)
        survival = round((total_survived / total_litter_size) * 100, 2) if total_litter_size else 0.0

    if is_admin(g.user):
        room_capacity = db().execute(
            """
            SELECT r.id, r.name, r.capacity, COUNT(c.id) AS occupied
            FROM rooms r
            LEFT JOIN cages c ON c.room_id = r.id
            GROUP BY r.id
            """
        ).fetchall()
    else:
        room_capacity = db().execute(
            """
            SELECT r.id, r.name, r.capacity, SUM(CASE WHEN c.lab_id = ? THEN 1 ELSE 0 END) AS occupied
            FROM rooms r
            LEFT JOIN cages c ON c.room_id = r.id
            GROUP BY r.id
            """,
            (g.user.lab_id,),
        ).fetchall()

    upcoming_tasks = db().execute(
        """
        SELECT b.event_type, b.event_date, c.cage_code
        FROM breeding_events b
        JOIN cages c ON b.cage_id = c.id
        WHERE b.event_date BETWEEN ? AND ?
        """
        + ("" if is_admin(g.user) else " AND c.lab_id = ? ")
        + """
        ORDER BY b.event_date ASC
        LIMIT 20
        """,
        (datetime.now(UTC).date().isoformat(), (datetime.now(UTC).date() + timedelta(days=14)).isoformat())
        if is_admin(g.user)
        else (datetime.now(UTC).date().isoformat(), (datetime.now(UTC).date() + timedelta(days=14)).isoformat(), g.user.lab_id),
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
    if is_admin(g.user):
        active = db().execute("SELECT COUNT(*) AS c FROM animals WHERE status = 'Active'").fetchone()["c"]
    else:
        active = db().execute(
            """
            SELECT COUNT(*) AS c
            FROM animals a
            JOIN cages c ON c.id = a.cage_id
            WHERE a.status = 'Active' AND c.lab_id = ?
            """,
            (g.user.lab_id,),
        ).fetchone()["c"]
    deficit = max(requested - active, 0)

    if is_admin(g.user):
        avg_litter_survival = db().execute(
            "SELECT AVG(CAST(survived_count AS FLOAT) / NULLIF(litter_size, 0)) AS v FROM litters"
        ).fetchone()["v"]
    else:
        avg_litter_survival = db().execute(
            """
            SELECT AVG(CAST(l.survived_count AS FLOAT) / NULLIF(l.litter_size, 0)) AS v
            FROM litters l
            JOIN cages c ON c.id = l.cage_id
            WHERE c.lab_id = ?
            """,
            (g.user.lab_id,),
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
    query = "SELECT cage_code, strain, genotype_summary, breeding_status, male_count, female_count, dob FROM cages"
    params: tuple[Any, ...] = ()
    if not is_admin(g.user):
        query += " WHERE lab_id = ?"
        params = (g.user.lab_id,)
    query += " ORDER BY cage_code"
    rows = db().execute(query, params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["cage_code", "strain", "genotype", "status", "male", "female", "dob"])
    for r in rows:
        writer.writerow([r["cage_code"], r["strain"], r["genotype_summary"], r["breeding_status"], r["male_count"], r["female_count"], r["dob"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=cages_report.csv"})


@app.get("/api/reports/cages.xlsx")
@require_auth()
def report_cages_xlsx() -> Response:
    query = "SELECT cage_code, strain, genotype_summary, breeding_status, male_count, female_count, dob FROM cages"
    params: tuple[Any, ...] = ()
    if not is_admin(g.user):
        query += " WHERE lab_id = ?"
        params = (g.user.lab_id,)
    query += " ORDER BY cage_code"
    rows = db().execute(query, params).fetchall()
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
    query = "SELECT cage_code, strain, genotype_summary, breeding_status, male_count, female_count, dob FROM cages"
    params: tuple[Any, ...] = ()
    if not is_admin(g.user):
        query += " WHERE lab_id = ?"
        params = (g.user.lab_id,)
    query += " ORDER BY cage_code"
    rows = db().execute(query, params).fetchall()
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
    scope_clause = ""
    params: list[Any] = list(ids)
    if not is_admin(g.user):
        scope_clause = " AND c.lab_id = ?"
        params.append(g.user.lab_id)
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
        WHERE c.id IN ({placeholders}) {scope_clause}
        """,
        params,
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
    if is_admin(g.user):
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
    else:
        facility = db().execute(
            """
            SELECT l.facility_id
            FROM labs l
            WHERE l.id = ?
            """,
            (g.user.lab_id,),
        ).fetchone()
        if not facility:
            return jsonify([])
        rooms = db().execute(
            """
            SELECT r.id, r.name, r.capacity,
                   COUNT(c.id) AS occupied,
                   ROUND((COUNT(c.id) * 100.0) / NULLIF(r.capacity, 0), 2) AS utilization_pct
            FROM rooms r
            LEFT JOIN cages c ON c.room_id = r.id
            WHERE r.facility_id = ?
            GROUP BY r.id
            ORDER BY utilization_pct DESC
            """,
            (facility["facility_id"],),
        ).fetchall()
    return jsonify([dict(r) for r in rooms])


@app.get("/api/facilities")
@require_auth(("Admin", "PI"))
def list_facilities() -> Response:
    rows = db().execute(
        """
        SELECT f.id, f.name, f.timezone,
               COUNT(DISTINCT l.id) AS labs,
               COUNT(DISTINCT r.id) AS rooms,
               COUNT(DISTINCT c.id) AS cages
        FROM facilities f
        LEFT JOIN labs l ON l.facility_id = f.id
        LEFT JOIN rooms r ON r.facility_id = f.id
        LEFT JOIN cages c ON c.room_id = r.id
        GROUP BY f.id
        ORDER BY f.name
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/facility/quotas")
@require_auth(("Admin", "PI"))
def facility_quotas() -> Response:
    if is_admin(g.user):
        rows = db().execute(
            """
            SELECT l.id AS lab_id,
                   l.name AS lab_name,
                   COALESCE(lp.size_tier, 'unassigned') AS size_tier,
                   COALESCE(lp.expected_cage_load, 0) AS expected_cage_load,
                   COALESCE(lp.active_project_count, 0) AS expected_active_projects,
                   COUNT(DISTINCT c.id) AS current_cages,
                   COUNT(DISTINCT p.id) AS current_projects
            FROM labs l
            LEFT JOIN lab_profiles lp ON lp.lab_id = l.id
            LEFT JOIN cages c ON c.lab_id = l.id
            LEFT JOIN projects p ON p.lab_id = l.id
            GROUP BY l.id
            ORDER BY current_cages DESC
            """
        ).fetchall()
    else:
        rows = db().execute(
            """
            SELECT l.id AS lab_id,
                   l.name AS lab_name,
                   COALESCE(lp.size_tier, 'unassigned') AS size_tier,
                   COALESCE(lp.expected_cage_load, 0) AS expected_cage_load,
                   COALESCE(lp.active_project_count, 0) AS expected_active_projects,
                   COUNT(DISTINCT c.id) AS current_cages,
                   COUNT(DISTINCT p.id) AS current_projects
            FROM labs l
            LEFT JOIN lab_profiles lp ON lp.lab_id = l.id
            LEFT JOIN cages c ON c.lab_id = l.id
            LEFT JOIN projects p ON p.lab_id = l.id
            WHERE l.id = ?
            GROUP BY l.id
            """,
            (g.user.lab_id,),
        ).fetchall()

    results = []
    for r in rows:
        expected_load = int(r["expected_cage_load"] or 0)
        current = int(r["current_cages"] or 0)
        remaining = expected_load - current
        utilization = round((current * 100.0) / expected_load, 2) if expected_load > 0 else None
        results.append(
            {
                "labId": r["lab_id"],
                "labName": r["lab_name"],
                "sizeTier": r["size_tier"],
                "expectedCageLoad": expected_load,
                "expectedActiveProjects": int(r["expected_active_projects"] or 0),
                "currentCages": current,
                "currentProjects": int(r["current_projects"] or 0),
                "remainingQuota": remaining,
                "utilizationPct": utilization,
            }
        )
    return jsonify(results)


@app.get("/api/facility/chargeback")
@require_auth(("Admin", "PI"))
def facility_chargeback() -> Response:
    period_days = int(request.args.get("periodDays", 30))
    rate_per_cage_day = float(request.args.get("ratePerCageDay", 0.85))
    if is_admin(g.user):
        rows = db().execute(
            """
            SELECT l.id AS lab_id, l.name AS lab_name, COUNT(c.id) AS cage_count
            FROM labs l
            LEFT JOIN cages c ON c.lab_id = l.id
            GROUP BY l.id
            ORDER BY cage_count DESC
            """
        ).fetchall()
    else:
        rows = db().execute(
            """
            SELECT l.id AS lab_id, l.name AS lab_name, COUNT(c.id) AS cage_count
            FROM labs l
            LEFT JOIN cages c ON c.lab_id = l.id
            WHERE l.id = ?
            GROUP BY l.id
            """,
            (g.user.lab_id,),
        ).fetchall()

    out = []
    for r in rows:
        cage_days = int(r["cage_count"]) * period_days
        amount = round(cage_days * rate_per_cage_day, 2)
        out.append(
            {
                "labId": r["lab_id"],
                "labName": r["lab_name"],
                "periodDays": period_days,
                "cageCount": int(r["cage_count"]),
                "cageDays": cage_days,
                "ratePerCageDay": rate_per_cage_day,
                "estimatedCharge": amount,
            }
        )
    return jsonify(out)


@app.get("/api/reports/breeder-productivity.csv")
@require_auth(("PI", "Admin"))
def report_breeder_productivity() -> Response:
    rows = breeding_productivity().get_json()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["cage_code", "breeding_status", "litter_count", "avg_survived", "last_litter_date"])
    for r in rows:
        writer.writerow([r["cage_code"], r["breeding_status"], r["litter_count"], r["avg_survived"], r["last_litter_date"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=breeder_productivity.csv"})


@app.get("/api/reports/survival.csv")
@require_auth(("PI", "Admin"))
def report_survival() -> Response:
    query = "SELECT l.id, l.birth_date, l.litter_size, l.survived_count, c.cage_code FROM litters l JOIN cages c ON c.id = l.cage_id"
    params: tuple[Any, ...] = ()
    if not is_admin(g.user):
        query += " WHERE c.lab_id = ?"
        params = (g.user.lab_id,)
    query += " ORDER BY l.birth_date DESC LIMIT 2000"
    rows = db().execute(query, params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["litter_id", "birth_date", "cage_code", "litter_size", "survived_count", "survival_pct"])
    for r in rows:
        pct = round((r["survived_count"] * 100.0) / r["litter_size"], 2) if r["litter_size"] else 0.0
        writer.writerow([r["id"], r["birth_date"], r["cage_code"], r["litter_size"], r["survived_count"], pct])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=survival_report.csv"})


@app.get("/api/reports/protocol-usage.csv")
@require_auth(("PI", "Admin"))
def report_protocol_usage() -> Response:
    query = """
        SELECT p.protocol_number, p.title, l.name AS lab_name, COUNT(c.id) AS cages
        FROM iacuc_protocols p
        JOIN labs l ON l.id = p.lab_id
        LEFT JOIN cages c ON c.protocol_id = p.id
    """
    params: tuple[Any, ...] = ()
    if not is_admin(g.user):
        query += " WHERE p.lab_id = ? "
        params = (g.user.lab_id,)
    query += " GROUP BY p.id ORDER BY cages DESC"
    rows = db().execute(query, params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["protocol_number", "title", "lab", "cages"])
    for r in rows:
        writer.writerow([r["protocol_number"], r["title"], r["lab_name"], r["cages"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=protocol_usage.csv"})


@app.get("/api/billing/rules")
@require_auth(("Admin", "PI"))
def billing_rules_list() -> Response:
    query = """
        SELECT br.id, br.lab_id, br.room_id, br.line_type, br.rate, br.service_name, br.active, br.created_at,
               l.name AS lab_name, r.name AS room_name
        FROM billing_rules br
        LEFT JOIN labs l ON l.id = br.lab_id
        LEFT JOIN rooms r ON r.id = br.room_id
    """
    params: tuple[Any, ...] = ()
    if not is_admin(g.user):
        query += " WHERE br.lab_id = ? OR br.lab_id IS NULL "
        params = (g.user.lab_id,)
    query += " ORDER BY br.id DESC"
    rows = db().execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/billing/rules")
@require_auth(("Admin",))
def billing_rule_create() -> Response:
    payload = request.get_json(force=True)
    line_type = str(payload.get("lineType", "per_diem")).strip()
    rate = float(payload.get("rate", 0))
    if line_type not in {"per_diem", "service"}:
        return jsonify({"error": "Invalid lineType"}), 400
    if rate < 0:
        return jsonify({"error": "rate must be non-negative"}), 400
    cur = db().execute(
        "INSERT INTO billing_rules (lab_id, room_id, line_type, rate, service_name, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            payload.get("labId"),
            payload.get("roomId"),
            line_type,
            rate,
            payload.get("serviceName"),
            1 if payload.get("active", True) else 0,
            now_iso(),
        ),
    )
    db().commit()
    audit_log(g.user.user_id, "billing_rule", cur.lastrowid, "create", None, payload)
    return jsonify({"id": cur.lastrowid}), 201


@app.post("/api/billing/run")
@require_auth(("Admin", "PI"))
def billing_run() -> Response:
    payload = request.get_json(force=True)
    period_start = str(payload.get("periodStart", "")).strip()
    period_end = str(payload.get("periodEnd", "")).strip()
    if not period_start or not period_end:
        return jsonify({"error": "periodStart and periodEnd are required"}), 400
    if period_end < period_start:
        return jsonify({"error": "periodEnd must be >= periodStart"}), 400

    # Ensure period exists and is open
    period = db().execute(
        "SELECT id, status FROM billing_periods WHERE period_start = ? AND period_end = ?",
        (period_start, period_end),
    ).fetchone()
    if not period:
        db().execute(
            "INSERT INTO billing_periods (period_start, period_end, status, created_at) VALUES (?, ?, 'open', ?)",
            (period_start, period_end, now_iso()),
        )
        db().commit()
        period = db().execute(
            "SELECT id, status FROM billing_periods WHERE period_start = ? AND period_end = ?",
            (period_start, period_end),
        ).fetchone()
    if period["status"] == "closed":
        return jsonify({"error": "Billing period is closed"}), 409

    # Derive per-diem rate per cage (lab-specific override > global)
    cages = db().execute(
        """
        SELECT c.id, c.lab_id, c.cage_code
        FROM cages c
        """
        + ("" if is_admin(g.user) else " WHERE c.lab_id = ? "),
        () if is_admin(g.user) else (g.user.lab_id,),
    ).fetchall()

    days = (datetime.fromisoformat(period_end) - datetime.fromisoformat(period_start)).days + 1
    days = max(days, 1)
    created = 0
    for c in cages:
        rule = db().execute(
            """
            SELECT rate
            FROM billing_rules
            WHERE active = 1 AND line_type = 'per_diem'
              AND (lab_id = ? OR lab_id IS NULL)
            ORDER BY CASE WHEN lab_id = ? THEN 0 ELSE 1 END, id DESC
            LIMIT 1
            """,
            (c["lab_id"], c["lab_id"]),
        ).fetchone()
        rate = float(rule["rate"]) if rule else 0.85
        qty = float(days)
        amount = round(qty * rate, 2)
        db().execute(
            """
            INSERT OR REPLACE INTO billing_entries
            (period_start, period_end, lab_id, cage_id, line_type, quantity, rate, amount, description, created_at)
            VALUES (?, ?, ?, ?, 'per_diem', ?, ?, ?, ?, ?)
            """,
            (period_start, period_end, c["lab_id"], c["id"], qty, rate, amount, f"Cage {c['cage_code']} per-diem", now_iso()),
        )
        created += 1
    db().commit()
    audit_log(g.user.user_id, "billing_period", f"{period_start}:{period_end}", "run", None, {"entries": created})
    return jsonify({"entriesUpserted": created, "periodStart": period_start, "periodEnd": period_end})


@app.post("/api/billing/close-period")
@require_auth(("Admin",))
def billing_close_period() -> Response:
    payload = request.get_json(force=True)
    period_start = str(payload.get("periodStart", "")).strip()
    period_end = str(payload.get("periodEnd", "")).strip()
    row = db().execute(
        "SELECT id, status FROM billing_periods WHERE period_start = ? AND period_end = ?",
        (period_start, period_end),
    ).fetchone()
    if not row:
        return jsonify({"error": "Period not found"}), 404
    if row["status"] == "closed":
        return jsonify({"ok": True, "status": "closed"})
    db().execute(
        "UPDATE billing_periods SET status = 'closed', closed_by = ?, closed_at = ? WHERE id = ?",
        (g.user.user_id, now_iso(), row["id"]),
    )
    db().commit()
    audit_log(g.user.user_id, "billing_period", row["id"], "close", None, {"periodStart": period_start, "periodEnd": period_end})
    return jsonify({"ok": True, "status": "closed"})


@app.get("/api/billing/statements.csv")
@require_auth(("Admin", "PI"))
def billing_statements_csv() -> Response:
    period_start = request.args.get("periodStart", "").strip()
    period_end = request.args.get("periodEnd", "").strip()
    clauses = []
    params: list[Any] = []
    if period_start:
        clauses.append("be.period_start = ?")
        params.append(period_start)
    if period_end:
        clauses.append("be.period_end = ?")
        params.append(period_end)
    if not is_admin(g.user):
        clauses.append("be.lab_id = ?")
        params.append(g.user.lab_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db().execute(
        f"""
        SELECT be.period_start, be.period_end, l.name AS lab_name, be.line_type,
               SUM(be.quantity) AS quantity, AVG(be.rate) AS rate, SUM(be.amount) AS amount
        FROM billing_entries be
        JOIN labs l ON l.id = be.lab_id
        {where}
        GROUP BY be.period_start, be.period_end, be.lab_id, be.line_type
        ORDER BY be.period_start DESC, lab_name
        """,
        params,
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["period_start", "period_end", "lab", "line_type", "quantity", "avg_rate", "amount"])
    for r in rows:
        writer.writerow([r["period_start"], r["period_end"], r["lab_name"], r["line_type"], r["quantity"], r["rate"], r["amount"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=billing_statements.csv"})


@app.get("/api/requests")
@require_auth()
def facility_requests_list() -> Response:
    params: list[Any] = []
    where = ""
    if not is_admin(g.user):
        where = "WHERE fr.lab_id = ?"
        params.append(g.user.lab_id)
    rows = db().execute(
        f"""
        SELECT fr.id, fr.request_type, fr.status, fr.details_json, fr.created_at, fr.updated_at,
               l.name AS lab_name, p.project_code, u.full_name AS requested_by_name
        FROM facility_requests fr
        JOIN labs l ON l.id = fr.lab_id
        LEFT JOIN projects p ON p.id = fr.project_id
        LEFT JOIN users u ON u.id = fr.requested_by
        {where}
        ORDER BY fr.id DESC
        LIMIT 500
        """,
        params,
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/requests")
@require_auth(("Technician", "PI", "Admin"))
def facility_request_create() -> Response:
    payload = request.get_json(force=True)
    lab_id = int(payload.get("labId", g.user.lab_id or 1))
    if not is_admin(g.user) and g.user.lab_id != lab_id:
        return jsonify({"error": "Forbidden"}), 403
    cur = db().execute(
        """
        INSERT INTO facility_requests
        (request_type, lab_id, project_id, status, details_json, requested_by, created_at, updated_at)
        VALUES (?, ?, ?, 'submitted', ?, ?, ?, ?)
        """,
        (
            payload.get("requestType", "general"),
            lab_id,
            payload.get("projectId"),
            json.dumps(payload.get("details", {})),
            g.user.user_id,
            now_iso(),
            now_iso(),
        ),
    )
    db().commit()
    audit_log(g.user.user_id, "facility_request", cur.lastrowid, "create", None, payload)
    return jsonify({"id": cur.lastrowid}), 201


@app.post("/api/requests/<int:request_id>/status")
@require_auth(("PI", "Admin"))
def facility_request_status(request_id: int) -> Response:
    payload = request.get_json(force=True)
    status = str(payload.get("status", "")).strip()
    if status not in {"submitted", "approved", "fulfilled", "rejected"}:
        return jsonify({"error": "Invalid status"}), 400
    row = db().execute("SELECT * FROM facility_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    if not is_admin(g.user) and int(row["lab_id"]) != int(g.user.lab_id or -1):
        return jsonify({"error": "Forbidden"}), 403
    db().execute(
        "UPDATE facility_requests SET status = ?, reviewed_by = ?, updated_at = ? WHERE id = ?",
        (status, g.user.user_id, now_iso(), request_id),
    )
    db().commit()
    audit_log(g.user.user_id, "facility_request", request_id, "status", {"status": row["status"]}, {"status": status})
    return jsonify({"ok": True})


@app.get("/api/operations/sla")
@require_auth(("PI", "Admin"))
def operations_sla() -> Response:
    rows = db().execute(
        """
        SELECT request_type, status, AVG((julianday(updated_at) - julianday(created_at)) * 24.0) AS avg_hours, COUNT(*) AS n
        FROM facility_requests
        """
        + ("" if is_admin(g.user) else " WHERE lab_id = ? ")
        + """
        GROUP BY request_type, status
        ORDER BY n DESC
        """,
        () if is_admin(g.user) else (g.user.lab_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/facility/benchmark")
@require_auth(("Admin",))
def facility_benchmark() -> Response:
    rows = db().execute(
        """
        SELECT f.id AS facility_id, f.name AS facility_name,
               COUNT(DISTINCT l.id) AS labs,
               COUNT(DISTINCT c.id) AS cages,
               COUNT(DISTINCT p.id) AS projects,
               COUNT(DISTINCT a.id) AS active_animals
        FROM facilities f
        LEFT JOIN labs l ON l.facility_id = f.id
        LEFT JOIN projects p ON p.lab_id = l.id
        LEFT JOIN cages c ON c.lab_id = l.id
        LEFT JOIN animals a ON a.cage_id = c.id AND a.status = 'Active'
        GROUP BY f.id
        ORDER BY cages DESC
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/integrations/export-jobs")
@require_auth(("PI", "Admin"))
def create_export_job() -> Response:
    payload = request.get_json(force=True)
    job_type = str(payload.get("jobType", "")).strip()
    if not job_type:
        return jsonify({"error": "jobType is required"}), 400
    cur = db().execute(
        "INSERT INTO export_jobs (job_type, target_url, status, payload_json, created_by, created_at) VALUES (?, ?, 'pending', ?, ?, ?)",
        (job_type, payload.get("targetUrl"), json.dumps(payload.get("payload", {})), g.user.user_id, now_iso()),
    )
    db().commit()
    audit_log(g.user.user_id, "export_job", cur.lastrowid, "create", None, payload)
    return jsonify({"id": cur.lastrowid}), 201


@app.post("/api/integrations/export-jobs/<int:job_id>/run")
@require_auth(("PI", "Admin"))
def run_export_job(job_id: int) -> Response:
    row = db().execute("SELECT * FROM export_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    # Simulated dispatch; external webhook delivery can be added in worker.
    db().execute("UPDATE export_jobs SET status = 'sent', sent_at = ? WHERE id = ?", (now_iso(), job_id))
    db().commit()
    audit_log(g.user.user_id, "export_job", job_id, "run", {"status": row["status"]}, {"status": "sent"})
    return jsonify({"ok": True, "status": "sent"})


@app.get("/api/integrations/export-jobs")
@require_auth(("PI", "Admin"))
def list_export_jobs() -> Response:
    rows = db().execute("SELECT id, job_type, target_url, status, created_at, sent_at FROM export_jobs ORDER BY id DESC LIMIT 500").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/audit")
@require_auth(("Admin",))
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
    app.run(host="0.0.0.0", port=8000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
