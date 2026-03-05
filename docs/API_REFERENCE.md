# API Reference

Base URL: `http://<host>:8000`
Auth: `Authorization: Bearer <token>` for protected endpoints.

## Authentication
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

## Cage Operations
- `GET /api/cages?q=&status=`
- `GET /api/cages/<id>`
- `POST /api/cages` (PI/Admin)
- `PATCH /api/cages/<id>`
- `GET /api/scan/<code>`
- `POST /api/cages/cards`
- `POST /api/cages/bulk-actions` (PI/Admin; retire breeders or bulk transfer)

## Project Management
- `GET /api/projects`
- `POST /api/projects` (PI/Admin)
- `PATCH /api/projects/<id>` (PI/Admin)
- `GET /api/projects/<id>/cages`
- `POST /api/projects/<id>/assign-cages` (PI/Admin)

## Public Scan
- `GET /scan/<token>` (browser page)
- `GET /api/public/scan/<token>` (JSON payload)

## Card Rendering Assets
- `GET /api/assets/qrcode.png?v=<url_or_text>` (server-generated QR PNG)
- `GET /api/assets/barcode.svg?v=<code128_value>` (server-generated barcode SVG)

## Lifecycle and Breeding
- `POST /api/cages/<id>/wean`
- `POST /api/cages/<id>/transfer`
- `POST /api/cages/<id>/note`
- `POST /api/litters`
- `POST /api/breeding/events`
- `GET /api/calendar?start=&end=`
- `GET /api/breeding/productivity`
- `GET /api/breeding/non-productive`
- `GET /api/tasks/reminders`
- `GET /api/operations/sla`

## Genotyping and Imports
- `POST /api/genotyping/upload` (CSV multipart)
- `GET /api/genotyping/mendelian`
- `GET /api/genotyping/alerts`
- `POST /api/import/excel` (XLSX multipart)

## Analytics and Forecasting
- `GET /api/analytics/summary`
- `POST /api/forecast/demand`
- `GET /api/forecast/cage-space`
- `GET /api/forecast/consolidation`
- `GET /api/animals`
- `GET /api/animals/<id>/pedigree`

## Reporting
- `GET /api/reports/cages.csv`
- `GET /api/reports/cages.xlsx`
- `GET /api/reports/cages.pdf`
- `GET /api/reports/breeder-productivity.csv`
- `GET /api/reports/survival.csv`
- `GET /api/reports/protocol-usage.csv`

## Compliance and Admin
- `GET /api/compliance/protocol-alerts`
- `GET /api/facility/capacity` (PI/Admin)
- `GET /api/facility/quotas` (PI/Admin)
- `GET /api/facilities` (PI/Admin)
- `GET /api/facility/chargeback` (PI/Admin)
- `GET /api/facility/benchmark` (Admin)
- `GET /api/audit` (PI/Admin)

## Billing
- `GET /api/billing/rules` (PI/Admin)
- `POST /api/billing/rules` (Admin)
- `POST /api/billing/run` (PI/Admin)
- `POST /api/billing/close-period` (Admin)
- `GET /api/billing/statements.csv` (PI/Admin)

## Facility Requests
- `GET /api/requests`
- `POST /api/requests`
- `POST /api/requests/<id>/status` (PI/Admin)

## Integration Jobs
- `POST /api/integrations/export-jobs`
- `POST /api/integrations/export-jobs/<id>/run`
- `GET /api/integrations/export-jobs`
