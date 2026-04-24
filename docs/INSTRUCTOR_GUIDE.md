# Murisphere Instructor Guide

Use this guide for technician onboarding, lab-group walkthroughs, and mixed sessions with researchers and facility staff.

## Goal
A learner should leave the session able to:
1. read a cage card confidently
2. scan a printed QR code with a phone and open the cage in the browser
3. choose when to use the traditional workspace versus the chat console
4. explain why timing, pedigree, and welfare data matter biologically

## Recommended Setup
Use the tutorial-ready seed so the tutorial, `Start Learning` panel, and example records all match.

```bash
./.venv/bin/python seed_tutorial_demo.py --db training_demo.db --force
MURISPHERE_DB=training_demo.db ./.venv/bin/python app.py
```

Best setup:
- phone for scanning printed cage cards
- laptop or tablet for the workspace tutorial and visual dashboards
- optional second phone or browser tab for the chat console

## Before The Session
1. Print at least two cage cards.
2. Confirm `Scan Base URL` uses a phone-reachable host or LAN IP.
3. Sign in once and verify the dashboard `Start Learning` section is visible.
4. Open both `/` and `/chat/` so you can demonstrate mode switching.
5. Keep these seeded examples ready:
   - `F1-L01-C0006`
   - `F1-L01-C0008`
   - `F1-L01-C0012`
   - `SMP-0004`
   - `L01-PRJ-01`
   - `Neurogenetics Lab Cohort Plan`

## Recommended Teaching Framing
Use one consistent message through the session:

`Print the cage card -> scan the QR with a phone -> open the cage in the browser -> choose the mode that is fastest for the task -> complete the task immediately.`

This keeps the group focused on operational truth rather than screen preference.

## Suggested 60-Minute Session
### 1. Orientation: 10 minutes
1. Sign in.
2. Pause on the workspace dashboard.
3. Open the `Start Learning` section.
4. Open the chat console.
5. Explain that Murisphere intentionally supports both interfaces.

### 2. Cage Card Literacy: 10 minutes
Ask learners to identify:
- cage ID
- lab / owner
- project codes
- strain and genotype
- breeding status
- population totals
- litter context
- protocol context

### 3. Phone Scan Workflow: 15 minutes
1. Print a cage card.
2. Scan a printed QR with the phone camera.
3. Confirm the browser opens the cage workflow.
4. Continue first in chat, then show the same cage in the workspace.
5. Save one small update and show the audit trail.

### 4. Biology And Pedigree: 10 minutes
1. Open a breeding cage with litter data.
2. Show sire, dam, and pup relationships.
3. Explain why delayed DOB, litter, or genotype entry causes downstream breeding and cohort errors.

### 5. Compliance And Abnormal Conditions: 10 minutes
1. Open the compliance workspace.
2. Show seeded alerts.
3. Demonstrate a protocol-blocked cage update in chat.
4. Explain warning versus action versus hard-stop.

### 6. Wrap-Up: 5 minutes
Ask each learner:
1. What would you check first on a cage card?
2. What usually makes phone scanning fail?
3. Which mode would you use for a quick cage update, and which for a room-wide review?
4. Why does real-time cage entry protect science, not just paperwork?

## Suggested 90-Minute Session
Add:
1. samples and genotyping order flow
2. project cohort planning and reservations
3. planner scenario discussion
4. one or two role-based mini-missions from the tutorial

## Good Facilitator Prompts
- “What makes this cage risky by next week?”
- “Which field on the card matters most for this project?”
- “If the QR failed, what would you check first?”
- “Would you handle this in the workspace or chat, and why?”
- “Does this pedigree support the genotype story?”
- “Which alert is operational noise, and which one changes science?”

## Common Learner Mistakes
- scanning the 1D barcode instead of the QR square
- using `localhost` for printed card scan URLs
- focusing on counts but ignoring litter timing
- reading genotype as a label instead of an inheritance question
- treating every alert as equally urgent
- assuming chat replaces the workspace instead of complementing it

## After The Session
Share:
- `docs/tutorial/user_training_tutorial.md`
- `docs/tutorial/user_training_tutorial.html`
- `docs/tutorial/user_training_tutorial.pdf`
- `docs/USER_GUIDE.md`

Then ask learners to repeat the technician, facility manager, and researcher modules on their own, switching between workspace and chat at least once in each role.
