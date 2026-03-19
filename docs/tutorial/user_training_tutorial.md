---
title: "Murisphere Workflow Tutorial"
subtitle: "Technician, Facility Manager, and Admin Workflow Guide"
author: "Murisphere Operations"
date: "2026-03-19"
geometry: margin=0.75in
fontsize: 11pt
colorlinks: true
toc: true
toc-depth: 3
---

# Purpose
This tutorial is organized by **real vivarium workflows** so technicians, PIs, and facility managers can move through daily work quickly, accurately, and consistently.

Murisphere is built around one operating rule:

**Print the cage card -> scan the QR with a phone -> open the cage in the browser -> complete the task immediately.**

# Roles
- Technician
- PI / Facility Manager
- Admin

# Training Environment Used In This Guide
The sample screenshots and examples in this tutorial assume a realistic demo environment:

- 20 labs
- 3,000 cages
- multiple projects per lab
- variable lab sizes (small, medium, large)
- active alerts, planner scenarios, breeding pairs, samples, and compliance records

# 1. Quick Start and Required Setup
## 1.1 First login and landing dashboard
1. Log in from phone, tablet, laptop browser, or the optional desktop companion.
2. After login, review the landing dashboard first.
3. Check alert severity, overdue work, room pressure, and planner risk before starting rounds.
4. Use clickable cage, project, and lab names to open the detailed view directly.

## 1.2 Card printing preflight
1. Open the cage card center.
2. Confirm the `Scan Base URL` points to a phone-reachable host or domain.
3. Print cards at **100% scale**.
4. Use the QR square for phone scanning.
5. Treat the 1D barcode strip as optional hardware-scanner support only.

## 1.3 Phone scan verification
1. Use the phone camera, not a separate mobile app.
2. Scan the printed QR code on a real card.
3. Tap the browser prompt.
4. Confirm cage ID and location before editing.
5. Save one test update and verify it appears immediately in cage history.

## 1.4 Optional desktop companion usage
Use the Tauri desktop companion for:
- batch card printing
- reporting and exports
- office workstations
- managed desktop environments

Use the web workflow for:
- phone scanning in rooms
- quick cage edits
- tablet rounds
- anywhere zero-install access matters

# 2. Mouse Technician Daily Workflows
## 2.1 Start-of-shift dashboard triage
1. Open the dashboard.
2. Review high-severity alerts first.
3. Review overdue tasks and protocol blocks.
4. Prioritize rooms with dense alert clusters or urgent welfare events.

## 2.2 Print or reprint cage cards
1. Search for the target cages.
2. Open the card center.
3. Batch-print selected cards.
4. Inspect print quality before placing cards in service.
5. Verify the QR is sharp, square, and fully visible.

## 2.3 Scan a printed cage card and quick-edit in room
1. Scan the printed QR with the phone camera.
2. Open the cage record in the browser.
3. Verify cage code, room, rack, and breeding status.
4. Update counts, notes, litter events, or status.
5. Save and confirm the audit trail entry appears.

## 2.4 Census and reconciliation
1. Start a census session for the room.
2. Scan each cage in sequence.
3. Reconcile observed M/F counts with the system totals.
4. Record mismatch notes before leaving the room.
5. Complete the session and verify all scans are synced.

## 2.5 Breeding operations
1. Create or review breeding pairs.
2. Record timed mating, plug check, litter, weaning, and transfer events.
3. Review pair productivity before keeping older breeders active.
4. Retire non-productive pairs when criteria are met.

## 2.6 Health, welfare, mortality, and euthanasia
1. Record welfare concerns during rounds.
2. Open vet cases and treatment schedules when needed.
3. Record mortality with necropsy requirement if appropriate.
4. Record euthanasia method, reason, and disposition.
5. Confirm critical welfare events raise alerts.

## 2.7 Tagging, samples, and genotyping logistics
1. Add ear tag, chip, tube, or well identifiers to animals.
2. Create sample records with unique sample codes.
3. Advance sample state through collection, shipment, receipt, and result.
4. Confirm chain-of-custody events are complete before handoff.

## 2.8 End-of-shift sync discipline
1. Confirm offline or queued writes are fully synced.
2. Close open census sessions and unfinished round notes.
3. Escalate unresolved high-severity findings before leaving.

# 3. Facility Manager Daily Workflows
## 3.1 Morning operations dashboard review
1. Open the landing dashboard.
2. Review alert counts by severity and category.
3. Review room density, cage pressure, and open task volume.
4. Open high-risk cages directly from dashboard links.

## 3.2 Capacity, quota, and chargeback review
1. Review facility capacity and room/rack utilization.
2. Review lab quotas and projected cage load.
3. Review chargeback and per-diem outputs for the current billing window.
4. Investigate overloaded rooms or underutilized allocations.

## 3.3 Alert ownership and notification dispatch
1. Review active alerts.
2. Acknowledge items that are known and assigned.
3. Dispatch notifications for unresolved urgent items.
4. Confirm escalation channels are configured correctly.

## 3.4 Recommendation and consolidation workflows
1. Generate recommendations.
2. Review each item with cage, lab, and risk context.
3. Decide: accept, adjust, ignore, or complete.
4. Track outcomes so the system can show operational value over time.

## 3.5 Planner scenarios and supply risk
1. Create planner scenarios with demand targets and needed-by dates.
2. Attach project-level demand where required.
3. Evaluate projected animal deficits, cage demand, and risk level.
4. Assign action owners for high-risk scenarios.

## 3.6 Desktop companion and office workflows
Use the optional desktop companion for:
- high-volume cage card printing
- long report review sessions
- export administration
- office or front-desk workstation use

# 4. Regulatory and Compliance Workflows
1. Monitor protocol expiration and hard-stop blocked edits.
2. Record deviations, CAPA items, and closure state.
3. Track quarantine intake, hold, release, and overdue cases.
4. Track qualification requirements for assigned procedures.
5. Capture attachments and e-signature evidence where required.
6. Use audit history to answer who changed what and when.

# 5. Research Support Workflows
1. Explore pedigree trees for breeding decisions.
2. Submit genotyping orders and receive provider callbacks.
3. Review Mendelian ratio and genotype deviation alerts.
4. Review planner scenarios tied to project demand.
5. Export CSV, PDF, and workflow job outputs for downstream systems.

# 6. Visual Walkthrough

## 6.1 Login Screen
![Login screen with role-aware access controls](assets/screenshot_login.svg){ width=95% }

## 6.2 Landing Dashboard, Cage Alerts, and Density View
![Dashboard-style cage alerts and room density visualization](assets/screenshot_cages_alerts.svg){ width=95% }
Use this screen immediately after login to prioritize work.

## 6.3 Cage Card Center and Batch Printing
![Card center and printing workflow](assets/screenshot_cards.svg){ width=95% }
Use this workflow to generate or reprint cards before rounds.

## 6.4 Complete Cage Card
![Complete cage card with owner, protocol, animal table, litter table, QR and barcode](assets/cage_card_complete.svg){ width=95% }
Population is the full cage total (M/F/T). `Tracked IDs Listed` shows how many individual records are printed. Litters include `DoW` (date of weaning).

## 6.5 Scan Base URL Setup
![Scan base URL configuration](assets/scan_base_url.svg){ width=95% }
Never print cards with `localhost` or another non-phone-reachable address.

## 6.6 Phone Camera Scan of Printed QR
![Phone scanning a printed QR cage card](assets/scan_phone.svg){ width=95% }
The phone camera should open the browser directly from the printed QR.

## 6.7 Scan-to-Edit Cage Workflow
![Phone scan flow from printed QR to cage browser view](assets/screenshot_scan.svg){ width=95% }
Use this flow for in-room edits with minimal taps.

## 6.8 Breeding Pair Productivity
![Breeding pair management and productivity tracking](assets/screenshot_breeding_pairs.svg){ width=95% }
Review productivity before continuing or retiring a pair.

## 6.9 Samples and Genotyping Workflow
![Sample chain-of-custody and genotyping result workflow](assets/screenshot_samples_genotyping.svg){ width=95% }
Sample and callback history should be complete and traceable.

## 6.10 Recommendations and Outcomes
![Recommendation lifecycle and decision outcomes](assets/screenshot_recommendations.svg){ width=95% }
Recommendations should become assigned actions, not passive dashboards.

## 6.11 Planner Scenario Evaluation
![Planner scenario risk and deficit evaluation](assets/screenshot_planner.svg){ width=95% }
Use the planner to understand supply gaps before they become operational failures.

## 6.12 Compliance Dashboard
![Compliance dashboard with alerts and open actions](assets/screenshot_compliance.svg){ width=95% }
Use this view for protocol, deviation, and evidence review.

## 6.13 Pedigree Explorer
![Multi-generation pedigree explorer](assets/screenshot_pedigree.svg){ width=95% }
Pedigree visualization is useful for breeding strategy and genotype interpretation.

## 6.14 Scan Troubleshooting Reference
![Scan troubleshooting reference](assets/scan_troubleshooting.svg){ width=95% }
Keep this guidance available anywhere cards are printed.

# 7. End-of-Shift and End-of-Day Checklists
## Technician
1. Confirm all queued writes are synced.
2. Confirm mortality, necropsy, euthanasia, and vet notes are complete.
3. Confirm all required room sessions are closed.
4. Hand off unresolved urgent issues before leaving.

## Facility Manager / Admin
1. Clear or owner-assign all high-severity alerts.
2. Review unresolved deviations and quarantine holds.
3. Review planner and recommendation items that remain high risk.
4. Export required summaries for audit, PI review, or operational handoff.

# 8. Troubleshooting and Escalation
- **No scan prompt appears:** improve lighting, flatten the card, and try the QR square again.
- **The phone reads only the barcode strip:** scan the QR square, not the 1D barcode.
- **Wrong page opens:** correct the `Scan Base URL` and reprint the card.
- **QR appears blank or broken:** verify the QR asset endpoint and regenerate the card.
- **Save appears queued:** reconnect and confirm sync before leaving the room.
- **Protocol hard-stop prevents edit:** assign a valid active protocol first.
- **Callback or sample mismatch occurs:** verify callback token, sample code, and animal mapping.
- **Planner risk remains high:** assign an owner and create a corrective action immediately.
