# Testing Strategy

## Automated Tests
- Integration tests: `tests/test_app.py`
- Data-scale seed test: `tests/test_seed_large_demo.py`
- Syntax checks:
  - `python -m py_compile app.py seed_large_demo.py`
  - `node --check static/app.js`

## CI Execution
- GitHub Actions matrix on Python 3.11 and 3.12.
- Tests run on push and pull request.

## Manual Validation Checklist
- Login/logout across roles.
- Scan-to-edit from printed card.
- Cage card print and barcode phone scan.
- Genotyping CSV upload.
- Excel cage import.
- Reports export (CSV/XLSX/PDF).

## Missing Tests to Add
- Tenant authorization denial tests.
- XSS regression tests.
- Public scan token misuse/abuse tests.
- Upload size and malformed file behavior tests.
