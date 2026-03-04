# Murisphere Code Audit Report

Date: 2026-03-04
Scope: `app.py`, `static/app.js`, test suite, CI/CD workflows
Auditor: Codex

## Executive Summary
The system is functional and testable, but it has several **production-blocking security and governance risks** that should be addressed before broad deployment.

Top concerns:
- Missing lab/facility tenant isolation in backend data access and mutation paths.
- Stored/reflective XSS risk in frontend rendering patterns.
- Sensitive token/session handling patterns suitable for prototype but not hardened production.

## Findings (ordered by severity)

### P0 - Cross-lab data access and mutation is not restricted by user scope
- Severity: Critical
- Location:
  - `app.py:305` (`/api/cages`)
  - `app.py:337` (`/api/cages/<id>`)
  - `app.py:373` (`PATCH /api/cages/<id>`)
  - `app.py:495`, `app.py:516`, `app.py:561`, `app.py:599`
- Issue:
  - Auth checks role, but most handlers do not enforce `lab_id` ownership for non-admin users.
  - A Technician or PI can operate on cages in other labs if they know IDs/tokens.
- Risk:
  - Multi-lab confidentiality and integrity breach.
  - Compliance risk for facility governance.
- Recommendation:
  - Enforce row-level authorization: all queries and updates must include allowed lab/facility scope from authenticated user context.

### P0 - Frontend renders unescaped server data into `innerHTML`
- Severity: Critical
- Location:
  - `static/app.js:49` (`tableFromCages`)
  - `static/app.js:203` (`runScan` template)
  - `static/app.js:269`, `static/app.js:358`, `static/app.js:365`
- Issue:
  - Several UI builders interpolate raw strings directly into HTML.
- Risk:
  - Stored XSS via notes/strain/genotype or imported records.
  - Token theft from `localStorage`, privilege escalation, data exfiltration.
- Recommendation:
  - Escape all content before insertion or render via DOM APIs (`textContent`), never raw `innerHTML` for untrusted values.

### P1 - Public scan endpoint exposes cage information without auth
- Severity: High
- Location:
  - `app.py:476` (`/api/public/scan/<token>`)
- Issue:
  - Possession of scan token gives direct unauthenticated access to cage details.
- Risk:
  - Token leakage from printed cards or logs exposes colony metadata.
- Recommendation:
  - Restrict payload for public scans to minimal non-sensitive fields.
  - Add token expiry/rotation, and optional signed one-time scan links.

### P1 - Debug mode enabled in runtime entrypoint
- Severity: High
- Location:
  - `app.py:928`
- Issue:
  - `debug=True` in `app.run(...)` can expose internals and unsafe behaviors if deployed incorrectly.
- Recommendation:
  - Disable debug by default; make environment-driven (`FLASK_ENV`, `DEBUG=0`).

### P1 - Session tokens stored plaintext and sent as bearer from `localStorage`
- Severity: High
- Location:
  - `app.py:266-271`, `app.py:152-164`
  - `static/app.js:2`, `static/app.js:22`
- Issue:
  - Token theft through XSS yields full account access until expiry.
- Recommendation:
  - Use HttpOnly secure cookies for session transport, rotate tokens, add idle timeout and revocation controls.

### P2 - Input validation is inconsistent for numeric and domain constraints
- Severity: Medium
- Location:
  - `app.py:417-422`, `app.py:499-501`, `app.py:565-576`, `app.py:718`
- Issue:
  - Counts may become negative; event dates/identifiers not strongly validated.
- Recommendation:
  - Add centralized validation layer (schema-based), enforce non-negative bounds and domain constraints.

### P2 - Large upload handling lacks guardrails
- Severity: Medium
- Location:
  - `app.py:638` (genotyping CSV), `app.py:744` (Excel import)
- Issue:
  - No explicit size/rate limits or parsing quotas.
- Recommendation:
  - Set request size limit, row limits, and reject oversized files early.

### P3 - Test coverage is strong for core flows but lacks adversarial/security cases
- Severity: Low
- Location:
  - `tests/test_app.py`, `tests/test_seed_large_demo.py`
- Gap:
  - No tests for tenant-bound authorization failures, XSS sanitization, token misuse, or upload abuse.
- Recommendation:
  - Add security regression tests and authorization matrix tests for all role/scope combinations.

## Positives
- Clear cage-centric domain model and API coverage.
- Good operational test baseline and scalable demo seeding.
- CI/CD pipelines in place and functioning.

## Priority Remediation Plan
1. Implement lab/facility row-level authorization checks on all reads/writes.
2. Remove unsafe `innerHTML` rendering of untrusted values.
3. Harden auth/session transport (HttpOnly cookies, token rotation).
4. Restrict public scan payload and lifecycle.
5. Add strict request validation and upload limits.
