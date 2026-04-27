# Murisphere Re-Think: Two Active Product Lines

## Why This Document Exists
We are deliberately keeping **two parallel lines active**:

1. **Line A: Continue the current Murisphere platform**
   Keep the existing backend, data model, reporting surface, and operational breadth.
2. **Line B: Rebuild from first principles**
   Start with what a mouse technician, researcher, and animal facility manager actually do all day, what they change, what they worry about, and what they must report.

The intent is not to throw away the current system. The intent is to use first-principles operations to decide what the next interface should feel like, which workflows deserve one-step acceleration, and what can be simplified or removed.

## Working Thesis
For mouse colony work, the core product is not “a dashboard.” It is a **decision and logging surface for daily animal operations**:
- what happened in this cage today
- what must happen next
- what numbers changed
- what is late, abnormal, risky, or non-compliant
- what the facility and lab leadership need to know before the day ends

A good system reduces cognitive load during room work. A great system also prepares the exact reports and evidence the facility must produce later.

## Sources And Grounding
This rethink is based on:
- current Murisphere workflows and APIs in the repository
- the NIH/OLAW *Guide for the Care and Use of Laboratory Animals*
- OLAW/IACUC expectations around records, oversight, training, and program review
- common vivarium operational patterns inferred from institutional animal care programs, breeding colony practice, and manager reporting needs

Important U.S. nuance:
- purpose-bred laboratory mice are generally outside USDA AWA annual species-count reporting, but mouse facilities still operate under IACUC/OLAW, institutional policy, grant expectations, veterinary oversight, training requirements, and AAALAC-style evidence expectations.

## Line A: Current Murisphere Approach
The current product already has broad operational coverage.

### What It Is Good At
- cage-centric records and scan-to-open workflows
- printable cage cards with QR routing
- animal, litter, breeding, weaning, transfer, mortality, euthanasia, wash, quarantine, and genotyping workflows
- project, cohort, planner, and assignment workflows
- facility capacity, quotas, requests, chargeback, and benchmark reporting
- alerts, audit trail, signatures, tasks, and compliance tracking
- export/report endpoints across operations, breeding, survival, protocol usage, billing, mortality, and cohort handoffs
- a strong visual workspace for dashboards, lists, analytics, and batch operations

### What It Risks Doing Poorly
The current interface grew around feature coverage. That produces breadth, but it also creates common failure modes:
- too many tabs and forms competing for attention
- room staff must translate their real-world task into the app’s information architecture
- high-frequency tasks are mixed with analytical and administrative tools
- the user must know where a function lives before acting
- the interface can privilege modules over immediate action

### What We Should Preserve From Line A
We should preserve:
- the backend domain model
- the audit trail
- role-based access control
- scan-to-cage routing
- reporting/export endpoints
- operational alerts and compliance state
- enterprise deployment work already completed
- the traditional workspace as a complete visual operating surface

The backend is not the problem. The interaction model is what should be reconsidered and expanded.

## Line B: First-Principles View Of Real Work

## Technician: What They Care About Daily
A technician is usually trying to answer six questions, repeatedly, at room speed:
1. **Which cages need attention right now?**
2. **What do I have to change in this cage?**
3. **Did anything abnormal happen?**
4. **What must I finish before end of day?**
5. **What must be documented for breeding, welfare, or protocol compliance?**
6. **Who needs to know what I just found or changed?**

### Technician Daily Basics
A technician’s day usually contains some mix of:
- morning room rounds / welfare observation
- cage scanning or cage list review
- cage change and husbandry work
- breeder setup, separation, and retirement
- plug checks
- litter observation and litter recording
- weaning counts and pup redistribution
- transfers between room/rack/cage/project states
- mortality logging
- euthanasia or disposition logging
- health-round observations and veterinary escalation
- sample collection for genotyping
- request fulfillment or facility support tasks
- end-of-day reconciliation: what is overdue, incomplete, or abnormal

### Technician Numbers They Actually Change
High-frequency technician edits are concrete counts and state changes:
- male count
- female count
- total count
- cage status / breeding status
- litter size born
- litter size survived
- weaned male count
- weaned female count
- transfer-out count / transfer destination
- mortality count by sex or animal
- euthanasia count or animal disposition
- wash state / cage empty-ready status
- room, rack, and cage location
- sample collected / shipped / resulted status
- notes about abnormal findings
- task status: pending, in progress, done, blocked

### Technician Decision Triggers
The system should interrupt or guide a technician when:
- cage count changes no longer match listed animals
- overdue plug check / wean / harvest / task exists
- mortality or poor survival trend appears
- cage has protocol or welfare alert
- quarantine cage is overdue for review or release
- breeder is persistently non-productive
- cage location or population exceeds policy or practical limits
- sample/genotype result is needed for the next decision

## Animal Facility Manager: What They Care About Daily
A facility manager is usually less interested in a single cage and more interested in whether the operation is controlled.

They are trying to answer these questions:
1. **Are rooms, racks, and staffing under control today?**
2. **What is overdue, non-compliant, or escalating?**
3. **Which labs are above quota, at risk, or blocked?**
4. **What billing, utilization, and request metrics changed?**
5. **Is training, protocol coverage, and veterinary follow-up current?**
6. **What must be reported to leadership, IACUC, veterinarians, or investigators?**

### Facility Manager Daily Basics
A facility manager commonly reviews:
- active alert load and escalations
- room and rack occupancy/utilization
- protocol expiration or mismatch alerts
- quarantine intake status
- mortality and necropsy queue
- deviations and unresolved compliance issues
- facility requests and SLAs
- chargeback / per diem / service billing status
- staffing qualifications and assignment readiness
- animal census changes by lab / room / facility
- breeding productivity and colony efficiency
- downstream project demand vs available animals/cages

### Facility Manager Numbers They Actually Change
Common manager-edited values include:
- room capacity and allocation
- lab quota and expected load
- billing rules, rates, and adjustments
- request status and SLA decisions
- protocol versions and expiration follow-up
- deviation status and corrective actions
- qualification/training status
- project status, targets, and priority
- escalation thresholds and notification channels
- cohort handoff SLAs and closeout outcomes

### Manager Decision Triggers
The system should elevate attention when:
- room utilization is too high or uneven
- one lab is consuming space faster than expected
- protocol expiration is approaching or already breached
- a repeated deviation pattern appears
- mortality/necropsy or health-case volume spikes
- tasks are blocked because qualifications are missing
- service requests breach SLA repeatedly
- cohorts are stalled in assigned or shipped status
- chargeback volume diverges from expected census

## Researcher / PI: What They Care About Daily
A researcher or PI is trying to answer a third set of questions:
1. **Do I have the right animals at the right time?**
2. **Are genotype-ready animals being reserved and handed off correctly?**
3. **Is breeder productivity supporting project demand?**
4. **What happened biologically that could change study timing or interpretation?**
5. **What reports do I need for the next lab meeting, renewal, or manuscript figure?**

### Researcher Daily Basics
A researcher commonly reviews:
- genotype-ready cohorts
- project animal reservations and releases
- breeder productivity by line
- protocol alignment for current studies
- sample and genotyping status
- closeout outcomes and downstream animal use
- pedigree relationships when a line behaves unexpectedly

### Researcher Numbers They Actually Change
Common researcher-edited values include:
- project target counts
- genotype targeting rules
- cohort reservation decisions
- project priority or desired date
- closeout summaries and outcome notes
- sample or genotyping request state

### Researcher Decision Triggers
The system should elevate attention when:
- cohorts no longer satisfy genotype targets
- expected breeders are non-productive
- samples are delayed or missing results
- animals are stuck in handoff states too long
- protocol or welfare constraints jeopardize planned use

## Reports Each Role Actually Needs
### Technician
- today’s cage action list
- overdue breeding/weaning/plug-check list
- cage transfer list
- mortality / necropsy follow-up list
- quarantine cages needing action
- sample collection and genotyping result queue
- cage cards for selected cages or rooms
- room census snapshot for reconciliation

### Facility Manager
- active alerts by severity and category
- room/rack capacity and utilization
- census by facility, room, lab, and project
- protocol alert report
- task backlog and blocked task report
- service request SLA report
- mortality / necropsy queue
- quarantine status report
- billing statement preview / chargeback summary
- breeder productivity and non-productive breeder report
- survival report
- genotype distribution / Mendelian exception report
- cage space forecast
- cohort handoff and closeout report
- lab quota utilization report
- staffing qualification expiration / gap report
- deviation trend report
- veterinary case summary

### Researcher / PI
- genotype-ready cohort list
- breeder productivity by line
- project cage list
- protocol usage report
- cohort closeout summary
- stalled handoff list
- sample/genotyping result summary
- pedigree views for line interpretation

## What This Means For Product Design
The first-principles takeaway is that the user should not have to decide between `dashboard`, `projects`, `breeding`, and `reports` before acting.

The system should let them begin with natural work statements:
- “What needs attention in Room 3 today?”
- “Open cage C-A1-042.”
- “Weaned litter 211: 3 males, 4 females.”
- “Show protocol alerts for Hudson Lab.”
- “Generate this week’s mortality report.”
- “What requests are late?”
- “What changed since yesterday?”

That is why a **chat-first interface** is a credible next step. It is not a replacement for the workspace; it is a second complete interaction layer over the same operational engine.

## Product Direction: Dual-Mode, Not Backend-From-Scratch
We should **not** restart the backend from zero.

We should instead:
1. keep the current domain model and APIs
2. treat the current platform as the operational engine
3. preserve the traditional workspace as the visual and batch-operations surface
4. add and refine a conversational controller over the most common jobs
5. present data as reply cards, action prompts, links, and checklists
6. use structured follow-ups for sensitive write operations

## The First Chat Workflows We Should Support
### Technician Flows
- “What needs attention today?” — implemented.
- “Show my overdue tasks.” — implemented.
- “Open cage C-A1-001.” — implemented.
- “Update cage C-A1-001 to 2 males and 3 females.” — implemented.
- “Add note to cage C-A1-001: one pup runted.” — implemented.
- “Show cages with active alerts.” — implemented.
- “What needs weaning this week?” — implemented.
- “Show mortality follow-up.” — implemented.
- “Generate cage cards for Room 2.” — implemented as room batch print links.

### Manager Flows
- “Give me the facility morning brief.” — implemented.
- “Show room utilization.” — implemented.
- “Which labs are above expected load?” — implemented.
- “Show protocol alerts and upcoming expirations.” — implemented.
- “What requests breached SLA?” — implemented with a 48-hour chat SLA review threshold.
- “Show chargeback summary for 30 days.” — implemented through facility snapshot/report links.
- “Generate survival and breeder productivity reports.” — implemented through report links.
- “What cohorts are stalled?” — implemented.

### Researcher Flows
- “Show project L01-PRJ-01.” — implemented.
- “Show genotype-ready animals.” — implemented.
- “Reserve matching animals for project L01-PRJ-01.” — implemented for explicit PI/Admin reservations.
- “Show recent sample results.” — implemented.
- “Generate a project closeout report.” — implemented with table summary and export links.

## Current Multi-Mode Parity Checkpoint
As of `v0.4.x` development, the chat layer covers the first-principles daily prompts above while the traditional workspace remains the visual/batch surface.

Room Mode now adds the missing phone-first technician loop:
- choose a room
- start a room pass
- scan cages by QR token or cage code
- see a compact STOP / ACTION / WATCH / INFO state
- perform common cage-side actions through large touch cards
- complete an end-of-shift reconciliation summary

Design guardrails:
- chat write actions must be explicit, role-scoped, and audit-logged
- scan, cage, project, and report links should let the user jump between chat and the workspace
- chat should summarize the next decision, not replace rich visual review when a large table or chart is better
- Room Mode should be the default place for in-room phone work, not a scaled-down admin dashboard

## Recommendation
Keep both lines active and deliberate:
1. **Keep the workspace complete**
   Visual review, dashboards, batch operations, and exports remain essential.
2. **Keep the chat layer complete**
   High-frequency intent-driven work should be available without module hunting.
3. **Re-rank features by daily touch frequency**
   Technician, researcher, and manager daily loops should drive the default examples and prompts.
4. **Treat dashboards as generated answers, not the only entry point**
   A dashboard should help, but it should not be the only way to think.

## Immediate Build Consequences
This document implies three concrete product directions:
1. keep the traditional workspace healthy and complete
2. grow the chat-first interface into an equally complete operational surface
3. let users mix and match between both modes without losing context

## References
- NIH OLAW, *Guide for the Care and Use of Laboratory Animals*: https://olaw.nih.gov/policies-laws/guide-for-the-care-and-use-of-laboratory-animals
- NIH OLAW, FAQ and policy materials: https://olaw.nih.gov
- USDA Animal Welfare Act scope note for rats, mice, and birds: https://www.nal.usda.gov/animal-health-and-welfare/animal-welfare-act
