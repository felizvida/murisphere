#!/usr/bin/env python3

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

"""UI clickability contract audit.

Checks whether interactive UI items in templates/index.html are actually wired as clickable
or submit-capable in static/app.js, and whether local links map to Flask routes.

Outputs:
- docs/test_reports/UI_CLICKABILITY_RESULT.json
- docs/test_reports/UI_CLICKABILITY_REPORT.html
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, UTC
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import app as appmod
from werkzeug.exceptions import MethodNotAllowed, NotFound

ROOT = Path(__file__).resolve().parent
INDEX_HTML = ROOT / "templates" / "index.html"
APP_JS = ROOT / "static" / "app.js"
OUT_DIR = ROOT / "docs" / "test_reports"
OUT_JSON = OUT_DIR / "UI_CLICKABILITY_RESULT.json"
OUT_HTML = OUT_DIR / "UI_CLICKABILITY_REPORT.html"


@dataclass
class Button:
    id: str | None
    kind: str
    parent_form_id: str | None
    data_tab: str | None


@dataclass
class Form:
    id: str | None


@dataclass
class Link:
    href: str
    id: str | None


class IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[Form] = []
        self.buttons: list[Button] = []
        self.links: list[Link] = []
        self.sections: set[str] = set()
        self._form_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "form":
            fid = a.get("id")
            self.forms.append(Form(id=fid))
            self._form_stack.append(fid)
        elif tag == "button":
            self.buttons.append(
                Button(
                    id=a.get("id"),
                    kind=(a.get("type") or "button").strip().lower(),
                    parent_form_id=self._form_stack[-1] if self._form_stack else None,
                    data_tab=a.get("data-tab"),
                )
            )
        elif tag == "a" and a.get("href"):
            self.links.append(Link(href=str(a["href"]), id=a.get("id")))
        elif tag == "section" and a.get("id"):
            self.sections.add(str(a["id"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._form_stack:
            self._form_stack.pop()


def parse_js_wiring(js_text: str) -> tuple[dict[str, set[str]], bool]:
    event_map: dict[str, set[str]] = {}
    # el("id").addEventListener("click", ...)
    for m in re.finditer(r"el\(\"([^\"]+)\"\)\.addEventListener\(\"([^\"]+)\"", js_text):
        eid, ev = m.group(1), m.group(2)
        event_map.setdefault(eid, set()).add(ev)
    tabs_wired = 'document.querySelectorAll(".tabs button")' in js_text and '.addEventListener("click"' in js_text
    return event_map, tabs_wired


def route_exists_for_get(path: str) -> bool:
    adapter = appmod.app.url_map.bind("localhost")
    try:
        adapter.match(path, method="GET")
        return True
    except MethodNotAllowed:
        return True
    except NotFound:
        return False


def grade_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")
    score = round((passed * 100.0) / max(passed + failed, 1), 2)
    return {"passed": passed, "failed": failed, "skipped": skipped, "score": score}


def build_html_report(summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    rows = []
    for r in results:
        badge = (
            '<span class="badge ok">PASS</span>'
            if r["status"] == "pass"
            else '<span class="badge bad">FAIL</span>'
            if r["status"] == "fail"
            else '<span class="badge skip">SKIP</span>'
        )
        rows.append(
            "<tr>"
            f"<td>{badge}</td>"
            f"<td><code>{r['category']}</code></td>"
            f"<td><code>{r['item']}</code></td>"
            f"<td>{r['detail']}</td>"
            "</tr>"
        )

    now = datetime.now(UTC).isoformat()
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>UI Clickability Audit</title>
  <style>
    :root {{
      --bg:#0f1b24;
      --card:#152635;
      --ink:#e7f4ff;
      --muted:#9ab4c8;
      --ok:#2bc48a;
      --bad:#ef5f67;
      --skip:#f2b84b;
      --line:#274154;
    }}
    body {{
      margin:0;
      font-family: "Space Grotesk", "Segoe UI", Arial, sans-serif;
      color:var(--ink);
      background: radial-gradient(circle at 10% 0%, #1f3d56 0%, #0f1b24 48%), linear-gradient(165deg, #0f1b24, #112636);
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    .hero {{
      background: linear-gradient(145deg, rgba(43,196,138,.15), rgba(43,196,138,.03));
      border:1px solid var(--line);
      border-radius:16px;
      padding:20px;
      box-shadow: 0 20px 40px rgba(0,0,0,.25);
    }}
    h1 {{ margin:0; font-size:2rem; letter-spacing:.2px; }}
    .meta {{ color:var(--muted); margin-top:8px; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; margin-top:16px; }}
    .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; }}
    .kpi .v {{ font-size:1.6rem; font-weight:700; margin-top:4px; }}
    .table-wrap {{ margin-top:16px; background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }}
    table {{ width:100%; border-collapse: collapse; }}
    th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background: #132231; color:#c9e6ff; position:sticky; top:0; }}
    .badge {{ border-radius:999px; padding:3px 9px; font-size:.75rem; font-weight:700; display:inline-block; }}
    .ok {{ background: rgba(43,196,138,.16); color: var(--ok); border:1px solid rgba(43,196,138,.4); }}
    .bad {{ background: rgba(239,95,103,.16); color: var(--bad); border:1px solid rgba(239,95,103,.4); }}
    .skip {{ background: rgba(242,184,75,.16); color: var(--skip); border:1px solid rgba(242,184,75,.4); }}
    code {{ color:#b3e2ff; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <h1>UI Clickability Audit</h1>
      <div class=\"meta\">Generated: {now}</div>
      <div class=\"grid\">
        <div class=\"kpi\"><div>Total Checks</div><div class=\"v\">{len(results)}</div></div>
        <div class=\"kpi\"><div>Passed</div><div class=\"v\">{summary['passed']}</div></div>
        <div class=\"kpi\"><div>Failed</div><div class=\"v\">{summary['failed']}</div></div>
        <div class=\"kpi\"><div>Score</div><div class=\"v\">{summary['score']}%</div></div>
      </div>
    </section>

    <section class=\"table-wrap\">
      <table>
        <thead>
          <tr><th>Status</th><th>Category</th><th>Item</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
  </div>
</body>
</html>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    parser = IndexParser()
    parser.feed(INDEX_HTML.read_text(encoding="utf-8"))

    js_text = APP_JS.read_text(encoding="utf-8")
    event_map, tabs_wired = parse_js_wiring(js_text)

    results: list[dict[str, Any]] = []

    # Form submission wiring
    for f in parser.forms:
        if not f.id:
            continue
        wired = "submit" in event_map.get(f.id, set())
        results.append(
            {
                "category": "form",
                "item": f"#{f.id}",
                "status": "pass" if wired else "fail",
                "detail": "submit listener found" if wired else "missing submit listener in static/app.js",
            }
        )

    # Button wiring
    for b in parser.buttons:
        if b.data_tab:
            section_ok = f"tab-{b.data_tab}" in parser.sections
            status = "pass" if tabs_wired and section_ok else "fail"
            detail = "tab click delegation + section present" if status == "pass" else "tab button missing delegation or target section"
            results.append(
                {
                    "category": "tab",
                    "item": f"data-tab={b.data_tab}",
                    "status": status,
                    "detail": detail,
                }
            )
            continue

        if not b.id:
            results.append(
                {
                    "category": "button",
                    "item": "<button(no-id)>",
                    "status": "skip",
                    "detail": "no stable id; skipped explicit wiring check",
                }
            )
            continue

        events = event_map.get(b.id, set())
        wired = "click" in events or "submit" in events or "change" in events
        if not wired and b.kind == "submit" and b.parent_form_id:
            wired = "submit" in event_map.get(b.parent_form_id, set())
        results.append(
            {
                "category": "button",
                "item": f"#{b.id}",
                "status": "pass" if wired else "fail",
                "detail": (
                    "clickable via direct or form submit listener"
                    if wired
                    else "missing click/submit/change listener (or form submit handler)"
                ),
            }
        )

    # Link routability for local links
    for link in parser.links:
        href = link.href.strip()
        if href.startswith("http://") or href.startswith("https://") or href.startswith("#"):
            results.append(
                {
                    "category": "link",
                    "item": href,
                    "status": "pass",
                    "detail": "external/anchor link",
                }
            )
            continue
        if not href.startswith("/"):
            results.append(
                {
                    "category": "link",
                    "item": href,
                    "status": "skip",
                    "detail": "relative link not audited",
                }
            )
            continue
        exists = route_exists_for_get(href)
        results.append(
            {
                "category": "link",
                "item": href,
                "status": "pass" if exists else "fail",
                "detail": "matched Flask route map" if exists else "no matching GET route",
            }
        )

    summary = grade_results(results)
    payload = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": summary,
        "results": results,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUT_HTML.write_text(build_html_report(summary, results), encoding="utf-8")

    print("UI clickability audit complete")
    print(f"passed={summary['passed']} failed={summary['failed']} skipped={summary['skipped']} score={summary['score']}%")
    print(f"json={OUT_JSON}")
    print(f"html={OUT_HTML}")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
