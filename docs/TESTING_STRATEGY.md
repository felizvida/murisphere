# Testing Strategy

## Automated Tests
- Integration and workflow tests: `tests/test_app.py`
- PostgreSQL request-level integration tests: `tests/test_postgres_integration.py`
- PostgreSQL migration/tooling tests: `tests/test_postgres_tools.py`
- Desktop scaffold tests: `tests/test_desktop_scaffold.py`
- Scale seed test (20 labs / 3,000 cages): `tests/test_seed_large_demo.py`
- Tutorial-ready seed test: `tests/test_seed_tutorial_demo.py`
- Alert fixture seed tests: `tests/test_seed_alert_conditions.py`
- Alert verifier unit tests: `tests/test_alert_coverage_verifier.py`
- Alert fixture enrichment utility: `seed_alert_conditions.py`
- Tutorial-ready learning/demo seed utility: `seed_tutorial_demo.py`
- QR/Barcode diagnostic: `qrcode_diagnostic.py`
- UI clickability contract + visual report: `ui_clickability_audit.py`
- Synthesized alert breadth verification: `alert_coverage_verifier.py`
- Cage-card table alignment/overflow audit: `cage_card_layout_audit.py`
- Tutorial PDF build validation: `docs/tutorial/build_tutorial_pdf.py`
- Syntax checks:
  - `python -m py_compile app.py storage.py storage_sqlite.py storage_postgres.py generate_postgres_schema.py seed_large_demo.py seed_tutorial_demo.py seed_alert_conditions.py alert_coverage_verifier.py qrcode_diagnostic.py ui_clickability_audit.py cage_card_layout_audit.py docs/tutorial/build_tutorial_pdf.py postgres_export_bundle.py postgres_readiness_audit.py`
  - `node --check static/app.js`

Current baseline:
- `52` Python tests in the local suite
- branch-aware source coverage gate at `>=72%`
- container smoke validation in CD before image publish

## CI Execution
- GitHub Actions matrix on Python `3.11` and `3.12`.
- Dedicated PostgreSQL integration job against a live Postgres service.
- Dedicated quality-gates job for coverage, diagnostics, audits, and generated artifacts.
- Desktop scaffold/Tauri compile check on macOS.
- Docker image smoke test in CD before pushing to GHCR.
- Concurrency cancellation enabled to avoid stale duplicate runs on the same ref.

## Release Gate Commands
```bash
python -m py_compile app.py storage.py storage_sqlite.py storage_postgres.py generate_postgres_schema.py seed_large_demo.py seed_tutorial_demo.py seed_alert_conditions.py alert_coverage_verifier.py qrcode_diagnostic.py ui_clickability_audit.py cage_card_layout_audit.py docs/tutorial/build_tutorial_pdf.py postgres_export_bundle.py postgres_readiness_audit.py
python -m coverage erase
python -m coverage run -m unittest discover -s tests -v
python -m coverage run --append qrcode_diagnostic.py
python -m coverage run --append ui_clickability_audit.py
db="$(mktemp -t murisphere-alerts.XXXXXX.db)"
: > "$db"
MURISPHERE_DB="$db" python -m coverage run --append seed_large_demo.py
python -m coverage run --append seed_alert_conditions.py --db "$db"
python -m coverage run --append alert_coverage_verifier.py --db "$db"
python -m coverage report
python -m coverage xml -o docs/test_reports/coverage.xml
python -m coverage json -o docs/test_reports/coverage.json
node --check static/app.js
python3 cage_card_layout_audit.py
python3 docs/tutorial/build_tutorial_pdf.py
```

Release artifacts:
- `docs/test_reports/coverage.xml`
- `docs/test_reports/coverage.json`
- `docs/test_reports/UI_CLICKABILITY_REPORT.html`
- `docs/test_reports/UI_CLICKABILITY_RESULT.json`
- `docs/test_reports/ALERT_FIXTURE_RESULT.json`
- `docs/test_reports/ALERT_COVERAGE_RESULT.json`
- `docs/test_reports/CAGE_CARD_LAYOUT_RESULT.json`
- `docs/tutorial/user_training_tutorial.pdf`

## Manual Validation Checklist
- Login/logout across roles.
- Scan-to-edit from printed card.
- Cage card print and QR phone scan (camera opens browser to cage info).
- Genotyping CSV upload.
- Excel cage import.
- Reports export (CSV/XLSX/PDF).
- Pull published container and confirm `/api/system/health`.

## Remaining Test Gaps
- Browser E2E test for real phone scan journey on printed cards.
- Load/performance tests for bulk operations and scan lookup latency.
- Abuse simulation tests for public scan and login endpoints (rate-limit policy).
- Signed desktop bundle verification in the release workflow.
