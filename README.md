# Murisphere

Murisphere is a browser-based mouse colony and vivarium management SaaS optimized for cage-level speed, data accuracy, and operational simplicity.

Current version: `v0.3.2`

## Product Name
`Murisphere`

## GitHub About Message
`Cage-first mouse colony management for modern vivaria: print QR cage cards, scan with any phone, run breeding and compliance workflows, and stay audit-ready.`

## Core Product Capabilities
- Cage-centric workflow with direct scan-to-edit on phone browsers.
- Printable cage cards with server-rendered QR code and CODE128 barcode.
- Colony lifecycle tracking (animals, litters, breeding, weaning, transfers, mortality).
- Facility operations (capacity, quotas, requests, wash workflow, billing/chargeback).
- Compliance stack (protocol expiry hard-stop, deviations, quarantine, audit, signatures).
- Research support (genotyping orders/callbacks, pedigree, planner scenarios, recommendations).

## Cage Card Showcase
![Murisphere complete cage card preview](docs/tutorial/assets/cage_card_complete.svg)
Population shows full cage totals (M/F/T). `Tracked IDs Listed` indicates how many individual records are printed. Litter rows include `DoW` (date of weaning).

Card content includes:
- Cage code and room/rack location.
- Group owner (PI), group/lab name, and linked project codes.
- Protocol number, protocol description, and protocol expiration date.
- Breeding status, cage DOB, and current population counts (M/F/Total).
- Animal table (ID, sex, DOB, genotype, status).
- Litter table (DOB, born, survived, sex split).
- QR code for direct phone-browser scan and barcode for optional scanner workflows.

## Technology
- Backend: Flask + SQLite, with explicit PostgreSQL runtime support through `storage.py`, `storage_sqlite.py`, and `storage_postgres.py`
- Frontend: responsive HTML/CSS/JS (desktop/tablet/phone)
- Desktop companion: Tauri shell for centralized Murisphere deployments
- Automation: GitHub Actions CI + CD (GHCR Docker publish)

## Quick Start
Option A (`venv`):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Option B (`uv`, if installed):
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python3 app.py
```

Open [http://localhost:8000](http://localhost:8000).

## Desktop Companion
Murisphere now includes a Tauri desktop companion scaffold in [desktop/README.md](/Users/liux17/Documents/colony/desktop/README.md).

Centralized desktop mode:
```bash
cd desktop
npm install
npm run dev
```

Local source-backed desktop mode:
```bash
cd desktop
npm install
npm run dev
```

The desktop shell is designed to share the same centralized backend as the browser and phone workflows. On first launch, you can save the Murisphere base URL in the desktop setup screen; when run from source, it can also auto-start the local Flask backend for development.

Desktop packaging:
```bash
cd desktop
npm install
npm run build
```

GitHub desktop bundle workflow:
- Tag `main` with `desktop-v<version>` to trigger [`.github/workflows/desktop-release.yml`](/Users/liux17/Documents/colony/.github/workflows/desktop-release.yml).
- The workflow builds platform bundles for macOS, Linux, and Windows and uploads them as workflow artifacts.

## Release Validation Commands
```bash
pip install -r requirements-dev.txt
python -m py_compile app.py storage.py storage_sqlite.py storage_postgres.py generate_postgres_schema.py seed_large_demo.py seed_alert_conditions.py alert_coverage_verifier.py qrcode_diagnostic.py ui_clickability_audit.py cage_card_layout_audit.py docs/tutorial/build_tutorial_pdf.py postgres_export_bundle.py postgres_readiness_audit.py
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

Generated artifacts:
- `docs/test_reports/coverage.xml`
- `docs/test_reports/coverage.json`
- `docs/test_reports/UI_CLICKABILITY_REPORT.html`
- `docs/test_reports/UI_CLICKABILITY_RESULT.json`
- `docs/test_reports/ALERT_FIXTURE_RESULT.json`
- `docs/test_reports/ALERT_COVERAGE_RESULT.json`
- `docs/test_reports/CAGE_CARD_LAYOUT_RESULT.json`
- `docs/tutorial/user_training_tutorial.pdf`

## PostgreSQL Migration Prep
Murisphere still runs on SQLite today, but the repo now includes migration-prep tooling for a centralized shared database rollout:

```bash
python3 postgres_readiness_audit.py --out docs/test_reports/POSTGRES_READINESS.json
python3 postgres_export_bundle.py --db murisphere.db --out dist/postgres-bundle
```

Outputs:
- `docs/test_reports/POSTGRES_READINESS.json` - SQLite-specific blockers still present in code/schema
- `dist/postgres-bundle/manifest.json` - logical export manifest with dependency-aware table order
- `dist/postgres-bundle/tables/*.jsonl` - table data export for ETL into PostgreSQL

Current state:
- application endpoints now route dialect-specific SQL through [storage.py](/Users/liux17/Documents/colony/storage.py), with backend implementations in [storage_sqlite.py](/Users/liux17/Documents/colony/storage_sqlite.py) and [storage_postgres.py](/Users/liux17/Documents/colony/storage_postgres.py)
- the runtime accepts `MURISPHERE_DB_DIALECT=postgres` plus `MURISPHERE_DATABASE_URL=<dsn>` for the PostgreSQL adapter path
- PostgreSQL bootstrap now uses the explicit checked-in [schema_postgres.sql](/Users/liux17/Documents/colony/schema_postgres.sql)
- the PostgreSQL readiness audit now passes for the Postgres-target runtime path
- current PostgreSQL schema bootstrap is a development bridge, not the final production migration plan

## CI/CD
- `./.github/workflows/ci.yml`
  - Python matrix tests (`3.11`, `3.12`)
  - Live PostgreSQL bootstrap/adapter integration job
  - Dedicated quality-gates job with coverage enforcement (`>=72%` branch-aware source coverage), QR diagnostic, UI clickability audit, seeded alert coverage audit, cage-card layout audit, tutorial PDF build, and artifact upload
  - Backend compile checks and frontend JS syntax checks
- `./.github/workflows/cd.yml`
  - Builds a smoke-test container, verifies `/api/system/health`, then publishes `ghcr.io/<owner>/murisphere` on `main`

## Demo Data and Scale
Seed a realistic environment:
```bash
python3 seed_large_demo.py
```

Seed profile:
- 20 labs
- 3,000 cages
- 2-6 projects per lab
- Variable lab sizes (small/medium/large tiers)

## Demo Users
- Admin: `admin@murisphere.local` / `admin1234`
- Technician: `tech@murisphere.local` / `tech1234`
- PI: `pi@murisphere.local` / `pi1234`

## Documentation
- [Documentation index](docs/DOCUMENTATION_INDEX.md)
- [User guide](docs/USER_GUIDE.md)
- [Workflow coverage matrix](docs/WORKFLOW_COVERAGE_MATRIX.md)
- [API reference](docs/API_REFERENCE.md)
- [Security and compliance](docs/SECURITY_COMPLIANCE.md)
- [Testing strategy](docs/TESTING_STRATEGY.md)
- [Deployment runbook](docs/DEPLOYMENT_RUNBOOK.md)
- [PostgreSQL migration guide](docs/POSTGRES_MIGRATION.md)
- [Operations runbook](docs/OPERATIONS_RUNBOOK.md)
- Tutorial HTML: `docs/tutorial/user_training_tutorial.html`
- Tutorial PDF: `docs/tutorial/user_training_tutorial.pdf`
- Release notes:
  - [v0.2.0](docs/releases/v0.2.0.md)
  - [v0.3.0](docs/releases/v0.3.0.md)
  - [v0.3.1](docs/releases/v0.3.1.md)
  - [v0.3.2](docs/releases/v0.3.2.md)

## Notes
- QR/barcode card assets are rendered server-side to avoid client CDN failures in restricted networks.
- For enterprise deployment, move from SQLite to PostgreSQL and add SSO/OIDC, rate limiting, and security header policy at ingress.

## License
Murisphere is licensed under the Apache License 2.0. See [LICENSE](/Users/liux17/Documents/colony/LICENSE) and [NOTICE](/Users/liux17/Documents/colony/NOTICE).
