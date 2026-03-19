from __future__ import annotations

import json
import unittest
from pathlib import Path


class DesktopScaffoldTests(unittest.TestCase):
    def test_tauri_project_files_exist(self) -> None:
        self.assertTrue(Path("desktop/package.json").exists())
        self.assertTrue(Path("desktop/scripts/sync-version.mjs").exists())
        self.assertTrue(Path("desktop/ui/index.html").exists())
        self.assertTrue(Path("desktop/src-tauri/Cargo.toml").exists())
        self.assertTrue(Path("desktop/src-tauri/tauri.conf.json").exists())
        self.assertTrue(Path("desktop/src-tauri/src/main.rs").exists())
        self.assertTrue(Path("desktop/src-tauri/capabilities/default.json").exists())
        self.assertTrue(Path("desktop/src-tauri/icons/icon.svg").exists())

    def test_tauri_config_targets_main_window(self) -> None:
        config = json.loads(Path("desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(config["productName"], "Murisphere Desktop")
        self.assertEqual(config["build"]["frontendDist"], "../ui")
        self.assertEqual(config["app"]["windows"][0]["label"], "main")
        self.assertTrue(config["app"]["withGlobalTauri"])

        version = Path("VERSION").read_text(encoding="utf-8").strip()
        package_json = json.loads(Path("desktop/package.json").read_text(encoding="utf-8"))
        cargo = Path("desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
        self.assertEqual(package_json["version"], version)
        self.assertEqual(config["version"], version)
        self.assertIn(f'version = "{version}"', cargo)

    def test_desktop_bootstrap_supports_remote_and_local_modes(self) -> None:
        rust = Path("desktop/src-tauri/src/main.rs").read_text(encoding="utf-8")
        self.assertIn("MURISPHERE_DESKTOP_REMOTE_URL", rust)
        self.assertIn("desktop_save_remote_url", rust)
        self.assertIn("desktop_connect", rust)
        self.assertIn("spawn_local_backend", rust)
        self.assertIn("/api/system/health", rust)
        self.assertIn("MURISPHERE_RUNTIME_MODE", rust)
        self.assertIn("desktop-config.json", rust)
        self.assertIn(".venv", rust)

    def test_desktop_index_exposes_setup_controls(self) -> None:
        html = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        self.assertIn("Save And Connect", html)
        self.assertIn("Use Local Source Mode", html)
        self.assertIn("window.__TAURI__?.core?.invoke", html)
        self.assertIn("desktop_status", html)
        self.assertIn("desktop_connect", html)

    def test_desktop_capability_uses_core_default(self) -> None:
        capability = json.loads(Path("desktop/src-tauri/capabilities/default.json").read_text(encoding="utf-8"))
        self.assertEqual(capability["identifier"], "default")
        self.assertIn("core:default", capability["permissions"])
