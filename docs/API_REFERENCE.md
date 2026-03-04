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

## Public Scan
- `GET /scan/<token>` (browser page)
- `GET /api/public/scan/<token>` (JSON payload)

## Lifecycle and Breeding
- `POST /api/cages/<id>/wean`
- `POST /api/cages/<id>/transfer`
- `POST /api/cages/<id>/note`
- `POST /api/litters`
- `POST /api/breeding/events`
- `GET /api/calendar?start=&end=`

## Genotyping and Imports
- `POST /api/genotyping/upload` (CSV multipart)
- `POST /api/import/excel` (XLSX multipart)

## Analytics and Forecasting
- `GET /api/analytics/summary`
- `POST /api/forecast/demand`

## Reporting
- `GET /api/reports/cages.csv`
- `GET /api/reports/cages.xlsx`
- `GET /api/reports/cages.pdf`

## Compliance and Admin
- `GET /api/compliance/protocol-alerts`
- `GET /api/facility/capacity` (PI/Admin)
- `GET /api/audit` (PI/Admin)
