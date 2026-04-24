# Murisphere

Murisphere is a cage-first mouse colony and vivarium management platform for technicians, researchers, and animal facility managers. It is designed around the real workflow of a printed cage card in the room, a phone in hand, and a shared operational record that has to stay biologically accurate, audit-ready, and fast.

The product intentionally supports **two complete operating modes**:
- **Traditional workspace** for visual review, dashboards, batch operations, reporting, and admin workflows.
- **Chat-first console** for intent-driven work on phone, tablet, or desktop, especially when someone already knows what they need to ask, change, or print.

## Product Name
`Murisphere`

## GitHub About Message
`Cage-first mouse colony management for modern vivaria: print QR cage cards, scan with any phone, run breeding and compliance workflows, and stay audit-ready.`

## Why Murisphere Exists
Mouse colony work is full of high-frequency, low-tolerance tasks:
- counts change in the room, not at a desk
- litters, weans, transfers, and mortality must be documented in real time
- protocol, welfare, and training constraints must be visible at the moment of action
- investigators and facility managers need reports from the same data that technicians are updating

Murisphere is built so the same system can support room-speed work, facility oversight, and research planning without forcing everyone into the same interaction style.

## Two Ways To Work
| Mode | Best for | Typical users |
|---|---|---|
| Traditional workspace | visual triage, dashboards, cohorts, analytics, reports, batch operations | facility managers, admins, PIs, technicians on tablets/desktops |
| Chat-first console | quick questions, direct updates, phone workflows, print-and-scan loops | technicians, researchers, managers on rounds |
| Mixed use | scan in chat, continue in workspace; review in workspace, finish in chat | everyone |

## Cage Card Showcase
![Murisphere complete cage card preview](docs/tutorial/assets/cage_card_complete.svg)

Population shows full cage totals (`M/F/T`). `Tracked IDs Listed` indicates how many individual animal records are printed on the card. Litter rows include `DoW` (date of weaning).

A complete Murisphere cage card includes:
- cage code and room/rack/slot location
- PI / group owner and lab name
- linked project codes
- protocol number, description, and expiration date
- breeding status, cage DOB, and population counts
- animal table (`ID`, `Sex`, `DOB`, `Genotype`, `Status`)
- litter table (`DOB`, `Born`, `Survived`, `M/F`, `DoW`)
- QR code for direct phone-browser scan
- CODE128 barcode for scanner-based workflows or visual redundancy

## Core Capabilities
- Cage-centric workflow with direct scan-to-open on phone browsers.
- Printable cage cards with server-rendered QR code and barcode assets.
- Colony lifecycle tracking for animals, litters, breeding, weaning, transfers, mortality, euthanasia, wash, quarantine, and retirement.
- Facility operations for capacity, quotas, requests, SLAs, chargeback, and room/rack monitoring.
- Compliance coverage for protocol expiry hard-stops, deviations, quarantine, signatures, and audit history.
- Research support for pedigree, genotyping orders/callbacks, cohort planning, reservations, handoffs, and closeouts.
- Dual-mode UI so users can work visually in the workspace or conversationally in chat.
- Chat-first daily workflows for weaning queues, mortality follow-up, room batch cage-card printing, quota pressure, request SLA review, sample results, matching animal reservations, and closeout report shortcuts.

## Technology
- Backend: Flask + SQLite today, with explicit PostgreSQL runtime support through `storage.py`, `storage_sqlite.py`, and `storage_postgres.py`
- Frontend: responsive HTML/CSS/JS with both workspace and chat-first interfaces
- Desktop companion: Tauri shell for centralized Murisphere deployments
- Automation: GitHub Actions CI/CD with container smoke checks and artifact quality gates

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

## Tutorial-Ready Demo Seed
For onboarding, screenshots, and role-based walkthroughs, use the dedicated training seed:

```bash
./.venv/bin/python seed_tutorial_demo.py --db training_demo.db --force
MURISPHERE_DB=training_demo.db ./.venv/bin/python app.py
```

Seed profile:
- 20 labs
- 3,000 cages
- 73 projects
- 372 animals
- 48 litters
- 48 breeding pairs
- 48 sample records
- 6 planner scenarios
- 80 alert-driving tasks

Demo users:
- Admin / facility manager: `admin@murisphere.local` / `admin1234`
- Technician: `tech@murisphere.local` / `tech1234`
- Researcher / PI: `pi@murisphere.local` / `pi1234`

## Suggested Learning Path
1. Read the [self-paced tutorial](docs/tutorial/user_training_tutorial.md).
2. Open the browser tutorial build at `docs/tutorial/user_training_tutorial.html`.
3. Use the in-app `Start Learning` section after login.
4. Practice the same scenarios in both the workspace and the chat console.

## Documentation Map
- [Documentation index](docs/DOCUMENTATION_INDEX.md)
- [User guide](docs/USER_GUIDE.md)
- [Instructor guide](docs/INSTRUCTOR_GUIDE.md)
- [First-principles rethink](docs/FIRST_PRINCIPLES_RETHINK.md)
- [Workflow coverage matrix](docs/WORKFLOW_COVERAGE_MATRIX.md)
- [API reference](docs/API_REFERENCE.md)
- [Security and compliance](docs/SECURITY_COMPLIANCE.md)
- [Testing strategy](docs/TESTING_STRATEGY.md)
- [Deployment runbook](docs/DEPLOYMENT_RUNBOOK.md)
- [PostgreSQL migration guide](docs/POSTGRES_MIGRATION.md)
- [Operations runbook](docs/OPERATIONS_RUNBOOK.md)
- Tutorial HTML: `docs/tutorial/user_training_tutorial.html`
- Tutorial PDF: `docs/tutorial/user_training_tutorial.pdf`

## Desktop Companion
Murisphere includes a Tauri desktop companion scaffold in [desktop/README.md](/Users/liux17/Documents/colony/desktop/README.md).

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

The desktop shell shares the same operational model as the browser and phone workflows. On first launch, you can save the Murisphere base URL in the desktop setup screen. When run from source, it can also auto-start the local Flask backend for development.

Desktop packaging:
```bash
cd desktop
npm install
npm run build
```

GitHub desktop bundle workflow:
- Tag `main` with `desktop-v<version>` to trigger [`.github/workflows/desktop-release.yml`](/Users/liux17/Documents/colony/.github/workflows/desktop-release.yml).
- The workflow builds platform bundles for macOS, Linux, and Windows and uploads them as workflow artifacts.

## CI/CD And Release Validation
```bash
pip install -r requirements-dev.txt
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
node --check static/chat.js
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
Murisphere still runs on SQLite today, but the repo includes migration-prep tooling for a centralized shared database rollout:

```bash
python3 postgres_readiness_audit.py --out docs/test_reports/POSTGRES_READINESS.json
python3 postgres_export_bundle.py --db murisphere.db --out dist/postgres-bundle
```

Outputs:
- `docs/test_reports/POSTGRES_READINESS.json` - SQLite-specific blockers still present in code/schema
- `dist/postgres-bundle/manifest.json` - logical export manifest with dependency-aware table order
- `dist/postgres-bundle/tables/*.jsonl` - table data export for ETL into PostgreSQL

Current state:
- application endpoints route dialect-specific SQL through [storage.py](/Users/liux17/Documents/colony/storage.py), with backend implementations in [storage_sqlite.py](/Users/liux17/Documents/colony/storage_sqlite.py) and [storage_postgres.py](/Users/liux17/Documents/colony/storage_postgres.py)
- the runtime accepts `MURISPHERE_DB_DIALECT=postgres` plus `MURISPHERE_DATABASE_URL=<dsn>` for the PostgreSQL adapter path
- PostgreSQL bootstrap uses the checked-in [schema_postgres.sql](/Users/liux17/Documents/colony/schema_postgres.sql)
- the PostgreSQL readiness audit now passes for the Postgres-target runtime path
- current PostgreSQL schema bootstrap is a development bridge, not the final production migration plan

## Notes
- QR/barcode card assets are rendered server-side to avoid client CDN failures in restricted networks.
- For enterprise deployment, move from SQLite to PostgreSQL and add SSO/OIDC, rate limiting, and security header policy at ingress.

## License
Murisphere is licensed under the Apache License 2.0. See [LICENSE](/Users/liux17/Documents/colony/LICENSE) and [NOTICE](/Users/liux17/Documents/colony/NOTICE).
