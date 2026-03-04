# Security and Compliance Guide

## Current Controls
- Role-based endpoint restrictions.
- Session tokens with expiration.
- Audit trail for major data mutations.
- Protocol tracking and expiry alerts.

## Gaps Identified in Audit
- Tenant isolation enforcement incomplete.
- Frontend XSS vectors in unsanitized HTML rendering.
- Public scan endpoint can disclose cage data to token holders.

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
