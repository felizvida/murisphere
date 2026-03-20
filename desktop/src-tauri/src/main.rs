#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

/*
 * Copyright 2026 Murisphere Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State};
use url::Url;

const DEFAULT_LOCAL_HOST: &str = "127.0.0.1";
const DEFAULT_LOCAL_PORT: u16 = 8421;
const LOCAL_STARTUP_TIMEOUT_SECS: u64 = 15;
const CONFIG_FILE_NAME: &str = "desktop-config.json";

#[derive(Default)]
struct DesktopState {
    backend_child: Mutex<Option<Child>>,
    active_target: Mutex<Option<String>>,
    last_error: Mutex<Option<String>>,
}

impl Drop for DesktopState {
    fn drop(&mut self) {
        if let Ok(mut child_slot) = self.backend_child.lock() {
            if let Some(child) = child_slot.as_mut() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

impl DesktopState {
    fn set_active_target(&self, target: Option<String>) {
        if let Ok(mut slot) = self.active_target.lock() {
            *slot = target;
        }
    }

    fn active_target(&self) -> Option<String> {
        self.active_target.lock().ok().and_then(|slot| slot.clone())
    }

    fn set_last_error(&self, message: Option<String>) {
        if let Ok(mut slot) = self.last_error.lock() {
            *slot = message;
        }
    }

    fn last_error(&self) -> Option<String> {
        self.last_error.lock().ok().and_then(|slot| slot.clone())
    }

    fn replace_backend_child(&self, next_child: Option<Child>) {
        if let Ok(mut slot) = self.backend_child.lock() {
            if let Some(mut current) = slot.take() {
                let _ = current.kill();
                let _ = current.wait();
            }
            *slot = next_child;
        }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct DesktopConfig {
    remote_url: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopBootstrapStatus {
    configured_remote_url: Option<String>,
    active_target: Option<String>,
    local_source_available: bool,
    setup_required: bool,
    last_error: Option<String>,
    env_remote_override: bool,
}

#[derive(Debug, Clone, Copy)]
enum ConnectMode {
    Auto,
    SavedOrEnv,
    LocalOnly,
}

fn main() {
    let desktop_state = DesktopState::default();
    tauri::Builder::default()
        .manage(desktop_state)
        .invoke_handler(tauri::generate_handler![
            desktop_status,
            desktop_save_remote_url,
            desktop_clear_remote_url,
            desktop_connect
        ])
        .setup(|app| {
            let state = app.state::<DesktopState>();
            if let Err(err) = connect_and_navigate(app.handle(), &state, ConnectMode::Auto) {
                state.set_last_error(Some(err.clone()));
                eprintln!("murisphere desktop bootstrap warning: {err}");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Murisphere desktop");
}

#[tauri::command]
fn desktop_status(
    app: AppHandle,
    state: State<'_, DesktopState>,
) -> Result<DesktopBootstrapStatus, String> {
    current_status(&app, &state)
}

#[tauri::command]
fn desktop_save_remote_url(
    app: AppHandle,
    state: State<'_, DesktopState>,
    remote_url: String,
) -> Result<DesktopBootstrapStatus, String> {
    let normalized = validate_remote_url(&remote_url)?;
    let config = DesktopConfig {
        remote_url: Some(normalized),
    };
    save_desktop_config(&app, &config)?;
    state.set_last_error(None);
    current_status(&app, &state)
}

#[tauri::command]
fn desktop_clear_remote_url(
    app: AppHandle,
    state: State<'_, DesktopState>,
) -> Result<DesktopBootstrapStatus, String> {
    clear_desktop_config(&app)?;
    state.set_last_error(None);
    current_status(&app, &state)
}

#[tauri::command]
fn desktop_connect(
    app: AppHandle,
    state: State<'_, DesktopState>,
    mode: Option<String>,
) -> Result<DesktopBootstrapStatus, String> {
    let connect_mode = parse_connect_mode(mode.as_deref())?;
    connect_and_navigate(&app, &state, connect_mode)?;
    current_status(&app, &state)
}

fn current_status(app: &AppHandle, state: &DesktopState) -> Result<DesktopBootstrapStatus, String> {
    let configured_remote_url = configured_remote_url(app)?;
    Ok(DesktopBootstrapStatus {
        configured_remote_url,
        active_target: state.active_target(),
        local_source_available: find_repo_root().is_some(),
        setup_required: state.active_target().is_none(),
        last_error: state.last_error(),
        env_remote_override: env::var("MURISPHERE_DESKTOP_REMOTE_URL").is_ok(),
    })
}

fn parse_connect_mode(value: Option<&str>) -> Result<ConnectMode, String> {
    match value.unwrap_or("auto") {
        "auto" => Ok(ConnectMode::Auto),
        "saved" => Ok(ConnectMode::SavedOrEnv),
        "local" => Ok(ConnectMode::LocalOnly),
        other => Err(format!("Unsupported desktop connect mode: {other}")),
    }
}

fn connect_and_navigate(
    app: &AppHandle,
    state: &DesktopState,
    mode: ConnectMode,
) -> Result<String, String> {
    let (target_url, child) = bootstrap_backend_target(app, mode)?;
    eprintln!("murisphere desktop target selected: {target_url}");
    navigate_main_window(app, &target_url)?;
    state.replace_backend_child(child);
    state.set_active_target(Some(target_url.clone()));
    state.set_last_error(None);
    Ok(target_url)
}

fn navigate_main_window(app: &AppHandle, target_url: &str) -> Result<(), String> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "Desktop main window not found".to_string())?;
    let parsed = Url::parse(target_url)
        .map_err(|err| format!("Invalid desktop target URL {target_url}: {err}"))?;
    window
        .navigate(parsed)
        .map_err(|err| format!("Failed to navigate Murisphere desktop window: {err}"))?;
    Ok(())
}

fn bootstrap_backend_target(
    app: &AppHandle,
    mode: ConnectMode,
) -> Result<(String, Option<Child>), String> {
    if let Some(remote_url) = resolve_remote_url(app, mode)? {
        eprintln!("murisphere desktop using centralized backend: {remote_url}");
        return Ok((remote_url, None));
    }

    if matches!(mode, ConnectMode::SavedOrEnv) {
        return Err("No centralized Murisphere backend URL is configured yet.".to_string());
    }

    let local_host = env::var("MURISPHERE_DESKTOP_LOCAL_HOST")
        .unwrap_or_else(|_| DEFAULT_LOCAL_HOST.to_string());
    let local_port = env::var("MURISPHERE_DESKTOP_LOCAL_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(DEFAULT_LOCAL_PORT);
    let local_url = format!("http://{local_host}:{local_port}");

    if local_backend_ready(&local_host, local_port) {
        eprintln!("murisphere desktop found existing local backend: {local_url}");
        return Ok((local_url, None));
    }

    let repo_root = find_repo_root().ok_or_else(|| {
        "No local Murisphere source tree detected. Set MURISPHERE_DESKTOP_REMOTE_URL for centralized desktop mode."
            .to_string()
    })?;
    let child = spawn_local_backend(&repo_root, &local_host, local_port)?;
    wait_for_local_backend(&local_host, local_port)?;
    eprintln!("murisphere desktop started local backend: {local_url}");
    Ok((local_url, Some(child)))
}

fn resolve_remote_url(app: &AppHandle, mode: ConnectMode) -> Result<Option<String>, String> {
    if matches!(mode, ConnectMode::LocalOnly) {
        return Ok(None);
    }
    if let Ok(remote_url) = env::var("MURISPHERE_DESKTOP_REMOTE_URL") {
        return Ok(Some(validate_remote_url(&remote_url)?));
    }
    configured_remote_url(app)
}

fn configured_remote_url(app: &AppHandle) -> Result<Option<String>, String> {
    let config = load_desktop_config(app)?;
    match config.remote_url {
        Some(url) => Ok(Some(validate_remote_url(&url)?)),
        None => Ok(None),
    }
}

fn validate_remote_url(value: &str) -> Result<String, String> {
    let normalized = normalize_base_url(value);
    if normalized.starts_with("http://") || normalized.starts_with("https://") {
        return Ok(normalized);
    }
    Err("Desktop backend URL must start with http:// or https://".to_string())
}

fn normalize_base_url(value: &str) -> String {
    value.trim().trim_end_matches('/').to_string()
}

fn local_backend_ready(host: &str, port: u16) -> bool {
    healthcheck_http(host, port)
}

fn wait_for_local_backend(host: &str, port: u16) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(LOCAL_STARTUP_TIMEOUT_SECS);
    while Instant::now() < deadline {
        if healthcheck_http(host, port) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(250));
    }
    Err(format!(
        "Timed out waiting for local Murisphere backend at http://{host}:{port}"
    ))
}

fn healthcheck_http(host: &str, port: u16) -> bool {
    let mut stream = match TcpStream::connect((host, port)) {
        Ok(stream) => stream,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    if stream
        .write_all(
            format!(
                "GET /api/system/health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            )
            .as_bytes(),
        )
        .is_err()
    {
        return false;
    }
    let mut buffer = String::new();
    if stream.read_to_string(&mut buffer).is_err() {
        return false;
    }
    buffer.contains("\"ok\":true")
}

fn desktop_config_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|err| format!("Unable to resolve desktop config directory: {err}"))?;
    fs::create_dir_all(&dir)
        .map_err(|err| format!("Unable to create desktop config directory: {err}"))?;
    Ok(dir.join(CONFIG_FILE_NAME))
}

fn load_desktop_config(app: &AppHandle) -> Result<DesktopConfig, String> {
    let path = desktop_config_path(app)?;
    if !path.exists() {
        return Ok(DesktopConfig::default());
    }
    let raw =
        fs::read_to_string(&path).map_err(|err| format!("Unable to read desktop config: {err}"))?;
    serde_json::from_str(&raw).map_err(|err| format!("Desktop config is not valid JSON: {err}"))
}

fn save_desktop_config(app: &AppHandle, config: &DesktopConfig) -> Result<(), String> {
    let path = desktop_config_path(app)?;
    let raw = serde_json::to_string_pretty(config)
        .map_err(|err| format!("Unable to serialize desktop config: {err}"))?;
    fs::write(path, raw).map_err(|err| format!("Unable to write desktop config: {err}"))
}

fn clear_desktop_config(app: &AppHandle) -> Result<(), String> {
    let path = desktop_config_path(app)?;
    if path.exists() {
        fs::remove_file(path).map_err(|err| format!("Unable to clear desktop config: {err}"))?;
    }
    Ok(())
}

fn find_repo_root() -> Option<PathBuf> {
    let mut dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for _ in 0..4 {
        if dir.join("app.py").exists()
            && dir.join("templates").exists()
            && dir.join("static").exists()
        {
            return Some(dir);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

fn spawn_local_backend(repo_root: &PathBuf, host: &str, port: u16) -> Result<Child, String> {
    let mut python_candidates: Vec<String> = Vec::new();

    if let Ok(explicit) = env::var("MURISPHERE_DESKTOP_PYTHON") {
        python_candidates.push(explicit);
    }

    if cfg!(target_os = "windows") {
        let repo_venv = repo_root.join(".venv").join("Scripts").join("python.exe");
        if repo_venv.exists() {
            python_candidates.push(repo_venv.to_string_lossy().to_string());
        }
    } else {
        let repo_venv = repo_root.join(".venv").join("bin").join("python");
        if repo_venv.exists() {
            python_candidates.push(repo_venv.to_string_lossy().to_string());
        }
    }

    if let Ok(virtual_env) = env::var("VIRTUAL_ENV") {
        let venv_python = if cfg!(target_os = "windows") {
            PathBuf::from(&virtual_env)
                .join("Scripts")
                .join("python.exe")
        } else {
            PathBuf::from(&virtual_env).join("bin").join("python")
        };
        if venv_python.exists() {
            python_candidates.push(venv_python.to_string_lossy().to_string());
        }
    }

    if cfg!(target_os = "windows") {
        python_candidates.push("python".to_string());
    } else {
        python_candidates.push("python3".to_string());
        python_candidates.push("python".to_string());
    }

    let mut last_error = None;
    for python in dedupe_preserve_order(python_candidates) {
        eprintln!("murisphere desktop trying local backend python: {python}");
        let mut command = Command::new(&python);
        command.current_dir(repo_root);
        command.arg("app.py");
        command.env("MURISPHERE_HOST", host);
        command.env("MURISPHERE_PORT", port.to_string());
        command.env("MURISPHERE_RUNTIME_MODE", "desktop-local");
        command.stdin(Stdio::null());
        command.stdout(Stdio::null());
        command.stderr(Stdio::inherit());
        match command.spawn() {
            Ok(child) => return Ok(child),
            Err(err) => {
                last_error = Some(format!("{python}: {err}"));
            }
        }
    }

    Err(format!(
        "Unable to launch local Murisphere backend automatically. Last error: {}",
        last_error.unwrap_or_else(|| "unknown process spawn failure".to_string())
    ))
}

fn dedupe_preserve_order(values: Vec<String>) -> Vec<String> {
    let mut deduped = Vec::new();
    for value in values {
        if !deduped.contains(&value) {
            deduped.push(value);
        }
    }
    deduped
}
