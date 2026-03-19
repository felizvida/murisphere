# Murisphere Desktop

Murisphere Desktop is a Tauri companion shell for the shared Murisphere platform.

## Modes
- Centralized mode: save your hosted Murisphere backend URL in the desktop setup screen, or override it with `MURISPHERE_DESKTOP_REMOTE_URL`.
- Local source mode: run from this repository and the shell can auto-start `app.py` on a loopback port for desktop development.

## Install Desktop Dependencies
```bash
cd desktop
npm install
```

macOS note:
- `cargo check` works with Xcode Command Line Tools, but `tauri build` is more reliable with full Xcode installed.

## Run In Centralized Mode
```bash
cd desktop
npm run dev
```

On first launch:
- Paste the hosted Murisphere base URL such as `https://murisphere.example.org`
- Click `Save And Connect`
- The desktop app stores that URL in the Tauri app config directory as `desktop-config.json`

Optional environment override:
```bash
cd desktop
export MURISPHERE_DESKTOP_REMOTE_URL=https://murisphere.example.org
npm run dev
```

## Run Against Local Source Backend
```bash
cd desktop
npm run dev
```

Optional environment variables:
- `MURISPHERE_DESKTOP_PYTHON` to point at a specific Python executable
- `MURISPHERE_DESKTOP_LOCAL_HOST` to change the loopback bind host
- `MURISPHERE_DESKTOP_LOCAL_PORT` to change the loopback port
- `MURISPHERE_DESKTOP_REMOTE_URL` to override the saved centralized backend URL

## Current Scope
- Opens the centralized Murisphere web app in a desktop shell
- Saves the centralized backend URL in the desktop app config directory
- Supports local source-backed desktop development
- Preserves the existing phone/tablet/browser workflow as the primary operational surface

## Next Desktop Steps
- Bundle a production backend/sidecar for offline workstation deployments
- Add native print presets, desktop notifications, and file-system/export integration
- Add enterprise packaging and auto-update policy
