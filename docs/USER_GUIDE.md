# User Guide

## Recommended Training Setup
If you are learning Murisphere for the first time, use the tutorial-ready seed and the self-paced tutorial.
After login, the landing dashboard includes a `Start Learning` section that links to the tutorial and the guided example workflows.
That same panel can store lightweight module-completion progress in the current browser so learners can resume later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./.venv/bin/python seed_tutorial_demo.py --db training_demo.db --force
MURISPHERE_DB=training_demo.db ./.venv/bin/python app.py
```

Then keep these two documents open together:
- `docs/tutorial/user_training_tutorial.md`
- `docs/USER_GUIDE.md`

## Roles
- Technician: in-room cage updates, routine events.
- PI: colony oversight, planning, reports.
- Admin: user governance, imports, facility-level administration.

## Samples And Genotyping
Use the `Reports` tab for the samples/genotyping workspace.

- review the genotyping overview dashboard for sample states, provider load, order flow, and genotype mix
- apply provider presets for Transnetyx, Charles River, or in-house qPCR workflows
- create samples from animal codes
- inspect sample event history
- select samples into genotyping orders
- submit draft orders
- download provider-ready CSV templates for a selected order
- import provider result CSV files back into the same order
- inspect order reconciliation to see resulted, missing, in-transit, and blocked items
- review cohort readiness by project and see genotype-ready assignment candidates
- define project-specific genotype target rules such as `Cre/+` or `fl/*`
- apply built-in cohort templates or save a project's current genotype rules as a reusable lab template
- reserve genotype-ready animals directly into project cohorts and release them when plans change
- move selected cohort animals through `reserved`, `assigned`, `shipped`, `consumed`, and `released`
- inspect assignment flow charts and recent project cohort activity before handing animals off to research teams
- review downstream completion and disposition summaries to see how much of a cohort has actually finished experimental use
- record project cohort closeouts with outcome notes and optional attachments
- classify closeouts with a structured outcome reason such as `Met Goal`, `Partial Data`, or `Welfare/Compliance Stop`
- define project-specific handoff SLAs for `assigned` and `shipped` stages plus a repeat-breach threshold
- export closeout and stalled-handoff reports as CSV or PDF directly from the analytics workspace
- inspect breeder decision signals that connect genotyping output back to colony planning
- review order items and results
- inspect Mendelian summaries and genotype alerts

## What The Tutorial-Ready Seed Includes
- 20 labs and 3,000 cages
- 73 projects across small, medium, and large labs
- active alerts for compliance and welfare practice
- pedigree-ready families with sire, dam, and pup relationships
- sample records in multiple chain-of-custody states
- planner scenarios for facility and project forecasting

## Critical Workflow: Print and Phone Scan
1. Login and open `Cages`.
2. Select cages and click `Generate + Print`.
3. Print at 100% scale.
4. On phone, scan the **QR code** (not the 1D barcode).
5. Tap the camera link to open cage info in browser.
6. Verify cage code and location before any update.
7. Apply updates and confirm save.

Notes:
- QR is for phone camera scan and browser jump.
- 1D barcode is for barcode devices/workflows and visual redundancy.
- If phone scan opens wrong host, update `Scan Base URL`.

## Daily Technician Tasks
- Scan cage card and open cage record.
- Watch cage list highlight colors and alert badges for abnormal cages.
- Update M/F counts.
- Update breeding status.
- Add notes and event records.
- Manage breeding pairs (sire/dam) and monitor pair productivity.
- Tag animals and track sample lifecycle (collected, shipped, received, resulted).
- Run health rounds and record observations.
- Record mortality events and necropsy-required flags when applicable.
- Queue cages for wash and track status.
- If offline queue warning appears, reconnect and verify queued updates synced.

## Visual Dashboards (Fast Situational Awareness)
- `Cages` tab: room density, breeding status mix, alerted cage ranking.
- `Breeding` tab: event timeline density, breeder productivity/survivor trend.
- `Analytics` tab: projected capacity bars, reminder pressure curve, sex balance donut, cross-lab cohort flow, stalled handoff age buckets, repeat-breach project watchlist, closeout outcome mix, and export controls.
- `Projects` tab: project cohort closeout panel plus per-project handoff SLA settings with live breach status.
- `Compliance` tab: alert severity stack, category mix donut, protocol expiration watch.
- `Scan/Edit` tab: pedigree explorer (interactive lineage chart by animal ID).

## PI/Admin Tasks
- Schedule breeding events and monitor calendar.
- Review analytics and demand forecasts.
- Review facility-wide cohort flow by lab to see where assignments are still in flight versus already completed.
- Watch the alert feed for stalled cohort assignments, especially animals that remain in `assigned` or `shipped` too long.
- Configure project handoff SLAs when one study has tighter timelines than the facility default.
- Watch for `Project Handoff SLA Repeatedly Breached` alerts to catch projects that are missing handoffs again and again.
- Filter cohort analytics by closeout status and outcome reason when you need to understand why studies ended early or finished partially.
- Export filtered closeout summaries or current stalled-handoff lists before PI reviews, audits, or weekly operations meetings.
- Build planner scenarios and evaluate projected deficits/risk.
- Generate recommendations and apply decisions (accept/adjust/ignore/complete).
- Submit genotyping orders and ingest callback results automatically.
- Review compliance dashboards: protocol alerts, deviation CAPA, quarantine alerts.
- Configure alert channels and dispatch escalations (`in_app`, webhook, email-simulated).
- Review and close necropsy status for mortality records.
- Run exports and compliance checks.
- Import large onboarding files when needed.

## Common Troubleshooting
- Tutorial examples missing: you are likely using the scale-only seed instead of `seed_tutorial_demo.py`.
- Scan opens wrong host: set `Scan Base URL` to phone-reachable host (never localhost on printed cards).
- Phone camera cannot detect code: ensure the printed card contains a QR square and sufficient contrast.
- Camera detects only barcode app, not browser link: scan the QR square, not the CODE128 bar pattern.
- Report export fails: re-login and retry endpoint.
- Card images missing: ensure server is running and reload cards.
- Pop-up blocked during print: allow pop-ups and use `Generate + Print`.
- Edit blocked by protocol: cage protocol is expired; reassign valid protocol before editing.
- Queued update warning: restore network and verify sync by reloading the cage.
