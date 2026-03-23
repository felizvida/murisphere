# Murisphere Instructor Guide

Use this guide for technician onboarding, lab-group walkthroughs, and mixed sessions with researchers and facility staff.

## Goal

A learner should leave the session able to:

1. read a cage card confidently
2. scan a printed QR code with a phone and open the cage in the browser
3. explain why timing, pedigree, and welfare data matter biologically

## Recommended setup

Use the tutorial-ready seed so the tutorial, dashboard learning hub, and example records all match.

```bash
./.venv/bin/python seed_tutorial_demo.py --db training_demo.db --force
MURISPHERE_DB=training_demo.db ./.venv/bin/python app.py
```

Best setup:

- phone for scanning printed cage cards
- laptop or tablet for the tutorial and dashboards

## Before the session

1. Print at least two cage cards.
2. Confirm `Scan Base URL` uses a phone-reachable host or LAN IP.
3. Sign in once and verify the dashboard `Start Learning` section is visible.
4. Keep these example records ready:
   - `F1-L01-C0006`
   - `F1-L01-C0008`
   - `SMP-0004`
   - `Neurogenetics Lab Cohort Plan`

## Suggested 60-minute session

### 1. Orientation: 10 minutes

1. Sign in.
2. Pause on the dashboard.
3. Open the in-app `Start Learning` section.
4. Launch the full tutorial from the dashboard.

Core message:

`Print the cage card -> scan the QR with a phone -> open the cage in the browser -> complete the task immediately.`

### 2. Cage card literacy: 10 minutes

Ask learners to identify:

- cage ID
- lab / owner
- strain and genotype
- breeding status
- population totals
- litter context
- protocol context

### 3. Phone scan workflow: 15 minutes

1. Scan a printed QR with the phone camera.
2. Confirm the browser opens the cage workflow.
3. Update counts or notes.
4. Show the audit trail after saving.

### 4. Biology and pedigree: 10 minutes

1. Open a breeding cage with litter data.
2. Show sire, dam, and pup relationships.
3. Explain why delayed DOB or genotype entry causes downstream errors.

### 5. Compliance and abnormal conditions: 10 minutes

1. Open the compliance view.
2. Show seeded alerts.
3. Explain warning vs action vs hard-stop.

### 6. Wrap-up: 5 minutes

Ask each learner:

1. What would you check first on a cage card?
2. What usually makes phone scanning fail?
3. Why does real-time cage entry protect science, not just paperwork?

## Suggested 90-minute session

Add:

1. projects and quotas
2. sample and genotyping chain-of-custody
3. planner scenario discussion
4. one or two mini-missions from the self-paced tutorial

## Good facilitator prompts

- “What makes this cage risky by next week?”
- “Which field on the card matters most for this project?”
- “If the QR failed, what would you check first?”
- “Does this pedigree support the genotype story?”
- “Which alert is operational noise, and which one changes science?”

## Common learner mistakes

- scanning the 1D barcode instead of the QR square
- using `localhost` for printed card scan URLs
- focusing on counts but ignoring litter timing
- reading genotype as a label instead of an inheritance question
- treating every alert as equally urgent

## After the session

Share:

- `docs/tutorial/user_training_tutorial.md`
- `docs/tutorial/user_training_tutorial.html`
- `docs/tutorial/user_training_tutorial.pdf`

Then ask learners to repeat Modules 2 through 6 on their own.
