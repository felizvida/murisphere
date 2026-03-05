# Security and Compliance Guide

## Current Controls
- Role-based endpoint restrictions.
- Session tokens with expiration.
- Audit trail for major data mutations.
- Protocol tracking and expiry alerts.
- Protocol-expiry hard stop for cage mutations.
- Export job listing/run scoped by lab for PI users.
- Pedigree traversal scope checks across ancestor nodes.

## Gaps Identified in Audit
- Public scan endpoint can disclose cage data to token holders.
- Local offline queue stores pending mutation payloads on client device.
- No rate-limiting/abuse protection on public scan and auth endpoints.

## Required Controls Before Production
- Row-level authorization by lab/facility.
- HttpOnly secure session cookies.
- CSP and output encoding strategy.
- Upload size and rate limits.
- Login rate limiting and lockout policy.

## Governance Practices
- Least-privilege role assignments.
- Quarterly access review.
- Change control for schema and API updates.
- Backup encryption and retention policy.
