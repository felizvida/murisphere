# Architecture Overview

## System Shape
- Web app architecture: Flask backend + SQLite database + static browser frontend.
- Browser-only operation on desktop/tablet/phone.
- Primary workflow: cage-card scan -> cage lookup -> in-room edit.

## Core Components
- API server: `app.py`
- UI templates: `templates/index.html`, `templates/scan.html`
- Frontend logic: `static/app.js`
- Card media rendering: server-side QR/Barcode asset endpoints
- Data model: `schema.sql`
- Demo scale seeding: `seed_large_demo.py`

## Data Domains
- Facility hierarchy: Facility -> Room -> Rack -> Cage
- Colony entities: Cage, Animal, Litter, Lifecycle Event
- Breeding/events: Timed mating, plug checks, weaning, harvest, retirement
- Compliance/governance: Users, Roles, Sessions, Audit logs, IACUC protocols
- Program layer: Lab, Project, Project-Cage mapping, Lab profiles

## Security Model (Current)
- Session bearer token in `Authorization` header.
- Role gates: Technician, PI, Admin.
- Audit logs for create/update lifecycle actions.

## Security Model (Target)
- Row-level tenant isolation by lab/facility scope.
- HttpOnly secure session cookies.
- Input schema validation and upload limits.
- Reduced public scan surface.

## Runtime and Deployment
- Local: `python app.py`
- Container: `Dockerfile`
- CI: `.github/workflows/ci.yml`
- CD image publish: `.github/workflows/cd.yml`
- No CDN dependency for cage-card QR/barcode rendering

## Performance Notes
- Lightweight scan lookup path with indexed cage keys.
- Bulk reporting endpoints for CSV/XLSX/PDF.
- Demo scaling validated at 20 labs and 3,000 cages.
