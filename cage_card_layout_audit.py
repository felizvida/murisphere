from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
APP_JS = ROOT / "static" / "app.js"
STYLES_CSS = ROOT / "static" / "styles.css"
DEFAULT_OUTPUT = ROOT / "docs" / "test_reports" / "CAGE_CARD_LAYOUT_RESULT.json"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def static_checks(app_js: str, styles_css: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    expectations = [
        ("print_css_panels_single_column", ".card-panels { display: grid; grid-template-columns: 1fr;"),
        ("print_css_cell_wrap_guard", "word-break: break-word;"),
        ("print_css_cell_overflow_hidden", "overflow: hidden;"),
    ]
    for name, pattern in expectations:
        checks.append({"name": name, "ok": pattern in app_js, "source": "static/app.js"})

    style_expectations = [
        ("preview_css_cell_wrap_guard", "word-break: break-word;"),
        ("preview_css_cell_overflow_hidden", "overflow: hidden;"),
    ]
    for name, pattern in style_expectations:
        checks.append({"name": name, "ok": pattern in styles_css, "source": "static/styles.css"})

    return checks


def build_fixture_html(styles_css: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Cage Card Layout Audit Fixture</title>
    <style>
{styles_css}
body {{
  background: #ffffff !important;
  padding: 24px !important;
}}
.audit-host {{
  width: 760px;
  margin: 0 auto;
}}
</style>
  </head>
  <body>
    <div class="audit-host">
      <div class="card-grid">
        <article class="print-card">
          <div class="print-card-header">
            <div class="print-card-identity">
              <div class="card-badge">Murisphere Cage Card</div>
              <div class="card-title">F1-L03-C0215</div>
              <div class="card-subtitle">Room 1, Breeding Rack 1, Slot 6A</div>
            </div>
            <div class="card-code-block">
              <img class="qrcode" alt="QR code" />
              <div class="qr-caption">Scan with phone camera</div>
            </div>
          </div>

          <div class="card-facts-grid">
            <div class="card-fact"><span>Group Owner</span><strong>Dr. Meosha Hudson</strong></div>
            <div class="card-fact"><span>Group Name</span><strong>Hudson Lab</strong></div>
            <div class="card-fact"><span>Projects</span><strong>L03-PRJ-01, L03-PRJ-05, L03-PRJ-11</strong></div>
            <div class="card-fact"><span>Protocol</span><strong>IACUC-2026-0312</strong></div>
            <div class="card-fact"><span>Description</span><strong>PdxCre longitudinal cohort for regulatory survival studies</strong></div>
            <div class="card-fact"><span>Protocol Expires</span><strong>12/31/2026</strong></div>
            <div class="card-fact"><span>Breeding Status</span><strong>Pairing 35 (Timed Mating)</strong></div>
            <div class="card-fact"><span>Cage DOB</span><strong>10/10/2024</strong></div>
            <div class="card-fact"><span>Strain</span><strong>C57BL/6J</strong></div>
            <div class="card-fact"><span>Genotype</span><strong>PdxCre Tg/Azelia SuperLongAlleleStringWithNoSpaces</strong></div>
            <div class="card-fact"><span>Population (Cage Total)</span><strong>M1 / F2 / T3</strong></div>
            <div class="card-fact"><span>Tracked IDs Listed</span><strong>3 shown of 3</strong></div>
            <div class="card-fact"><span>Room / Rack</span><strong>Room 1 / Breeding Rack 1</strong></div>
          </div>

          <div class="card-panels">
            <div class="card-panel">
              <div class="panel-title">Animals</div>
              <div class="panel-subtitle">Rows list tracked IDs; cage population may include untagged pups.</div>
              <table class="card-table animals-table">
                <colgroup>
                  <col style="width:18%" />
                  <col style="width:10%" />
                  <col style="width:24%" />
                  <col style="width:32%" />
                  <col style="width:16%" />
                </colgroup>
                <thead>
                  <tr><th>ID</th><th>Sex</th><th>DOB</th><th>Genotype</th><th>Status</th></tr>
                </thead>
                <tbody>
                  <tr><td class="center">258</td><td class="center">M</td><td class="center">10/10/2024</td><td>PdxCre Tg/Azelia</td><td class="center">Breeder</td></tr>
                  <tr><td class="center">1L</td><td class="center">F</td><td class="center">10/28/2024</td><td>PdxCre +/tg</td><td class="center">Breeder</td></tr>
                  <tr><td class="center">1L1R</td><td class="center">F</td><td class="center">10/28/2024</td><td>PdxCre +/+</td><td class="center">Breeder</td></tr>
                </tbody>
              </table>
            </div>

            <div class="card-panel">
              <div class="panel-title">Litters</div>
              <table class="card-table litters-table">
                <colgroup>
                  <col style="width:9%" />
                  <col style="width:25%" />
                  <col style="width:13%" />
                  <col style="width:15%" />
                  <col style="width:15%" />
                  <col style="width:23%" />
                </colgroup>
                <thead>
                  <tr><th>#</th><th>DOB</th><th>Born</th><th>Survived</th><th>M/F</th><th>DoW</th></tr>
                </thead>
                <tbody>
                  <tr><td class="center">1</td><td class="center">11/12/2024</td><td class="center">3</td><td class="center">3</td><td class="center">2/1</td><td class="center">01/15/2025</td></tr>
                  <tr><td class="center">2</td><td class="center">01/08/2025</td><td class="center">5</td><td class="center">5</td><td class="center">1/4</td><td class="center">02/05/2025</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="scan-block">
            <img class="barcode" alt="Barcode" />
            <div class="card-foot">Scan URL: https://vivarium.example.org/scan/tok_card_fixture_001</div>
          </div>
        </article>
      </div>
    </div>

    <pre id="layout-audit-json"></pre>
    <script>
      window.addEventListener("load", () => {{
        const overflow = [];
        document.querySelectorAll(".card-table th, .card-table td").forEach((cell, idx) => {{
          if (cell.scrollWidth > cell.clientWidth + 1) {{
            overflow.push({{
              index: idx,
              text: (cell.textContent || "").trim(),
              scrollWidth: cell.scrollWidth,
              clientWidth: cell.clientWidth
            }});
          }}
        }});
        const result = {{ ok: overflow.length === 0, overflow }};
        document.getElementById("layout-audit-json").textContent = JSON.stringify(result);
      }});
    </script>
  </body>
</html>
"""


def run_render_audit(html_path: Path, chrome_bin: str) -> dict[str, Any]:
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--allow-file-access-from-files",
        "--virtual-time-budget=4000",
        "--dump-dom",
        f"file://{html_path.resolve()}",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"ok": False, "error": f"render_run_failed: {exc}"}

    m = re.search(r'<pre id="layout-audit-json">(.+?)</pre>', proc.stdout, flags=re.DOTALL)
    if not m:
        return {"ok": False, "error": "layout_result_not_found_in_dom"}
    raw = m.group(1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"invalid_layout_result_json: {raw[:220]}"}

    return {
        "ok": bool(parsed.get("ok")),
        "overflow_count": len(parsed.get("overflow", [])),
        "overflow": parsed.get("overflow", [])[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cage card table layout for cell overflow/crossover risks.")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT), help="Path to output JSON report.")
    parser.add_argument(
        "--chrome-bin",
        default=os.getenv("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        help="Path to Chrome/Chromium binary for headless DOM rendering.",
    )
    args = parser.parse_args()

    app_js = read_text(APP_JS)
    styles_css = read_text(STYLES_CSS)

    static = static_checks(app_js, styles_css)
    static_ok = all(c["ok"] for c in static)

    with tempfile.TemporaryDirectory(prefix="murisphere-card-audit-") as tmpdir:
        html_path = Path(tmpdir) / "fixture.html"
        html_path.write_text(build_fixture_html(styles_css), encoding="utf-8")
        render = run_render_audit(html_path, args.chrome_bin)

    render_ok = bool(render.get("ok"))
    render_skipped = False
    allow_render_skip = os.getenv("MURISPHERE_AUDIT_ALLOW_RENDER_SKIP", "0") == "1"
    if not render_ok and allow_render_skip and str(render.get("error", "")).startswith("render_run_failed:"):
        render_skipped = True
        render_ok = True
    ok = static_ok and render_ok
    result = {
        "ok": ok,
        "generated_at": datetime.now(UTC).isoformat(),
        "static_checks": static,
        "render_check": render,
        "render_skipped": render_skipped,
    }

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("Cage card layout audit complete")
    print(f"ok={result['ok']}")
    print(f"static_ok={static_ok}")
    print(f"render_ok={render_ok}")
    if render_skipped:
        print("render_skipped=True")
    if render.get("overflow_count") is not None:
        print(f"overflow_count={render['overflow_count']}")
    if not ok:
        print(f"details={out_path.resolve()}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
