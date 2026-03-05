# Murisphere Checkpoint (2026-03-05, Release Prep)

## Current State
- Release target is `v0.3.0`.
- Cage cards render server-side QR (`/api/assets/qrcode.png`) and barcode (`/api/assets/barcode.svg`) with no CDN dependency.
- Phone camera QR scan opens browser cage info via `/scan/<token>` and public token lookup endpoint.
- Large synthesized environment and alert pressure verification are implemented.
- Tutorial assets and workflow-first training docs are updated.

## Key Files in Active Change Set
- Core app/data model: `app.py`, `schema.sql`
- Frontend UX: `static/app.js`, `static/styles.css`, `templates/index.html`
- Tests: `tests/test_app.py`, `tests/test_alert_coverage_verifier.py`
- Diagnostics: `qrcode_diagnostic.py`, `ui_clickability_audit.py`, `alert_coverage_verifier.py`
- Release docs: `README.md`, `docs/*.md`, `docs/releases/v0.3.0.md`, tutorial files

## Verification Commands
```bash
python3 -m unittest discover -s tests -v
python3 qrcode_diagnostic.py
python3 ui_clickability_audit.py
python3 alert_coverage_verifier.py --db murisphere.db --ensure-schema
```

## Expected Results
- All unit/integration tests pass.
- QR diagnostic passes and confirms scan endpoint compatibility.
- UI clickability audit passes and updates HTML/JSON reports.
- Alert coverage verifier passes with broad multi-category alert pressure.

## Resume Priorities (if work pauses)
1. Implement rate-limiting and brute-force protection for auth/public scan.
2. Add browser E2E tests for phone-like scan flow on printed cards.
3. Add tenant-level security regression tests for all remaining API surfaces.
