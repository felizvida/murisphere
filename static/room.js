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

const state = {
  token: "",
  user: null,
  summary: null,
  selectedRoomId: null,
  activePassId: null,
  selectedCage: null,
};

const PENDING_SCAN_KEY = "murisphere_pending_scan";

const el = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function showMessage(text, tone = "info") {
  const node = el("globalMessage");
  if (!node) return;
  node.textContent = text || "";
  node.className = `global-message ${tone}`;
  node.classList.toggle("hidden", !text);
  window.clearTimeout(showMessage._timer);
  if (text) {
    showMessage._timer = window.setTimeout(() => node.classList.add("hidden"), 3600);
  }
}

function headers(isJson = true) {
  const out = {};
  if (state.token) out.Authorization = `Bearer ${state.token}`;
  if (isJson) out["Content-Type"] = "application/json";
  return out;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `Request failed: ${res.status}`);
    err.status = res.status;
    err.payload = data;
    if (Number(err.status) === 401) setAuth("", null);
    throw err;
  }
  return data;
}

async function withAction(label, fn) {
  try {
    return await fn();
  } catch (err) {
    showMessage(`${label}: ${err?.message || "Action failed"}`, "error");
    return null;
  }
}

function setAuth(token, user) {
  state.token = token || "";
  state.user = user || null;
  if (user) {
    el("sessionChip").textContent = `${user.fullName} (${user.role})`;
    el("sessionChip").classList.remove("hidden");
    el("loginPanel").classList.add("hidden");
    el("appPanel").classList.remove("hidden");
  } else {
    el("sessionChip").classList.add("hidden");
    el("loginPanel").classList.remove("hidden");
    el("appPanel").classList.add("hidden");
  }
}

function rememberPendingScanFromUrl() {
  const url = new URL(window.location.href);
  const token = url.searchParams.get("scanToken");
  if (!token) return;
  localStorage.setItem(PENDING_SCAN_KEY, token);
  url.searchParams.delete("scanToken");
  window.history.replaceState({}, "", url.pathname + url.search);
}

function consumePendingScan() {
  const token = localStorage.getItem(PENDING_SCAN_KEY);
  if (!token) return "";
  localStorage.removeItem(PENDING_SCAN_KEY);
  return token;
}

function tierBadge(tier) {
  const safe = escapeHtml(tier || "INFO");
  return `<span class="tier ${safe}">${safe}</span>`;
}

function renderRooms(rooms) {
  const selectedId = Number(state.selectedRoomId || state.summary?.selectedRoom?.id || 0);
  el("roomList").innerHTML = rooms.length
    ? rooms
        .map(
          (room) => `
            <button type="button" class="room-pill ${Number(room.id) === selectedId ? "active" : ""}" data-room-id="${escapeHtml(room.id)}">
              ${escapeHtml(room.name)} · ${escapeHtml(room.cageCount)}
            </button>
          `,
        )
        .join("")
    : `<div class="empty">No rooms are available in your scope.</div>`;
}

function renderStats(stats) {
  const cards = [
    ["Cages", stats.cageCount],
    ["Need action", stats.queueCount],
    ["STOP", stats.stopCount],
    ["Scanned", `${stats.scannedCount}/${stats.cageCount}`],
  ];
  el("missionStats").innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
        </article>
      `,
    )
    .join("");
}

function renderPass(pass) {
  state.activePassId = pass?.id || null;
  const panel = el("activePassPanel");
  const summaryPanel = el("passSummaryPanel");
  if (!pass) {
    panel.classList.add("hidden");
    summaryPanel.classList.add("hidden");
    el("startPassBtn").textContent = "Start Room Pass";
    return;
  }
  el("startPassBtn").textContent = "Resume Room Pass";
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <div>
      <p class="eyebrow">Active room pass</p>
      <h2>${escapeHtml(pass.scannedCages)} scanned · ${escapeHtml(pass.remainingCages)} remaining</h2>
      <p class="muted">Started ${escapeHtml(pass.startedAt)}. Actions logged by you: ${escapeHtml(pass.actionsLoggedByUser)}</p>
    </div>
    <button id="completePassBtn" type="button" class="quiet-button">Complete</button>
  `;
  summaryPanel.classList.remove("hidden");
  summaryPanel.innerHTML = `
    <div class="section-head">
      <div>
        <p class="eyebrow">Reconciliation</p>
        <h2>End-of-shift evidence</h2>
      </div>
    </div>
    <div class="fact-grid">
      <div class="fact"><div class="label">Expected</div><div class="value">${escapeHtml(pass.expectedCages)}</div></div>
      <div class="fact"><div class="label">Scanned</div><div class="value">${escapeHtml(pass.scannedCages)}</div></div>
      <div class="fact"><div class="label">Remaining</div><div class="value">${escapeHtml(pass.remainingCages)}</div></div>
      <div class="fact"><div class="label">Actions</div><div class="value">${escapeHtml(pass.actionsLoggedByUser)}</div></div>
    </div>
    ${
      pass.notScannedPreview?.length
        ? `<p class="muted" style="margin-top:.7rem">Not scanned yet: ${pass.notScannedPreview.map(escapeHtml).join(", ")}</p>`
        : `<p class="muted" style="margin-top:.7rem">Every expected cage in this room pass has been scanned.</p>`
    }
  `;
}

function renderQueue(queue) {
  el("actionQueue").innerHTML = queue.length
    ? queue
        .map(
          (item) => `
            <button type="button" class="queue-card ${escapeHtml(item.tier)}" data-cage-code="${escapeHtml(item.cageCode)}">
              <span class="queue-title">
                <strong>${escapeHtml(item.cageCode)}</strong>
                ${tierBadge(item.tier)}
              </span>
              <div class="muted">${escapeHtml(item.room)} / ${escapeHtml(item.rack || "-")} · ${escapeHtml(item.primaryAction)}</div>
              <ul class="reason-list">${(item.reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
            </button>
          `,
        )
        .join("")
    : `<div class="empty">No cages need attention in this room right now. That rare creature: a quiet queue.</div>`;
}

function renderSummary(summary) {
  state.summary = summary;
  state.selectedRoomId = summary.selectedRoom?.id || state.selectedRoomId;
  el("roomTitle").textContent = summary.selectedRoom ? summary.selectedRoom.name : "No room selected";
  el("roomSubtitle").textContent = summary.selectedRoom
    ? `${summary.selectedRoom.cageCount} cages · M${summary.selectedRoom.maleCount}/F${summary.selectedRoom.femaleCount}`
    : "No room is available in your scope.";
  renderRooms(summary.rooms || []);
  renderStats(summary.stats || {});
  renderQueue(summary.actionQueue || []);
  renderPass(summary.activePass || null);
}

async function loadSummary(roomId = state.selectedRoomId) {
  const query = roomId ? `?roomId=${encodeURIComponent(roomId)}` : "";
  const summary = await api(`/api/room-mode/summary${query}`, { headers: headers(false) });
  renderSummary(summary);
  return summary;
}

function renderCage(data) {
  state.selectedCage = data;
  const cage = data.cage;
  const detail = el("cageDetail");
  detail.classList.remove("hidden");
  detail.innerHTML = `
    <div class="cage-hero ${escapeHtml(data.tier)}">
      <div class="cage-title">
        <strong>${escapeHtml(cage.cageCode)}</strong>
        ${tierBadge(data.tier)}
      </div>
      <p class="muted">${escapeHtml(cage.room)} / ${escapeHtml(cage.rack)} · ${escapeHtml(cage.lab)}</p>
      ${data.protocolMessage ? `<p style="margin-top:.55rem;font-weight:800">${escapeHtml(data.protocolMessage)}</p>` : ""}
    </div>
    <div class="cage-body">
      <div class="fact-grid">
        <div class="fact"><div class="label">Population</div><div class="value">M${escapeHtml(cage.maleCount)} / F${escapeHtml(cage.femaleCount)} / T${escapeHtml(cage.populationTotal)}</div></div>
        <div class="fact"><div class="label">Status</div><div class="value">${escapeHtml(cage.breedingStatus)}</div></div>
        <div class="fact"><div class="label">Strain</div><div class="value">${escapeHtml(cage.strain)}</div></div>
        <div class="fact"><div class="label">Genotype</div><div class="value">${escapeHtml(cage.genotypeSummary)}</div></div>
        <div class="fact"><div class="label">Protocol</div><div class="value">${escapeHtml(cage.protocol || "-")}</div></div>
        <div class="fact"><div class="label">Project</div><div class="value">${escapeHtml(cage.projectCodes || "-")}</div></div>
      </div>

      <div>
        <p class="eyebrow">Primary actions</p>
        <div class="action-grid">
          ${(data.primaryActions || [])
            .map(
              (action) => `
                <button type="button" class="action-button" data-action="${escapeHtml(action.key)}" data-tone="${escapeHtml(action.tone || "action")}">
                  ${escapeHtml(action.label)}
                </button>
              `,
            )
            .join("")}
        </div>
      </div>

      <section id="countPanel" class="action-panel">
        <form id="countForm" class="action-form">
          <div class="two-col">
            <label>Males<input id="maleCountInput" type="number" min="0" value="${escapeHtml(cage.maleCount)}" /></label>
            <label>Females<input id="femaleCountInput" type="number" min="0" value="${escapeHtml(cage.femaleCount)}" /></label>
          </div>
          <label>Status
            <select id="statusInput">
              ${["Breeding", "Holding", "Weaning", "Retired", "Experimental", "Quarantine"]
                .map((s) => `<option ${s === cage.breedingStatus ? "selected" : ""}>${escapeHtml(s)}</option>`)
                .join("")}
            </select>
          </label>
          <button type="submit">Save count/status</button>
        </form>
      </section>

      <section id="notePanel" class="action-panel">
        <form id="noteForm" class="action-form">
          <label>Room note<textarea id="noteInput" placeholder="Example: one pup runted, nesting good"></textarea></label>
          <button type="submit">Save note</button>
        </form>
      </section>

      <section id="mortalityPanel" class="action-panel">
        <form id="mortalityForm" class="action-form">
          <div class="two-col">
            <label>Males found dead<input id="mortMaleInput" type="number" min="0" value="0" /></label>
            <label>Females found dead<input id="mortFemaleInput" type="number" min="0" value="0" /></label>
          </div>
          <label>Cause<input id="mortCauseInput" placeholder="found dead, culled, unknown" /></label>
          <label>Notes<textarea id="mortNotesInput"></textarea></label>
          <label><input id="necropsyInput" type="checkbox" style="min-height:auto;width:auto" /> Necropsy required</label>
          <button type="submit">Record mortality</button>
        </form>
      </section>

      <section id="weanPanel" class="action-panel">
        <form id="weanForm" class="action-form">
          <label>Litter
            <select id="weanLitterInput">
              ${(data.weaningDue || data.litters || [])
                .filter((litter) => !litter.weanedOn)
                .map((litter) => `<option value="${escapeHtml(litter.id)}">${escapeHtml(litter.birthDate)} · due ${escapeHtml(litter.dueOn || litter.dueToWeanOn || "-")}</option>`)
                .join("")}
            </select>
          </label>
          <div class="two-col">
            <label>Weaned males<input id="weanMaleInput" type="number" min="0" value="0" /></label>
            <label>Weaned females<input id="weanFemaleInput" type="number" min="0" value="0" /></label>
          </div>
          <button type="submit">Record weaning</button>
        </form>
      </section>

      <div class="card-stack">
        ${(data.alerts || [])
          .map((alert) => `<article class="alert-card ${escapeHtml(alert.tier)}">${tierBadge(alert.tier)} <strong>${escapeHtml(alert.title)}</strong><p class="muted">${escapeHtml(alert.message)}</p></article>`)
          .join("")}
        ${(data.tasks || [])
          .map(
            (task) => `
              <article class="task-card ${escapeHtml(task.tier)}">
                <div class="queue-title"><strong>${escapeHtml(task.type)}</strong>${tierBadge(task.tier)}</div>
                <p class="muted">Due ${escapeHtml(task.dueOn)} · ${escapeHtml(task.status)}</p>
                <button type="button" class="quiet-button task-done" data-task-id="${escapeHtml(task.id)}">Mark done</button>
              </article>
            `,
          )
          .join("")}
        ${(data.litters || [])
          .map((litter) => `<article class="litter-card ${escapeHtml(litter.tier)}"><strong>Litter ${escapeHtml(litter.birthDate)}</strong><p class="muted">Born ${escapeHtml(litter.litterSize)} · survived ${escapeHtml(litter.survivedCount)} · weaned ${escapeHtml(litter.weanedOn || "no")}</p></article>`)
          .join("")}
        ${(data.notes || [])
          .map((note) => `<article class="note-card"><strong>Recent note</strong><p class="muted">${escapeHtml(note.text)}</p></article>`)
          .join("")}
      </div>
    </div>
  `;
  wireCageActions();
  detail.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function openCage(code, scanIntoPass = false) {
  if (!code) return;
  const payload = await api(`/api/room-mode/cage/${encodeURIComponent(code)}`, { headers: headers(false) });
  renderCage(payload);
  if (scanIntoPass && state.activePassId) {
    const scan = await api(`/api/room-mode/pass/${state.activePassId}/scan`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ code }),
    });
    renderPass(scan.summary);
    if (scan.outOfRoom) showMessage("Cage scanned, but it is outside the active room pass.", "warn");
    else showMessage(`Scanned ${payload.cage.cageCode}`, "info");
  }
}

function showActionPanel(name) {
  document.querySelectorAll(".action-panel").forEach((panel) => panel.classList.remove("active"));
  const panel = el(`${name}Panel`);
  if (panel) panel.classList.add("active");
}

function submitForm(formId) {
  const form = el(formId);
  if (!form) return;
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
    return;
  }
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

function wireCageActions() {
  const cage = state.selectedCage?.cage;
  if (!cage) return;
  el("cageDetail").querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action;
      if (action === "stop") {
        showMessage(state.selectedCage.protocolMessage || "Stop and escalate before changing this cage.", "warn");
        return;
      }
      if (action === "tasks") {
        const task = el("cageDetail").querySelector(".task-card");
        if (task) task.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      showActionPanel(action);
    });
  });

  el("countForm")?.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    await withAction("Save count", async () => {
      await api(`/api/cages/${cage.id}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({
          maleCount: Number(el("maleCountInput").value),
          femaleCount: Number(el("femaleCountInput").value),
          breedingStatus: el("statusInput").value,
        }),
      });
      showMessage("Count/status saved.", "info");
      await refreshAfterCageAction(cage.cageCode);
    });
  });

  el("noteForm")?.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    await withAction("Save note", async () => {
      await api(`/api/cages/${cage.id}/note`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ text: el("noteInput").value }),
      });
      showMessage("Note saved.", "info");
      await refreshAfterCageAction(cage.cageCode);
    });
  });

  el("mortalityForm")?.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    await withAction("Record mortality", async () => {
      await api(`/api/cages/${cage.id}/mortality`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          male: Number(el("mortMaleInput").value),
          female: Number(el("mortFemaleInput").value),
          cause: el("mortCauseInput").value,
          notes: el("mortNotesInput").value,
          necropsyRequired: el("necropsyInput").checked,
        }),
      });
      showMessage("Mortality recorded.", "info");
      await refreshAfterCageAction(cage.cageCode);
    });
  });

  el("weanForm")?.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    await withAction("Record weaning", async () => {
      await api(`/api/cages/${cage.id}/wean`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          litterId: Number(el("weanLitterInput").value || 0) || null,
          male: Number(el("weanMaleInput").value),
          female: Number(el("weanFemaleInput").value),
        }),
      });
      showMessage("Weaning recorded.", "info");
      await refreshAfterCageAction(cage.cageCode);
    });
  });

  el("cageDetail").querySelectorAll(".task-done").forEach((button) => {
    button.addEventListener("click", () =>
      withAction("Close task", async () => {
        await api(`/api/tasks/${button.dataset.taskId}/status`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ status: "done" }),
        });
        showMessage("Task marked done.", "info");
        await refreshAfterCageAction(cage.cageCode);
      }),
    );
  });
}

async function refreshAfterCageAction(cageCode) {
  await loadSummary(state.selectedRoomId);
  await openCage(cageCode, false);
}

async function startPass() {
  if (!state.selectedRoomId) {
    showMessage("Choose a room before starting a pass.", "warn");
    return;
  }
  const res = await api("/api/room-mode/pass/start", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ roomId: state.selectedRoomId }),
  });
  renderPass(res.summary);
  showMessage(res.existing ? "Resumed active room pass." : "Room pass started.", "info");
}

async function completePass() {
  if (!state.activePassId) return;
  const res = await api(`/api/room-mode/pass/${state.activePassId}/complete`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ notes: "Completed from Room Mode" }),
  });
  renderPass(res.summary);
  showMessage("Room pass completed.", "info");
  await loadSummary(state.selectedRoomId);
}

async function signOut() {
  await withAction("Sign out", async () => {
    await api("/api/auth/logout", { method: "POST", headers: headers(false) });
    setAuth("", null);
  });
}

async function init() {
  rememberPendingScanFromUrl();
  el("loginForm").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    await withAction("Login", async () => {
      const payload = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: el("email").value, password: el("password").value }),
      });
      setAuth(payload.token, payload.user);
      await loadSummary();
      const pending = consumePendingScan();
      if (pending) await openCage(pending, false);
    });
  });
  el("loginSubmitBtn").addEventListener("click", () => submitForm("loginForm"));

  el("roomList").addEventListener("click", (evt) => {
    const button = evt.target.closest("[data-room-id]");
    if (!button) return;
    state.selectedRoomId = Number(button.dataset.roomId);
    withAction("Load room", () => loadSummary(state.selectedRoomId));
  });

  el("scanForm").addEventListener("submit", (evt) => {
    evt.preventDefault();
    const code = el("scanCode").value.trim();
    withAction("Open cage", () => openCage(code, true));
  });
  el("scanBtn").addEventListener("click", () => submitForm("scanForm"));

  el("actionQueue").addEventListener("click", (evt) => {
    const button = evt.target.closest("[data-cage-code]");
    if (!button) return;
    el("scanCode").value = button.dataset.cageCode || "";
    withAction("Open cage", () => openCage(button.dataset.cageCode, false));
  });

  el("activePassPanel").addEventListener("click", (evt) => {
    if (evt.target.closest("#completePassBtn")) withAction("Complete pass", completePass);
  });

  el("startPassBtn").addEventListener("click", () => withAction("Start pass", startPass));
  el("refreshBtn").addEventListener("click", () => withAction("Refresh", () => loadSummary(state.selectedRoomId)));
  el("logoutBtn").addEventListener("click", signOut);
  el("navMissionBtn").addEventListener("click", () => el("actionQueue").scrollIntoView({ behavior: "smooth" }));
  el("navScanBtn").addEventListener("click", () => el("scanCode").focus());
}

init().catch((err) => {
  console.error(err);
  showMessage(err?.message || "Room Mode failed to initialize", "error");
});
