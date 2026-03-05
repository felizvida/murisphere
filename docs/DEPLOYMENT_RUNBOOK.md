# Deployment Runbook

## 1) Prerequisites
- Python 3.11+
- Linux/macOS host or container runtime
- HTTPS reverse proxy for production
- Writable persistent storage for DB and uploaded attachments

## 2) Local Deployment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 3) Container Deployment
```bash
docker build -t murisphere:latest .
docker run -p 8000:8000 murisphere:latest
```

## 4) Persistent Data
- Set `MURISPHERE_DB` to a persistent path.
- Set `MURISPHERE_ATTACHMENT_DIR` to persistent storage.
- Back up DB file daily with retention policy.

## 5) Upgrade Procedure
1. Back up DB and attachments.
2. Pull new image/build or deploy new app package.
3. Restart service.
4. Run release validation:
   - `python3 qrcode_diagnostic.py`
   - `python3 ui_clickability_audit.py`
   - `python3 alert_coverage_verifier.py --db <db_path> --ensure-schema`
5. Print one cage card and confirm real phone QR scan in facility network.

## 6) Production Hardening Checklist
- Disable debug mode.
- Configure TLS and HSTS at ingress.
- Add rate limiting and request size limits.
- Rotate credentials and secrets.
- Enforce row-level lab/facility authorization.

## 7) Rollback
- Keep previous container tag.
- Restore prior DB backup if schema changes are incompatible.
