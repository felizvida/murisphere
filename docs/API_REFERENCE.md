# API Reference

Base URL: `http://<host>:8000`  
Auth header for protected routes: `Authorization: Bearer <token>`

Browser scan landing page:
- `GET /scan/<token>` (opens cage context UI in browser)

## Authentication
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

## Cage Scan and Core Operations
- `GET /api/cages?q=&status=`
- `GET /api/cages/<id>`
- `POST /api/cages` (PI/Admin)
- `PATCH /api/cages/<id>`
- `GET /api/scan/<code>`
- `GET /api/public/scan/<token>`
- `POST /api/cages/cards`
- `POST /api/cages/bulk-actions` (PI/Admin)
- `POST /api/cages/<id>/wean`
- `POST /api/cages/<id>/transfer`
- `POST /api/cages/<id>/note`

## Card Asset Rendering
- `GET /api/assets/qrcode.png?v=<url_or_text>`
- `GET /api/assets/barcode.svg?v=<code128_value>`

## Projects and Lab Planning
- `GET /api/projects`
- `POST /api/projects` (PI/Admin)
- `PATCH /api/projects/<id>` (PI/Admin)
- `GET /api/projects/<id>/cages`
- `POST /api/projects/<id>/assign-cages` (PI/Admin)

## Breeding, Litters, Calendar
- `POST /api/litters`
- `POST /api/breeding/events`
- `POST /api/breeding/pairs`
- `GET /api/breeding/pairs`
- `POST /api/breeding/pairs/<id>/status`
- `GET /api/breeding/pairs/<id>/productivity`
- `GET /api/calendar?start=&end=`
- `GET /api/breeding/productivity`
- `GET /api/breeding/non-productive`
- `GET /api/tasks/reminders`

## Animal Records and Genetics
- `GET /api/animals`
- `GET /api/animals/<id>/pedigree`
- `POST /api/animals/<id>/tags`
- `GET /api/animals/<id>/tags`
- `POST /api/samples`
- `GET /api/samples`
- `POST /api/samples/<id>/status`
- `GET /api/samples/<id>/events`
- `POST /api/genotyping/upload` (CSV multipart)
- `POST /api/genotyping/orders`
- `GET /api/genotyping/orders`
- `POST /api/genotyping/orders/<id>/submit`
- `POST /api/genotyping/orders/callback` (provider callback token required)
- `GET /api/genotyping/mendelian`
- `GET /api/genotyping/alerts`

## Forecasting and Analytics
- `POST /api/forecast/demand`
- `GET /api/forecast/cage-space`
- `GET /api/forecast/consolidation`
- `GET /api/analytics/summary`
- `POST /api/planner/scenarios`
- `GET /api/planner/scenarios`
- `POST /api/planner/scenarios/<id>/projects`
- `POST /api/planner/scenarios/<id>/evaluate`
- `GET /api/planner/scenarios/<id>/plans`

## Census, Tasks, Staffing
- `POST /api/census/sessions`
- `POST /api/census/sessions/<id>/scan`
- `POST /api/census/sessions/<id>/complete`
- `GET /api/census/sessions/<id>`
- `POST /api/tasks/assign` (PI/Admin)
- `GET /api/tasks`
- `POST /api/tasks/<id>/status`
- `POST /api/staff/qualifications` (Admin)
- `GET /api/staff/qualification-alerts` (PI/Admin)

## Health and Veterinary Workflows
- `POST /api/health/rounds`
- `POST /api/health/rounds/<id>/observe`
- `POST /api/health/rounds/<id>/complete`
- `GET /api/health/rounds/<id>`
- `POST /api/vet/cases`
- `GET /api/vet/cases`
- `POST /api/vet/cases/<id>/treatments`

## Compliance Workflows
- `GET /api/compliance/protocol-alerts`
- `GET /api/alerts/feed`
- `GET /api/alerts/stream` (SSE, real-time stream)
- `POST /api/alerts/<id>/ack`
- `POST /api/alerts/dispatch` (PI/Admin)
- `POST /api/compliance/deviations`
- `GET /api/compliance/deviations`
- `POST /api/compliance/deviations/<id>/status` (PI/Admin)
- `POST /api/quarantine/intakes`
- `GET /api/quarantine/intakes`
- `POST /api/quarantine/intakes/<id>/status` (PI/Admin)
- `GET /api/compliance/quarantine-alerts` (PI/Admin)
- `POST /api/recommendations/generate` (PI/Admin)
- `GET /api/recommendations`
- `POST /api/recommendations/<id>/decision` (PI/Admin)
- `GET /api/recommendations/outcomes`
- `POST /api/cages/<id>/euthanasia`
- `POST /api/cages/<id>/mortality`
- `GET /api/mortality`
- `POST /api/mortality/<id>/necropsy` (PI/Admin)

## Facility Operations
- `POST /api/cages/<id>/wash`
- `POST /api/wash-events/<id>/status`
- `GET /api/wash-events`
- `GET /api/facility/capacity` (PI/Admin)
- `GET /api/facility/quotas` (PI/Admin)
- `GET /api/facilities` (PI/Admin)
- `GET /api/facility/chargeback` (PI/Admin)
- `GET /api/facility/benchmark` (Admin)
- `GET /api/operations/sla` (PI/Admin)
- `GET /api/notifications/channels` (PI/Admin)
- `POST /api/notifications/channels` (PI/Admin)
- `GET /api/requests`
- `POST /api/requests`
- `POST /api/requests/<id>/status` (PI/Admin)

## Billing
- `GET /api/billing/rules` (PI/Admin)
- `POST /api/billing/rules` (Admin)
- `POST /api/billing/run` (PI/Admin)
- `POST /api/billing/close-period` (Admin)
- `GET /api/billing/statements.csv` (PI/Admin)
- `POST /api/billing/adjustments` (Admin)
- `POST /api/billing/review` (PI/Admin)
- `GET /api/billing/rate-model` (PI/Admin)

## Orders and Integrations
- `POST /api/orders`
- `GET /api/orders`
- `POST /api/orders/<id>/status` (PI/Admin)
- `POST /api/protocols/<id>/versions` (PI/Admin)
- `GET /api/protocols/<id>/versions` (PI/Admin)
- `POST /api/integrations/export-jobs`
- `POST /api/integrations/export-jobs/<id>/run`
- `GET /api/integrations/export-jobs`

## Reporting and Governance
- `GET /api/reports/cages.csv`
- `GET /api/reports/cages.xlsx`
- `GET /api/reports/cages.pdf`
- `GET /api/reports/breeder-productivity.csv`
- `GET /api/reports/survival.csv`
- `GET /api/reports/protocol-usage.csv`
- `GET /api/reports/euthanasia.csv`
- `GET /api/reports/mortality.csv`
- `POST /api/attachments`
- `GET /api/attachments?entityType=&entityId=`
- `GET /api/attachments/<id>/download`
- `POST /api/sign`
- `GET /api/audit` (Admin)
- `POST /api/import/excel` (Admin)
