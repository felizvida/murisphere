from __future__ import annotations

import sqlite3


Connection = sqlite3.Connection
Row = sqlite3.Row
IntegrityError = sqlite3.IntegrityError


def quote_ident(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parameter_placeholder() -> str:
    return "?"


def connect(db_target: str) -> Connection:
    conn = sqlite3.connect(db_target)
    conn.row_factory = sqlite3.Row
    enable_connection_features(conn)
    return conn


def enable_connection_features(conn: Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")


def table_columns(conn: Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
    return [str(row[1]) for row in rows]


def sql_list_agg(expression: str, separator: str = ", ") -> str:
    return f"GROUP_CONCAT({expression}, {quote_literal(separator)})"


def sql_hours_between(later_column: str, earlier_column: str) -> str:
    later = quote_ident(later_column)
    earlier = quote_ident(earlier_column)
    return f"((julianday({later}) - julianday({earlier})) * 24.0)"
