# Security and Compliance Guide

## Implemented Controls (Current Release)
- Role-based access control: `Technician`, `PI`, `Admin`.
- Lab-scoped authorization checks on core data domains (cages, projects, orders, vet cases, recommendations, scenarios).
- Session authentication with hashed token storage and expiry; bearer header or HttpOnly cookie transport.
- Upload request size cap via `MURISPHERE_MAX_UPLOAD_BYTES` (default 5 MB).
- Full audit trail for major create/update/decision workflows.
- IACUC protocol tracking with protocol-expiry hard-stop on cage mutations.
- Compliance workflows: deviations/CAPA, quarantine intake/status, mortality + necropsy tracking, e-signature capture.
- Scope-aware alert feed and acknowledgment/dispatch logging.

## Public Scan Surface
- `GET /api/public/scan/<token>` is intentionally unauthenticated for room-floor phone scan workflows.
- Payload is reduced to cage-operational fields for quick lookup.
- Operational requirement: protect card/token handling and regenerate cards/tokens when leakage is suspected.

## Enterprise Hardening Items (Remaining)
- Add login/public endpoint rate-limiting and lockout policy.
- Add CSRF protection strategy for cookie-authenticated state-changing requests.
- Add strict security headers (CSP, `X-Frame-Options`, `Referrer-Policy`) at app or reverse proxy layer.
- Move secret management to a managed vault and enforce rotation policy.
- Migrate persistent storage from SQLite to PostgreSQL with encrypted backups and HA replication.

## Governance Practices
- Least-privilege role assignment with documented owner per lab/facility.
- Quarterly access review and immediate deprovisioning for role changes.
- Change control for schema/API releases with rollback plan.
- Backup retention + restore drills with evidence retention.
- Compliance evidence exports: audit logs, mortality/euthanasia reports, protocol-usage reports, signed actions.
