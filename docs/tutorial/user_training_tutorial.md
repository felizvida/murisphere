---
title: "Murisphere Workflow Tutorial"
subtitle: "Technician + Facility Manager Workflow Guide"
author: "Murisphere Operations"
date: "2026-03-05"
geometry: margin=0.75in
fontsize: 11pt
colorlinks: true
toc: true
toc-depth: 3
---

# Purpose
This tutorial is organized by **typical vivarium workflows** so teams can execute daily operations quickly and consistently.

# Roles
- Technician
- PI / Facility Manager
- Admin

# 1. Quick Start
1. Log in from phone/tablet/browser.
2. Set `Scan Base URL` to a phone-reachable host.
3. Print cards at 100% scale.
4. Validate one real scan before room rounds.

# 2. Mouse Technician Daily Workflows
## 2.1 Start-of-shift room prep
1. Review active alerts and prioritize high severity cages.
2. Review assigned tasks and due windows.
3. Confirm protocol blocks are addressed.

## 2.2 Phone scan of printed cage card
1. Scan printed QR with phone camera (not the 1D barcode strip).
2. Open link in browser.
3. Verify cage ID/location.
4. Update counts/status/notes.
5. Save and confirm persistence.

## 2.3 Census and reconciliation
1. Start census session.
2. Scan each cage and record observed counts.
3. Complete session and resolve mismatches.

## 2.4 Breeding operations
1. Create/manage breeding pairs.
2. Log timed mating, plug check, weaning, transfer events.
3. Review pair productivity and retire non-productive pairs.

## 2.5 Health and welfare
1. Run health rounds and log findings.
2. Open vet cases and treatments.
3. Record mortality + necropsy requirement.
4. Record euthanasia events.

## 2.6 Tagging and samples
1. Add animal tags (ear tag/chip/tube/well).
2. Create sample records.
3. Advance sample status (collected→shipped→received→resulted).
4. Verify sample chain-of-custody events.

# 3. Facility Manager Daily Workflows
## 3.1 Morning operations review
1. Review alert feed and severity distribution.
2. Acknowledge/escalate unresolved alerts.
3. Dispatch alert notifications.

## 3.2 Capacity and room operations
1. Review capacity/quotas and cage-space forecasts.
2. Review consolidation opportunities.
3. Prioritize cage wash and transfer workflows.

## 3.3 Recommendation lifecycle
1. Generate recommendations.
2. Decision each recommendation: accept, adjust, ignore, complete.
3. Track outcomes by recommendation type/status.

## 3.4 Planner scenarios
1. Create scenario with demand and constraints.
2. Attach project-level demand.
3. Evaluate projected deficit and risk.
4. Review plan snapshots and assign corrective actions.

# 4. Regulatory and Compliance Workflows
1. Protocol expiry monitoring and edit hard-stop.
2. Deviation/CAPA logging and closure.
3. Quarantine intake/clearance tracking.
4. Qualification expiration monitoring.
5. E-signature and attachment evidence.
6. Full audit review.

# 5. Research Support Workflows
1. Pedigree analysis for breeding decisions.
2. Genotyping order submission.
3. Provider callback result ingestion.
4. Mendelian/deviation monitoring.
5. Reporting/export/integration jobs.

# 6. Visual Walkthrough

## 6.1 Login and Role-aware Access
![Login screen with role-aware access controls](assets/screenshot_login.svg){ width=95% }

## 6.2 Complete Cage Card (Print + Scan)
![Complete cage card with owner, protocol, animal table, litter table, QR and barcode](assets/cage_card_complete.svg){ width=95% }
Population is the full cage total (M/F/T). `Tracked IDs Listed` shows how many individual records are printed. Litters include `DoW` (date of weaning).

## 6.3 Phone Scan and Quick Edit
![Phone scan flow from printed QR to cage browser view](assets/screenshot_scan.svg){ width=95% }

## 6.4 Cage Alerts and Room Density
![Cage alert highlighting and room density visualization](assets/screenshot_cages_alerts.svg){ width=95% }

## 6.5 Breeding Pair Productivity
![Breeding pair management and productivity tracking](assets/screenshot_breeding_pairs.svg){ width=95% }

## 6.6 Samples and Genotyping Workflow
![Sample chain-of-custody and genotyping result workflow](assets/screenshot_samples_genotyping.svg){ width=95% }

## 6.7 Recommendations and Outcomes
![Recommendation lifecycle and decision outcomes](assets/screenshot_recommendations.svg){ width=95% }

## 6.8 Planner Scenario Evaluation
![Planner scenario risk and deficit evaluation](assets/screenshot_planner.svg){ width=95% }

## 6.9 Compliance Dashboard
![Compliance dashboard with alerts and open actions](assets/screenshot_compliance.svg){ width=95% }

## 6.10 Pedigree Explorer
![Multi-generation pedigree explorer](assets/screenshot_pedigree.svg){ width=95% }

# 7. End-of-Shift / End-of-Day Checklists
## Technician
1. Confirm offline queue drained and synced.
2. Confirm health/vet/mortality/euthanasia records complete.
3. Close open room sessions.

## Manager
1. Resolve or owner-assign all high severity alerts.
2. Review unresolved deviations/quarantine blocks.
3. Review planner risk and recommendation decisions.
4. Export daily summary/audit package.

# 8. Troubleshooting and Escalation
- No scan prompt: improve lighting and card contrast.
- Camera only sees barcode value: scan the QR square, not the CODE128 bars.
- Wrong destination: fix `Scan Base URL`; never use localhost for printed cards.
- QR broken: verify `/api/assets/qrcode.png?v=test`.
- Save queued: reconnect and verify sync before leaving room.
- Protocol hard-stop: assign valid protocol and retry.
- Genotyping callback mismatch: verify callback token and sample code mapping.
