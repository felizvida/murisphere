# Murisphere Project Checkpoint

Date: 2026-03-04
Purpose: Full project recovery document assuming zero prior human memory.

## 1) Current State Summary
Murisphere is a web-based mouse colony management SaaS (Flask + SQLite + responsive frontend) with:
- cage-centric workflows
- scan-to-edit flow
- role-based auth
- audit logging
- reporting/import/export
- large demo seeding (20 labs, 3,000 cages)
- CI/CD pipelines
- full docs set

Repository path:
- `/Users/liux17/Documents/colony`

Main branch state right now:
- `main` is ahead of `origin/main` by 1 commit from earlier hardening/doc work.
- There are additional uncommitted local UI changes for mobile redesign + QR/print attempts.

## 2) Git Recovery Snapshot
Recent commits:
- `bc59baf` Remediate audit findings and expand documentation set
- `07abcdc` Add CI/CD workflows and full integration test suite
- `11e1f6d` Remove local artifacts and add gitignore
- `06b7512` Initial Murisphere SaaS implementation

Current uncommitted files:
- `templates/index.html`
- `static/styles.css`
- `static/app.js`
- `docs/tutorial/user_training_tutorial.html`
- `docs/tutorial/user_training_tutorial.pdf`

## 3) Implemented Architecture
Backend:
- `app.py`
- session-based auth (cookie + optional bearer compatibility)
- token digest storage in DB
- lab-scoped authorization for non-admin users
- upload size cap via `MURISPHERE_MAX_UPLOAD_BYTES` (default 5MB)

Database:
- `schema.sql`
- core entities: facilities/labs/projects/rooms/racks/cages/animals/litters/events/audit/sessions

Frontend:
- `templates/index.html` main SPA-like page
- `templates/scan.html` public scan landing page
- `static/app.js` UI logic
- `static/styles.css` current mobile-first redesign in progress

DevOps:
- CI: `.github/workflows/ci.yml`
- CD: `.github/workflows/cd.yml`
- container: `Dockerfile`, `.dockerignore`

## 4) Authentication and Demo Accounts
Default seeded users:
- `admin@murisphere.local` / `admin1234`
- `tech@murisphere.local` / `tech1234`
- `pi@murisphere.local` / `pi1234`

## 5) Data Seeding
Large seed script:
- `seed_large_demo.py`

Expected outcome:
- 20 labs
- 3,000 cages
- 2-6 projects per lab
- varied lab size tiers

Command:
```bash
python3 seed_large_demo.py
```

## 6) Validation Baseline (last successful run)
These passed before this checkpoint:
```bash
python3 -m py_compile app.py seed_large_demo.py docs/tutorial/build_tutorial_pdf.py
node --check static/app.js
.venv/bin/python -m unittest discover -s tests -v
```

Test suite status at last run:
- 8/8 tests passing

## 7) Known Open Issue (Critical UX)
Issue:
- Printed card scan flow still failing in latest local UI iteration.
- User reports QR appears as broken image or blank square.

Scope of issue:
- card preview/print in `static/app.js` and `static/styles.css`
- QR dependencies loaded from CDN in `templates/index.html`

Current attempted approach:
- Added QR library (`qrcode` CDN)
- Tried canvas rendering, then data URL image rendering
- Converted canvas to image during print serialization
- Still unresolved in user environment

Potential causes to investigate first:
1. QR library not actually loading (network/CDN blocked/CSP/ad blocker)
2. `QRCode.toDataURL` callback returning error, leading to empty/bad `src`
3. Browser blocking `data:` images in that context
4. Race condition: print called before QR generation finished
5. Mixed content/host policy issues

## 8) Exact Next Debug Plan (resume checklist)
1. Add runtime diagnostics in `app.js`:
   - log `typeof window.QRCode`
   - log callback error from `toDataURL`
   - log generated URL prefix/length
2. Add fallback:
   - if QR render fails, show visible text warning inside each card
3. Replace external CDN with local bundled/minified QR script in `static/` (remove network dependency)
4. Verify preview first, then print path:
   - ensure QR renders in preview
   - then test print window retains rendered image
5. Add automated frontend smoke check for QR elements existence (basic DOM assertion script if possible)
6. Update tutorial wording only after confirmed working.

## 9) Key Functional Files
Core app:
- `app.py`
- `schema.sql`
- `seed_large_demo.py`

Frontend:
- `templates/index.html`
- `templates/scan.html`
- `static/app.js`
- `static/styles.css`

Tests:
- `tests/test_app.py`
- `tests/test_seed_large_demo.py`

Docs:
- `docs/DOCUMENTATION_INDEX.md`
- `docs/CODE_AUDIT_REPORT.md`
- `docs/POST_REMEDIATION_AUDIT.md`
- `docs/tutorial/user_training_tutorial.html`
- `docs/tutorial/user_training_tutorial.pdf`

## 10) Documentation Inventory
Already present:
- architecture, API reference, deployment runbook, operations runbook, security/compliance, testing strategy, user guide, tutorial (HTML+PDF), initial and post-remediation audit.

## 11) Recommended Immediate Operator Commands
Check status:
```bash
cd /Users/liux17/Documents/colony
git status --short --branch
```

Run app:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Run tests:
```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 12) Project Continuation Note
Do not assume scan-to-phone is solved yet.
Treat QR rendering and printed-card scan reliability as the first task on resume.
