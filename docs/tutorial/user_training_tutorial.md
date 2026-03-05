---
title: "Murisphere Mobile Scan Tutorial"
subtitle: "Professional Step-by-Step Guide for Printed Cage Cards"
author: "Murisphere Operations"
date: "2026-03-05"
geometry: margin=0.8in
fontsize: 11pt
colorlinks: true
toc: true
toc-depth: 2
---

# Purpose
This tutorial shows technicians exactly how to use a **phone camera** to scan a **printed cage card** and open the correct cage record in Murisphere.

# Who Should Use This
- Technicians working in-room
- PI delegates verifying cage records
- Facility trainers onboarding new users

# Before You Start
1. Confirm Murisphere is reachable from your phone browser.
2. In the `Cages` tab, set `Scan Base URL` to a phone-reachable address.
3. Print cards using `Generate + Print`.

# Visual Walkthrough
## Figure A - Printed Card to Phone Flow (Illustration)

```text
+-------------------- Printed Cage Card --------------------+
| Cage ID: C-A1-0243                                       |
| Strain: C57BL/6J      M/F: 2/3                           |
|                                                          |
|   [ QR CODE ]        [ BARCODE ]                         |
|                                                          |
| Scan URL: https://vivarium.example.org/scan/tok_xxx      |
+-----------------------------------------------------------+
                 ||
                 \/
+-------------------- Phone Camera -------------------------+
| Camera detects QR -> link banner appears                 |
| Tap banner -> browser opens cage info page               |
| Tap "Open Murisphere (login for edits)"                 |
+-----------------------------------------------------------+
```

## Figure B - Troubleshooting Matrix (Illustration)

```text
Issue                        Likely Cause                 Action
-------------------------    -------------------------    -------------------------------
No scan prompt               Low contrast / glare         Improve lighting, flatten card
Wrong page opens             Bad Scan Base URL            Use LAN IP/domain, not localhost
Blank QR or broken image     Asset endpoint unavailable    Verify server is running, regenerate cards
Slow open                    Weak room network            Retest on strong Wi-Fi
```

# Step-by-Step: Phone Scan of Printed Card
## Step 1 - Print Fresh Cards
1. Open `Cages`.
2. Confirm `Scan Base URL` points to a phone-reachable host.
3. Click `Generate + Print`.
4. Verify each card has a visible square QR.

## Step 2 - Scan with Phone Camera
1. Hold the printed card under even lighting.
2. Open default camera app:
   - iPhone: Camera app
   - Android: Camera app
3. Point camera at the **QR code** until a link banner appears.
4. Tap the banner/link.

## Step 3 - Validate Identity
1. Confirm cage ID on the opened page matches printed cage ID.
2. Confirm location and M/F counts are plausible.
3. If mismatch: stop and rescan before editing.

## Step 4 - Enter Edit Mode
1. Tap `Open Murisphere (login for edits)`.
2. Sign in if prompted.
3. App should land in scan/edit context for that cage.

## Step 5 - Perform Update
1. Update counts/status/notes.
2. Save changes.
3. Confirm save acknowledgement and audit trail entry.

# Required Quality Checks
- Do not update if cage ID mismatch.
- Do not use `localhost` for printed scan URLs.
- Reprint cards after base URL changes.

# High-Value Troubleshooting
## If camera does not detect code
- Move 10-20 cm from card.
- Avoid reflections and shadows.
- Increase print quality.

## If code opens but wrong destination
- Check `Scan Base URL` in `Cages` tab.
- Use LAN IP or production DNS.

## If QR appears broken
- Confirm app server is reachable from browser.
- Open `/api/assets/qrcode.png?v=test` in browser and verify PNG loads.
- Regenerate cards and retry scan.

# Trainer Checklist
1. Demonstrate one complete scan -> edit -> save cycle.
2. Have trainee repeat with a second cage.
3. Verify trainee can troubleshoot URL and scan issues.
4. Confirm trainee understands ID verification before edits.

# Daily Room SOP (Quick)
1. Check scan URL base setting.
2. Print cards for active cages.
3. Run scan-update rounds.
4. Review scheduled tasks and compliance alerts.
