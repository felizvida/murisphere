from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
SQLITE_SCHEMA = ROOT / "schema.sql"
POSTGRES_SCHEMA = ROOT / "schema_postgres.sql"
AUTOINCREMENT_RE = re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.IGNORECASE)
REAL_RE = re.compile(r"\bREAL\b", re.IGNORECASE)


def translate_schema(source: str) -> str:
    lines: list[str] = ["-- Generated from schema.sql by generate_postgres_schema.py", ""]
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.upper().startswith("PRAGMA "):
            continue
        lines.append(line)
    text = "\n".join(lines).rstrip() + "\n"
    text = AUTOINCREMENT_RE.sub("SERIAL PRIMARY KEY", text)
    text = REAL_RE.sub("DOUBLE PRECISION", text)
    return text


def main() -> int:
    translated = translate_schema(SQLITE_SCHEMA.read_text(encoding="utf-8"))
    POSTGRES_SCHEMA.write_text(translated, encoding="utf-8")
    print(f"Wrote {POSTGRES_SCHEMA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
