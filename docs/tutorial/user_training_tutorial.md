---
title: "Murisphere Role-Based Tutorial"
subtitle: "Technician, Facility Manager, and Researcher Workflows Across Workspace and Chat"
author: "Murisphere Operations"
date: "2026-04-13"
geometry: margin=0.72in
fontsize: 11pt
colorlinks: true
toc: true
toc-depth: 3
---

# Purpose
This tutorial teaches Murisphere through the three roles that actually drive mouse colony work every day:

1. **Technician**
2. **Facility manager / vivarium administrator**
3. **Researcher / PI**

Murisphere now supports **two full operating modes**:
- a **traditional workspace** for visual review, dashboards, lists, reports, and batch actions
- a **chat-first console** for direct, phone-friendly commands and quick operational work

The important point is not to choose one forever. The important point is to use the mode that is fastest and safest for the task in front of you.

This tutorial is built from a **real seeded training dataset** generated on **April 13, 2026**. The cage codes, projects, sample records, planner scenarios, and alerts below come from that training dataset.

# Training Setup
## Create the tutorial database
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./.venv/bin/python seed_tutorial_demo.py --db training_demo.db --force
MURISPHERE_DB=training_demo.db ./.venv/bin/python app.py
```

## Training accounts
- Admin / facility manager: `admin@murisphere.local` / `admin1234`
- Technician: `tech@murisphere.local` / `tech1234`
- Researcher / PI: `pi@murisphere.local` / `pi1234`

## What this seed contains
| Category | Count |
|---|---:|
| Labs | 20 |
| Cages | 3,000 |
| Projects | 73 |
| Animals | 372 |
| Litters | 48 |
| Breeding pairs | 48 |
| Sample records | 48 |
| Planner scenarios | 6 |
| Alert-driving tasks | 80 |

## Real examples used in this guide
| Topic | Example |
|---|---|
| Technician breeding cage | `F1-L01-C0006` |
| Technician larger breeder cage | `F1-L01-C0008` |
| Researcher sample/result cage | `F1-L01-C0012` |
| Resulted sample | `SMP-0004` on `F1-L01-C0012-P01` |
| Main project example | `L01-PRJ-01` |
| Main planner example | `Neurogenetics Lab Cohort Plan` |
| Non-expired protocol example lab | `Developmental Signaling Unit` |

# How To Use This Guide
## Best device mix
The ideal training setup uses:
- a **phone** for scanning printed cage cards
- a **laptop or tablet** for the workspace
- an optional second browser tab for the **chat console** at `/chat/`

## Which mode should you use?
| Mode | Best for | Typical examples |
|---|---|---|
| Workspace | dashboards, list views, analytics, reports, batch printing, visual alerts | room utilization, compliance review, project inspector, genotyping workspace |
| Chat | direct actions, quick lookup, phone work, intent-driven updates | `Open cage F1-L01-C0006`, `Show overdue tasks`, `Print cage card for F1-L01-C0006` |
| Mixed | moving fluidly between both | print in workspace, scan with phone, update in chat, return to workspace for review |

## Shared rule for all roles
**Print the cage card -> scan the QR with a phone -> open the cage in the browser -> choose the fastest safe mode -> complete the task immediately.**

# Biological Background You Learn Along The Way
Murisphere is not just a logistics tool. The fields on the card and in the app are meaningful because they affect breeding, welfare, and experimental interpretation.

## Why timing matters
- **DOB** drives weaning windows, age-matched cohorts, and breeding readiness.
- **Date of weaning (DoW)** matters because delayed or early weaning changes both welfare and downstream study timing.
- **Plug checks, pair setup, and breeder age** change whether a line is actually productive.

## Why genotype matters
A genotype is not only a label. It is an inheritance and experiment-readiness question.

For example:
- a `Cre/+` animal may be useful for one project but not another
- a `fl/fl` animal may need to be paired with the right driver line
- missing genotype results can stall a project even when the colony appears numerically healthy

## Why pedigree matters
If a line behaves unexpectedly, the pedigree helps answer:
- who the sire and dam were
- whether the litter pattern is plausible
- whether poor survival or odd genotype mix is isolated or repeated

## Why compliance fields matter biologically
Protocol, welfare, veterinary, and quarantine fields are not only administrative:
- they change what can be done to the cage
- they can stop in-room updates or project handoffs
- they protect both animal welfare and study validity

![Pedigree and lineage view used to explain biological context](assets/screenshot_pedigree.svg){ width=92% }

# Shared Foundations For All Roles
## What a cage card must do
A cage card is not decoration. It is the physical hand-off between room work and the database.

A complete Murisphere card should show:
- cage code
- PI / lab
- project codes
- room / rack / slot
- protocol number, description, and expiration date
- breeding status
- strain and genotype summary
- male / female / total counts
- tracked animals
- litter history
- QR code that opens the cage in the browser

![Complete cage card with owner, protocol, animal table, litter table, and QR code](assets/cage_card_complete.svg){ width=95% }

## Phone QR workflow
1. Print the card at **100% scale**.
2. Use the **phone camera**, not a dedicated scanner.
3. Point at the **QR square**, not the 1D barcode.
4. Open the browser link.
5. Continue in either the workspace or the chat console.
6. Verify cage code and location before any write.

![Phone scanning a printed QR cage card](assets/scan_phone.svg){ width=84% }

## Common prompts used across all roles
The tutorial sections below show the exact seeded responses for these prompts:

- `What needs attention today?`
- `Open cage F1-L01-C0006`
- `Show reports`
- `Print cage card for F1-L01-C0006`
- `Show project L01-PRJ-01`
- `What needs weaning this week?`
- `Show mortality follow-up`
- `Generate cage cards for Room A1`
- `Which labs are above expected load?`
- `What requests breached SLA?`
- `Show recent sample results`
- `Reserve 1 matching animal for project L01-PRJ-01`
- `Generate a project closeout report`

# Role 1: Technician
## What a technician cares about daily
A technician is trying to move quickly without losing biological or compliance accuracy.

Daily concerns usually are:
- what cages need attention first
- which cages are overdue for plug check or wean
- whether counts and actual animals still match
- whether a cage is blocked by protocol or welfare conditions
- whether mortality, abnormal observations, or sample events were documented immediately

## Typical technician data entries
| Entry | Why it matters |
|---|---|
| male count / female count | reflects real room state and affects downstream planning |
| breeding status | changes expected tasks and litter timing |
| note text | captures abnormal findings at the moment they occur |
| task completion status | proves work was actually done |
| mortality record | supports welfare, veterinary, and census accuracy |
| litter / weaning values | affect survival metrics and future cage load |
| transfer destination | preserves chain-of-custody and location accuracy |
| sample collection state | affects genotyping and project readiness |

## Typical technician reports
- today’s action list
- overdue task list
- cages with active alerts
- weaning list
- mortality follow-up list
- printable cage cards for the next room pass

## Technician workflow in the workspace
### 1. Start from the dashboard or `Cages`
In the seeded dataset, the technician sees a room-facing operational surface with alerts, cage density, and due work.

![Workspace view with cage alerts and room-facing operational context](assets/screenshot_cages_alerts.svg){ width=94% }

Recommended first actions:
1. look for highlighted cages and alert badges
2. filter to the room you are entering
3. print or reprint cage cards if needed before rounds

### 2. Generate a cage card
Use the selected cage workflow to print `F1-L01-C0006`.

Expected printed card context:
- Lab: `Neurogenetics Lab`
- Location: `Room A1 / Rack R1`
- Protocol: `IACUC-2026-0101`
- Population: `M3 / F3 / T6`

![Workspace card-printing flow](assets/screenshot_cards.svg){ width=94% }

### 3. Scan in the room and reopen the cage
After printing:
1. scan the QR
2. open the browser link
3. sign in if needed
4. continue from either mode

![Scan landing flow after QR open](assets/screenshot_scan.svg){ width=92% }

### 4. Use the workspace for visual review
For `F1-L01-C0006`, the workspace helps the technician visually confirm:
- strain and genotype summary
- animal rows
- litter timing
- alert badges
- whether a protocol or welfare issue is blocking edits

## Technician workflow in chat
### 1. Start the shift with the morning brief
Prompt:
```text
What needs attention today?
```

Observed response in the seeded training environment on **April 13, 2026**:
- message: `Here is the current operating brief. Start with the alerts and due tasks, then open a cage or report from here.`
Operational snapshot:
- `6` active alerts
- `6` high alerts
- `6` tasks due now
- `6` overdue tasks
- `42` scoped cages
- `84` scoped animals
- top priority alerts included:
  - `Protocol Expired` on `F1-L01-C0001`
  - `Protocol Expired` on `F1-L01-C0002`
  - `Protocol Expired` on `F1-L01-C0003`
- top due tasks included:
  - `Task #42 · wean` on `F1-L01-C0042`
  - `Task #41 · plug_check` on `F1-L01-C0041`
  - `Task #40 · wean` on `F1-L01-C0040`

### 2. Open the same cage directly
Prompt:
```text
Open cage F1-L01-C0006
```

Observed response:
- message: `Cage F1-L01-C0006 is open. You can inspect it, update counts, or add a note from here.`
Cage summary:
- strain: `Rosa26-LSL`
- genotype summary: `fl/fl`
- population: `M3 / F3 / T6`
- location: `Room A1 / Rack R1`
- protocol: `IACUC-2026-0101`
- project: `L01-PRJ-01`
- DOB: `2026-03-06`
- public scan page: `/scan/tok_1_1_0006_4348`

Tracked animals included:
- `F1-L01-C0006-SIRE`
- `F1-L01-C0006-DAM`
- `F1-L01-C0006-P01`
- `F1-L01-C0006-P02`
- `F1-L01-C0006-P03`
- `F1-L01-C0006-P04`

### 3. Notice the abnormal condition before editing
This same cage had active alerts:
- `Protocol Expired`
- `Open Vet Case`
- `Protocol Deviation Open`

That is an important technician lesson: **not every open cage is writable**.

### 4. Attempt the update and observe the hard-stop
Prompt:
```text
Update cage F1-L01-C0006 males=3 females=4 status=Holding note=Tutorial walkthrough adjustment
```

Real result from the seeded dataset:
```text
Protocol IACUC-2026-0101 expired on 2020-01-01
```

This is correct behavior. The app should stop room-side edits when protocol state blocks action.

### 5. Still do useful work: complete the due task
Prompt:
```text
Complete task 6
```

Observed response:
- message: `Task #6 is now done.`
- updated task card:
  - task: `#6`
  - type: `wean`
  - cage: `F1-L01-C0006`

### 6. Re-check the queue
Prompt:
```text
Show overdue tasks
```

Observed response:
- message: `These are the current open tasks in your scope.`
Task pressure card:
  - `20` open tasks
  - `20` overdue
- first rows in the open-task table included:
- `F1-L01-C0042`
- `F1-L01-C0041`
- `F1-L01-C0040`
- `F1-L01-C0039`
- all four were still `pending` and assigned to `Admin User`

### 7. Ask for the weaning queue
Prompt:
```text
What needs weaning this week?
```

Observed response in the refreshed seeded training environment on **April 24, 2026**:

- message: `These litters are due or coming due for weaning in the next 7 days.`

Weaning pressure:

- `11` litters due within 7 days
- `0` overdue

First rows in the weaning queue:

- `F1-L01-C0015` · litter DOB `2026-04-03` · due to wean `2026-04-24` · `5` survived · `Room A1 / Rack R1`
- `F1-L01-C0033` · litter DOB `2026-04-03` · due to wean `2026-04-24` · `5` survived · `Room A1 / Rack R1`
- `F1-L01-C0012` · litter DOB `2026-04-04` · due to wean `2026-04-25` · `5` survived · `Room A1 / Rack R1`

### 8. Ask for mortality follow-up
Prompt:
```text
Show mortality follow-up
```

Observed response:

- message: `These mortality records still need necropsy or veterinary follow-up.`

Mortality follow-up pressure:

- `20` open records
- `20` animals represented

First follow-up rows:

- `#40` · cage `F1-L02-C0037` · cause `found dead` · necropsy `pending`
- `#39` · cage `F1-L02-C0035` · cause `found dead` · necropsy `pending`
- `#38` · cage `F1-L02-C0033` · cause `found dead` · necropsy `pending`

The response also includes a direct `Mortality CSV` export link.

### 9. Batch-print the next room pass
Prompt:
```text
Generate cage cards for Room A1
```

Observed response:

- message: `Batch cage cards are ready for Room A1. The print view includes up to 40 cages so the URL remains browser-safe.`

Batch print set:

- room: `Room A1`
- cards: `40`

First included cards:

- `F1-L01-C0001`
- `F1-L01-C0002`
- `F1-L01-C0003`

The response includes a link like `/print/cards?ids=...` that opens the print view.

## Technician overlap you should not skip
Even though these also matter to managers and researchers, a technician should practice them explicitly:
- printing the card
- scanning with the phone camera
- opening the cage from QR
- checking alerts before editing
- reading protocol state before changing counts
- completing tasks in real time rather than later

## Technician mini-mission
1. Print `F1-L01-C0008`.
2. Scan the printed card with a phone.
3. Open the cage in chat.
4. Ask `What needs weaning this week?`.
5. Ask `Show mortality follow-up`.
6. Ask `Show overdue tasks`.
7. Return to the workspace and visually confirm alerts for the same room.

# Role 2: Facility Manager
## What a facility manager cares about daily
A facility manager is less interested in one cage and more interested in whether the facility is controlled.

They care about:
- room and rack utilization
- which labs are above quota or trending up
- protocol expirations and unresolved deviations
- mortality and necropsy backlog
- request SLAs and repeated breaches
- which reports leadership, veterinarians, or IACUC will ask for next

## Typical manager data entries
| Entry | Why it matters |
|---|---|
| request status | keeps service flow and accountability visible |
| billing adjustments | affects chargeback accuracy |
| SLA settings | determines when delayed handoffs become actionable |
| protocol follow-up state | prevents non-compliant work from lingering |
| deviation / escalation state | supports corrective action and oversight |
| project priority / closeout state | helps resource allocation across labs |
| qualification or training updates | prevents blocked work from being invisible |

## Typical manager reports
- room utilization
- quota utilization by lab
- chargeback summary
- protocol expiration report
- mortality and necropsy report
- breeder productivity report
- survival report
- cohort handoff and closeout report

## Facility manager workflow in the workspace
### 1. Start from analytics and compliance
The workspace is the strongest place to scan facility-wide signals quickly.

![Compliance and operations visuals for facility-wide review](assets/screenshot_compliance.svg){ width=94% }

Use the workspace to review:
- alert severity mix
- protocol expiration watch list
- deviation and compliance concentration
- room and lab pressure at a glance

### 2. Move into analytics for capacity and flow
The seeded analytics workspace shows planning and throughput context that is hard to absorb in pure text.

![Planner and analytics workspace used for manager review](assets/screenshot_planner.svg){ width=94% }

Use this view to ask:
- where is capacity tight
- which cohort handoffs are stalling
- which labs are breaching expectations repeatedly
- what should be exported before the weekly meeting

### 3. Generate exports
From the workspace, a manager can generate:
- closeout CSV/PDF
- stalled handoff CSV/PDF
- chargeback summaries
- protocol usage and survival exports

## Facility manager workflow in chat
### 1. Start with the morning brief
Prompt:
```text
Give me the facility morning brief
```

Observed response in the seeded training environment on **April 13, 2026**:
- message: `Here is the facility morning brief. Alert load, due tasks, and scoped population are summarized first.`
Operational snapshot:
- `6` active alerts
- `6` high alerts
- `6` tasks due now
- `6` overdue tasks
- `3,000` scoped cages
- `372` scoped animals
- priority alerts included multiple `Protocol Expired` cages in `Neurogenetics Lab`

### 2. Ask the next obvious question
Prompt:
```text
Show protocol alerts
```

Observed response:
- message: `These protocols are expired or approaching expiration inside the alert window.`
- protocol alert table included:
  - `IACUC-2026-014` · `Synaptic Development Cohort` · expires `2020-01-01`
  - `IACUC-2026-0101` · `Neurogenetics Lab Protocol 1` · expires `2020-01-01`
  - `IACUC-2026-0201` · `Synaptic Circuits Group Protocol 1` · expires `2020-01-01`
  - `IACUC-2026-0202` · `Synaptic Circuits Group Protocol 2` · expires `2020-01-01`

### 3. Check room pressure
Prompt:
```text
Show room utilization
```

Observed response:
- message: `Here is the current facility-level utilization, quota pressure, and chargeback snapshot.`
- room utilization table:
  - `Room A1` occupied `3000` cages out of `240` capacity
  - utilization: `1250.0%`
- first rows in lab quota pressure:
  - `Cancer Models Core` at `89.6%`
  - `Aging Biology Lab` at `119.87%`
  - `Renal Physiology Unit` at `133.58%`
  - `Molecular Pathology Group` at `133.09%`

This is a good example of chat as a manager’s quick exception console: concise numbers first, then the manager can switch to the workspace if they need a wider visual picture.

### 4. Pull chargeback or SLA context
Prompt:
```text
Show chargeback summary
```

Observed response:
- message: `Here is the current facility-level utilization, quota pressure, and chargeback snapshot.`
- first rows in chargeback snapshot:
  - `Cancer Models Core` · `362` cages · `10,860` cage-days · estimated charge `9231.0`
  - `Aging Biology Lab` · `362` cages · `10,860` cage-days · estimated charge `9231.0`
  - `Renal Physiology Unit` · `362` cages · `10,860` cage-days · estimated charge `9231.0`

Prompt:
```text
Which labs are above expected load?
```

Observed response in the refreshed seeded training environment on **April 24, 2026**:

- message: `These labs are above expected load or close enough to quota to deserve attention.`

Load pressure:

- `5` labs above expected load
- `7` labs at or above `90%`

First quota-watch rows:

- `Renal Physiology Unit` · `362` current cages · `271` expected · utilization `133.58%`
- `Molecular Pathology Group` · `362` current cages · `272` expected · utilization `133.09%`
- `Pain Mechanisms Program` · `152` current cages · `121` expected · utilization `125.62%`

Prompt:
```text
What requests breached SLA?
```

Observed response:

- message: `Facility requests at or above 48 hours are treated as SLA breaches for this chat review.`

Request SLA pressure in this refreshed seed:

- `0` open submitted/approved requests
- `0` breached SLA requests

Prompt:
```text
Show reports
```

Observed response:
- message: `These are the reports and exports currently available from chat.`
- export links included:
  - `Cages CSV`
  - `Cages Excel`
  - `Cages PDF`
  - `Breeder productivity CSV`
  - `Survival CSV`
  - `Protocol usage CSV`
  - `Mortality CSV`
  - `Cohort closeouts CSV/PDF`
  - `Stalled handoffs CSV/PDF`
  - `Billing statements CSV`

## Facility manager overlap you should not skip
Managers should still practice the same phone-based scan flow as technicians, because managers often verify conditions during rounds or incident follow-up.

Do not skip:
- scanning a printed card
- confirming a cage’s protocol state on phone
- using chat for a quick facility brief while away from a desk
- returning to the workspace for a broader visual explanation

## Facility manager mini-mission
1. In chat, ask `Give me the facility morning brief`.
2. Ask `Show room utilization`.
3. Ask `Which labs are above expected load?`.
4. Ask `What requests breached SLA?`.
5. Switch to the workspace and open analytics.
6. Export a cohort or handoff report.
7. Return to chat and ask `Show protocol alerts`.

# Role 3: Researcher / PI
## What a researcher cares about daily
A researcher or PI is usually asking:
- do I have the right animals by genotype, sex, and timing
- are cohorts being reserved and handed off correctly
- are breeding lines supporting project demand
- are sample and genotype results arriving fast enough
- what story do the pedigree and closeout outcomes tell

## Typical researcher data entries
| Entry | Why it matters |
|---|---|
| project target counts | determines whether colony output meets study demand |
| genotype targeting rules | defines what animals are actually useful |
| cohort reservations / releases | links colony output to project planning |
| project priority or desired date | helps facility planning and breeder decisions |
| closeout notes and outcomes | captures what happened after animals were handed off |
| sample or genotyping state | ties line verification to experimental readiness |

## Typical researcher reports
- genotype-ready cohort list
- breeder productivity by line
- project cage list
- protocol usage report
- cohort closeout summary
- stalled handoff list
- sample and genotype result summary

## Researcher workflow in the workspace
### 1. Use the workspace for samples, cohorts, and planning
The visual workspace is especially strong for researchers when they need to compare several things at once.

![Samples and genotyping workspace with provider and result context](assets/screenshot_samples_genotyping.svg){ width=94% }

From the workspace, a researcher can:
- review sample chain-of-custody
- inspect provider workflow and results
- review genotype-ready animals
- apply or inspect project genotype target rules
- reserve animals into a cohort
- review handoff status and closeout history

### 2. Use pedigree when the biology matters
If a line behaves unexpectedly, open the pedigree explorer to see sire, dam, and pup relationships before making breeding or assignment decisions.

### 3. Use planner views when demand is changing
A researcher should understand not just today’s available animals, but whether next month’s demand is realistic.

## Researcher workflow in chat
### 1. Open the main project
Prompt:
```text
Show project L01-PRJ-01
```

Observed response:
- message: `Project L01-PRJ-01 is open. You can review handoffs, closeouts, and reporting from here.`
Project card values:
  - title: `Neurogenetics Lab Project 1`
  - lab: `Neurogenetics Lab`
  - target animals: `588`
  - assigned cages: `22`
  - active handoffs: `0`
Handoff SLA card:
  - assigned max days: `2`
  - shipped max days: `5`
  - repeat breach threshold: `2`
  - source: `default`

### 2. Move from project to a specific cage
Prompt:
```text
Open cage F1-L01-C0012
```

Observed response:
- message: `Cage F1-L01-C0012 is open. You can inspect it, update counts, or add a note from here.`
Cage summary:
  - strain: `C57BL/6J`
  - genotype summary: `Pending`
  - population: `M3 / F4 / T7`
  - location: `Room A1 / Rack R1`
  - protocol: `IACUC-2026-014`
  - project: `L01-PRJ-02`
  - DOB: `2026-02-25`
- tracked animals included `F1-L01-C0012-P01` through `P05` plus sire and dam
- active cage alerts included `Protocol Expired`, `Open Vet Case`, `Protocol Deviation Open`, and `Task Overdue`

This seeded example is useful because it connects a project to a sample/result workflow.

### 3. Ask about reports or readiness
Prompt:
```text
Show reports
```

Observed response:
- message: `These are the reports and exports currently available from chat.`
- report links included:
  - `Cages CSV/Excel/PDF`
  - `Breeder productivity CSV`
  - `Survival CSV`
  - `Protocol usage CSV`
  - `Mortality CSV`
  - `Cohort closeouts CSV/PDF`
  - `Stalled handoffs CSV/PDF`
  - `Billing statements CSV`

Prompt:
```text
Show genotype-ready animals
```

Observed response:
- message: `These are the current genotype-ready animals and project matches in your scope.`
Genotype-ready snapshot:
  - `1` visible project
  - `20` ready animals in the returned table
  - `84` unassigned ready animals in scope
Project readiness table:
  - `L01-PRJ-01` in `Neurogenetics Lab`
  - `84` matching ready animals
  - `0` reserved
  - target `588`
  - recommended action: `assign_now`
First ready animals returned:
  - `F1-L01-C0042-P06` · `fl/+`
  - `F1-L01-C0042-P05` · `WT/WT`
  - `F1-L01-C0042-P04` · `tg/tg`
  - each matched `L01-PRJ-01` and was currently `unassigned`

Prompt:
```text
Reserve 1 matching animal for project L01-PRJ-01
```

Observed response in the refreshed seeded training environment on **April 24, 2026**:

- message: `Reserved 1 matching animal(s) for project L01-PRJ-01.`

Reserved animal:

- `F1-L01-C0042-P06`
- sex `F`
- genotype `fl/+`
- cage `F1-L01-C0042`

This is a write action. It is intentionally explicit: the user must name the project and count.

Prompt:
```text
Show stalled cohort handoffs
```

Observed response:
- message: `These are the current stalled cohort handoffs in your scope.`
Stalled handoff snapshot:
  - `0` stalled assignments
  - `0` repeat-breach projects
  - `0` items in the `8d+` bucket
- the `Stalled handoffs` and `Repeat breach watchlist` tables were empty in this seeded run

### 4. Use the sample/result example
The tutorial-ready seed includes:
- sample `SMP-0004`
- animal `F1-L01-C0012-P01`
- cage `F1-L01-C0012`

Use that chain to practice moving from colony context to sample context and back again.

Prompt:
```text
Show recent sample results
```

Observed response:

- message: `These are the most recent samples with received, resulted, or rejected states.`

Sample result state:

- `5` recent review rows
- `2` resulted

First result rows:

- `SMP-0011` · animal `F1-L01-C0042-P01` · cage `F1-L01-C0042` · status `received` · result/genotype `WT/WT`
- `SMP-0008` · animal `F1-L01-C0023-P01` · cage `F1-L01-C0023` · status `resulted` · result/genotype `fl/+`
- `SMP-0007` · animal `F1-L01-C0017-P01` · cage `F1-L01-C0017` · status `received` · result/genotype `tg/tg`

Prompt:
```text
Generate a project closeout report
```

Observed response:

- message: `Here is the closeout report shortcut. Use the links for exportable evidence, and the table for fast review.`
- the refreshed seed had no closeout rows yet
- links included `Cohort closeouts CSV` and `Cohort closeouts PDF`

## Researcher overlap you should not skip
Researchers should still be able to:
- read a printed cage card
- scan a QR from a phone during a lab conversation
- switch from chat to the workspace when they need visual cohort or pedigree detail
- understand why a protocol or welfare block changes the meaning of “available animals”

## Researcher mini-mission
1. In chat, ask `Show project L01-PRJ-01`.
2. Open `F1-L01-C0012`.
3. In the workspace, inspect samples/genotyping.
4. Review `SMP-0004` and the linked animal context.
5. Return to chat and ask `Show recent sample results`.
6. Ask `Reserve 1 matching animal for project L01-PRJ-01`.
7. Ask `Generate a project closeout report`.

# Shared Cross-Role Workflows
## Workflow: Print a cage card
You can start this in either mode.

### Workspace path
1. Open `Cages`.
2. Select a cage or filtered set of cages.
3. Choose `Generate + Print`.
4. Print at `100% scale`.

### Chat path
Prompt:
```text
Print cage card for F1-L01-C0006
```

Observed response:
- message: `Cage card for F1-L01-C0006 is ready. Open the print view on a desktop or tablet, print at 100% scale, then scan the QR with a phone camera.`
Print card returned:
  - badge: `Breeding`
  - lab: `Neurogenetics Lab`
  - location: `Room A1 / Rack R1`
  - protocol: `IACUC-2026-0101`
  - population: `M3 / F3`
Links:
  - print view: `/print/cards?ids=8`
  - scan page: `/scan/tok_1_1_0006_4348`

## Workflow: Scan a printed card with a phone
1. Scan the QR square.
2. Open the browser link.
3. Verify cage code and location.
4. Continue in workspace or chat.
5. Save changes immediately.

## Workflow: Move between modes without losing context
Recommended pattern:
1. use chat to open or update a cage quickly
2. jump into the workspace when you need lists, visuals, pedigree, or exports
3. come back to chat when you know the next direct action

This is not a compromise. It is the intended operating model.

# Fun Applications To Learn Together
These scenarios make good team exercises because they combine biology, operations, and data quality.

## 1. Weekly colony huddle
Ask each learner to answer:
- which cages are risky this week
- which litters will drive next week’s wean workload
- which genotype results are still blocking the project

## 2. Facility operations check-in
Use the workspace to identify pressure visually, then ask chat for the concise version:
- `Give me the facility morning brief`
- `Show stalled cohort handoffs`
- `Show protocol alerts`

## 3. Research planning conversation
Stand by a rack, scan a printed card, and ask:
- is this cage actually useful for `L01-PRJ-01`
- what genotype do we still need
- what breeder or sample action is next

## 4. Pedigree teaching moment
Open a breeding cage and compare:
- what the card shows
- what the pedigree view shows
- what the genotype rule for the project requires

# Troubleshooting
- Tutorial examples missing: you are likely using the scale-only seed instead of `seed_tutorial_demo.py`.
- Scan opens the wrong host: set `Scan Base URL` to a phone-reachable host or LAN IP, never `localhost` on printed cards.
- Phone camera cannot detect the code: make sure the printed card contains a QR square with enough contrast.
- Camera detects only a barcode app, not a browser link: scan the QR square, not the CODE128 bars.
- Report export fails: re-login and retry the endpoint.
- Card images missing: confirm the server is running and reload the print page.
- Edit blocked by protocol: the protocol is expired or otherwise not valid for direct cage edits.
- Same scan reopens repeatedly: refresh once after the latest build; scan tokens are now cleared from the URL after capture.

![Troubleshooting visual for QR scan and print quality](assets/scan_troubleshooting.svg){ width=84% }

# Final Checklist
A learner is ready to use Murisphere when they can:
- read a cage card accurately
- print and scan a cage card without help
- explain when to use workspace versus chat
- open a cage in both modes
- recognize a protocol hard-stop
- complete at least one role-specific write action
- retrieve the report that matters for their role
- explain why pedigree, genotype, litter timing, and protocol state all change operational decisions
