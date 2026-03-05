# Murisphere Checkpoint (2026-03-05)

## Current State
- QR issue is resolved using server-side image generation.
- Cage cards now render both QR and barcode without external CDN scripts.
- Phone scan should open `/scan/<token>` when scanning printed card QR.

## Key Files Updated
- `app.py`
- `static/app.js`
- `templates/index.html`
- `requirements.txt`
- `tests/test_app.py`
- `qrcode_diagnostic.py`
- `docs/releases/v0.2.0.md`
- tutorial docs (`docs/tutorial/*`)

## Verification Commands
```bash
python qrcode_diagnostic.py
python -m unittest discover -s tests -p 'test_*.py' -q
```

## Expected Results
- Diagnostic prints `QR diagnostic passed`.
- Unit/integration tests pass.
- Printed cage cards show a visible QR square and barcode.
- Phone camera scan opens cage info page in browser.

## Resume Priorities
1. Verify QR scan behavior on physical printouts across iPhone and Android.
2. Add browser E2E tests for card generation and scan URL correctness.
3. Add optional signed/expiring public scan tokens for stronger security.
