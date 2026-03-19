# Deployment Runbook

## 1) Prerequisites
- Python 3.11+
- Linux/macOS host or container runtime
- HTTPS reverse proxy for production
- Writable persistent storage for DB and uploaded attachments
- Optional desktop companion toolchain: Node.js, Rust, and Tauri CLI dependencies

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

## 3a) Centralized Desktop Companion
The recommended desktop pattern is a Tauri shell pointed at the same centralized Murisphere backend used by browsers and phones.

```bash
cd desktop
npm install
npm run dev
```

Desktop onboarding flow:
1. Launch the app.
2. Enter the centralized Murisphere base URL in the setup screen.
3. Click `Save And Connect`.
4. The desktop shell stores the URL in its app config directory for future launches.

Optional environment override:
```bash
cd desktop
export MURISPHERE_DESKTOP_REMOTE_URL=https://murisphere.example.org
npm run dev
```

For development from source, the desktop shell can auto-start the local Flask backend on a loopback port:

```bash
cd desktop
npm install
npm run dev
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
- For desktop rollout, distribute only shells pointed at centralized backends or a managed sidecar package.

## 7) Rollback
- Keep previous container tag.
- Restore prior DB backup if schema changes are incompatible.
