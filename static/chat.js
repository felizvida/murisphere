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
  busy: false,
};

const PENDING_SCAN_KEY = "murisphere_pending_scan";

const el = (id) => document.getElementById(id);

function showMessage(text, tone = "info") {
  const node = el("globalMessage");
  if (!node) return;
  node.textContent = text || "";
  node.className = `global-message ${tone}`;
  if (!text) {
    node.classList.add("hidden");
    return;
  }
  node.classList.remove("hidden");
  window.clearTimeout(showMessage._timer);
  showMessage._timer = window.setTimeout(() => node.classList.add("hidden"), 3600);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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
    el("chatTranscript").innerHTML = "";
  }
}

function headers(isJson = true) {
  const out = {};
  if (state.token) out.Authorization = `Bearer ${state.token}`;
  if (isJson) out["Content-Type"] = "application/json";
  return out;
}

function handleSessionExpired(message = "Session expired. Please sign in again.") {
  setAuth("", null);
  showMessage(message, "warn");
}

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `Request failed: ${res.status}`);
    err.status = res.status;
    err.payload = data;
    if (err && Number(err.status) === 401) {
      handleSessionExpired();
    }
    throw err;
  }
  return data;
}

async function withAction(label, fn) {
  try {
    await fn();
  } catch (err) {
    if (err && Number(err.status) === 401) {
      handleSessionExpired();
      return;
    }
    showMessage(`${label}: ${err?.message || "Action failed"}`, "error");
  }
}

function rememberPendingScanFromUrl() {
  const url = new URL(window.location.href);
  const scanToken = url.searchParams.get("scanToken");
  if (!scanToken) return;
  localStorage.setItem(PENDING_SCAN_KEY, scanToken);
  url.searchParams.delete("scanToken");
  window.history.replaceState({}, "", url.pathname + url.search);
}

function consumePendingScan() {
  const token = localStorage.getItem(PENDING_SCAN_KEY);
  if (!token) return null;
  localStorage.removeItem(PENDING_SCAN_KEY);
  return token;
}

function setBusy(busy) {
  state.busy = busy;
  el("sendChatBtn").disabled = busy;
  el("chatInput").disabled = busy;
}

function scrollTranscript() {
  const host = el("chatTranscript");
  host.scrollTop = host.scrollHeight;
}

function createTurn(role, bodyHtml = "") {
  const turn = document.createElement("section");
  turn.className = `turn ${role}`;
  turn.innerHTML = `
    <div class="turn-label">${role === "assistant" ? "Murisphere" : "You"}</div>
    <div class="bubble">${bodyHtml}</div>
  `;
  el("chatTranscript").appendChild(turn);
  scrollTranscript();
  return turn;
}

function renderStatsCard(card) {
  return `
    <article class="reply-card">
      <h4>${escapeHtml(card.title)}</h4>
      <div class="metric-grid">
        ${(card.items || [])
          .map(
            (item) => `
              <div class="metric ${escapeHtml(item.tone || "normal")}">
                <div class="label">${escapeHtml(item.label)}</div>
                <div class="value">${escapeHtml(item.value)}</div>
              </div>
            `,
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderListCard(card) {
  const items = card.items || [];
  return `
    <article class="reply-card">
      <h4>${escapeHtml(card.title)}</h4>
      ${
        items.length
          ? `<ul class="item-list">${items
              .map(
                (item) => `
                  <li>
                    <div class="item-title">${escapeHtml(item.title)}</div>
                    ${item.subtitle ? `<div class="item-subtitle">${escapeHtml(item.subtitle)}</div>` : ""}
                    ${item.detail ? `<div class="item-detail">${escapeHtml(item.detail)}</div>` : ""}
                  </li>
                `,
              )
              .join("")}</ul>`
          : `<p class="turn-body">${escapeHtml(card.emptyText || "Nothing to show.")}</p>`
      }
    </article>
  `;
}

function renderChecklistCard(card) {
  const items = card.items || [];
  return `
    <article class="reply-card">
      <h4>${escapeHtml(card.title)}</h4>
      <ul class="checklist">
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </article>
  `;
}

function renderLinksCard(card) {
  const links = card.links || [];
  return `
    <article class="reply-card">
      <h4>${escapeHtml(card.title)}</h4>
      <div class="card-links">
        ${links
          .map(
            (link) =>
              `<a class="soft-link" href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label)}</a>`,
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderTableCard(card) {
  const rows = card.rows || [];
  return `
    <article class="reply-card">
      <h4>${escapeHtml(card.title)}</h4>
      ${
        rows.length
          ? `
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>${(card.columns || []).map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr>
                </thead>
                <tbody>
                  ${rows
                    .map(
                      (row) =>
                        `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`,
                    )
                    .join("")}
                </tbody>
              </table>
            </div>
          `
          : `<p class="turn-body">${escapeHtml(card.emptyText || "Nothing to show.")}</p>`
      }
    </article>
  `;
}

function renderDetailCard(card) {
  return `
    <article class="reply-card">
      <h4>${escapeHtml(card.title)}</h4>
      ${card.badge ? `<div class="badge">${escapeHtml(card.badge)}</div>` : ""}
      <div class="detail-grid">
        ${(card.fields || [])
          .map(
            (field) => `
              <div class="detail-row">
                <div class="label">${escapeHtml(field.label)}</div>
                <div class="value">${escapeHtml(field.value)}</div>
              </div>
            `,
          )
          .join("")}
      </div>
      ${
        (card.links || []).length
          ? `<div class="card-links">${card.links
              .map(
                (link) =>
                  `<a class="soft-link" href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label)}</a>`,
              )
              .join("")}</div>`
          : ""
      }
    </article>
  `;
}

function renderCard(card) {
  if (!card || !card.kind) return "";
  switch (card.kind) {
    case "stats":
      return renderStatsCard(card);
    case "list":
      return renderListCard(card);
    case "checklist":
      return renderChecklistCard(card);
    case "links":
      return renderLinksCard(card);
    case "table":
      return renderTableCard(card);
    case "cage":
    case "project":
      return renderDetailCard(card);
    default:
      return `
        <article class="reply-card">
          <h4>${escapeHtml(card.title || "Response")}</h4>
          <p class="turn-body">Unsupported card type: ${escapeHtml(card.kind)}</p>
        </article>
      `;
  }
}

function updatePromptStrip(suggestions = []) {
  const prompts = suggestions.length
    ? suggestions
    : ["What needs attention today?", "Give me the facility morning brief", "Show alerts", "Show overdue tasks", "Show reports"];
  el("quickPromptStrip").innerHTML = prompts
    .map((prompt) => `<button type="button" data-chat-prompt="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>`)
    .join("");
}

function appendAssistantReply(reply) {
  const turn = document.createElement("section");
  turn.className = "turn assistant";
  turn.innerHTML = `
    <div class="turn-label">Murisphere</div>
    <div class="bubble"><div class="turn-body">${escapeHtml(reply.message || "")}</div></div>
    <div class="turn-cards">${(reply.cards || []).map((card) => renderCard(card)).join("")}</div>
    <div class="turn-suggestions">
      ${(reply.suggestions || [])
        .map((prompt) => `<button type="button" data-chat-prompt="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>`)
        .join("")}
    </div>
  `;
  el("chatTranscript").appendChild(turn);
  updatePromptStrip(reply.suggestions || []);
  scrollTranscript();
}

async function sendChat(message, { silentUser = false } = {}) {
  if (state.busy) return;
  const text = String(message || "").trim();
  if (!silentUser && !text) return;
  if (!silentUser) createTurn("user", `<div class="turn-body">${escapeHtml(text)}</div>`);
  setBusy(true);
  try {
    const reply = await api("/api/chat", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ message: text }),
    });
    appendAssistantReply(reply);
  } finally {
    setBusy(false);
    el("chatInput").focus();
  }
}

async function bootstrapConversation() {
  const pendingScan = consumePendingScan();
  if (pendingScan) {
    await sendChat(`Open cage ${pendingScan}`, { silentUser: true });
    return;
  }
  await sendChat("", { silentUser: true });
}

async function tryRestoreSession() {
  try {
    const me = await api("/api/auth/me", { headers: headers(false) });
    setAuth("", me);
    await bootstrapConversation();
  } catch (err) {
    if (err && Number(err.status) !== 401) {
      showMessage(err?.message || "Unable to restore session", "error");
    }
  }
}

async function signOut() {
  await withAction("Sign out", async () => {
    await api("/api/auth/logout", { method: "POST", headers: headers(false) });
    setAuth("", null);
    updatePromptStrip();
  });
}

async function runPrompt(prompt) {
  await withAction("Chat", async () => {
    await sendChat(prompt);
  });
}

function autoResizeComposer() {
  const input = el("chatInput");
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
}

function bindEvents() {
  el("loginForm").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    await withAction("Login", async () => {
      const payload = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: el("email").value, password: el("password").value }),
      });
      setAuth(payload.token, payload.user);
      el("chatTranscript").innerHTML = "";
      updatePromptStrip();
      await bootstrapConversation();
    });
  });

  el("chatForm").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const message = el("chatInput").value.trim();
    if (!message) return;
    el("chatInput").value = "";
    autoResizeComposer();
    await withAction("Chat", async () => {
      await sendChat(message);
    });
  });

  el("dailyBriefingBtn").addEventListener("click", () => runPrompt("What needs attention today?"));
  el("technicianChecklistBtn").addEventListener("click", () => runPrompt("Technician checklist"));
  el("managerChecklistBtn").addEventListener("click", () => runPrompt("Manager checklist"));
  el("clearConversationBtn").addEventListener("click", async () => {
    await withAction("Clear conversation", async () => {
      el("chatTranscript").innerHTML = "";
      await bootstrapConversation();
    });
  });
  el("logoutBtn").addEventListener("click", signOut);

  el("quickPromptStrip").addEventListener("click", async (evt) => {
    const button = evt.target.closest("[data-chat-prompt]");
    if (!button) return;
    await runPrompt(button.dataset.chatPrompt || "");
  });

  el("chatTranscript").addEventListener("click", async (evt) => {
    const button = evt.target.closest("[data-chat-prompt]");
    if (!button) return;
    await runPrompt(button.dataset.chatPrompt || "");
  });

  el("chatInput").addEventListener("input", autoResizeComposer);
  el("chatInput").addEventListener("keydown", (evt) => {
    if (evt.key === "Enter" && !evt.shiftKey) {
      evt.preventDefault();
      el("chatForm").requestSubmit();
    }
  });
}

rememberPendingScanFromUrl();
updatePromptStrip();
bindEvents();
autoResizeComposer();
tryRestoreSession();
