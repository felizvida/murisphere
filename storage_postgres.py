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

import re
from typing import Any, Iterable


try:
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row  # type: ignore[import-not-found]
except ModuleNotFoundError:
    psycopg = None
    dict_row = None


POSTGRES_TABLES_WITHOUT_ID = {"lab_profiles"}
INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)

IntegrityError = psycopg.IntegrityError if psycopg is not None else None


def quote_ident(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parameter_placeholder() -> str:
    return "%s"


def require_psycopg() -> tuple[Any, Any]:
    if psycopg is None or dict_row is None:
        raise RuntimeError("PostgreSQL support requires psycopg. Install `psycopg[binary]`.")
    return psycopg, dict_row


def translate_qmark_sql(sql: str) -> str:
    out: list[str] = []
    in_single = False
    in_double = False
    idx = 0
    while idx < len(sql):
        char = sql[idx]
        nxt = sql[idx + 1] if idx + 1 < len(sql) else ""
        if char == "'" and not in_double:
            if in_single and nxt == "'":
                out.append("''")
                idx += 2
                continue
            in_single = not in_single
            out.append(char)
            idx += 1
            continue
        if char == '"' and not in_single:
            if in_double and nxt == '"':
                out.append('""')
                idx += 2
                continue
            in_double = not in_double
            out.append(char)
            idx += 1
            continue
        if char == "?" and not in_single and not in_double:
            out.append("%s")
        else:
            out.append(char)
        idx += 1
    return "".join(out)


def split_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    idx = 0
    while idx < len(script):
        char = script[idx]
        nxt = script[idx + 1] if idx + 1 < len(script) else ""

        if in_line_comment:
            current.append(char)
            if char == "\n":
                in_line_comment = False
            idx += 1
            continue

        if in_block_comment:
            current.append(char)
            if char == "*" and nxt == "/":
                current.append(nxt)
                in_block_comment = False
                idx += 2
                continue
            idx += 1
            continue

        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double and char == "-" and nxt == "-":
            current.append(char)
            current.append(nxt)
            in_line_comment = True
            idx += 2
            continue
        elif not in_single and not in_double and char == "/" and nxt == "*":
            current.append(char)
            current.append(nxt)
            in_block_comment = True
            idx += 2
            continue
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        idx += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


class CursorWrapper:
    def __init__(self, cursor: Any, *, lastrowid: int | None = None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def close(self) -> None:
        self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)


class ConnectionWrapper:
    def __init__(self, conn: Any):
        self._conn = conn

    def _prepare_sql(self, sql: str) -> tuple[str, bool]:
        translated = translate_qmark_sql(sql.strip())
        match = INSERT_TABLE_RE.match(translated)
        if not match:
            return translated, False
        table = match.group(1).lower()
        if "returning" in translated.lower() or table in POSTGRES_TABLES_WITHOUT_ID:
            return translated, False
        return translated + " RETURNING id", True

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> CursorWrapper:
        translated, returns_id = self._prepare_sql(sql)
        cur = self._conn.cursor()
        cur.execute(translated, tuple(params or ()))
        lastrowid = None
        if returns_id:
            row = cur.fetchone()
            if isinstance(row, dict):
                lastrowid = row.get("id")
            elif row:
                lastrowid = row[0]
        return CursorWrapper(cur, lastrowid=lastrowid)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def executescript(self, script: str) -> None:
        for statement in split_sql_statements(script):
            self.execute(statement)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def connect(db_target: str) -> ConnectionWrapper:
    pg, pg_dict_row = require_psycopg()
    conn = pg.connect(db_target, autocommit=False, row_factory=pg_dict_row)
    wrapped = ConnectionWrapper(conn)
    enable_connection_features(wrapped)
    return wrapped


def enable_connection_features(_conn: ConnectionWrapper) -> None:
    return None


def table_columns(conn: ConnectionWrapper, table: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = ?
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    return [str(row["column_name"] if isinstance(row, dict) else row[0]) for row in rows]


def sql_list_agg(expression: str, separator: str = ", ") -> str:
    return f"STRING_AGG({expression}, {quote_literal(separator)})"


def sql_hours_between(later_column: str, earlier_column: str) -> str:
    later = quote_ident(later_column)
    earlier = quote_ident(earlier_column)
    return f"(EXTRACT(EPOCH FROM ({later}::timestamp - {earlier}::timestamp)) / 3600.0)"
