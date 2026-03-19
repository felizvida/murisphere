from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHECKS = [
    ("sqlite_driver", Path("app.py"), re.compile(r"\bsqlite3\b")),
    ("group_concat", Path("app.py"), re.compile(r"GROUP_CONCAT")),
    ("insert_or_replace", Path("app.py"), re.compile(r"INSERT OR REPLACE")),
    ("julianday", Path("app.py"), re.compile(r"julianday")),
    ("pragma_usage", Path("app.py"), re.compile(r"PRAGMA")),
    ("sqlite_schema_pragma", Path("schema.sql"), re.compile(r"^PRAGMA ", re.MULTILINE)),
    ("autoincrement", Path("schema.sql"), re.compile(r"AUTOINCREMENT")),
]


def build_report() -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for check_id, rel_path, pattern in CHECKS:
        text = (ROOT / rel_path).read_text(encoding="utf-8")
        matches = list(pattern.finditer(text))
        findings.append(
            {
                "id": check_id,
                "file": str(rel_path),
                "count": len(matches),
                "lines": sorted({text[: match.start()].count("\n") + 1 for match in matches}),
            }
        )

    blocking = [f for f in findings if int(f["count"]) > 0]
    return {
        "ok": len(blocking) == 0,
        "summary": {
            "checks": len(findings),
            "blockingChecks": len(blocking),
        },
        "findings": findings,
        "notes": [
            "A zero count means the specific SQLite-only pattern is no longer present.",
            "Non-zero counts identify code or schema that still needs refactoring before direct PostgreSQL runtime support.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Murisphere for SQLite-specific blockers before PostgreSQL runtime migration.")
    parser.add_argument("--out", help="Optional output path for the JSON report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    payload = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
