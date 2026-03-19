from __future__ import annotations

import os
import sqlite3
from typing import Iterable


DATABASE_DIALECT = (os.getenv("MURISPHERE_DB_DIALECT", "sqlite").strip().lower() or "sqlite")

Connection = sqlite3.Connection
Row = sqlite3.Row
IntegrityError = sqlite3.IntegrityError


def is_sqlite() -> bool:
    return DATABASE_DIALECT == "sqlite"


def quote_ident(value: str) -> str:
    return f'"{value.replace("\"", "\"\"")}"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parameter_placeholder() -> str:
    return "?" if is_sqlite() else "%s"


def connect(db_path: str) -> Connection:
    if not is_sqlite():
        raise NotImplementedError(f"Database dialect '{DATABASE_DIALECT}' is not wired yet")
    conn = sqlite3.connect(db_path)
    conn.row_factory = Row
    enable_connection_features(conn)
    return conn


def enable_connection_features(conn: Connection) -> None:
    if is_sqlite():
        conn.execute("PRAGMA foreign_keys = ON")


def table_columns(conn: Connection, table: str) -> list[str]:
    if is_sqlite():
        rows = conn.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
        return [str(row[1]) for row in rows]
    raise NotImplementedError(f"Table column inspection is not wired for '{DATABASE_DIALECT}'")


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
