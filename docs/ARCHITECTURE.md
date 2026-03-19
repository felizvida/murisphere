# Architecture Overview

## System Shape
- Web app architecture: Flask backend + SQLite database + static browser frontend.
- Hybrid client direction: browser/phone primary plus optional Tauri desktop companion.
- Browser-only operation on desktop/tablet/phone.
- Primary workflow: cage-card scan -> cage lookup -> in-room edit.
- Design priority: cage-level speed -> data accuracy -> operational simplicity -> analytics.

## Core Components
- API server: `app.py`
- UI templates: `templates/index.html`, `templates/scan.html`
- Frontend logic: `static/app.js`
- Desktop companion scaffold: `desktop/`
- Card media rendering: server-side QR/Barcode asset endpoints
- Data model: `schema.sql`
- Demo scale seeding: `seed_large_demo.py`
- Validation tools: `qrcode_diagnostic.py`, `ui_clickability_audit.py`, `alert_coverage_verifier.py`
- Migration tools: `postgres_readiness_audit.py`, `postgres_export_bundle.py`

## Data Domains
- Facility hierarchy: Facility -> Room -> Rack -> Cage
- Colony entities: Cage, Animal, Litter, Lifecycle Event
- Breeding/events: Timed mating, plug checks, weaning, harvest, retirement
- Compliance/governance: Users, Roles, Sessions, Audit logs, IACUC protocols
- Program layer: Lab, Project, Project-Cage mapping, Lab profiles
- Enterprise operations: census sessions, facility requests, billing rules/entries/reviews, order lifecycle
- Welfare and oversight: health rounds, vet cases/treatments, quarantine intake/status, mortality/necropsy
- Planning intelligence: recommendation engine and planner scenarios with projected deficit/risk

## Security Model (Current)
- Session bearer token in `Authorization` header.
- Role gates: Technician, PI, Admin.
- Lab scope enforcement across principal entity workflows.
- Audit logs for create/update lifecycle actions.
- Protocol-expiry hard stop on cage mutations.

## Security Model (Target)
- Row-level tenant isolation by lab/facility scope.
- HttpOnly secure session cookies.
- Input schema validation and upload limits.
- Reduced public scan surface.

## Runtime and Deployment
- Local: `python app.py`
- Container: `Dockerfile`
- Desktop companion: Tauri shell in `desktop/`, targeting a centralized backend or source-local Flask runtime
- CI: `.github/workflows/ci.yml`
- CD image publish: `.github/workflows/cd.yml`
- Desktop bundle workflow: `.github/workflows/desktop-release.yml`
- No CDN dependency for cage-card QR/barcode rendering

## Performance Notes
- Lightweight scan lookup path with indexed cage keys.
- Bulk reporting endpoints for CSV/XLSX/PDF.
- Demo scaling validated at 20 labs and 3,000 cages.
- Alert/analytics layers are additive and do not block cage update paths.

## Enterprise Direction
- Recommended deployment remains centralized backend plus shared database.
- Web stays primary for phone and tablet cage workflows.
- Tauri is positioned as a desktop companion for reporting, printing, local desktop integrations, and future workstation/offline flows.
- PostgreSQL remains the target shared database for enterprise rollout; the repo now includes a readiness audit and logical export bundle generator to support that transition.
