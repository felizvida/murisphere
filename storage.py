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
from typing import Any, Iterable

import storage_postgres
import storage_sqlite


SQLITE_DIALECTS = {"sqlite"}
POSTGRES_DIALECTS = {"postgres", "postgresql", "psql"}


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

_integrity_errors: list[type[BaseException]] = [storage_sqlite.IntegrityError]
if storage_postgres.IntegrityError is not None:
    _integrity_errors.append(storage_postgres.IntegrityError)
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


def _backend_module() -> Any:
    return storage_postgres if is_postgres() else storage_sqlite


def parameter_placeholder() -> str:
    return _backend_module().parameter_placeholder()


def connect(db_target: str) -> Connection:
    return _backend_module().connect(db_target)


def enable_connection_features(conn: Connection) -> None:
    _backend_module().enable_connection_features(conn)


def table_columns(conn: Connection, table: str) -> list[str]:
    return _backend_module().table_columns(conn, table)


def sql_list_agg(expression: str, separator: str = ", ") -> str:
    return _backend_module().sql_list_agg(expression, separator)


def sql_hours_between(later_column: str, earlier_column: str) -> str:
    return _backend_module().sql_hours_between(later_column, earlier_column)


def translate_qmark_sql(sql: str) -> str:
    if is_postgres():
        return storage_postgres.translate_qmark_sql(sql)
    return sql


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
