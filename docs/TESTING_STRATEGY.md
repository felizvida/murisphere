# Testing Strategy

## Automated Tests
- Integration and workflow tests: `tests/test_app.py`
- Scale seed test (20 labs / 3,000 cages): `tests/test_seed_large_demo.py`
- Alert verifier unit tests: `tests/test_alert_coverage_verifier.py`
- QR/Barcode diagnostic: `qrcode_diagnostic.py`
- UI clickability contract + visual report: `ui_clickability_audit.py`
- Synthesized alert breadth verification: `alert_coverage_verifier.py`
- Syntax checks:
  - `python -m py_compile app.py seed_large_demo.py alert_coverage_verifier.py`
  - `node --check static/app.js`

Current baseline: 25 automated Python tests passing.

## CI Execution
- GitHub Actions matrix on Python 3.11 and 3.12.
- Tests run on push and pull request.

## Release Gate Commands
```bash
python3 -m unittest discover -s tests -v
python3 qrcode_diagnostic.py
python3 ui_clickability_audit.py
python3 alert_coverage_verifier.py --db murisphere.db --ensure-schema
```

Release artifacts:
- `docs/test_reports/UI_CLICKABILITY_REPORT.html`
- `docs/test_reports/UI_CLICKABILITY_RESULT.json`
- `docs/test_reports/ALERT_COVERAGE_RESULT.json`

## Manual Validation Checklist
- Login/logout across roles.
- Scan-to-edit from printed card.
- Cage card print and QR phone scan (camera opens browser to cage info).
- Genotyping CSV upload.
- Excel cage import.
- Reports export (CSV/XLSX/PDF).

## Remaining Test Gaps
- Browser E2E test for real phone scan journey on printed cards.
- Load/performance tests for bulk operations and scan lookup latency.
- Abuse simulation tests for public scan and login endpoints (rate-limit policy).
