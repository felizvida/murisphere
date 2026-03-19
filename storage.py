from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Iterable


try:
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row  # type: ignore[import-not-found]
except ModuleNotFoundError:
    psycopg = None
    dict_row = None


SQLITE_DIALECTS = {"sqlite", "sqlite3"}
POSTGRES_DIALECTS = {"postgres", "postgresql", "psql"}
POSTGRES_TABLES_WITHOUT_ID = {"lab_profiles"}
INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


def _resolve_dialect() -> str:
    raw = os.getenv("MURISPHERE_DB_DIALECT", "").strip().lower()
    if raw in SQLITE_DIALECTS:
        return "sqlite"
    if raw in POSTGRES_DIALECTS:
        return "postgres"
    target = (os.getenv("MURISPHERE_DATABASE_URL") or os.getenv("MURISPHERE_DB") or "").strip().lower()
    if target.startswith("postgres://") or target.startswith("postgresql://"):
        return "postgres"
    return "sqlite"


DATABASE_DIALECT = _resolve_dialect()

Connection = Any
Row = Any
_integrity_errors = [sqlite3.IntegrityError]
if psycopg is not None:
    _integrity_errors.append(psycopg.IntegrityError)
IntegrityError = tuple(_integrity_errors)


def is_sqlite() -> bool:
    return DATABASE_DIALECT == "sqlite"


def is_postgres() -> bool:
    return DATABASE_DIALECT == "postgres"


def quote_ident(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parameter_placeholder() -> str:
    return "?" if is_sqlite() else "%s"


def _require_psycopg() -> tuple[Any, Any]:
    if psycopg is None or dict_row is None:
        raise RuntimeError("PostgreSQL support requires psycopg. Install `psycopg[binary]`.")
    return psycopg, dict_row


def _translate_qmark_sql(sql: str) -> str:
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


def _split_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    for char in script:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


class PostgresCursorWrapper:
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


class PostgresConnectionWrapper:
    def __init__(self, conn: Any):
        self._conn = conn

    def _prepare_sql(self, sql: str) -> tuple[str, bool]:
        translated = _translate_qmark_sql(sql.strip())
        match = INSERT_TABLE_RE.match(translated)
        if not match:
            return translated, False
        table = match.group(1).lower()
        if "returning" in translated.lower() or table in POSTGRES_TABLES_WITHOUT_ID:
            return translated, False
        return translated + " RETURNING id", True

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> PostgresCursorWrapper:
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
        return PostgresCursorWrapper(cur, lastrowid=lastrowid)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def executescript(self, script: str) -> None:
        for statement in _split_sql_statements(script):
            self.execute(statement)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def connect(db_target: str) -> Connection:
    if is_sqlite():
        conn = sqlite3.connect(db_target)
        conn.row_factory = sqlite3.Row
        enable_connection_features(conn)
        return conn
    pg, pg_dict_row = _require_psycopg()
    conn = pg.connect(db_target, autocommit=False, row_factory=pg_dict_row)
    wrapped = PostgresConnectionWrapper(conn)
    enable_connection_features(wrapped)
    return wrapped


def enable_connection_features(conn: Connection) -> None:
    if is_sqlite():
        conn.execute("PRAGMA foreign_keys = ON")


def table_columns(conn: Connection, table: str) -> list[str]:
    if is_sqlite():
        rows = conn.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
        return [str(row[1]) for row in rows]
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
    if is_sqlite():
        return f"GROUP_CONCAT({expression}, {quote_literal(separator)})"
    return f"STRING_AGG({expression}, {quote_literal(separator)})"


def sql_hours_between(later_column: str, earlier_column: str) -> str:
    later = quote_ident(later_column)
    earlier = quote_ident(earlier_column)
    if is_sqlite():
        return f"((julianday({later}) - julianday({earlier})) * 24.0)"
    return f"(EXTRACT(EPOCH FROM ({later}::timestamp - {earlier}::timestamp)) / 3600.0)"


def sql_upsert(
    table: str,
    insert_columns: Iterable[str],
    conflict_columns: Iterable[str],
    update_columns: Iterable[str],
) -> str:
    insert_list = list(insert_columns)
    conflict_list = list(conflict_columns)
    update_list = list(update_columns)
    if not insert_list:
        raise ValueError("insert_columns must not be empty")
    if not conflict_list:
        raise ValueError("conflict_columns must not be empty")
    if not update_list:
        raise ValueError("update_columns must not be empty")

    columns_sql = ", ".join(quote_ident(column) for column in insert_list)
    placeholders_sql = ", ".join(parameter_placeholder() for _ in insert_list)
    conflict_sql = ", ".join(quote_ident(column) for column in conflict_list)
    update_sql = ", ".join(
        f"{quote_ident(column)} = EXCLUDED.{quote_ident(column)}"
        for column in update_list
    )
    return (
        f"INSERT INTO {quote_ident(table)} ({columns_sql}) "
        f"VALUES ({placeholders_sql}) "
        f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}"
    )
