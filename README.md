# Murisphere

Murisphere is a browser-based mouse colony and vivarium management SaaS optimized for **cage-level operations**.

## Product Name
**Murisphere**

## Why this implementation
- Cage-centric data model and workflows first.
- Scan-to-edit in browser (no dedicated mobile app required).
- Role-based permissions and complete audit trail.
- Facility-aware room/rack/capacity management.
- Reporting/export and API-first interoperability.

## Tech stack
- Backend: Flask + SQLite
- Frontend: Responsive HTML/CSS/JS (desktop/tablet/mobile)
- Export: CSV/Excel/PDF-style download endpoint

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open [http://localhost:8000](http://localhost:8000).

## Testing
```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

QR diagnostics:
```bash
python qrcode_diagnostic.py
```

## CI/CD
- CI workflow: `.github/workflows/ci.yml`
  - Python matrix tests (3.11, 3.12)
  - Backend syntax checks
  - Frontend JS syntax checks
- CD workflow: `.github/workflows/cd.yml`
  - Builds and publishes Docker image to GHCR on pushes to `main`
  - Image: `ghcr.io/<owner>/murisphere:latest` and `:sha-...`

## Documentation
- Documentation index: `docs/DOCUMENTATION_INDEX.md`
- Code audit report: `docs/CODE_AUDIT_REPORT.md`
- Step-by-step tutorial (HTML): `docs/tutorial/user_training_tutorial.html`
- Step-by-step tutorial (PDF): `docs/tutorial/user_training_tutorial.pdf`

## Large demo dataset (20 labs / 3,000 cages)
To populate a realistic large environment with variable lab sizes and multiple projects per lab:

```bash
python3 seed_large_demo.py
```

This seeds:
- 20 labs
- 3,000 cages
- 2-6 projects per lab
- Small/medium/large lab size tiers

## Demo users
- Admin: `admin@murisphere.local` / `admin1234`
- Technician: `tech@murisphere.local` / `tech1234`
- PI: `pi@murisphere.local` / `pi1234`

## Implemented requirement coverage

### 1) Web architecture
- Browser-only web app with responsive UI.
- Secure login, sessions, role checks, audit logging.

### 2) Cage-centric workflow
- Cage card payload generation with all required fields.
- Server-rendered QR PNG + CODE128 barcode SVG per cage card.
- Scan-to-open and in-room quick updates (counts/status/notes).

### 3) Core colony management
- Cages, animals, litters, lifecycle events, location hierarchy.
- Bulk litter-to-animal creation.

### 4) Breeding & scheduling
- Breeding event APIs + calendar view.
- Task-style event tracking for plug checks/weaning/harvests/retirement.

### 5) Genotyping integration
- CSV upload workflow to populate genotype results.
- Animal genotype update pipeline.

### 6) Analytics and planning
- Dashboard metrics: colony size, sex ratio, survival, capacity.
- Demand forecast endpoint for projected litter needs.

### 7) Reporting & interoperability
- CSV / XLSX / PDF endpoints.
- JSON APIs suitable for LIMS/ELN integration.
- Excel onboarding import endpoint.

### 8) Compliance & governance
- IACUC protocol table + near-expiration alerts.
- RBAC and full audit history endpoint.

### 9) Facility administration
- Multi-entity model: facilities/labs/rooms/racks.
- Capacity utilization endpoint.

### 10) Usability/performance
- Search/filter and low-click cage editing.
- Lightweight API paths for fast scan lookups.

## Notes
- This is a production-oriented MVP foundation. For enterprise deployment, next steps are PostgreSQL, SSO/OIDC, background jobs, HA deployment, and hardened PDF card rendering.
- QR and barcode rendering are intentionally server-generated to avoid client-side CDN/script failures in restricted facility networks.
