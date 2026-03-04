# Deployment Runbook

## 1) Prerequisites
- Python 3.11+
- Linux/macOS host or container runtime
- HTTPS reverse proxy for production

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
- Back up DB file daily with retention policy.

## 5) Production Hardening Checklist
- Disable debug mode.
- Configure TLS and HSTS at ingress.
- Add rate limiting and request size limits.
- Rotate credentials and secrets.
- Enforce row-level lab/facility authorization.

## 6) Rollback
- Keep previous container tag.
- Restore prior DB backup if schema changes are incompatible.
