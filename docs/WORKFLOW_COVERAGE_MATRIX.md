# Workflow Coverage Matrix

This document enumerates routine workflows for:
- mouse technicians (in-room operations)
- facility managers/administrators (oversight, compliance, capacity, billing)

It maps each workflow to implemented features and identifies remaining roadmap gaps.
Release baseline: `v0.3.0` (2026-03-05).

## Mouse Technician Typical Routine Workflows

1. Start-of-shift room rounds and cage checks  
Features:
- Scan card to open cage: `GET /api/scan/<code>`, `GET /api/public/scan/<token>`
- Mobile UI visual cage alert overlay (row highlight + alert badge)
- Cage health rounds: `POST /api/health/rounds`, `POST /api/health/rounds/<id>/observe`, `POST /api/health/rounds/<id>/complete`
- Fast cage updates and notes: `PATCH /api/cages/<id>`, `POST /api/cages/<id>/note`

2. Breeding workflow execution  
Features:
- Setup and event logging: `POST /api/breeding/events`
- Weaning and transfers: `POST /api/cages/<id>/wean`, `POST /api/cages/<id>/transfer`
- Litter creation and bulk pup creation: `POST /api/litters`

3. Census and reconciliation  
Features:
- Census session start/scan/complete: `/api/census/sessions*`
- Reconciliation reports via cage detail + audit logs

4. Husbandry support and room logistics  
Features:
- Cage wash queue and status: `POST /api/cages/<id>/wash`, `POST /api/wash-events/<id>/status`, `GET /api/wash-events`
- Task assignments and qualification checks: `/api/tasks*`, `/api/staff/qualifications`

5. Animal welfare interventions  
Features:
- Vet case and treatments: `/api/vet/cases*`
- Planned euthanasia records: `POST /api/cages/<id>/euthanasia`
- Unexpected mortality records + necropsy status: `POST /api/cages/<id>/mortality`, `POST /api/mortality/<id>/necropsy`

6. Inbound animal intake and quarantine handling  
Features:
- Quarantine intake creation/listing/status: `/api/quarantine/intakes*`
- Quarantine overdue alerts: `GET /api/compliance/quarantine-alerts`

## Facility Manager / Vivarium Manager Typical Routine Workflows

1. Daily compliance review  
Features:
- Protocol expiry alerts: `GET /api/compliance/protocol-alerts`
- Deviation CAPA workflow: `/api/compliance/deviations*`
- Quarantine alerts: `GET /api/compliance/quarantine-alerts`
- Signature and attachment trails: `POST /api/sign`, `/api/attachments*`
- Full audit trail access: `GET /api/audit`

2. Capacity, room operations, and utilization  
Features:
- Capacity and quotas: `GET /api/facility/capacity`, `GET /api/facility/quotas`
- Facility multi-site view: `GET /api/facilities`
- Consolidation recommendations: `GET /api/forecast/consolidation`
- Cage-space forecast: `GET /api/forecast/cage-space`

3. Service request and SLA monitoring  
Features:
- Requests queue and approvals: `/api/requests*`
- SLA metrics: `GET /api/operations/sla`
- Facility benchmark endpoint: `GET /api/facility/benchmark`

4. Financial operations and chargeback  
Features:
- Billing rules/run/close/statements: `/api/billing/*`
- Billing adjustments and statement review: `POST /api/billing/adjustments`, `POST /api/billing/review`
- Chargeback dashboard endpoint: `GET /api/facility/chargeback`

5. Research support and planning  
Features:
- Demand forecast: `POST /api/forecast/demand`
- Breeding productivity and non-productive breeders: breeding analytics endpoints
- Genotyping ingestion, Mendelian analytics, alerts: `/api/genotyping/*`
- Data exports and integration jobs: reports endpoints + `/api/integrations/export-jobs*`

## Regulation and Compliance-Critical Workflows

Implemented:
- Protocol expiration hard-stop for cage edits
- Role-based access control (Technician/PI/Admin)
- Full audit records on write operations
- Deviation logging + CAPA + closure
- E-signature capture for approvals
- Quarantine tracking and alerting
- Euthanasia and mortality reporting
- Qualification gating for task assignment
- Active alert feed, acknowledgment, and escalation dispatch

## Helpful Research Workflows

Implemented:
- Multi-project labs and project-to-cage mapping
- Pedigree graph APIs
- Breeding timeline and reminders
- Genotype upload and filtering/alerts
- Forecasting for animal demand and space

## Gaps Still on Roadmap (Not Yet Implemented)

1. Sentinel program scheduling/results integration (microbiological surveillance)  
2. Controlled substance inventory/workflow for treatment drugs  
3. Full SOP checklist templates with required step signoff per room procedure  
4. Advanced necropsy pathology report ingestion (lab result attachment parsing)

These are non-blocking for core daily operations but are common in large regulated facilities.
