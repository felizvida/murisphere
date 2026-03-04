# Post-Remediation Audit Summary

Date: 2026-03-04

## Remediations Completed

### Tenant Isolation
- Implemented lab-scoped access checks for non-admin users across cage read/write workflows.
- Added scoped authorization helper (`ensure_cage_scope`) and applied to mutation endpoints.
- Restricted audit endpoint to Admin role.

### Frontend XSS Hardening
- Escaped dynamic values across major UI rendering paths.
- Reduced unsafe raw HTML interpolation risk by encoding data before insertion.

### Session/Auth Hardening
- Added HttpOnly session cookie issuance at login.
- Session lookup now supports cookie auth and stores hashed token digest in DB.
- Logout removes both DB session and cookie.

### Public Scan Hardening
- Public scan endpoint now returns reduced cage payload (no token, no notes/genotype details).

### Runtime/Validation Hardening
- Disabled debug by default (env-controlled via `FLASK_DEBUG=1`).
- Added upload request size cap (`MURISPHERE_MAX_UPLOAD_BYTES`, default 5MB).
- Added non-negative validation for key count fields.

## Verification
- Backend compile checks passed.
- Frontend JS syntax check passed.
- Automated tests passed: 8/8.
- Added cross-lab access regression test.

## Residual Risks / Next Hardening Steps
1. Add CSRF protection strategy for cookie-authenticated state-changing endpoints.
2. Add centralized request schema validation (e.g., Pydantic/Marshmallow).
3. Add rate-limiting and brute-force login protection.
4. Add security headers (CSP, X-Frame-Options, Referrer-Policy).
5. Migrate from SQLite to PostgreSQL for concurrent production workloads.
