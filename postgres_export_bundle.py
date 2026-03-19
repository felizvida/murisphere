from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


APP_NAME = "Murisphere"
DEFAULT_DB = os.getenv("MURISPHERE_DB", "murisphere.db")
ROOT = Path(__file__).resolve().parent


def read_version() -> str:
    version_file = ROOT / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "dev"


def discover_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def quote_ident(value: str) -> str:
    return f'"{value.replace("\"", "\"\"")}"'


def foreign_key_map(conn: sqlite3.Connection, tables: Iterable[str]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for table in tables:
        deps = {
            str(row[2])
            for row in conn.execute(f"PRAGMA foreign_key_list({quote_ident(table)})").fetchall()
            if row[2]
        }
        mapping[table] = deps
    return mapping


def load_order(tables: list[str], fk_map: dict[str, set[str]]) -> list[str]:
    incoming: dict[str, int] = {table: 0 for table in tables}
    outgoing: dict[str, set[str]] = defaultdict(set)
    for table, deps in fk_map.items():
        for dep in deps:
            if dep not in incoming:
                continue
            incoming[table] += 1
            outgoing[dep].add(table)

    ready = deque(sorted(table for table, count in incoming.items() if count == 0))
    ordered: list[str] = []
    while ready:
        current = ready.popleft()
        ordered.append(current)
        for dependent in sorted(outgoing[current]):
            incoming[dependent] -= 1
            if incoming[dependent] == 0:
                ready.append(dependent)

    if len(ordered) != len(tables):
        remaining = [table for table in tables if table not in ordered]
        ordered.extend(sorted(remaining))
    return ordered


def export_table(conn: sqlite3.Connection, table: str, destination: Path) -> int:
    columns = conn.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
    ordered_pk_columns = [
        quote_ident(str(column[1]))
        for column in sorted((column for column in columns if column[5]), key=lambda column: int(column[5]))
    ]
    order_clause = ", ".join(ordered_pk_columns) if ordered_pk_columns else "rowid"

    count = 0
    with destination.open("w", encoding="utf-8") as handle:
        for row in conn.execute(f"SELECT * FROM {quote_ident(table)} ORDER BY {order_clause}"):
            handle.write(json.dumps(dict(row), default=str, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def export_bundle(db_path: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = discover_tables(conn)
        fk_map = foreign_key_map(conn, tables)
        ordered_tables = load_order(tables, fk_map)

        table_manifest: list[dict[str, object]] = []
        for table in ordered_tables:
            relative_path = Path("tables") / f"{table}.jsonl"
            row_count = export_table(conn, table, out_dir / relative_path)
            table_manifest.append(
                {
                    "name": table,
                    "rowCount": row_count,
                    "file": str(relative_path).replace("\\", "/"),
                    "dependsOn": sorted(fk_map.get(table, set())),
                }
            )
    finally:
        conn.close()

    schema_src = ROOT / "schema.sql"
    if schema_src.exists():
        shutil.copyfile(schema_src, out_dir / "schema-sqlite.sql")

    manifest = {
        "app": APP_NAME,
        "version": read_version(),
        "exportedAt": datetime.now(UTC).isoformat(),
        "sourceEngine": "sqlite",
        "sourceDb": str(db_path),
        "targetEngine": "postgresql",
        "tableCount": len(table_manifest),
        "tables": table_manifest,
        "recommendedLoadOrder": ordered_tables,
        "notes": [
            "This bundle is a logical export for PostgreSQL migration and central-backend bootstrapping.",
            "Rows are stored as JSON Lines files in table load order.",
            "Run postgres_readiness_audit.py to review remaining SQLite-specific application blockers.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "README.txt").write_text(
        "\n".join(
            [
                "Murisphere PostgreSQL Migration Bundle",
                "",
                f"Source DB: {db_path}",
                f"Exported: {manifest['exportedAt']}",
                "",
                "Artifacts:",
                "- manifest.json",
                "- schema-sqlite.sql",
                "- tables/*.jsonl",
                "",
                "Next step:",
                "- Run postgres_readiness_audit.py for SQLite-specific code and schema blockers.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a Murisphere SQLite database into a PostgreSQL-ready logical bundle.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to the source SQLite database.")
    parser.add_argument("--out", default="dist/postgres-bundle", help="Output directory for the export bundle.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).resolve()
    out_dir = Path(args.out).resolve()
    manifest = export_bundle(db_path, out_dir)
    total_rows = sum(int(table["rowCount"]) for table in manifest["tables"])
    print(
        json.dumps(
            {
                "ok": True,
                "outDir": str(out_dir),
                "tableCount": manifest["tableCount"],
                "totalRows": total_rows,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
