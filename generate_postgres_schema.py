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

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
SQLITE_SCHEMA = ROOT / "schema.sql"
POSTGRES_SCHEMA = ROOT / "schema_postgres.sql"
AUTOINCREMENT_RE = re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.IGNORECASE)
REAL_RE = re.compile(r"\bREAL\b", re.IGNORECASE)
APACHE_SQL_HEADER = """/*
 * Copyright 2026 Murisphere Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */"""


def strip_leading_license_block(lines: list[str]) -> list[str]:
    if not lines or not lines[0].lstrip().startswith("/*"):
        return lines

    idx = 0
    while idx < len(lines):
        if "*/" in lines[idx]:
            idx += 1
            break
        idx += 1

    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return lines[idx:]


def translate_schema(source: str) -> str:
    lines: list[str] = [APACHE_SQL_HEADER, "", "-- Generated from schema.sql by generate_postgres_schema.py", ""]
    source_lines = strip_leading_license_block(source.splitlines())
    for line in source_lines:
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
