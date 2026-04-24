# User Guide

## Recommended Training Setup
If you are learning Murisphere for the first time, use the tutorial-ready seed and the self-paced tutorial. After login, the landing dashboard includes a `Start Learning` section that links to the tutorial and guided example workflows.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./.venv/bin/python seed_tutorial_demo.py --db training_demo.db --force
MURISPHERE_DB=training_demo.db ./.venv/bin/python app.py
```

Keep these documents open together while you learn:
- `docs/tutorial/user_training_tutorial.md`
- `docs/USER_GUIDE.md`

## Choose Your Mode
Murisphere supports two complete ways to work.

### Traditional workspace
Best for:
- seeing dashboards, lists, and visual alerts
- batch printing cage cards
- reviewing projects, planner scenarios, compliance, and reports
- facility-wide triage on a larger screen

### Chat-first console
Best for:
- direct phone workflows
- asking for a specific cage, report, or action
- fast in-room updates after scanning a cage card
- role-based prompts such as `What needs attention today?`

### Mixed use
The intended pattern is often mixed:
- print in the workspace, then scan and continue in chat
- scan into a cage in chat, then switch into the workspace for richer visuals
- review alerts visually, then clear specific work by chat command

## Roles
- Technician: in-room cage updates, routine events, task completion, sample collection.
- Facility manager / admin: utilization, quotas, compliance, requests, billing, closeout oversight.
- Researcher / PI: project planning, genotype readiness, cohort review, breeder strategy, exports.

## Shared Workflow: Print, Scan, Act
1. Open the `Cages` workspace or ask chat to print a cage card.
2. Generate the print view and print at `100%` scale.
3. On phone, scan the **QR code** rather than the 1D barcode.
4. Open the cage in the browser.
5. Continue in either the workspace or the chat console.
6. Confirm the cage code and location before making any write.
7. Save immediately so the audit history reflects the real room event.

Notes:
- QR is for phone camera scan and browser jump.
- The 1D barcode supports scanner-based workflows and visual redundancy.
- If phone scan opens the wrong host, update `Scan Base URL` before printing cards.

## Technician Quick Reference
### Typical data entries
- male count
- female count
- breeding status
- note text
- task completion status
- mortality record
- litter and weaning values
- transfer destination
- sample collection state

### Typical reports
- today’s action list
- overdue task list
- cages with active alerts
- weaning list
- mortality follow-up list
- printable cage cards for the next room pass

### Recommended mode usage
- Use **chat** for `Open cage ...`, `Update cage ...`, `Complete task ...`, `Show overdue tasks`
- Use **workspace** for visual cage review, alert color scanning, pedigree inspection, and batch card printing

## Facility Manager Quick Reference
### Typical data entries
- request status
- quota/capacity settings
- billing adjustments
- SLA settings
- protocol follow-up actions
- deviation or escalation status
- project priority and closeout state
- training / qualification status

### Typical reports
- room utilization
- lab quota usage
- chargeback summary
- protocol expiration report
- mortality and necropsy report
- breeder productivity and survival report
- stalled cohort handoff report
- cohort closeout outcome report

### Recommended mode usage
- Use **workspace** for utilization, analytics, cohort flow, and exports
- Use **chat** for morning briefs, exception triage, request checks, and direct report requests

## Researcher / PI Quick Reference
### Typical data entries
- project targets
- genotype targeting rules
- cohort reservations and releases
- project handoff status
- closeout summaries
- sample / genotyping requests

### Typical reports
- genotype-ready cohort list
- breeder productivity by line
- project cage list
- protocol usage report
- cohort closeout summary
- stalled handoff list

### Recommended mode usage
- Use **workspace** for visual cohort review, pedigree, samples/genotyping, and planner scenarios
- Use **chat** for direct project summaries, cage lookup, and report retrieval on phone

## Samples And Genotyping
Use the `Reports` workspace for the samples/genotyping area, or use chat to jump directly into sample and project context.

Available workflows:
- review the genotyping dashboard for sample states, provider load, order flow, genotype mix, and turnaround pressure
- apply provider presets for Transnetyx, Charles River, or in-house qPCR workflows
- create samples from animal codes
- inspect sample event history
- select samples into genotyping orders
- submit draft orders
- download provider-ready CSV templates for a selected order
- import provider result CSV files back into the same order
- inspect reconciliation to see resulted, missing, in-transit, and blocked items
- review cohort readiness by project and see genotype-ready assignment candidates
- define project-specific genotype target rules such as `Cre/+` or `fl/*`
- apply built-in cohort templates or save a project’s current genotype rules as a reusable lab template
- reserve genotype-ready animals directly into project cohorts and release them when plans change
- move selected cohort animals through `reserved`, `assigned`, `shipped`, `consumed`, and `released`
- inspect assignment flow charts and recent cohort activity before handoff to research teams
- review downstream completion and disposition summaries to see how much of a cohort has actually finished experimental use
- record cohort closeouts with outcome notes and optional attachments
- define project-specific handoff SLAs and review repeat-breach alerts
- export closeout and stalled-handoff reports as CSV or PDF from analytics

## Visual Dashboards
### Workspace surfaces
- `Cages`: room density, breeding status mix, alerted cage ranking, card-print workflows
- `Breeding`: event timeline density, breeder productivity, survival trend
- `Analytics`: projected capacity, reminder pressure, sex balance, cohort flow, stalled handoff age buckets, repeat-breach watchlist, closeout outcome mix, export controls
- `Projects`: project inspector, genotype target rules, reservations, assignment flow, SLA settings
- `Compliance`: alert severity stack, category mix, protocol expiration watch, deviation context
- `Scan/Edit`: fast cage actions plus pedigree explorer
- `Reports`: samples/genotyping workspace, provider workflow, export actions

### Chat surfaces
- morning briefs
- role-based checklists
- direct cage opening
- guided updates with protocol hard-stops
- alerts, overdue tasks, and report summaries
- print and scan links returned as actions

## What The Tutorial-Ready Seed Includes
- 20 labs and 3,000 cages
- 73 projects across small, medium, and large labs
- active alerts for compliance and welfare practice
- pedigree-ready families with sire, dam, and pup relationships
- sample records in multiple chain-of-custody states
- planner scenarios for facility and project forecasting

## Common Troubleshooting
- Tutorial examples missing: you are likely using the scale-only seed instead of `seed_tutorial_demo.py`.
- Scan opens wrong host: set `Scan Base URL` to a phone-reachable host or LAN IP, never `localhost` on printed cards.
- Phone camera cannot detect code: ensure the printed card contains a QR square with good contrast.
- Camera detects only a barcode app, not a browser link: scan the QR square, not the CODE128 bar pattern.
- Report export fails: re-login and retry the endpoint.
- Card images missing: ensure the server is running, then reload the cards.
- Pop-up blocked during print: allow pop-ups and use `Generate + Print` again.
- Edit blocked by protocol: the cage protocol is expired; assign a valid protocol before editing counts or state.
- Queued update warning: restore network and verify sync by reloading the cage.
- Same scan keeps reopening: refresh once after the latest build; scan tokens are now cleared from the URL after capture.
