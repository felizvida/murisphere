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
  cages: [],
  projects: [],
  cards: [],
  alerts: [],
  alertsByCage: {},
  learning: null,
  plannerScenarios: [],
  selectedPlannerScenarioId: null,
  samples: [],
  selectedSampleIds: [],
  genotypingOrders: [],
  selectedGenotypingOrderId: null,
  genotypingDashboard: null,
  providerPresets: [],
  cohortInsights: null,
  selectedCohortAnimalIds: [],
  selectedCohortProjectId: null,
};
const PENDING_SCAN_KEY = "murisphere_pending_scan";
const SCAN_BASE_KEY = "murisphere_scan_base_url";
const MUTATION_QUEUE_KEY = "murisphere_mutation_queue";
const LEARNING_PROGRESS_KEY = "murisphere_learning_progress";
const SEVERITY_RANK = { high: 3, medium: 2, low: 1 };

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
  showMessage._timer = window.setTimeout(() => {
    node.classList.add("hidden");
  }, 3600);
}

function handleSessionExpired(message = "Session expired. Please sign in again.") {
  setAuth("", null);
  state.cages = [];
  state.projects = [];
  state.cards = [];
  state.alerts = [];
  state.alertsByCage = {};
  state.learning = null;
  state.plannerScenarios = [];
  state.selectedPlannerScenarioId = null;
  state.samples = [];
  state.selectedSampleIds = [];
  state.genotypingOrders = [];
  state.selectedGenotypingOrderId = null;
  state.genotypingDashboard = null;
  state.providerPresets = [];
  state.cohortInsights = null;
  state.selectedCohortAnimalIds = [];
  state.selectedCohortProjectId = null;
  showMessage(message, "warn");
}

function handleBackgroundError(err, context = "Background refresh failed") {
  if (err && Number(err.status) === 401) {
    handleSessionExpired();
    return;
  }
  const message = err?.message || "Unexpected background error";
  console.warn(`${context}: ${message}`, err);
}

async function withAction(label, fn) {
  try {
    await fn();
  } catch (err) {
    if (err && Number(err.status) === 401) {
      handleSessionExpired();
      return;
    }
    const message = err?.message || "Action failed";
    showMessage(`${label}: ${message}`, "error");
    throw err;
  }
}

function headers(isJson = true) {
  const base = {};
  if (state.token) {
    base.Authorization = `Bearer ${state.token}`;
  }
  if (isJson) base["Content-Type"] = "application/json";
  return base;
}

function setAuth(token, user) {
  state.token = token;
  state.user = user;
  if (user) {
    el("sessionChip").classList.remove("hidden");
    el("sessionChip").textContent = `${user.fullName} (${user.role})`;
    el("loginPanel").classList.add("hidden");
    el("appPanel").classList.remove("hidden");
  } else {
    el("sessionChip").classList.add("hidden");
    el("loginPanel").classList.remove("hidden");
    el("appPanel").classList.add("hidden");
  }
}

function activateTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.toggle("active", c.id === `tab-${name}`));
}

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `Request failed: ${res.status}`);
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

function mutationQueueKey() {
  return `${MUTATION_QUEUE_KEY}:${state.user?.id || "anon"}`;
}

function learningProgressKey() {
  return `${LEARNING_PROGRESS_KEY}:${state.user?.id || "anon"}`;
}

function readMutationQueue() {
  try {
    return JSON.parse(localStorage.getItem(mutationQueueKey()) || "[]");
  } catch {
    return [];
  }
}

function writeMutationQueue(items) {
  localStorage.setItem(mutationQueueKey(), JSON.stringify(items));
}

function enqueueMutation(path, opts) {
  const queue = readMutationQueue();
  queue.push({
    path,
    opts: {
      method: opts.method || "POST",
      body: opts.body || null,
    },
    queuedAt: new Date().toISOString(),
  });
  writeMutationQueue(queue);
}

function readLearningProgress() {
  try {
    return JSON.parse(localStorage.getItem(learningProgressKey()) || "{}");
  } catch {
    return {};
  }
}

function writeLearningProgress(progress) {
  localStorage.setItem(learningProgressKey(), JSON.stringify(progress || {}));
}

function moduleComplete(moduleId) {
  return !!readLearningProgress()[moduleId];
}

function setModuleComplete(moduleId, complete) {
  const progress = readLearningProgress();
  if (complete) progress[moduleId] = true;
  else delete progress[moduleId];
  writeLearningProgress(progress);
}

async function flushMutationQueue() {
  const queue = readMutationQueue();
  if (!queue.length) return 0;
  const remaining = [];
  let sent = 0;
  for (const item of queue) {
    try {
      const opts = {
        method: item.opts.method || "POST",
        headers: headers(),
      };
      if (item.opts.body != null) opts.body = item.opts.body;
      await api(item.path, opts);
      sent += 1;
    } catch (err) {
      if (err && Number(err.status) === 401) {
        throw err;
      }
      remaining.push(item);
    }
  }
  writeMutationQueue(remaining);
  return sent;
}

function severityClass(level) {
  if (level === "high" || level === "medium" || level === "low") return level;
  return "low";
}

function alertBadge(alerts) {
  if (!alerts || !alerts.length) return "";
  const top = alerts[0];
  return `<span class="alert-pill ${esc(severityClass(top.severity))}">${esc(top.severity.toUpperCase())} ${esc(alerts.length)} alert${alerts.length > 1 ? "s" : ""}</span>`;
}

function tableFromCages(rows, alertsByCage = {}) {
  return `
    <table class="table">
      <thead><tr><th>ID</th><th>Cage</th><th>Alert</th><th>Strain</th><th>Genotype</th><th>Status</th><th>M/F</th><th>Projects</th><th>Location</th></tr></thead>
      <tbody>
        ${rows
          .map(
            (c) => {
              const alerts = alertsByCage[c.id] || [];
              const rowClass = alerts.length ? `alert-${severityClass(alerts[0].severity)}` : "";
              return `
          <tr class="${rowClass}">
            <td>${esc(c.id)}</td>
            <td><button type="button" class="table-link" data-cage-id="${esc(c.id)}">${esc(c.cageCode)}</button></td>
            <td>${alertBadge(alerts)}</td><td>${esc(c.strain)}</td><td>${esc(c.genotypeSummary)}</td><td>${esc(c.breedingStatus)}</td>
            <td>${esc(c.maleCount)}/${esc(c.femaleCount)}</td><td>${esc(c.projectCodes || "Unassigned")}</td><td>${esc(c.room)} / ${esc(c.rack)}</td>
          </tr>`;
            }
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function tableFromProjects(rows) {
  return `
    <table class="table">
      <thead><tr><th>Code</th><th>Title</th><th>Status</th><th>Target</th><th>Lab</th><th>Assigned Cages</th></tr></thead>
      <tbody>
        ${rows
          .map(
            (p) => `
          <tr>
            <td><button type="button" class="table-link" data-project-id="${esc(p.id)}">${esc(p.project_code)}</button></td>
            <td><button type="button" class="table-link" data-project-id="${esc(p.id)}">${esc(p.title)}</button></td><td>${esc(p.status)}</td>
            <td>${esc(p.target_animals)}</td><td>${esc(p.lab_name)}</td><td>${esc(p.assigned_cages)}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function tableFromQuotas(rows) {
  return `
    <table class="table">
      <thead><tr><th>Lab</th><th>Tier</th><th>Expected Cages</th><th>Current Cages</th><th>Remaining</th><th>Projects</th></tr></thead>
      <tbody>
        ${rows
          .map(
            (q) => `
          <tr>
            <td>${esc(q.labName)}</td><td>${esc(q.sizeTier)}</td><td>${esc(q.expectedCageLoad)}</td>
            <td>${esc(q.currentCages)}</td><td>${esc(q.remainingQuota)}</td><td>${esc(q.currentProjects)}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function esc(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtDate(v) {
  if (!v) return "N/A";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${mm}/${dd}/${d.getFullYear()}`;
}

function chartCard(title, subtitle, inner, legend = "") {
  return `
    <article class="viz-card">
      <h4>${esc(title)}</h4>
      <div class="viz-sub">${esc(subtitle || "")}</div>
      ${inner}
      ${legend ? `<div class="viz-legend">${legend}</div>` : ""}
    </article>
  `;
}

function drawBars(rows, opts = {}) {
  const width = opts.width || 340;
  const height = opts.height || 170;
  const pad = 28;
  if (!rows.length) return `<svg class="viz-svg" viewBox="0 0 ${width} ${height}" aria-label="empty"></svg>`;
  const maxVal = Math.max(...rows.map((r) => toNum(r.value)), 1);
  const barW = Math.max(14, (width - pad * 2) / rows.length - 8);
  const step = (width - pad * 2) / rows.length;
  const bars = rows
    .map((r, i) => {
      const val = toNum(r.value);
      const h = Math.max(2, ((height - pad * 2) * val) / maxVal);
      const x = pad + i * step + (step - barW) / 2;
      const y = height - pad - h;
      const label = String(r.label || "").slice(0, 6);
      const color = r.color || "#18a172";
      return `<g>
        <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="6" fill="${color}">
          <title>${esc(r.label)}: ${val}</title>
        </rect>
        <text x="${(x + barW / 2).toFixed(1)}" y="${height - 10}" text-anchor="middle" font-size="9" fill="#3f5963">${esc(label)}</text>
      </g>`;
    })
    .join("");
  return `<svg class="viz-svg" viewBox="0 0 ${width} ${height}" role="img">${bars}</svg>`;
}

function drawDonut(parts, opts = {}) {
  const size = opts.size || 160;
  const stroke = opts.stroke || 18;
  const r = (size - stroke) / 2;
  const c = size / 2;
  const total = Math.max(1, parts.reduce((acc, p) => acc + toNum(p.value), 0));
  let start = -Math.PI / 2;
  const segs = parts
    .map((p) => {
      const frac = toNum(p.value) / total;
      const end = start + frac * Math.PI * 2;
      const x1 = c + r * Math.cos(start);
      const y1 = c + r * Math.sin(start);
      const x2 = c + r * Math.cos(end);
      const y2 = c + r * Math.sin(end);
      const large = end - start > Math.PI ? 1 : 0;
      const d = `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
      start = end;
      return `<path d="${d}" stroke="${p.color}" stroke-width="${stroke}" fill="none" stroke-linecap="round"><title>${esc(
        p.label
      )}: ${toNum(p.value)}</title></path>`;
    })
    .join("");
  return `<svg class="viz-svg" viewBox="0 0 ${size} ${size}">
    ${segs}
    <circle cx="${c}" cy="${c}" r="${r - stroke * 0.8}" fill="#fff"></circle>
    <text x="${c}" y="${c - 3}" text-anchor="middle" font-size="13" font-weight="700" fill="#1c3a42">${total}</text>
    <text x="${c}" y="${c + 13}" text-anchor="middle" font-size="9" fill="#5a6b73">total</text>
  </svg>`;
}

function drawSparkline(values, color = "#18a172") {
  const v = values.map(toNum);
  const width = 320;
  const height = 48;
  if (!v.length) return `<svg class="sparkline" viewBox="0 0 ${width} ${height}"></svg>`;
  const min = Math.min(...v);
  const max = Math.max(...v);
  const span = Math.max(1, max - min);
  const pts = v
    .map((n, i) => {
      const x = (i / Math.max(1, v.length - 1)) * (width - 8) + 4;
      const y = height - 4 - ((n - min) / span) * (height - 12);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></polyline>
  </svg>`;
}

function renderCageVisuals() {
  const cages = state.cages || [];
  if (!cages.length) {
    el("cageVisuals").innerHTML = chartCard("Cage Visuals", "No data", `<p class="hint">Load cages to render visualizations.</p>`);
    return;
  }
  const byRoom = {};
  const byStatus = {};
  const topAlerts = [];
  for (const c of cages) {
    byRoom[c.room] = (byRoom[c.room] || 0) + 1;
    byStatus[c.breedingStatus] = (byStatus[c.breedingStatus] || 0) + 1;
    const alerts = state.alertsByCage[c.id] || [];
    if (alerts.length) topAlerts.push({ label: c.cageCode, value: alerts.length, color: alerts[0].severity === "high" ? "#ca513d" : "#eb9c44" });
  }
  const roomRows = Object.entries(byRoom)
    .map(([label, value]) => ({ label, value, color: "#2f9f78" }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 12);
  const statusParts = Object.entries(byStatus).map(([label, value], i) => ({
    label,
    value,
    color: ["#18a172", "#3ba0d8", "#eb9c44", "#ca513d", "#64748b"][i % 5],
  }));
  const alertRows = topAlerts.sort((a, b) => b.value - a.value).slice(0, 10);

  const roomLegend = roomRows.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("");
  const statusLegend = statusParts.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("");
  const alertLegend = alertRows.length
    ? alertRows.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("")
    : `<span class="legend-item">No alerted cages</span>`;

  el("cageVisuals").innerHTML = [
    chartCard("Room Density", "Cages per room", drawBars(roomRows), roomLegend),
    chartCard("Breeding Status Mix", "Distribution of cage statuses", drawDonut(statusParts), statusLegend),
    chartCard("Alerted Cages", "Cages requiring attention", drawBars(alertRows, { height: 150 }), alertLegend),
  ].join("");
}

function renderAnalyticsVisuals(summary, nonProd, reminders, space, consolidation) {
  const roomRows = (space.rooms || []).map((r) => ({
    label: r.roomName || `Room ${r.roomId}`,
    value: toNum(r.projectedUtilizationPct || 0),
    color: toNum(r.projectedUtilizationPct || 0) > 100 ? "#ca513d" : "#18a172",
  }));
  const reminderSeries = reminders
    .slice(0, 21)
    .map((r) => new Date(r.event_date || r.due_on || Date.now()).getTime())
    .sort((a, b) => a - b);
  const bins = {};
  for (const ts of reminderSeries) {
    const k = new Date(ts).toISOString().slice(0, 10);
    bins[k] = (bins[k] || 0) + 1;
  }
  const reminderBars = Object.entries(bins).slice(0, 10).map(([label, value]) => ({ label: label.slice(5), value, color: "#3b82f6" }));
  const nonProdBars = nonProd.slice(0, 10).map((x) => ({ label: x.cage_code, value: 1, color: "#eb9c44" }));
  const sexParts = [
    { label: "Male", value: toNum(summary.sexRatio?.M || 0), color: "#3ba0d8" },
    { label: "Female", value: toNum(summary.sexRatio?.F || 0), color: "#e6739f" },
  ];
  const overCap = roomRows.filter((r) => r.value > 100).length;
  const utilLegend = roomRows.slice(0, 10).map((r) => `<span class="legend-item">${esc(r.label)} ${toNum(r.value).toFixed(0)}%</span>`).join("");
  const reminderLegend = reminderBars.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("");
  const npLegend = `<span class="legend-item">${nonProd.length} non-productive cages</span><span class="legend-item">${consolidation.length} consolidation opportunities</span><span class="legend-item">${overCap} projected over-cap rooms</span>`;
  const sexLegend = sexParts.map((p) => `<span class="legend-item">${esc(p.label)} ${esc(p.value)}</span>`).join("");

  el("analyticsVisuals").innerHTML = [
    chartCard("Projected Capacity", "30-day room utilization", drawBars(roomRows.slice(0, 12)), utilLegend),
    chartCard("Task Pressure Curve", "Upcoming reminders by day", `${drawBars(reminderBars, { height: 130 })}${drawSparkline(reminderBars.map((r) => r.value), "#3b82f6")}`, reminderLegend),
    chartCard("Breeding Throughput Risk", "Non-productive and consolidation pressure", drawBars(nonProdBars, { height: 120 }), npLegend),
    chartCard("Population Sex Balance", "Current sex ratio snapshot", drawDonut(sexParts), sexLegend),
  ].join("");
}

function plannerRiskClass(level) {
  if (level === "high" || level === "medium" || level === "low") return level;
  return "low";
}

function plannerScenarioById(id) {
  return (state.plannerScenarios || []).find((scenario) => Number(scenario.id) === Number(id));
}

function parseJsonField(raw) {
  if (!raw) return {};
  if (typeof raw === "object") return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function plannerLabs() {
  const labs = new Map();
  (state.projects || []).forEach((project) => {
    const id = Number(project.lab_id || project.labId || 0);
    if (!id) return;
    if (!labs.has(id)) labs.set(id, { id, name: project.lab_name || `Lab ${id}` });
  });
  (state.plannerScenarios || []).forEach((scenario) => {
    const id = Number(scenario.lab_id || scenario.labId || 0);
    if (!id) return;
    if (!labs.has(id)) labs.set(id, { id, name: scenario.lab_name || `Lab ${id}` });
  });
  if (!labs.size && state.user?.labId) labs.set(Number(state.user.labId), { id: Number(state.user.labId), name: `Lab ${state.user.labId}` });
  return Array.from(labs.values()).sort((a, b) => a.name.localeCompare(b.name));
}

function populatePlannerControls() {
  const labSelect = el("plannerLabId");
  const scenarioSelect = el("plannerScenarioSelect");
  const projectSelect = el("plannerProjectSelect");
  const selectedScenario = plannerScenarioById(state.selectedPlannerScenarioId);
  const labs = plannerLabs();
  const fallbackLabId = Number(selectedScenario?.lab_id || state.user?.labId || labs[0]?.id || 0);
  const currentLabId = Number(labSelect.value || fallbackLabId || 0);
  labSelect.innerHTML = labs.length
    ? labs.map((lab) => `<option value="${esc(lab.id)}">${esc(lab.name)} (ID ${esc(lab.id)})</option>`).join("")
    : `<option value="">No labs</option>`;
  if (currentLabId) labSelect.value = String(currentLabId);

  if (!state.selectedPlannerScenarioId && state.plannerScenarios.length) {
    state.selectedPlannerScenarioId = Number(state.plannerScenarios[0].id);
  }
  scenarioSelect.innerHTML = state.plannerScenarios.length
    ? state.plannerScenarios
        .map(
          (scenario) =>
            `<option value="${esc(scenario.id)}">${esc(scenario.name)} · ${esc(scenario.lab_name || `Lab ${scenario.lab_id}`)}</option>`
        )
        .join("")
    : `<option value="">No scenarios yet</option>`;
  if (state.selectedPlannerScenarioId) scenarioSelect.value = String(state.selectedPlannerScenarioId);

  const activeLabId = Number(plannerScenarioById(state.selectedPlannerScenarioId)?.lab_id || labSelect.value || 0);
  const visibleProjects = (state.projects || []).filter((project) => !activeLabId || Number(project.lab_id || 0) === activeLabId);
  projectSelect.innerHTML = visibleProjects.length
    ? visibleProjects
        .map((project) => `<option value="${esc(project.id)}">${esc(project.project_code)} · ${esc(project.title)}</option>`)
        .join("")
    : `<option value="">No projects available</option>`;

  if (!el("plannerNeededBy").value) {
    const due = new Date();
    due.setDate(due.getDate() + 21);
    el("plannerNeededBy").value = due.toISOString().slice(0, 10);
  }
}

function renderPlannerScenarios(scenarios) {
  const host = el("plannerScenarios");
  if (!scenarios.length) {
    host.innerHTML = `<p class="hint">No planner scenarios yet. Create one to estimate deficits and cage pressure.</p>`;
    return;
  }
  host.innerHTML = `
    <div class="planner-list">
      ${scenarios
        .map((scenario) => {
          const selected = Number(scenario.id) === Number(state.selectedPlannerScenarioId);
          return `
            <article class="planner-item">
              <div class="planner-item-head">
                <div>
                  <strong>${esc(scenario.name)}</strong>
                  <div class="learning-copy">${esc(scenario.lab_name || `Lab ${scenario.lab_id}`)} · target ${esc(scenario.target_animals)} by ${esc(
                    fmtDate(scenario.needed_by)
                  )}</div>
                </div>
                <span class="detail-pill">${esc(selected ? "selected" : scenario.status || "draft")}</span>
              </div>
              <div class="planner-meta">
                <span class="legend-item">Max new cages ${esc(scenario.max_new_cages || 0)}</span>
                <span class="legend-item">Status ${esc(scenario.status || "draft")}</span>
              </div>
              <div class="learning-actions">
                <button type="button" class="table-link" data-planner-scenario-id="${esc(scenario.id)}">Inspect Scenario</button>
                <button type="button" class="table-link" data-evaluate-planner-id="${esc(scenario.id)}">Evaluate</button>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPlannerInspector(detail, plans) {
  const host = el("plannerInspector");
  if (!detail?.scenario) {
    host.innerHTML = `<p class="hint">Select a scenario to review project demand, risk, and recent plans.</p>`;
    return;
  }
  const scenario = detail.scenario;
  const projects = detail.projects || [];
  const latestPlan = (plans || [])[0] || null;
  const recommendation = parseJsonField(latestPlan?.recommendation_json);
  const demandBars = latestPlan
    ? drawBars(
        [
          { label: "Target", value: recommendation.targetAnimals || scenario.target_animals || 0, color: "#4f8ef7" },
          { label: "Current", value: recommendation.currentActiveAnimals || 0, color: "#18a172" },
          { label: "Deficit", value: recommendation.projectedDeficit || latestPlan.projected_deficit || 0, color: "#ca513d" },
        ],
        { height: 120 }
      )
    : `<p class="hint">No evaluation yet. Run Evaluate Selected Scenario to generate a plan.</p>`;

  host.innerHTML = `
    <div class="detail-shell">
      <div class="detail-head">
        <h4>${esc(scenario.name)}</h4>
        <span class="alert-pill ${esc(plannerRiskClass(latestPlan?.risk_level || "low"))}">${esc((latestPlan?.risk_level || "draft").toUpperCase())}</span>
      </div>
      <div class="detail-grid">
        ${chartCard(
          "Scenario Demand",
          `${esc(scenario.lab_name || `Lab ${scenario.lab_id}`)} · needed by ${esc(fmtDate(scenario.needed_by))}`,
          demandBars,
          `<span class="legend-item">Target ${esc(scenario.target_animals || 0)}</span><span class="legend-item">Max new cages ${esc(
            scenario.max_new_cages || 0
          )}</span>`
        )}
        ${chartCard(
          "Latest Plan",
          latestPlan ? `Plan ${esc(latestPlan.id)} created ${esc(fmtDate(latestPlan.created_at))}` : "Awaiting evaluation",
          latestPlan
            ? `<div class="learning-pill-row">
                <span class="learning-pill ${esc(plannerRiskClass(latestPlan.risk_level))}">${esc(latestPlan.risk_level.toUpperCase())} risk</span>
                <span class="legend-item">Litters ${esc(latestPlan.estimated_litters)}</span>
                <span class="legend-item">Cages ${esc(latestPlan.estimated_cages)}</span>
                <span class="legend-item">Deficit ${esc(latestPlan.projected_deficit)}</span>
              </div>`
            : `<p class="learning-copy">Attach one or more projects and evaluate to estimate litter count, cages, and supply risk.</p>`,
          projects.length
            ? projects.map((project) => `<span class="legend-item">${esc(project.project_code)} need ${esc(project.animals_needed)}</span>`).join("")
            : `<span class="legend-item">No project demand attached yet</span>`
        )}
      </div>
      <div class="detail-grid">
        <article class="viz-card">
          <h4>Scenario Projects</h4>
          <table class="table compact-table">
            <thead><tr><th>Project</th><th>Title</th><th>Animals Needed</th><th>Priority</th></tr></thead>
            <tbody>
              ${
                projects
                  .map(
                    (project) => `<tr>
                      <td><button type="button" class="table-link" data-project-id="${esc(project.id)}">${esc(project.project_code)}</button></td>
                      <td>${esc(project.title)}</td>
                      <td>${esc(project.animals_needed)}</td>
                      <td>${esc(project.priority)}</td>
                    </tr>`
                  )
                  .join("") || `<tr><td colspan="4">No project demand attached.</td></tr>`
              }
            </tbody>
          </table>
        </article>
        <article class="viz-card">
          <h4>Plan History</h4>
          <div class="timeline-list">
            ${
              (plans || [])
                .slice(0, 6)
                .map(
                  (plan) =>
                    `<div class="timeline-item"><strong>Plan ${esc(plan.id)} · ${esc((plan.risk_level || "low").toUpperCase())}</strong><span>${esc(
                      fmtDate(plan.created_at)
                    )}</span></div>`
                )
                .join("") || `<div class="hint">No plan history yet.</div>`
            }
          </div>
        </article>
      </div>
    </div>
  `;
}

function renderRecommendationPanel(recommendations, outcomes) {
  const host = el("recommendationPanel");
  const outcomeBars = (outcomes || []).map((row) => ({
    label: `${row.rec_type}:${row.status}`.slice(0, 10),
    value: toNum(row.n || 0),
    color: row.status === "accepted" || row.status === "completed" ? "#18a172" : row.status === "ignored" ? "#64748b" : "#eb9c44",
  }));
  host.innerHTML = `
    <div class="detail-grid">
      <article class="viz-card">
        <h4>Open Recommendations</h4>
        <div class="recommendation-list">
          ${
            recommendations.length
              ? recommendations
                  .map(
                    (recommendation) => `
                      <div class="recommendation-item">
                        <div class="recommendation-item-head">
                          <div>
                            <strong>${esc(recommendation.rec_type)}</strong>
                            <div class="learning-copy">${esc(recommendation.rationale || "No rationale")}</div>
                          </div>
                          <span class="detail-pill">${esc(recommendation.status)}</span>
                        </div>
                        <div class="recommendation-meta">
                          <span class="legend-item">${esc(recommendation.cage_code || "facility-wide")}</span>
                          <span class="legend-item">${esc(fmtDate(recommendation.created_at))}</span>
                        </div>
                        ${
                          roleAllows(["PI", "Admin"])
                            ? `<div class="learning-actions">
                                <button type="button" class="table-link" data-recommendation-id="${esc(recommendation.id)}" data-recommendation-decision="accepted">Accept</button>
                                <button type="button" class="table-link" data-recommendation-id="${esc(recommendation.id)}" data-recommendation-decision="completed">Complete</button>
                                <button type="button" class="table-link" data-recommendation-id="${esc(recommendation.id)}" data-recommendation-decision="ignored">Ignore</button>
                              </div>`
                            : ``
                        }
                      </div>
                    `
                  )
                  .join("")
              : `<p class="hint">No open recommendations right now.</p>`
          }
        </div>
      </article>
      <article class="viz-card">
        <h4>Recommendation Outcomes</h4>
        ${
          outcomeBars.length
            ? `${drawBars(outcomeBars.slice(0, 10), { height: 130 })}<div class="viz-legend">${(outcomes || [])
                .map((row) => `<span class="legend-item">${esc(row.rec_type)} · ${esc(row.status)} ${esc(row.n)}</span>`)
                .join("")}</div>`
            : `<p class="hint">No recommendation outcomes recorded yet.</p>`
        }
      </article>
    </div>
  `;
}

function sampleSelected(sampleId) {
  return state.selectedSampleIds.includes(Number(sampleId));
}

function setSampleSelected(sampleId, selected) {
  const id = Number(sampleId);
  const next = new Set(state.selectedSampleIds.map(Number));
  if (selected) next.add(id);
  else next.delete(id);
  state.selectedSampleIds = Array.from(next.values());
  renderSampleSelectionBanner();
}

function renderSampleSelectionBanner() {
  const banner = el("sampleSelectionBanner");
  if (!banner) return;
  if (!state.selectedSampleIds.length) {
    banner.classList.add("hidden");
    banner.textContent = "";
    return;
  }
  banner.classList.remove("hidden");
  banner.textContent = `${state.selectedSampleIds.length} sample${state.selectedSampleIds.length > 1 ? "s" : ""} selected for genotyping order creation.`;
}

function renderWorkflowRail(steps, currentStep, completedSteps = []) {
  const active = String(currentStep || "").toLowerCase();
  const done = new Set((completedSteps || []).map((step) => String(step).toLowerCase()));
  const activeIndex = steps.findIndex((step) => String(step).toLowerCase() === active);
  return `<div class="workflow-rail">${steps
    .map((step, index) => {
      const key = String(step).toLowerCase();
      const isActive = key === active;
      const isDone = done.has(key) || (activeIndex >= index && activeIndex !== -1);
      const cls = isActive ? "active" : isDone ? "complete" : "pending";
      return `<div class="workflow-step ${cls}">
        <span>${index + 1}</span>
        <strong>${esc(step)}</strong>
      </div>`;
    })
    .join("")}</div>`;
}

function renderGenotypingOverview(dashboard) {
  const host = el("genotypingOverview");
  if (!host) return;
  if (!dashboard) {
    host.innerHTML = "";
    return;
  }
  const sampleParts = (dashboard.sampleStatus || []).map((row, idx) => ({
    label: row.label,
    value: row.value,
    color: ["#3b82f6", "#18a172", "#eb9c44", "#ca513d", "#64748b"][idx % 5],
  }));
  const orderBars = (dashboard.orderStatus || []).map((row, idx) => ({
    label: row.label,
    value: row.value,
    color: ["#18a172", "#3ba0d8", "#eb9c44", "#ca513d", "#64748b"][idx % 5],
  }));
  const providerBars = (dashboard.providers || []).map((row) => ({
    label: row.provider,
    value: row.pending,
    color: row.pending > 0 ? "#eb9c44" : "#18a172",
  }));
  const genotypeBars = (dashboard.genotypeDistribution || []).slice(0, 8).map((row, idx) => ({
    label: row.label,
    value: row.value,
    color: ["#0f7a58", "#3b82f6", "#eb9c44", "#ca513d", "#8b5cf6", "#14b8a6"][idx % 6],
  }));
  const turnaroundSeries = (dashboard.turnaround || []).map((row) => toNum(row.value));
  const recentRows = (dashboard.recentActivity || [])
    .map(
      (row) =>
        `<div class="timeline-item"><strong>${esc(row.ref_code || row.kind)}</strong><span>${esc(row.label)} · ${esc(fmtDate(row.happened_at))}</span></div>`
    )
    .join("");
  host.innerHTML = `
    <div class="detail-grid">
      ${chartCard(
        "Sample Chain Of Custody",
        "Where samples sit today",
        sampleParts.length ? drawDonut(sampleParts, { size: 168 }) : `<p class="hint">No samples recorded yet.</p>`,
        sampleParts.map((row) => `<span class="legend-item">${esc(row.label)} ${esc(row.value)}</span>`).join("")
      )}
      ${chartCard(
        "Order Flow",
        "Current order statuses",
        orderBars.length ? drawBars(orderBars, { height: 132 }) : `<p class="hint">No genotyping orders yet.</p>`,
        orderBars.map((row) => `<span class="legend-item">${esc(row.label)} ${esc(row.value)}</span>`).join("")
      )}
      ${chartCard(
        "Provider Load",
        "Pending items by provider",
        providerBars.length ? drawBars(providerBars, { height: 132 }) : `<p class="hint">No provider work queued.</p>`,
        (dashboard.providers || [])
          .map((row) => `<span class="legend-item">${esc(row.provider)} ${esc(row.pending)} pending / ${esc(row.resulted)} resulted</span>`)
          .join("")
      )}
      ${chartCard(
        "Genotype Distribution",
        "Observed animal genotype mix",
        genotypeBars.length ? drawBars(genotypeBars, { height: 132 }) : `<p class="hint">No genotype results recorded yet.</p>`,
        genotypeBars.map((row) => `<span class="legend-item">${esc(row.label)} ${esc(row.value)}</span>`).join("")
      )}
    </div>
    <div class="detail-grid">
      ${chartCard(
        "Turnaround Pressure",
        "Sample age buckets from collection date",
        drawSparkline(turnaroundSeries, "#0f7a58"),
        (dashboard.turnaround || []).map((row) => `<span class="legend-item">${esc(row.label)} ${esc(row.value)}</span>`).join("")
      )}
      <article class="viz-card">
        <h4>Recent Genotyping Activity</h4>
        <div class="timeline-list">${recentRows || `<div class="hint">No recent sample or order activity yet.</div>`}</div>
      </article>
    </div>
  `;
}

function applyProviderPreset(presetKey) {
  const preset = (state.providerPresets || []).find((row) => row.key === presetKey);
  if (!preset) return;
  el("sampleProvider").value = preset.sampleProvider || preset.name;
  el("orderProvider").value = preset.orderProvider || preset.name;
  if (preset.defaultSampleType && el("sampleType").querySelector(`option[value="${preset.defaultSampleType}"]`)) {
    el("sampleType").value = preset.defaultSampleType;
  }
  if (!el("orderMarkerPanel").value.trim() && preset.defaultMarkerPanel) {
    el("orderMarkerPanel").value = preset.defaultMarkerPanel;
  }
  if (!el("callbackMarkerPanel").value.trim() && preset.defaultMarkerPanel) {
    el("callbackMarkerPanel").value = preset.defaultMarkerPanel;
  }
  showMessage(`Applied ${preset.name} preset to the sample and order forms.`, "success");
}

function renderProviderPresets(presets) {
  const host = el("providerPresetList");
  if (!host) return;
  if (!presets?.length) {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = `
    <div class="detail-grid">
      ${presets
        .map(
          (preset) => `
            <article class="learning-card provider-preset-card">
              <div class="sample-item-head">
                <div>
                  <strong>${esc(preset.name)}</strong>
                  <div class="learning-copy">${esc(preset.notes || "Preset workflow")}</div>
                </div>
                <span class="detail-pill">${esc(preset.defaultSampleType || "sample")}</span>
              </div>
              <div class="sample-meta">
                <span class="legend-item">Panel ${esc(preset.defaultMarkerPanel || "custom")}</span>
                <span class="legend-item">${esc((preset.exportColumns || []).join(" · "))}</span>
              </div>
              <div class="learning-actions">
                <button type="button" class="table-link" data-provider-preset="${esc(preset.key)}">Apply To Forms</button>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function cohortAnimalSelected(animalId) {
  return state.selectedCohortAnimalIds.includes(Number(animalId));
}

function setCohortAnimalSelected(animalId, selected) {
  const id = Number(animalId);
  const next = new Set(state.selectedCohortAnimalIds.map(Number));
  if (selected) next.add(id);
  else next.delete(id);
  state.selectedCohortAnimalIds = Array.from(next.values());
}

function renderCohortInsights(insights) {
  const host = el("cohortInsights");
  if (!host) return;
  if (!insights) {
    host.innerHTML = "";
    return;
  }
  const canManageProjects = roleAllows(["PI", "Admin"]);
  const projects = insights.projects || [];
  if (!state.selectedCohortProjectId || !projects.some((row) => Number(row.id) === Number(state.selectedCohortProjectId))) {
    state.selectedCohortProjectId = projects.length ? Number(projects[0].id) : null;
  }
  const activeProject = projects.find((row) => Number(row.id) === Number(state.selectedCohortProjectId)) || null;
  const projectBars = (insights.projects || []).slice(0, 8).map((row) => ({
    label: row.projectCode,
    value: row.matchedReadyAnimals,
    color: row.assignmentPressure > 0 ? "#eb9c44" : "#18a172",
  }));
  const candidateAnimals = (insights.readyAnimals || []).filter((animal) =>
    activeProject
      ? (animal.matchingProjects || []).some((project) => Number(project.id) === Number(activeProject.id)) ||
        Number(animal.assignment?.project_id || 0) === Number(activeProject.id)
      : true
  );
  const readyAnimals = candidateAnimals
    .slice(0, 8)
    .map(
      (animal) => `<div class="timeline-item">
        <strong><button type="button" class="table-link" data-sample-animal-id="${esc(animal.id)}">${esc(animal.animalCode)}</button></strong>
        <span><button type="button" class="table-link" data-sample-cage-id="${esc(animal.cageId)}">${esc(animal.cageCode)}</button> · ${esc(
          animal.genotype
        )} · ${
          animal.matchingProjects?.length ? esc(animal.matchingProjects.map((project) => project.projectCode).join(", ")) : "no match"
        }${animal.assignment ? ` · reserved to ${esc(animal.assignment.project_code)}` : ""}</span>
        <span class="timeline-actions">
          <button type="button" class="table-link" data-cohort-animal-toggle="${esc(animal.id)}">${
            cohortAnimalSelected(animal.id) ? "Deselect" : "Select"
          }</button>
        </span>
      </div>`
    )
    .join("");
  const breederSignals = (insights.breederSignals || [])
    .slice(0, 6)
    .map(
      (row) => `<article class="sample-item">
        <div class="sample-item-head">
          <div>
            <strong><button type="button" class="table-link" data-sample-cage-id="${esc(row.cageId || "")}">${esc(row.cageCode)}</button></strong>
            <div class="learning-copy">${esc(row.sireCode)} × ${esc(row.damCode)}</div>
          </div>
          <span class="detail-pill">${esc(row.signal)}</span>
        </div>
        <div class="sample-meta">
          <span class="legend-item">${esc(row.readyAnimals)} ready</span>
          <span class="legend-item">${esc(row.litterCount)} litters</span>
          <span class="legend-item">avg survived ${esc(row.avgSurvived)}</span>
        </div>
        <p class="learning-copy">${esc(row.note)}</p>
      </article>`
    )
    .join("");
  const targetRules = (activeProject?.targetRules || [])
    .map(
      (rule) => `<div class="timeline-item">
        <strong>${esc(rule.genotypePattern)}</strong>
        <span>${esc(rule.targetCount)} animals · priority ${esc(rule.priority)}</span>
        <span class="timeline-actions"><button type="button" class="table-link" data-target-remove-id="${esc(rule.id)}">Remove</button></span>
      </div>`
    )
    .join("");
  host.innerHTML = `
    <div class="detail-grid">
      ${chartCard(
        "Project Cohort Readiness",
        `${esc(insights.unassignedReadyCount || 0)} genotype-ready animals are still unassigned`,
        projectBars.length ? drawBars(projectBars, { height: 132 }) : `<p class="hint">No active project cohorts are visible yet.</p>`,
        (insights.projects || [])
          .slice(0, 8)
          .map(
            (row) =>
              `<span class="legend-item">${esc(row.projectCode)} ${esc(row.matchedReadyAnimals)} match / ${esc(row.reservedAnimals)} reserved / ${esc(
                row.targetAnimals
              )} target</span>`
          )
          .join("")
      )}
      <article class="viz-card">
        <h4>Assignment Candidates</h4>
        <div class="timeline-list">${readyAnimals || `<div class="hint">No genotype-ready animals are visible yet.</div>`}</div>
      </article>
    </div>
    <div class="detail-grid">
      <article class="viz-card">
        <h4>Breeder Decisions</h4>
        <div class="sample-list">${breederSignals || `<p class="hint">No breeder signals are available yet.</p>`}</div>
      </article>
      <article class="viz-card">
        <h4>Assignment Pressure</h4>
        <div class="grid-form compact-form cohort-toolbar">
          <label>Project
            <select id="cohortProjectSelect">
              ${
                projects.length
                  ? projects
                      .map(
                        (row) =>
                          `<option value="${esc(row.id)}" ${Number(row.id) === Number(state.selectedCohortProjectId) ? "selected" : ""}>${esc(
                            row.projectCode
                          )} · ${esc(row.title)}</option>`
                      )
                      .join("")
                  : `<option value="">No projects available</option>`
              }
            </select>
          </label>
          <label>Genotype Target<input id="cohortTargetPattern" placeholder="e.g., Cre/+ or fl/*" /></label>
          <label>Target Count<input id="cohortTargetCount" type="number" min="0" value="4" /></label>
          <div class="learning-actions">
            <button type="button" id="saveCohortTargetBtn" ${canManageProjects ? "" : "disabled title='Requires PI/Admin role'"}>Add Target Rule</button>
            <button type="button" id="reserveCohortAnimalsBtn" ${canManageProjects ? "" : "disabled title='Requires PI/Admin role'"}>Reserve Selected</button>
            <button type="button" id="releaseCohortAnimalsBtn" ${canManageProjects ? "" : "disabled title='Requires PI/Admin role'"}>Release Selected</button>
          </div>
        </div>
        ${
          activeProject
            ? `<div class="learning-copy">Selected project: ${esc(activeProject.projectCode)} · matched ${esc(
                activeProject.matchedReadyAnimals
              )} · reserved ${esc(activeProject.reservedAnimals)} · deficit ${esc(activeProject.assignmentPressure)} · selected ${
                state.selectedCohortAnimalIds.length
              }</div>`
            : `<p class="hint">No project selected.</p>`
        }
        <div class="timeline-list">${targetRules || `<div class="hint">No genotype target rules yet. Add one above or rely on broad target count only.</div>`}</div>
        <div class="timeline-list">
          ${
            (insights.projects || [])
              .slice(0, 8)
              .map(
                (row) => `<div class="timeline-item"><strong><button type="button" class="table-link" data-project-id="${esc(row.id)}">${esc(
                  row.projectCode
                )}</button></strong><span>${esc(row.recommendedAction)} · deficit ${esc(
                  row.assignmentPressure
                )} · reserved ${esc(row.reservedAnimals)}</span></div>`
              )
              .join("") || `<div class="hint">No project demand context is visible yet.</div>`
          }
        </div>
      </article>
    </div>
  `;
}

function renderReconciliationInspector(reconciliation) {
  const host = el("reconciliationInspector");
  if (!host) return;
  if (!reconciliation?.summary) {
    host.innerHTML = "";
    return;
  }
  const summary = reconciliation.summary;
  const bars = [
    { label: "done", value: summary.resultedItems, color: "#18a172" },
    { label: "missing", value: summary.missingResultItems, color: "#ca513d" },
    { label: "provider", value: summary.withProviderItems, color: "#3b82f6" },
    { label: "transit", value: summary.inTransitItems, color: "#eb9c44" },
    { label: "ready", value: summary.readyToShipItems, color: "#64748b" },
    { label: "blocked", value: summary.blockedItems, color: "#8b5cf6" },
  ];
  const items = reconciliation.items || [];
  host.innerHTML = `
    <article class="viz-card">
      <h4>Order Reconciliation</h4>
      <div class="viz-sub">Expected ${esc(summary.expectedItems)} items · ${esc(summary.completionPct)}% completed</div>
      ${drawBars(bars, { height: 132 })}
      <div class="viz-legend">
        <span class="legend-item">Resulted ${esc(summary.resultedItems)}</span>
        <span class="legend-item">Missing ${esc(summary.missingResultItems)}</span>
        <span class="legend-item">With Provider ${esc(summary.withProviderItems)}</span>
        <span class="legend-item">In Transit ${esc(summary.inTransitItems)}</span>
        <span class="legend-item">Ready ${esc(summary.readyToShipItems)}</span>
        <span class="legend-item">Blocked ${esc(summary.blockedItems)}</span>
      </div>
      <div class="timeline-list reconciliation-list">
        ${
          items.length
            ? items
                .slice(0, 8)
                .map(
                  (item) => `<div class="timeline-item">
                    <strong>${esc(item.sample_code || `#${item.sample_id}`)}</strong>
                    <span>${esc(item.workflowState)} · ${esc(item.result || item.sample_status || "pending")}</span>
                  </div>`
                )
                .join("")
            : `<div class="hint">No items in this order yet.</div>`
        }
      </div>
    </article>
  `;
}

function downloadProviderTemplate(orderId) {
  const activeId = Number(orderId || state.selectedGenotypingOrderId || 0);
  if (!activeId) {
    showMessage("Select a genotyping order first.", "warn");
    return;
  }
  window.open(`/api/genotyping/orders/${activeId}/provider-template.csv`, "_blank", "noopener");
}

function populateOrderControls() {
  const projectSelect = el("orderProjectSelect");
  const orderSelect = el("callbackOrderSelect");
  const importSelect = el("importOrderSelect");
  const projects = state.projects || [];
  projectSelect.innerHTML =
    `<option value="">No project / lab-level order</option>` +
    projects
      .map((project) => `<option value="${esc(project.id)}">${esc(project.project_code)} · ${esc(project.title)}</option>`)
      .join("");
  orderSelect.innerHTML = state.genotypingOrders.length
    ? state.genotypingOrders
        .map((order) => `<option value="${esc(order.id)}">${esc(order.order_ref)} · ${esc(order.status)} · ${esc(order.provider)}</option>`)
        .join("")
    : `<option value="">No orders available</option>`;
  importSelect.innerHTML = orderSelect.innerHTML;
  if (!state.selectedGenotypingOrderId && state.genotypingOrders.length) {
    state.selectedGenotypingOrderId = Number(state.genotypingOrders[0].id);
  }
  if (state.selectedGenotypingOrderId) {
    orderSelect.value = String(state.selectedGenotypingOrderId);
    importSelect.value = String(state.selectedGenotypingOrderId);
  }
}

function renderSampleList(samples) {
  const host = el("sampleList");
  if (!samples.length) {
    host.innerHTML = `<p class="hint">No samples yet. Create one from an animal code to start chain-of-custody tracking.</p>`;
    renderSampleSelectionBanner();
    return;
  }
  host.innerHTML = `
    <div class="sample-list">
      ${samples
        .map(
          (sample) => `
            <article class="sample-item">
              <div class="sample-item-head">
                <div>
                  <strong>${esc(sample.sample_code)}</strong>
                  <div class="learning-copy">${esc(sample.sample_type)} · ${esc(sample.provider || "provider not set")} · animal ${esc(
                    sample.animal_code
                  )}</div>
                </div>
                <span class="alert-pill ${esc(sample.status === "rejected" ? "high" : sample.status === "resulted" ? "low" : "medium")}">${esc(
                  sample.status
                )}</span>
              </div>
              <div class="sample-meta">
                <span class="legend-item">Collected ${esc(fmtDate(sample.collected_on))}</span>
                <span class="legend-item">Cage ${esc(sample.cage_code || "N/A")}</span>
                <span class="legend-item">Tracking ${esc(sample.tracking_number || "pending")}</span>
              </div>
              <div class="learning-actions">
                <button type="button" class="table-link" data-sample-id="${esc(sample.id)}">Inspect</button>
                <button type="button" class="table-link" data-sample-toggle="${esc(sample.id)}">${sampleSelected(sample.id) ? "Deselect" : "Select For Order"}</button>
                <button type="button" class="table-link" data-sample-cage-id="${esc(sample.cage_id)}">Open Cage</button>
                <button type="button" class="table-link" data-sample-animal-id="${esc(sample.animal_id)}">Open Pedigree</button>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
  renderSampleSelectionBanner();
}

function renderSampleInspector(sample, events = [], genotypes = []) {
  const host = el("sampleInspector");
  if (!sample) {
    host.innerHTML = "";
    return;
  }
  const workflow = renderWorkflowRail(["Collected", "Shipped", "Received", "Resulted"], sample.status);
  const eventBars = drawBars(
    events.map((event, idx) => ({
      label: `${idx + 1}`.padStart(2, "0"),
      value: idx + 1,
      color: event.event_type === "resulted" ? "#18a172" : event.event_type === "rejected" ? "#ca513d" : "#4f8ef7",
    })),
    { height: 110 }
  );
  host.innerHTML = `
    <div class="detail-shell">
      <div class="detail-head">
        <h4>${esc(sample.sample_code)}</h4>
        <span class="detail-pill">${esc(sample.status)}</span>
      </div>
      ${workflow}
      <div class="detail-grid">
        ${chartCard(
          "Sample Timeline",
          `${esc(sample.sample_type)} · ${esc(sample.provider || "provider not set")}`,
          events.length ? eventBars : `<p class="hint">No sample events yet.</p>`,
          events.map((event) => `<span class="legend-item">${esc(event.event_type)} ${esc(fmtDate(event.event_time))}</span>`).join("")
        )}
        ${chartCard(
          "Genotype History",
          `Animal ${esc(sample.animal_code)}`,
          genotypes.length
            ? `<div class="timeline-list">${genotypes
                .slice(0, 6)
                .map((row) => `<div class="timeline-item"><strong>${esc(row.result)}</strong><span>${esc(fmtDate(row.created_at))}</span></div>`)
                .join("")}</div>`
            : `<p class="hint">No genotype results recorded yet for this animal.</p>`,
          genotypes.map((row) => `<span class="legend-item">${esc(row.source)} ${esc(row.result)}</span>`).join("")
        )}
      </div>
      <div class="detail-grid">
        <article class="viz-card">
          <h4>Event History</h4>
          <div class="timeline-list">
            ${
              events
                .map(
                  (event) =>
                    `<div class="timeline-item"><strong>${esc(event.event_type)}</strong><span>${esc(fmtDate(event.event_time))}</span></div>`
                )
                .join("") || `<div class="hint">No events yet.</div>`
            }
          </div>
        </article>
        <article class="viz-card">
          <h4>Quick Actions</h4>
          <div class="learning-actions">
            <button type="button" class="table-link" data-sample-update-id="${esc(sample.id)}" data-sample-next-status="shipped">Mark Shipped</button>
            <button type="button" class="table-link" data-sample-update-id="${esc(sample.id)}" data-sample-next-status="received">Mark Received</button>
            <button type="button" class="table-link" data-sample-update-id="${esc(sample.id)}" data-sample-next-status="resulted">Mark Resulted</button>
            <button type="button" class="table-link" data-sample-animal-id="${esc(sample.animal_id)}">Open Pedigree</button>
          </div>
          <p class="learning-copy">Use these to move the sample through the chain-of-custody while keeping the timeline and genotype history visible.</p>
        </article>
      </div>
    </div>
  `;
}

function renderOrderList(orders) {
  const host = el("orderList");
  if (!orders.length) {
    host.innerHTML = `<p class="hint">No genotyping orders yet. Select one or more samples and create an order.</p>`;
    return;
  }
  host.innerHTML = `
    <div class="order-list">
      ${orders
        .map(
          (order) => `
            <article class="order-item">
              <div class="order-item-head">
                <div>
                  <strong>${esc(order.order_ref)}</strong>
                  <div class="learning-copy">${esc(order.provider)} · ${esc(order.item_count)} items · ${esc(order.resulted_count || 0)} resulted</div>
                </div>
                <span class="detail-pill">${esc(order.status)}</span>
              </div>
              <div class="order-meta">
                <span class="legend-item">Created ${esc(fmtDate(order.created_at))}</span>
                <span class="legend-item">Updated ${esc(fmtDate(order.updated_at))}</span>
              </div>
              <div class="learning-actions">
                <button type="button" class="table-link" data-order-id="${esc(order.id)}">Inspect Order</button>
                ${
                  order.status === "draft"
                    ? `<button type="button" class="table-link" data-submit-order-id="${esc(order.id)}">Submit Order</button>`
                    : ``
                }
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderOrderInspector(detail) {
  const host = el("orderInspector");
  if (!detail?.order) {
    host.innerHTML = "";
    renderReconciliationInspector(null);
    return;
  }
  const order = detail.order;
  const items = detail.items || [];
  const reconciliation = detail.reconciliation || null;
  const orderRail = renderWorkflowRail(
    ["Draft", "Submitted", "Received", "Closed"],
    order.status,
    order.status === "failed" ? [] : order.status === "closed" ? ["draft", "submitted", "received", "closed"] : []
  );
  const resultBars = drawBars(
    [
      { label: "Items", value: items.length, color: "#4f8ef7" },
      { label: "Resulted", value: items.filter((item) => item.result).length, color: "#18a172" },
    ],
    { height: 110 }
  );
  host.innerHTML = `
    <div class="detail-shell">
      <div class="detail-head">
        <h4>${esc(order.order_ref)}</h4>
        <span class="detail-pill">${esc(order.status)}</span>
      </div>
      ${orderRail}
      <div class="detail-grid">
        ${chartCard(
          "Order Throughput",
          `${esc(order.provider)} · ${esc(order.lab_name || "Lab")}${order.project_code ? ` · ${esc(order.project_code)}` : ""}`,
          resultBars,
          `<span class="legend-item">${esc(items.length)} items</span><span class="legend-item">${esc(
            items.filter((item) => item.result).length
          )} resulted</span>`
        )}
        ${chartCard(
          "Provider Handoff",
          "Export CSV or post results back into this order",
          `<div class="learning-actions">
             <button type="button" class="table-link" data-order-template-id="${esc(order.id)}">Download Provider CSV</button>
             ${
               order.status === "draft"
                 ? `<button type="button" class="table-link" data-submit-order-id="${esc(order.id)}">Submit Order</button>`
                 : ``
             }
           </div>
           <p class="learning-copy">Current status: ${esc(order.status)}. Use callback simulation for seeded demos, or import a provider CSV to reconcile real-style results against this order.</p>`,
          `<span class="legend-item">Updated ${esc(fmtDate(order.updated_at))}</span><span class="legend-item">${
            reconciliation?.summary ? `${esc(reconciliation.summary.completionPct)}% complete` : "No reconciliation yet"
          }</span>`
        )}
      </div>
      <article class="viz-card">
        <h4>Order Items</h4>
        <table class="table compact-table">
          <thead><tr><th>Sample</th><th>Animal</th><th>Marker Panel</th><th>Result</th><th>Resulted At</th></tr></thead>
          <tbody>
            ${
              items
                .map(
                  (item) => `<tr>
                    <td><button type="button" class="table-link" data-sample-id="${esc(item.sample_id)}">${esc(item.sample_code || `#${item.sample_id}`)}</button></td>
                    <td><button type="button" class="table-link" data-sample-animal-id="${esc(item.animal_id)}">${esc(item.animal_code || `#${item.animal_id}`)}</button></td>
                    <td>${esc(item.marker_panel || "N/A")}</td>
                    <td>${esc(item.result || "Pending")}</td>
                    <td>${esc(fmtDate(item.result_at))}</td>
                  </tr>`
                )
                .join("") || `<tr><td colspan="5">No items in this order.</td></tr>`
            }
          </tbody>
        </table>
      </article>
    </div>
  `;
  renderReconciliationInspector(reconciliation);
}

function renderGenotypeAnalytics(mendelian, alerts) {
  const host = el("genotypeAnalytics");
  const alertBars = (alerts || []).map((row) => ({
    label: row.cageCode || `L${row.litterId}`,
    value: Math.round(toNum(row.maxDeviation || 0) * 100),
    color: "#ca513d",
  }));
  const mendelianCards = (mendelian || [])
    .slice(0, 6)
    .map((row) => {
      const observed = row.observed || {};
      return `
        <article class="sample-item">
          <div class="sample-item-head">
            <div>
              <strong>${esc(row.cageCode || `Litter ${row.litterId}`)}</strong>
              <div class="learning-copy">Born ${esc(fmtDate(row.birthDate))} · ${esc(row.totalGenotyped)} genotyped</div>
            </div>
            <span class="detail-pill">ratio</span>
          </div>
          <div class="sample-meta">
            ${Object.entries(observed)
              .map(([key, value]) => `<span class="legend-item">${esc(key)} ${esc(value)}</span>`)
              .join("")}
          </div>
        </article>
      `;
    })
    .join("");
  host.innerHTML = `
    <div class="detail-grid">
      <article class="viz-card">
        <h4>Mendelian Tracking</h4>
        ${
          mendelian.length
            ? `<div class="sample-list">${mendelianCards}</div>`
            : `<p class="hint">No genotyped litters available yet.</p>`
        }
      </article>
      <article class="viz-card">
        <h4>Genotype Alerts</h4>
        ${
          alerts.length
            ? `${drawBars(alertBars.slice(0, 10), { height: 130 })}<div class="viz-legend">${alerts
                .slice(0, 8)
                .map((row) => `<span class="legend-item">${esc(row.cageCode || `L${row.litterId}`)} dev ${Math.round(
                    toNum(row.maxDeviation || 0) * 100
                  )}%</span>`)
                .join("")}</div>`
            : `<p class="hint">No genotype-deviation alerts at the current threshold.</p>`
        }
      </article>
    </div>
  `;
}

async function resolveAnimalCode(animalCode) {
  const rows = await api(`/api/animals?q=${encodeURIComponent(animalCode)}`, { headers: headers(false) });
  const exact = rows.find((row) => String(row.animal_code).toLowerCase() === String(animalCode).trim().toLowerCase());
  return exact || rows[0] || null;
}

async function inspectSample(sampleId) {
  const sample = state.samples.find((row) => Number(row.id) === Number(sampleId));
  if (!sample) {
    renderSampleInspector(null, [], []);
    return;
  }
  const [events, genotypes] = await Promise.all([
    api(`/api/samples/${sampleId}/events`, { headers: headers(false) }),
    api(`/api/animals/${sample.animal_id}/genotypes`, { headers: headers(false) }),
  ]);
  renderSampleInspector(sample, events, genotypes);
}

async function inspectGenotypingOrder(orderId) {
  if (!orderId) {
    renderOrderInspector(null);
    return;
  }
  state.selectedGenotypingOrderId = Number(orderId);
  populateOrderControls();
  const detail = await api(`/api/genotyping/orders/${orderId}`, { headers: headers(false) });
  renderOrderInspector(detail);
}

async function loadSampleWorkspace() {
  if (!state.projects.length) {
    try {
      await loadProjects();
    } catch {
      state.projects = [];
    }
  }
  const [samples, orders, mendelian, alerts, dashboard, presets, cohorts] = await Promise.all([
    api("/api/samples", { headers: headers(false) }),
    api("/api/genotyping/orders", { headers: headers(false) }),
    api("/api/genotyping/mendelian", { headers: headers(false) }),
    api("/api/genotyping/alerts?threshold=0.1", { headers: headers(false) }),
    api("/api/genotyping/dashboard", { headers: headers(false) }),
    api("/api/genotyping/providers", { headers: headers(false) }),
    api("/api/genotyping/cohorts", { headers: headers(false) }),
  ]);
  state.samples = samples;
  state.genotypingOrders = orders;
  state.genotypingDashboard = dashboard;
  state.providerPresets = presets;
  state.cohortInsights = cohorts;
  state.selectedSampleIds = state.selectedSampleIds.filter((id) => samples.some((row) => Number(row.id) === Number(id)));
  state.selectedCohortAnimalIds = state.selectedCohortAnimalIds.filter((id) =>
    (cohorts.readyAnimals || []).some((row) => Number(row.id) === Number(id))
  );
  if (!state.selectedGenotypingOrderId || !orders.some((row) => Number(row.id) === Number(state.selectedGenotypingOrderId))) {
    state.selectedGenotypingOrderId = orders.length ? Number(orders[0].id) : null;
  }
  populateOrderControls();
  renderProviderPresets(presets);
  renderGenotypingOverview(dashboard);
  renderSampleList(samples);
  renderOrderList(orders);
  renderGenotypeAnalytics(mendelian, alerts);
  renderCohortInsights(cohorts);
  if (samples.length) await inspectSample(samples[0].id);
  else renderSampleInspector(null, [], []);
  if (state.selectedGenotypingOrderId) await inspectGenotypingOrder(state.selectedGenotypingOrderId);
  else renderOrderInspector(null);
}

async function loadPlannerScenarioInspector(scenarioId) {
  if (!scenarioId) {
    renderPlannerInspector(null, []);
    return;
  }
  state.selectedPlannerScenarioId = Number(scenarioId);
  populatePlannerControls();
  renderPlannerScenarios(state.plannerScenarios);
  const [detail, plans] = await Promise.all([
    api(`/api/planner/scenarios/${scenarioId}`, { headers: headers(false) }),
    api(`/api/planner/scenarios/${scenarioId}/plans`, { headers: headers(false) }),
  ]);
  renderPlannerInspector(detail, plans);
}

async function loadPlannerWorkspace() {
  if (!state.projects.length) {
    try {
      await loadProjects();
    } catch {
      state.projects = [];
    }
  }
  const [scenarios, recommendations, outcomes] = await Promise.all([
    api("/api/planner/scenarios", { headers: headers(false) }),
    api("/api/recommendations?status=open", { headers: headers(false) }),
    api("/api/recommendations/outcomes", { headers: headers(false) }),
  ]);
  state.plannerScenarios = scenarios;
  if (!state.selectedPlannerScenarioId || !plannerScenarioById(state.selectedPlannerScenarioId)) {
    state.selectedPlannerScenarioId = scenarios.length ? Number(scenarios[0].id) : null;
  }
  populatePlannerControls();
  renderPlannerScenarios(scenarios);
  renderRecommendationPanel(recommendations, outcomes);
  await loadPlannerScenarioInspector(state.selectedPlannerScenarioId);
}

async function evaluatePlannerScenario(scenarioId) {
  const activeId = Number(scenarioId || state.selectedPlannerScenarioId || 0);
  if (!activeId) {
    showMessage("Select or create a planner scenario first.", "warn");
    return;
  }
  const result = await api(`/api/planner/scenarios/${activeId}/evaluate`, {
    method: "POST",
    headers: headers(),
  });
  await loadPlannerWorkspace();
  showMessage(`Planner evaluated. deficit=${result.projectedDeficit}, risk=${result.riskLevel}.`, "success");
}

function renderBreedingVisuals(events, productivity = []) {
  const eventMap = {};
  for (const e of events.slice(0, 40)) {
    const d = (e.event_date || "").slice(5);
    eventMap[d] = (eventMap[d] || 0) + 1;
  }
  const eventBars = Object.entries(eventMap).map(([label, value]) => ({ label, value, color: "#18a172" }));
  const prodBars = productivity.slice(0, 12).map((p) => ({ label: p.cage_code, value: toNum(p.litter_count), color: "#6c8cf4" }));
  const survSeries = productivity.slice(0, 20).map((p) => toNum(p.avg_survived));
  const legendA = eventBars.map((e) => `<span class="legend-item">${esc(e.label)} ${esc(e.value)}</span>`).join("");
  const legendB = `<span class="legend-item">Top cages by litter count</span><span class="legend-item">avg survived trend</span>`;
  el("breedingVisuals").innerHTML = [
    chartCard("Event Timeline Density", "Upcoming breeding events", drawBars(eventBars.slice(0, 12), { height: 130 }), legendA),
    chartCard("Breeder Productivity", "Litter count and survivor trend", `${drawBars(prodBars, { height: 130 })}${drawSparkline(survSeries, "#6c8cf4")}`, legendB),
  ].join("");
}

function renderComplianceVisuals(alerts, protocolAlerts = []) {
  const bySeverity = { high: 0, medium: 0, low: 0 };
  const byCategory = {};
  for (const a of alerts) {
    bySeverity[a.severity] = (bySeverity[a.severity] || 0) + 1;
    byCategory[a.category] = (byCategory[a.category] || 0) + 1;
  }
  const sevBars = Object.entries(bySeverity).map(([label, value]) => ({
    label,
    value,
    color: label === "high" ? "#ca513d" : label === "medium" ? "#eb9c44" : "#18a172",
  }));
  const catParts = Object.entries(byCategory).map(([label, value], i) => ({
    label,
    value,
    color: ["#4f8ef7", "#18a172", "#eb9c44", "#ca513d", "#7c6cf2"][i % 5],
  }));
  const protocolBars = protocolAlerts.slice(0, 10).map((p) => ({
    label: p.protocol_number,
    value: Math.max(1, Math.round(toNum((new Date(p.expires_on).getTime() - Date.now()) / 86400000))),
    color: "#ca513d",
  }));
  const legendS = sevBars.map((s) => `<span class="legend-item">${esc(s.label)} ${esc(s.value)}</span>`).join("");
  const legendC = catParts.length
    ? catParts.map((c) => `<span class="legend-item">${esc(c.label)} ${esc(c.value)}</span>`).join("")
    : `<span class="legend-item">No active categories</span>`;
  const legendP = protocolAlerts.length
    ? `<span class="legend-item">${protocolAlerts.length} protocols near expiration</span>`
    : `<span class="legend-item">No protocol expiry alerts</span>`;
  el("complianceVisuals").innerHTML = [
    chartCard("Alert Severity Stack", "Current active alert pressure", drawBars(sevBars, { height: 120 }), legendS),
    chartCard("Alert Category Mix", "Where irregularities concentrate", drawDonut(catParts.length ? catParts : [{ label: "none", value: 1, color: "#d0dde0" }]), legendC),
    chartCard("Protocol Expiration Watch", "Protocol urgency by days remaining", drawBars(protocolBars, { height: 120 }), legendP),
  ].join("");
}

function renderDashboardVisuals(summary, alerts, reminders, quotas) {
  const sevCounts = { high: 0, medium: 0, low: 0 };
  for (const a of alerts) sevCounts[a.severity] = (sevCounts[a.severity] || 0) + 1;
  const sevBars = Object.entries(sevCounts).map(([label, value]) => ({
    label,
    value,
    color: label === "high" ? "#ca513d" : label === "medium" ? "#eb9c44" : "#18a172",
  }));

  const taskBins = {};
  for (const t of reminders.slice(0, 30)) {
    const d = String(t.event_date || t.due_on || "").slice(5, 10);
    if (!d) continue;
    taskBins[d] = (taskBins[d] || 0) + 1;
  }
  const taskBars = Object.entries(taskBins).map(([label, value]) => ({ label, value, color: "#4f8ef7" }));
  const quotaBars = quotas.slice(0, 10).map((q) => ({
    label: q.labName,
    value: toNum(q.utilizationPct || 0),
    color: toNum(q.utilizationPct || 0) > 100 ? "#ca513d" : "#18a172",
  }));

  const sexParts = [
    { label: "Male", value: toNum(summary.sexRatio?.M || 0), color: "#3ba0d8" },
    { label: "Female", value: toNum(summary.sexRatio?.F || 0), color: "#e6739f" },
  ];

  el("dashboardVisuals").innerHTML = [
    chartCard("Alert Pressure", "Current active alert severities", drawBars(sevBars, { height: 120 }), sevBars.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("")),
    chartCard("Task Queue", "Near-term reminders by day", `${drawBars(taskBars, { height: 120 })}${drawSparkline(taskBars.map((x) => x.value), "#4f8ef7")}`, taskBars.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("")),
    chartCard("Lab Utilization", "Quota utilization by lab", drawBars(quotaBars, { height: 120 }), quotaBars.map((r) => `<span class="legend-item">${esc(r.label)} ${toNum(r.value).toFixed(0)}%</span>`).join("")),
    chartCard("Population Balance", "Active sex ratio", drawDonut(sexParts), sexParts.map((r) => `<span class="legend-item">${esc(r.label)} ${esc(r.value)}</span>`).join("")),
  ].join("");
}

function learningPill(label, ready) {
  return `<span class="learning-pill ${ready ? "ready" : "pending"}">${esc(label)} ${ready ? "ready" : "pending"}</span>`;
}

function renderLearningHub(overview) {
  const host = el("dashboardLearning");
  if (!host) return;
  if (!overview) {
    host.innerHTML = "";
    return;
  }
  state.learning = overview;
  const counts = overview.counts || {};
  const availability = overview.workflowAvailability || {};
  const scanBase = normalizedScanBase();
  const phoneReady = !(scanBase.includes("localhost") || scanBase.includes("127.0.0.1"));
  const examples = overview.examples || {};
  const modules = overview.modules || [];
  const completed = modules.filter((module) => moduleComplete(module.id)).length;
  const nextModule = modules.find((module) => !moduleComplete(module.id)) || modules[0];
  const progressPct = modules.length ? Math.round((completed * 100) / modules.length) : 0;

  const exampleCards = [];
  if (examples.cage) {
    exampleCards.push(`
      <article class="learning-example">
        <div class="learning-example-title">Practice cage</div>
        <strong>${esc(examples.cage.cage_code)}</strong>
        <div class="learning-copy">${esc(examples.cage.strain || "Cage example")} · ${esc(examples.cage.breeding_status || "status unknown")}</div>
        <div class="learning-actions">
          <button type="button" class="table-link" data-learning-cage-id="${esc(examples.cage.id)}">Open Cage</button>
          <button type="button" class="table-link" data-learning-scan-code="${esc(examples.cage.cage_code)}">Open In Scan/Edit</button>
        </div>
      </article>
    `);
  }
  if (examples.project) {
    exampleCards.push(`
      <article class="learning-example">
        <div class="learning-example-title">Project example</div>
        <strong>${esc(examples.project.project_code)}</strong>
        <div class="learning-copy">${esc(examples.project.title || "Project")} · ${esc(examples.project.status || "status unknown")}</div>
        <div class="learning-actions">
          <button type="button" class="table-link" data-learning-project-id="${esc(examples.project.id)}">Open Project</button>
          <button type="button" class="table-link" data-learning-tab="projects">Project Workspace</button>
        </div>
      </article>
    `);
  }
  if (examples.pedigreeAnimal) {
    exampleCards.push(`
      <article class="learning-example">
        <div class="learning-example-title">Pedigree example</div>
        <strong>${esc(examples.pedigreeAnimal.animal_code)}</strong>
        <div class="learning-copy">From cage ${esc(examples.pedigreeAnimal.cage_code || "N/A")}</div>
        <div class="learning-actions">
          <button type="button" class="table-link" data-learning-animal-id="${esc(examples.pedigreeAnimal.id)}">Open Pedigree</button>
          <button type="button" class="table-link" data-learning-tab="scan">Pedigree Workspace</button>
        </div>
      </article>
    `);
  }
  if (examples.sample) {
    exampleCards.push(`
      <article class="learning-example">
        <div class="learning-example-title">Sample chain-of-custody</div>
        <strong>${esc(examples.sample.sample_code)}</strong>
        <div class="learning-copy">${esc(examples.sample.status || "status unknown")} · animal ${esc(examples.sample.animal_code || "N/A")}</div>
        <div class="learning-actions">
          <a class="button-link button-link-soft" href="${esc(overview.tutorialUrl)}" target="_blank" rel="noopener">Read Sample Module</a>
        </div>
      </article>
    `);
  }
  if (examples.plannerScenario) {
    exampleCards.push(`
      <article class="learning-example">
        <div class="learning-example-title">Planner scenario</div>
        <strong>${esc(examples.plannerScenario.name)}</strong>
        <div class="learning-copy">${esc(examples.plannerScenario.lab_name || "Lab")} · ${esc(examples.plannerScenario.status || "status unknown")}</div>
        <div class="learning-actions">
          <button type="button" class="table-link" data-learning-tab="analytics">Open Analytics</button>
          <a class="button-link button-link-soft" href="${esc(overview.tutorialUrl)}" target="_blank" rel="noopener">Read Planner Module</a>
        </div>
      </article>
    `);
  }

  host.innerHTML = `
    <section class="learning-hero">
      <div class="learning-hero-copy">
        <div class="card-badge">Start Learning</div>
        <h4>Self-paced onboarding lives inside the dashboard now.</h4>
        <p class="learning-copy">
          Learn Murisphere with real seeded examples, a biology-first tutorial, and the exact phone scan workflow technicians use in the room.
        </p>
        <div class="learning-actions">
          <a class="button-link" href="${esc(overview.tutorialUrl)}" target="_blank" rel="noopener">Open Full Tutorial</a>
          <a class="button-link button-link-soft" href="${esc(overview.tutorialPdfUrl)}" target="_blank" rel="noopener">Open PDF</a>
          <button type="button" class="button-link button-link-soft" data-learning-tab="cages">Set Scan Base URL</button>
        </div>
      </div>
      <div class="learning-readiness">
        <div class="learning-stat"><span>Visible scope</span><strong>${esc(counts.labs || 0)} labs · ${esc(counts.cages || 0)} cages · ${esc(counts.projects || 0)} projects</strong></div>
        <div class="learning-stat"><span>Tutorial data</span><strong>${esc(counts.animals || 0)} animals · ${esc(counts.litters || 0)} litters · ${esc(counts.samples || 0)} samples · ${esc(counts.plannerScenarios || 0)} scenarios</strong></div>
        <div class="learning-status ${overview.tutorialReady ? "ready" : "pending"}">
          ${overview.tutorialReady ? "Tutorial-ready workflow data detected." : "Core app data is ready; richer learning examples appear when the tutorial seed is loaded."}
        </div>
        <div class="learning-status ${phoneReady ? "ready" : "warn"}">
          Phone scan base: ${esc(scanBase)}${phoneReady ? "" : " (not phone-reachable; use LAN IP or public domain)"}
        </div>
        <div class="learning-pill-row">
          ${learningPill("Breeding + pedigree", availability.breedingPedigree)}
          ${learningPill("Samples", availability.sampleGenotyping)}
          ${learningPill("Planner", availability.planner)}
          ${learningPill("Projects", availability.projects)}
        </div>
        <div class="learning-progress">
          <div class="learning-progress-head">
            <div>
              <span class="learning-step">Learner Progress</span>
              <strong>${completed}/${modules.length} modules complete</strong>
            </div>
            <span class="detail-pill">${esc(progressPct)}%</span>
          </div>
          <div class="learning-progress-bar"><span style="width:${progressPct}%"></span></div>
          <div class="learning-progress-copy">
            ${nextModule ? `Next suggested module: ${esc(nextModule.order)}. ${esc(nextModule.title)}.` : "All modules are marked complete."}
          </div>
          <div class="learning-actions">
            ${
              nextModule
                ? `<button type="button" class="button-link" data-learning-tab="${esc(nextModule.tab)}">Continue Module ${esc(nextModule.order)}</button>`
                : `<a class="button-link" href="${esc(overview.tutorialUrl)}" target="_blank" rel="noopener">Review Tutorial</a>`
            }
            <button type="button" class="button-link button-link-soft" data-learning-reset="1">Reset Progress</button>
          </div>
        </div>
      </div>
    </section>
    <div class="learning-grid">
      ${modules
        .map(
          (module) => `
            <article class="learning-card ${moduleComplete(module.id) ? "complete" : ""}">
              <div class="learning-step">Module ${esc(module.order)}</div>
              <h4>${esc(module.title)}</h4>
              <p class="learning-copy">${esc(module.summary)}</p>
              <div class="learning-pill-row">
                <span class="learning-pill ${moduleComplete(module.id) ? "ready" : "pending"}">${moduleComplete(module.id) ? "Completed" : "Not started"}</span>
              </div>
              <div class="learning-actions">
                <button type="button" class="table-link" data-learning-tab="${esc(module.tab)}">${esc(module.actionLabel)}</button>
                <a class="button-link button-link-soft" href="${esc(overview.tutorialUrl)}" target="_blank" rel="noopener">Read Guide</a>
                <button type="button" class="button-link button-link-soft" data-learning-toggle-module="${esc(module.id)}">
                  ${moduleComplete(module.id) ? "Mark Incomplete" : "Mark Complete"}
                </button>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
    <div class="learning-examples">
      <div class="viz-heading">Seeded Examples</div>
      ${
        exampleCards.length
          ? `<div class="learning-example-grid">${exampleCards.join("")}</div>`
          : `<div class="viz-card"><p class="learning-copy">No advanced example records are visible in this database yet. Load the tutorial-ready seed to practice pedigree, samples, and planner workflows with matching examples.</p></div>`
      }
    </div>
  `;
}

function renderCageInspector(detail) {
  if (!detail?.cage) {
    el("cageInspector").innerHTML = "";
    return;
  }
  const cage = detail.cage;
  const animals = detail.animals || [];
  const history = detail.history || [];
  const statusCounts = {};
  for (const a of animals) statusCounts[a.status || "Unknown"] = (statusCounts[a.status || "Unknown"] || 0) + 1;
  const statusBars = Object.entries(statusCounts).map(([label, value], i) => ({
    label,
    value,
    color: ["#18a172", "#4f8ef7", "#eb9c44", "#ca513d", "#7c6cf2"][i % 5],
  }));
  const historyRows = history
    .slice(0, 8)
    .map((h) => `<div class="timeline-item"><strong>${esc(h.action)}</strong><span>${esc(fmtDate(h.created_at))}</span></div>`)
    .join("");
  const animalsRows = animals
    .slice(0, 8)
    .map((a) => `<tr><td>${esc(a.animal_code)}</td><td>${esc(a.sex)}</td><td>${esc(a.genotype || "Pending")}</td><td>${esc(a.status)}</td></tr>`)
    .join("");

  el("cageInspector").innerHTML = `
    <div class="detail-shell">
      <div class="detail-head">
        <h4>${esc(cage.cageCode)}</h4>
        <span class="detail-pill">${esc(cage.room)} / ${esc(cage.rack)}</span>
      </div>
      <div class="detail-grid">
        ${chartCard(
          "Population",
          `${esc(cage.strain)} | ${esc(cage.genotypeSummary)}`,
          drawDonut([
            { label: "Male", value: toNum(cage.maleCount), color: "#3ba0d8" },
            { label: "Female", value: toNum(cage.femaleCount), color: "#e6739f" },
          ]),
          `<span class="legend-item">M ${esc(cage.maleCount)}</span><span class="legend-item">F ${esc(cage.femaleCount)}</span><span class="legend-item">Status ${esc(cage.breedingStatus)}</span>`
        )}
        ${chartCard("Animal Status", "Composition in cage", drawBars(statusBars, { height: 120 }), statusBars.map((x) => `<span class="legend-item">${esc(x.label)} ${esc(x.value)}</span>`).join(""))}
      </div>
      <div class="detail-grid">
        <article class="viz-card">
          <h4>Recent Animals</h4>
          <table class="table compact-table">
            <thead><tr><th>ID</th><th>Sex</th><th>Genotype</th><th>Status</th></tr></thead>
            <tbody>${animalsRows || `<tr><td colspan="4">No animal rows.</td></tr>`}</tbody>
          </table>
        </article>
        <article class="viz-card">
          <h4>Audit Timeline</h4>
          <div class="timeline-list">${historyRows || `<div class="hint">No recent cage audit entries.</div>`}</div>
        </article>
      </div>
    </div>
  `;
}

function renderProjectInspector(project, cages, targets = [], assignments = []) {
  if (!project) {
    el("projectInspector").innerHTML = "";
    return;
  }
  const byStatus = {};
  for (const c of cages) byStatus[c.breeding_status] = (byStatus[c.breeding_status] || 0) + 1;
  const statusBars = Object.entries(byStatus).map(([label, value], i) => ({
    label,
    value,
    color: ["#18a172", "#4f8ef7", "#eb9c44", "#ca513d", "#7c6cf2"][i % 5],
  }));
  const assigned = toNum(project.assigned_cages || 0);
  const target = Math.max(0, toNum(project.target_animals || 0));
  const progress = Math.min(100, target ? Math.round((assigned * 100) / target) : 0);

  el("projectInspector").innerHTML = `
    <div class="detail-shell">
      <div class="detail-head">
        <h4>${esc(project.project_code)} - ${esc(project.title)}</h4>
        <span class="detail-pill">${esc(project.status)}</span>
      </div>
      <div class="detail-grid">
        ${chartCard(
          "Target Progress",
          `Assigned cages vs target animals`,
          `<div class="progress-wrap"><div class="progress-bar"><span style="width:${progress}%"></span></div><div class="viz-sub">${assigned} assigned / target ${target}</div></div>`,
          `<span class="legend-item">${esc(project.lab_name)}</span>`
        )}
        ${chartCard(
          "Cage Status Mix",
          "Assigned cage breeding status",
          drawBars(statusBars, { height: 120 }),
          statusBars.map((x) => `<span class="legend-item">${esc(x.label)} ${esc(x.value)}</span>`).join("")
        )}
      </div>
      <div class="detail-grid">
        <article class="viz-card">
          <h4>Genotype Targets</h4>
          <div class="timeline-list">
            ${
              targets.length
                ? targets
                    .map(
                      (row) =>
                        `<div class="timeline-item"><strong>${esc(row.genotype_pattern)}</strong><span>${esc(row.target_count)} animals · priority ${esc(
                          row.priority
                        )}</span></div>`
                    )
                    .join("")
                : `<div class="hint">No genotype rules saved for this project yet.</div>`
            }
          </div>
        </article>
        <article class="viz-card">
          <h4>Reserved Animals</h4>
          <div class="timeline-list">
            ${
              assignments.length
                ? assignments
                    .slice(0, 8)
                    .map(
                      (row) =>
                        `<div class="timeline-item"><strong>${esc(row.animal_code)}</strong><span>${esc(row.genotype || "Pending")} · ${esc(
                          row.cage_code || "N/A"
                        )} · ${esc(row.status)}</span></div>`
                    )
                    .join("")
                : `<div class="hint">No animals reserved to this project yet.</div>`
            }
          </div>
        </article>
      </div>
      <article class="viz-card">
        <h4>Assigned Cages</h4>
        <table class="table compact-table">
          <thead><tr><th>Cage</th><th>Strain</th><th>Genotype</th><th>Status</th><th>M/F</th></tr></thead>
          <tbody>
            ${
              cages
                .slice(0, 18)
                .map(
                  (c) => `<tr>
                    <td><button type="button" class="table-link" data-cage-id="${esc(c.id)}">${esc(c.cage_code)}</button></td>
                    <td>${esc(c.strain)}</td>
                    <td>${esc(c.genotype_summary)}</td>
                    <td>${esc(c.breeding_status)}</td>
                    <td>${esc(c.male_count)}/${esc(c.female_count)}</td>
                  </tr>`
                )
                .join("") || `<tr><td colspan="5">No cages assigned.</td></tr>`
            }
          </tbody>
        </table>
      </article>
    </div>
  `;
}

async function openCageInspector(cageId) {
  if (!cageId) return;
  const detail = await api(`/api/cages/${cageId}`, { headers: headers(false) });
  activateTab("cages");
  renderCageInspector(detail);
  showMessage(`Loaded cage ${detail.cage.cageCode}`, "success");
}

async function openProjectInspector(projectId) {
  if (!projectId) return;
  const project = state.projects.find((p) => Number(p.id) === Number(projectId));
  const [cages, targets, assignments] = await Promise.all([
    api(`/api/projects/${projectId}/cages`, { headers: headers(false) }),
    api(`/api/projects/${projectId}/genotype-targets`, { headers: headers(false) }),
    api(`/api/projects/${projectId}/assignments`, { headers: headers(false) }),
  ]);
  activateTab("projects");
  renderProjectInspector(project, cages, targets, assignments);
  showMessage(`Loaded project ${project?.project_code || projectId}`, "success");
}

async function openLearningScan(code) {
  if (!code) return;
  activateTab("scan");
  el("scanCode").value = code;
  await runScan();
  showMessage(`Opened scan workflow for ${code}`, "success");
}

async function openLearningPedigree(animalId) {
  if (!animalId) return;
  activateTab("scan");
  el("pedigreeAnimalId").value = String(animalId);
  await loadPedigreeViz();
  showMessage(`Opened pedigree for animal ${animalId}`, "success");
}

function renderPedigreeGraph(data) {
  const host = el("pedigreeViz");
  if (!data || !data.nodes?.length) {
    host.innerHTML = `<p class="hint">No pedigree data for selected animal.</p>`;
    return;
  }
  const nodesById = {};
  for (const n of data.nodes) nodesById[n.id] = n;
  const depth = { [data.rootId]: 0 };
  const queue = [data.rootId];
  while (queue.length) {
    const id = queue.shift();
    const node = nodesById[id];
    if (!node) continue;
    const d = depth[id] || 0;
    for (const pid of [node.sire_id, node.dam_id]) {
      if (!pid || !(pid in nodesById)) continue;
      if (!(pid in depth) || depth[pid] > d + 1) {
        depth[pid] = d + 1;
        queue.push(pid);
      }
    }
  }
  const columns = {};
  for (const n of data.nodes) {
    const d = depth[n.id] ?? data.generations;
    if (!columns[d]) columns[d] = [];
    columns[d].push(n);
  }
  const depthKeys = Object.keys(columns)
    .map(Number)
    .sort((a, b) => a - b);
  const colWidth = 170;
  const rowHeight = 70;
  const width = Math.max(520, (Math.max(...depthKeys, 0) + 1) * colWidth + 40);
  const maxRows = Math.max(...depthKeys.map((k) => columns[k].length), 1);
  const height = Math.max(320, maxRows * rowHeight + 50);
  const pos = {};
  for (const d of depthKeys) {
    columns[d].forEach((n, i) => {
      pos[n.id] = { x: 20 + d * colWidth, y: 20 + i * rowHeight };
    });
  }
  const edges = data.edges
    .map((e) => {
      const a = pos[e.from];
      const b = pos[e.to];
      if (!a || !b) return "";
      const sx = a.x + 130;
      const sy = a.y + 20;
      const tx = b.x;
      const ty = b.y + 20;
      const mx = (sx + tx) / 2;
      return `<path class="pedigree-edge" d="M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}"></path>`;
    })
    .join("");
  const nodes = data.nodes
    .map((n) => {
      const p = pos[n.id];
      if (!p) return "";
      const sex = (n.sex || "U").toLowerCase() === "m" ? "male" : (n.sex || "U").toLowerCase() === "f" ? "female" : "unknown";
      return `<g class="pedigree-node ${sex}" transform="translate(${p.x},${p.y})">
        <rect width="130" height="42"></rect>
        <text x="8" y="16">${esc(n.animal_code || `ID-${n.id}`)}</text>
        <text x="8" y="31" fill="#50626b">${esc((n.genotype || "N/A").slice(0, 18))}</text>
        <title>ID ${n.id} | ${n.sex || "U"} | ${n.strain || ""}</title>
      </g>`;
    })
    .join("");
  host.innerHTML = `
    <div class="viz-sub">Pinch/scroll to zoom. Drag to pan.</div>
    <div class="pedigree-stage" id="pedigreeStage">
      <svg class="viz-svg" viewBox="0 0 ${width} ${height}">
        <g id="pedigreeLayer">${edges}${nodes}</g>
      </svg>
    </div>
  `;
  const stage = el("pedigreeStage");
  stage.scrollLeft = Math.max(0, width / 2 - stage.clientWidth / 2);
  stage.scrollTop = Math.max(0, height / 2 - stage.clientHeight / 2);
}

function normalizedScanBase() {
  const saved = (localStorage.getItem(SCAN_BASE_KEY) || "").trim();
  const raw = saved || window.location.origin;
  return raw.replace(/\/+$/, "");
}

function scanUrlForCard(card) {
  return `${normalizedScanBase()}${card.scanUrl}`;
}

function assignCardMedia(root = document) {
  root.querySelectorAll("img.qrcode").forEach((img) => {
    const value = img.getAttribute("data-qr");
    if (!value) return;
    img.src = `/api/assets/qrcode.png?v=${encodeURIComponent(value)}`;
  });
  root.querySelectorAll("img.barcode").forEach((img) => {
    const value = img.getAttribute("data-barcode");
    if (!value) return;
    img.src = `/api/assets/barcode.svg?v=${encodeURIComponent(value)}`;
  });
}

async function waitForImages(root = document) {
  const nodes = Array.from(root.querySelectorAll("img"));
  await Promise.all(
    nodes.map(
      (img) =>
        new Promise((resolve) => {
          if (img.complete) return resolve(null);
          img.addEventListener("load", () => resolve(null), { once: true });
          img.addEventListener("error", () => resolve(null), { once: true });
        })
    )
  );
}

function cardMarkup(c) {
  const male = toNum(c.animalCount?.M);
  const female = toNum(c.animalCount?.F);
  const total = male + female;
  const projects = (c.projects || []).length ? c.projects.join(", ") : "Unassigned";
  const location = [c.roomName, c.rackName].filter(Boolean).join(", ") || c.location || "N/A";
  const animals = (c.animals || []).slice(0, 5);
  const litters = (c.litters || []).slice(0, 4);
  const trackedAnimals = (c.animals || []).length;

  const animalRows = animals
    .map(
      (a) => `
      <tr>
        <td class="center">${esc(a.animalCode || "")}</td>
        <td class="center">${esc(a.sex || "U")}</td>
        <td class="center">${esc(fmtDate(a.dob))}</td>
        <td>${esc(a.genotype || "Pending")}</td>
        <td class="center">${esc(a.status || "Active")}</td>
      </tr>`
    )
    .join("");
  const animalFill = Array.from({ length: Math.max(0, 5 - animals.length) })
    .map(
      () => `
      <tr class="empty">
        <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
      </tr>`
    )
    .join("");

  const litterRows = litters
    .map(
      (l, idx) => `
      <tr>
        <td class="center">${esc(idx + 1)}</td>
        <td class="center">${esc(fmtDate(l.birthDate))}</td>
        <td class="center">${esc(l.born)}</td>
        <td class="center">${esc(l.survived)}</td>
        <td class="center">${esc(`${toNum(l.maleCount)}/${toNum(l.femaleCount)}`)}</td>
        <td class="center">${esc(fmtDate(l.dow))}</td>
      </tr>`
    )
    .join("");
  const litterFill = Array.from({ length: Math.max(0, 4 - litters.length) })
    .map(
      () => `
      <tr class="empty">
        <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
      </tr>`
    )
    .join("");

  return `
    <article class="print-card">
      <div class="print-card-header">
        <div class="print-card-identity">
          <div class="card-badge">Murisphere Cage Card</div>
          <div class="card-title">${esc(c.cageCode)}</div>
          <div class="card-subtitle">${esc(location)}</div>
        </div>
        <div class="card-code-block">
          <img class="qrcode" data-qr="${esc(scanUrlForCard(c))}" alt="QR code" />
          <div class="qr-caption">Scan with phone camera</div>
        </div>
      </div>

      <div class="card-facts-grid">
        <div class="card-fact"><span>Group Owner</span><strong>${esc(c.groupOwner || "N/A")}</strong></div>
        <div class="card-fact"><span>Group Name</span><strong>${esc(c.groupName || c.piLab || "N/A")}</strong></div>
        <div class="card-fact"><span>Projects</span><strong>${esc(projects)}</strong></div>
        <div class="card-fact"><span>Protocol</span><strong>${esc(c.protocol || "N/A")}</strong></div>
        <div class="card-fact"><span>Description</span><strong>${esc(c.protocolDescription || "N/A")}</strong></div>
        <div class="card-fact"><span>Protocol Expires</span><strong>${esc(fmtDate(c.protocolExpiresOn))}</strong></div>
        <div class="card-fact"><span>Breeding Status</span><strong>${esc(c.breedingStatus || "N/A")}</strong></div>
        <div class="card-fact"><span>Cage DOB</span><strong>${esc(fmtDate(c.dob))}</strong></div>
        <div class="card-fact"><span>Strain</span><strong>${esc(c.strain)}</strong></div>
        <div class="card-fact"><span>Genotype</span><strong>${esc(c.genotype)}</strong></div>
        <div class="card-fact"><span>Population (Cage Total)</span><strong>${esc(`M${male} / F${female} / T${total}`)}</strong></div>
        <div class="card-fact"><span>Tracked IDs Listed</span><strong>${esc(`${Math.min(trackedAnimals, 5)} shown of ${trackedAnimals}`)}</strong></div>
        <div class="card-fact"><span>Room / Rack</span><strong>${esc(location)}</strong></div>
      </div>

      <div class="card-panels">
        <div class="card-panel">
          <div class="panel-title">Animals</div>
          <div class="panel-subtitle">Rows list tracked IDs; cage population may include untagged pups.</div>
          <table class="card-table animals-table">
            <colgroup>
              <col style="width:18%" />
              <col style="width:10%" />
              <col style="width:24%" />
              <col style="width:32%" />
              <col style="width:16%" />
            </colgroup>
            <thead>
              <tr><th>ID</th><th>Sex</th><th>DOB</th><th>Genotype</th><th>Status</th></tr>
            </thead>
            <tbody>
              ${animalRows}${animalFill}
            </tbody>
          </table>
        </div>
        <div class="card-panel">
          <div class="panel-title">Litters</div>
          <table class="card-table litters-table">
            <colgroup>
              <col style="width:9%" />
              <col style="width:25%" />
              <col style="width:13%" />
              <col style="width:15%" />
              <col style="width:15%" />
              <col style="width:23%" />
            </colgroup>
            <thead>
              <tr><th>#</th><th>DOB</th><th>Born</th><th>Survived</th><th>M/F</th><th>DoW</th></tr>
            </thead>
            <tbody>
              ${litterRows}${litterFill}
            </tbody>
          </table>
        </div>
      </div>

      <div class="scan-block">
        <img class="barcode" data-barcode="${esc(c.cageCode)}" alt="Barcode" />
        <div class="card-foot">Scan URL: ${esc(scanUrlForCard(c))}</div>
      </div>
    </article>
  `;
}

async function renderCards(cards) {
  state.cards = cards;
  el("cardPreview").innerHTML = `<div class="card-grid">${cards.map(cardMarkup).join("")}</div>`;
  assignCardMedia(el("cardPreview"));
  await waitForImages(el("cardPreview"));
}

async function fetchCards() {
  const ids = state.cages.slice(0, 20).map((c) => c.id);
  if (!ids.length) {
    showMessage("No cages available to print.", "warn");
    return [];
  }
  return api("/api/cages/cards", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ ids }),
  });
}

async function generateCards() {
  const cards = await fetchCards();
  if (!cards.length) return;
  await renderCards(cards);
}

async function printCardsDirect() {
  if (!state.cards.length) {
    const cards = await fetchCards();
    if (!cards.length) return;
    await renderCards(cards);
  }
  assignCardMedia(el("cardPreview"));
  await waitForImages(el("cardPreview"));
  const printableRoot = el("cardPreview").cloneNode(true);
  const source = printableRoot.innerHTML;
  const win = window.open("", "_blank", "width=1100,height=800");
  if (!win) {
    showMessage("Please allow popups to print cage cards.", "warn");
    return;
  }
  win.document.write(`
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <title>Murisphere Cage Cards</title>
        <style>
          body {
            font-family: "Avenir Next", "Segoe UI", Arial, sans-serif;
            margin: 12px;
            color: #102a36;
            background: linear-gradient(155deg, #f6fbf9, #edf6f2);
          }
          .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(640px, 1fr)); gap: 12px; }
          .print-card {
            border: 1.25px solid #7fa296;
            border-radius: 12px;
            padding: 10px;
            break-inside: avoid;
            min-height: 440px;
            background:
              linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(246, 251, 248, 0.98)),
              radial-gradient(circle at 90% 0, rgba(24, 161, 114, 0.08), transparent 42%);
            box-shadow: 0 4px 18px rgba(24, 56, 48, 0.12);
          }
          .print-card-header { display: grid; grid-template-columns: minmax(0, 1fr) 112px; gap: 10px; margin-bottom: 8px; align-items: start; }
          .print-card-identity { display: grid; gap: 2px; }
          .card-badge {
            display: inline-flex;
            width: fit-content;
            font-size: 9px;
            letter-spacing: .08em;
            text-transform: uppercase;
            padding: 2px 7px;
            border-radius: 999px;
            color: #0f5942;
            background: #e7f6ef;
            border: 1px solid #b8dccb;
          }
          .card-title { font-size: 20px; font-weight: 700; letter-spacing: .01em; color: #0f2f3c; }
          .card-subtitle { font-size: 11px; color: #415d69; line-height: 1.2; }
          .card-code-block { width: 108px; text-align: center; }
          .qrcode { width: 104px; height: 104px; border: 1px solid #2a4a57; border-radius: 8px; object-fit: contain; background: #fff; }
          .qr-caption { margin-top: 3px; font-size: 9px; color: #2d4956; }
          .card-facts-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 4px 10px;
            margin-bottom: 8px;
          }
          .card-fact {
            display: grid;
            grid-template-columns: 112px minmax(0, 1fr);
            gap: 6px;
            align-items: baseline;
            font-size: 10px;
            line-height: 1.2;
          }
          .card-fact > span { color: #33525f; font-weight: 600; }
          .card-fact > strong { color: #163744; font-weight: 700; overflow-wrap: anywhere; }
          .card-panels { display: grid; grid-template-columns: 1fr; gap: 8px; }
          .card-panel {
            border: 1px solid #9dbbb0;
            border-radius: 8px;
            overflow: hidden;
            background: #fff;
          }
          .panel-title {
            padding: 4px 6px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: .02em;
            color: #123844;
            background: linear-gradient(180deg, #edf7f3, #e6f1ec);
            border-bottom: 1px solid #9dbbb0;
          }
          .panel-subtitle {
            padding: 2px 6px 4px;
            font-size: 8.5px;
            color: #48616c;
            border-bottom: 1px solid #d4e6dd;
            background: #f8fcfa;
          }
          .card-table { width: 100%; border-collapse: collapse; font-size: 9.5px; table-layout: fixed; }
          .card-table th, .card-table td {
            border-right: 1px solid #abc5ba;
            border-bottom: 1px solid #abc5ba;
            padding: 3px 4px;
            vertical-align: top;
            overflow-wrap: anywhere;
            word-break: break-word;
            overflow: hidden;
          }
          .card-table th:last-child, .card-table td:last-child { border-right: none; }
          .card-table thead th { background: #f3faf7; text-align: left; color: #163744; }
          .card-table td.center, .card-table th.center { text-align: center; }
          .card-table tr.empty td { color: transparent; }
          .scan-block { display: grid; grid-template-columns: minmax(0, 1fr); gap: 6px; align-items: center; margin-top: 8px; }
          .barcode {
            width: 100%;
            height: 56px;
            border: 1px solid #2a4a57;
            background: #fff;
            border-radius: 5px;
          }
          .card-foot {
            font-size: 9px;
            color: #2e4956;
            word-break: break-all;
            font-family: "IBM Plex Mono", "Consolas", monospace;
          }
          @page { size: letter portrait; margin: 0.35in; }
        </style>
      </head>
      <body>${source}</body>
    </html>
  `);
  win.document.close();
  win.focus();
  win.print();
}

async function loadCages(q = "") {
  const list = await api(`/api/cages?q=${encodeURIComponent(q)}`, { headers: headers(false) });
  state.cages = list;
  el("cageTable").innerHTML = list.length ? tableFromCages(list, state.alertsByCage) : `<p class="hint">No cages match this search.</p>`;
  renderCageVisuals();
}

function rebuildAlertsByCage(alerts) {
  const byCage = {};
  for (const a of alerts) {
    if (!a.cage_id) continue;
    if (!byCage[a.cage_id]) byCage[a.cage_id] = [];
    byCage[a.cage_id].push(a);
  }
  for (const cageId of Object.keys(byCage)) {
    byCage[cageId].sort((x, y) => (SEVERITY_RANK[y.severity] || 0) - (SEVERITY_RANK[x.severity] || 0));
  }
  state.alertsByCage = byCage;
}

async function loadActiveAlertFeed() {
  if (!state.user) return;
  const alerts = await api("/api/alerts/feed?status=active", { headers: headers(false) });
  state.alerts = alerts;
  rebuildAlertsByCage(alerts);
  const high = alerts.filter((a) => a.severity === "high").length;
  const medium = alerts.filter((a) => a.severity === "medium").length;
  const banner = el("alertBanner");
  if (alerts.length) {
    banner.classList.remove("hidden");
    banner.textContent = `Active alerts: ${alerts.length} (high ${high}, medium ${medium}). Cages are highlighted below.`;
  } else {
    banner.classList.add("hidden");
    banner.textContent = "";
  }
  if (state.cages.length) {
    el("cageTable").innerHTML = tableFromCages(state.cages, state.alertsByCage);
  } else {
    el("cageTable").innerHTML = `<p class="hint">No cages loaded.</p>`;
  }
  renderCageVisuals();
  renderComplianceVisuals(state.alerts, []);
}

function alertCardMarkup(alert) {
  return `<div class="cage-card">
    <strong>${esc(alert.title)}</strong> <span class="alert-pill ${esc(severityClass(alert.severity))}">${esc(alert.severity.toUpperCase())}</span><br/>
    Cage: ${
      alert.cage_id
        ? `<button type="button" class="table-link" data-cage-id="${esc(alert.cage_id)}">${esc(alert.cage_code || `#${alert.cage_id}`)}</button>`
        : esc(alert.cage_code || "N/A")
    } | ${esc(alert.category)}<br/>
    ${esc(alert.message)}<br/>
    <button type="button" data-ack-alert="${esc(alert.id)}">Acknowledge</button>
  </div>`;
}

async function runScan() {
  const code = el("scanCode").value.trim();
  if (!code) return;
  try {
    const data = await api(`/api/scan/${encodeURIComponent(code)}`, { headers: headers(false) });
    const c = data.cage;
    el("scanResult").innerHTML = `
      <div class="cage-card">
        <strong>${esc(c.cageCode)}</strong> (${esc(data.lookupMs)}ms)<br/>
        ${esc(c.strain)} | ${esc(c.genotypeSummary)} | ${esc(c.breedingStatus)}<br/>
        Counts: M ${esc(c.maleCount)} / F ${esc(c.femaleCount)}<br/>
        ${esc(c.room)} / ${esc(c.rack)}<br/>
        ${(state.alertsByCage[c.id] || []).map((a) => `<span class="alert-pill ${esc(severityClass(a.severity))}">${esc(a.title)}</span>`).join(" ")}
      </div>
      <form id="quickUpdate" class="grid-form">
        <label>Male Count<input id="uMale" type="number" value="${esc(c.maleCount)}" /></label>
        <label>Female Count<input id="uFemale" type="number" value="${esc(c.femaleCount)}" /></label>
        <label>Status<input id="uStatus" value="${esc(c.breedingStatus)}" /></label>
        <label>Notes<input id="uNotes" value="${esc(c.notes || "")}" /></label>
        <button type="submit">Save Changes</button>
      </form>
    `;
    el("quickUpdate").addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        maleCount: Number(el("uMale").value),
        femaleCount: Number(el("uFemale").value),
        breedingStatus: el("uStatus").value,
        notes: el("uNotes").value,
      };
      const req = {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify(payload),
      };
      try {
        await api(`/api/cages/${c.id}`, req);
        await loadCages();
        showMessage("Saved with audit log.", "success");
      } catch (err) {
        enqueueMutation(`/api/cages/${c.id}`, req);
        showMessage(`Network issue: queued locally and will retry automatically. (${err.message})`, "warn");
      }
    });
  } catch (err) {
    el("scanResult").innerHTML = `<p class="hint">${err.message}</p>`;
  }
}

function readPendingScanToken() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("scanToken");
  if (fromUrl) {
    localStorage.setItem(PENDING_SCAN_KEY, fromUrl);
    return fromUrl;
  }
  return localStorage.getItem(PENDING_SCAN_KEY) || "";
}

async function openPendingScanIfAny() {
  const token = readPendingScanToken();
  if (!token || !state.user) return;
  activateTab("scan");
  el("scanCode").value = token;
  await runScan();
  localStorage.removeItem(PENDING_SCAN_KEY);
}

async function loadAnalytics() {
  const [a, nonProd, reminders, space, consolidation] = await Promise.all([
    api("/api/analytics/summary", { headers: headers(false) }),
    api("/api/breeding/non-productive?staleDays=45", { headers: headers(false) }),
    api("/api/tasks/reminders?windowDays=14", { headers: headers(false) }),
    api("/api/forecast/cage-space?days=30", { headers: headers(false) }),
    api("/api/forecast/consolidation?maxAnimals=2", { headers: headers(false) }),
  ]);
  const projectedOverCap = (space.rooms || []).filter((r) => (r.projectedUtilizationPct || 0) > 100).length;
  el("analyticsSummary").innerHTML = `
    <div class="kpi"><div>Total Cages</div><div class="value">${a.totalCages}</div></div>
    <div class="kpi"><div>Active Animals</div><div class="value">${a.totalActiveAnimals}</div></div>
    <div class="kpi"><div>Pup Survival</div><div class="value">${a.pupSurvivalPct}%</div></div>
    <div class="kpi"><div>Sex Ratio (M/F)</div><div class="value">${a.sexRatio.M}/${a.sexRatio.F}</div></div>
    <div class="kpi"><div>Non-Productive Breeders</div><div class="value">${nonProd.length}</div></div>
    <div class="kpi"><div>Upcoming/Overdue Tasks</div><div class="value">${reminders.length}</div></div>
    <div class="kpi"><div>Projected Over-Cap Rooms (30d)</div><div class="value">${projectedOverCap}</div></div>
    <div class="kpi"><div>Consolidation Opportunities</div><div class="value">${consolidation.length}</div></div>
  `;
  renderAnalyticsVisuals(a, nonProd, reminders, space, consolidation);
  await loadPlannerWorkspace();
}

async function loadCalendar() {
  const [events, productivity] = await Promise.all([
    api("/api/calendar", { headers: headers(false) }),
    api("/api/breeding/productivity?minLitters=0", { headers: headers(false) }),
  ]);
  el("calendarList").innerHTML = events
    .map((e) => `<div class="cage-card">${esc(e.event_date)} | Cage ${esc(e.cage_code)} | ${esc(e.event_type)}</div>`)
    .join("");
  renderBreedingVisuals(events, productivity);
}

async function loadProjects() {
  const rows = await api("/api/projects", { headers: headers(false) });
  state.projects = rows;
  el("projectList").innerHTML = rows.length ? tableFromProjects(rows) : `<p class="hint">No projects yet.</p>`;
}

async function loadQuotas() {
  const rows = await api("/api/facility/quotas", { headers: headers(false) });
  el("quotaList").innerHTML = rows.length ? tableFromQuotas(rows) : `<p class="hint">No quota data.</p>`;
  return rows;
}

async function loadDashboard() {
  const [summary, alerts, reminders, learning] = await Promise.all([
    api("/api/analytics/summary", { headers: headers(false) }),
    api("/api/alerts/feed?status=active", { headers: headers(false) }),
    api("/api/tasks/reminders?windowDays=14", { headers: headers(false) }),
    api("/api/learning/overview", { headers: headers(false) }),
  ]);
  let quotas = [];
  try {
    quotas = await api("/api/facility/quotas", { headers: headers(false) });
  } catch {
    quotas = [];
  }

  const highAlerts = alerts.filter((a) => a.severity === "high").length;
  const overCapacity = quotas.filter((q) => toNum(q.utilizationPct || 0) > 100).length;
  el("dashboardKpis").innerHTML = `
    <div class="kpi"><div>Total Cages</div><div class="value">${esc(summary.totalCages)}</div></div>
    <div class="kpi"><div>Active Animals</div><div class="value">${esc(summary.totalActiveAnimals)}</div></div>
    <div class="kpi"><div>Active Alerts</div><div class="value">${esc(alerts.length)}</div></div>
    <div class="kpi"><div>High Alerts</div><div class="value">${esc(highAlerts)}</div></div>
    <div class="kpi"><div>Upcoming Tasks</div><div class="value">${esc(reminders.length)}</div></div>
    <div class="kpi"><div>Pup Survival</div><div class="value">${esc(summary.pupSurvivalPct)}%</div></div>
    <div class="kpi"><div>Sex Ratio</div><div class="value">${esc(summary.sexRatio.M)}/${esc(summary.sexRatio.F)}</div></div>
    <div class="kpi"><div>Labs Over Capacity</div><div class="value">${esc(overCapacity)}</div></div>
  `;
  renderDashboardVisuals(summary, alerts, reminders, quotas);
  renderLearningHub(learning);
  el("dashboardAlerts").innerHTML =
    alerts.slice(0, 8).map(alertCardMarkup).join("") || `<p class="hint">No active alerts.</p>`;
  el("dashboardTasks").innerHTML =
    reminders
      .slice(0, 10)
      .map(
        (r) =>
          `<div class="cage-card">${esc(r.event_date || r.due_on)} | <strong>${esc(r.event_type || r.task_type)}</strong> | Cage ${esc(r.cage_code || `#${r.cage_id || "N/A"}`)}</div>`
      )
      .join("") || `<p class="hint">No tasks due in this window.</p>`;
}

async function loadPedigreeViz() {
  const animalId = Number(el("pedigreeAnimalId").value || 0);
  const generations = Number(el("pedigreeGenerations").value || 3);
  if (!animalId) {
    el("pedigreeViz").innerHTML = `<p class="hint">Enter an animal ID to visualize pedigree.</p>`;
    return;
  }
  try {
    const data = await api(`/api/animals/${animalId}/pedigree?generations=${generations}`, { headers: headers(false) });
    renderPedigreeGraph(data);
  } catch (err) {
    el("pedigreeViz").innerHTML = `<p class="hint">${esc(err.message)}</p>`;
  }
}

function roleAllows(roleList) {
  return !!state.user && roleList.includes(state.user.role);
}

function setButtonEnabled(id, enabled, blockedMessage = "") {
  const node = el(id);
  if (!node) return;
  node.disabled = !enabled;
  node.title = enabled ? "" : blockedMessage;
}

function applyRoleAccess() {
  const canManageProjects = roleAllows(["PI", "Admin"]);
  const isAdminUser = roleAllows(["Admin"]);
  const canPlan = roleAllows(["PI", "Admin"]);
  const canHandleSamples = roleAllows(["Technician", "PI", "Admin"]);
  const canImportGenotyping = roleAllows(["PI", "Admin"]);
  setButtonEnabled("dispatchAlertsBtn", canManageProjects, "Requires PI/Admin role");
  setButtonEnabled("loadSlaBtn", canManageProjects, "Requires PI/Admin role");
  setButtonEnabled("loadQuotasBtn", canManageProjects, "Requires PI/Admin role");
  setButtonEnabled("generateRecommendationsBtn", canPlan, "Requires PI/Admin role");
  setButtonEnabled("evaluatePlannerBtn", canPlan, "Requires PI/Admin role");
  setButtonEnabled("simulateCallbackBtn", isAdminUser, "Requires Admin role");
  setButtonEnabled("downloadProviderTemplateBtn", canHandleSamples, "Requires Technician/PI/Admin role");

  const projectSubmit = el("projectForm")?.querySelector("button[type='submit']");
  if (projectSubmit) {
    projectSubmit.disabled = !canManageProjects;
    projectSubmit.title = canManageProjects ? "" : "Requires PI/Admin role";
  }

  const genoSubmit = el("genoUploadForm")?.querySelector("button[type='submit']");
  if (genoSubmit) {
    genoSubmit.disabled = !canManageProjects;
    genoSubmit.title = canManageProjects ? "" : "Requires PI/Admin role";
  }

  const excelSubmit = el("excelImportForm")?.querySelector("button[type='submit']");
  if (excelSubmit) {
    excelSubmit.disabled = !isAdminUser;
    excelSubmit.title = isAdminUser ? "" : "Requires Admin role";
  }

  const plannerScenarioSubmit = el("plannerScenarioForm")?.querySelector("button[type='submit']");
  if (plannerScenarioSubmit) {
    plannerScenarioSubmit.disabled = !canPlan;
    plannerScenarioSubmit.title = canPlan ? "" : "Requires PI/Admin role";
  }

  const plannerProjectSubmit = el("plannerProjectForm")?.querySelector("button[type='submit']");
  if (plannerProjectSubmit) {
    plannerProjectSubmit.disabled = !canPlan;
    plannerProjectSubmit.title = canPlan ? "" : "Requires PI/Admin role";
  }

  const sampleSubmit = el("sampleCreateForm")?.querySelector("button[type='submit']");
  if (sampleSubmit) {
    sampleSubmit.disabled = !canHandleSamples;
    sampleSubmit.title = canHandleSamples ? "" : "Requires Technician/PI/Admin role";
  }

  const orderSubmit = el("genotypingOrderForm")?.querySelector("button[type='submit']");
  if (orderSubmit) {
    orderSubmit.disabled = !canHandleSamples;
    orderSubmit.title = canHandleSamples ? "" : "Requires Technician/PI/Admin role";
  }

  const callbackSubmit = el("genotypingCallbackForm")?.querySelector("button[type='submit']");
  if (callbackSubmit) {
    callbackSubmit.disabled = !isAdminUser;
    callbackSubmit.title = isAdminUser ? "" : "Requires Admin role";
  }

  const importSubmit = el("genotypingImportForm")?.querySelector("button[type='submit']");
  if (importSubmit) {
    importSubmit.disabled = !canImportGenotyping;
    importSubmit.title = canImportGenotyping ? "" : "Requires PI/Admin role";
  }
}

async function handleTabOpen(tab) {
  activateTab(tab);
  if (tab === "dashboard") await loadDashboard();
  if (tab === "analytics") await loadAnalytics();
  if (tab === "breeding") await loadCalendar();
  if (tab === "scan") await loadPedigreeViz();
  if (tab === "reports") await loadSampleWorkspace();
  if (tab === "compliance") await loadActiveAlertFeed();
  if (tab === "projects") {
    await loadProjects();
    try {
      await loadQuotas();
    } catch {
      el("quotaList").innerHTML = `<p class="hint">Quota view requires PI/Admin role.</p>`;
    }
  }
}

async function init() {
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      withAction(`Load ${btn.dataset.tab} view`, () => handleTabOpen(btn.dataset.tab)).catch(() => undefined);
    });
  });

  el("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Login failed", async () => {
      const data = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: el("email").value, password: el("password").value }),
      });
      setAuth(data.token, data.user);
      applyRoleAccess();
      activateTab("dashboard");
      await loadCages();
      await loadProjects();
      await loadDashboard();
      await loadActiveAlertFeed();
      try {
        await loadQuotas();
      } catch {
        el("quotaList").innerHTML = `<p class="hint">Quota view requires PI/Admin role.</p>`;
      }
      const flushed = await flushMutationQueue();
      if (flushed) showMessage(`Recovered ${flushed} offline queued updates.`, "success");
      await openPendingScanIfAny();
      showMessage(`Signed in as ${data.user.fullName}`, "success");
    }).catch(() => undefined);
  });

  el("scanBtn").addEventListener("click", () => withAction("Scan failed", runScan).catch(() => undefined));
  el("loadPedigreeBtn").addEventListener("click", () => withAction("Pedigree load failed", loadPedigreeViz).catch(() => undefined));
  el("refreshCages").addEventListener("click", () => withAction("Cage refresh failed", () => loadCages()).catch(() => undefined));
  el("searchBtn").addEventListener("click", () => withAction("Search failed", () => loadCages(el("searchCages").value)).catch(() => undefined));
  el("searchCages").addEventListener("keydown", (evt) => {
    if (evt.key !== "Enter") return;
    evt.preventDefault();
    withAction("Search failed", () => loadCages(el("searchCages").value)).catch(() => undefined);
  });
  el("scanBaseUrl").value = normalizedScanBase();
  el("saveScanBaseBtn").addEventListener("click", () => {
    const v = el("scanBaseUrl").value.trim().replace(/\/+$/, "");
    if (!v) {
      showMessage("Enter a valid reachable base URL.", "error");
      return;
    }
    localStorage.setItem(SCAN_BASE_KEY, v);
    if (v.includes("localhost") || v.includes("127.0.0.1")) {
      showMessage("Saved, but localhost/127.0.0.1 is not reachable from phones. Use LAN IP or public domain.", "warn");
      return;
    }
    showMessage(`Saved scan base URL: ${v}`, "success");
  });

  el("printCardsBtn").addEventListener("click", () => withAction("Cage card generation failed", generateCards).catch(() => undefined));
  el("quickPrintBtn").addEventListener("click", () => withAction("Print action failed", printCardsDirect).catch(() => undefined));

  el("breedingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const req = {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        cageId: Number(el("breedCageId").value),
        eventType: el("breedType").value,
        eventDate: el("breedDate").value,
      }),
    };
    try {
      await api("/api/breeding/events", req);
      await loadCalendar();
      showMessage("Breeding event scheduled.", "success");
    } catch (err) {
      enqueueMutation("/api/breeding/events", req);
      showMessage(`Network issue: event queued locally. (${err.message})`, "warn");
    }
  });

  el("projectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Project creation failed", async () => {
      await api("/api/projects", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          projectCode: el("projectCode").value.trim(),
          title: el("projectTitle").value.trim(),
          status: el("projectStatus").value,
          targetAnimals: Number(el("projectTarget").value || 0),
        }),
      });
      el("projectCode").value = "";
      el("projectTitle").value = "";
      el("projectTarget").value = "0";
      await loadProjects();
      showMessage("Project created.", "success");
    }).catch(() => undefined);
  });
  el("refreshProjectsBtn").addEventListener("click", () => withAction("Project refresh failed", loadProjects).catch(() => undefined));
  el("loadQuotasBtn").addEventListener("click", () => withAction("Quota load failed", loadQuotas).catch(() => undefined));

  el("loadPlannerBtn").addEventListener("click", () => withAction("Planner load failed", loadPlannerWorkspace).catch(() => undefined));
  el("generateRecommendationsBtn").addEventListener("click", () => {
    withAction("Recommendation generation failed", async () => {
      const result = await api("/api/recommendations/generate", { method: "POST", headers: headers() });
      await loadPlannerWorkspace();
      showMessage(`Generated ${result.generated} recommendations.`, "success");
    }).catch(() => undefined);
  });
  el("evaluatePlannerBtn").addEventListener("click", () => withAction("Planner evaluation failed", () => evaluatePlannerScenario()).catch(() => undefined));

  el("plannerScenarioForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Planner scenario creation failed", async () => {
      const result = await api("/api/planner/scenarios", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          labId: Number(el("plannerLabId").value || 0),
          name: el("plannerName").value.trim(),
          neededBy: el("plannerNeededBy").value,
          targetAnimals: Number(el("plannerTargetAnimals").value || 0),
          maxNewCages: Number(el("plannerMaxNewCages").value || 0),
        }),
      });
      el("plannerName").value = "";
      state.selectedPlannerScenarioId = Number(result.id);
      await loadPlannerWorkspace();
      showMessage("Planner scenario created.", "success");
    }).catch(() => undefined);
  });

  el("plannerProjectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Planner project demand update failed", async () => {
      const scenarioId = Number(el("plannerScenarioSelect").value || 0);
      const projectId = Number(el("plannerProjectSelect").value || 0);
      if (!scenarioId) throw new Error("Select a scenario first");
      if (!projectId) throw new Error("Select a project first");
      await api(`/api/planner/scenarios/${scenarioId}/projects`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          projects: [
            {
              projectId,
              animalsNeeded: Number(el("plannerAnimalsNeeded").value || 0),
              priority: Number(el("plannerPriority").value || 1),
            },
          ],
        }),
      });
      state.selectedPlannerScenarioId = scenarioId;
      await loadPlannerWorkspace();
      showMessage("Planner demand attached to scenario.", "success");
    }).catch(() => undefined);
  });

  el("plannerScenarioSelect").addEventListener("change", () => {
    const nextId = Number(el("plannerScenarioSelect").value || 0);
    state.selectedPlannerScenarioId = nextId || null;
    withAction("Planner scenario load failed", () => loadPlannerScenarioInspector(nextId)).catch(() => undefined);
  });

  el("loadSamplesBtn").addEventListener("click", () => withAction("Sample workspace load failed", loadSampleWorkspace).catch(() => undefined));
  el("loadOrdersBtn").addEventListener("click", () => withAction("Order load failed", loadSampleWorkspace).catch(() => undefined));
  el("loadGenotypeAnalyticsBtn").addEventListener("click", () => withAction("Genotype analytics load failed", loadSampleWorkspace).catch(() => undefined));

  el("sampleCreateForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Sample creation failed", async () => {
      const animal = await resolveAnimalCode(el("sampleAnimalCode").value.trim());
      if (!animal) throw new Error("Animal code not found");
      const payload = {
        animalId: Number(animal.id),
        sampleType: el("sampleType").value,
        provider: el("sampleProvider").value.trim(),
        status: el("sampleStatus").value,
      };
      const sampleCode = el("sampleCode").value.trim();
      if (sampleCode) payload.sampleCode = sampleCode;
      const created = await api("/api/samples", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload),
      });
      el("sampleAnimalCode").value = "";
      el("sampleCode").value = "";
      await loadSampleWorkspace();
      await inspectSample(created.id);
      showMessage(`Created sample ${created.sampleCode}.`, "success");
    }).catch(() => undefined);
  });

  el("genotypingOrderForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Genotyping order creation failed", async () => {
      if (!state.selectedSampleIds.length) throw new Error("Select at least one sample");
      const projectId = Number(el("orderProjectSelect").value || 0);
      const payload = {
        provider: el("orderProvider").value.trim(),
        sampleIds: state.selectedSampleIds,
        markerPanel: el("orderMarkerPanel").value.trim(),
      };
      if (projectId) payload.projectId = projectId;
      const created = await api("/api/genotyping/orders", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload),
      });
      state.selectedSampleIds = [];
      state.selectedGenotypingOrderId = Number(created.id);
      await loadSampleWorkspace();
      await inspectGenotypingOrder(created.id);
      showMessage(`Created genotyping order ${created.orderRef}.`, "success");
    }).catch(() => undefined);
  });

  el("genotypingCallbackForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Provider callback simulation failed", async () => {
      const orderId = Number(el("callbackOrderSelect").value || 0);
      if (!orderId) throw new Error("Select an order first");
      const order = state.genotypingOrders.find((row) => Number(row.id) === orderId);
      if (!order) throw new Error("Selected order is not loaded");
      const sampleCode = el("callbackSampleCode").value.trim();
      const resultValue = el("callbackResult").value.trim();
      if (!sampleCode || !resultValue) throw new Error("Sample code and result are required");
      const res = await fetch("/api/genotyping/orders/callback", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Provider-Token": "dev-callback-token",
        },
        body: JSON.stringify({
          orderRef: order.order_ref,
          status: el("callbackStatus").value,
          results: [
            {
              sampleCode,
              result: resultValue,
              markerPanel: el("callbackMarkerPanel").value.trim() || null,
            },
          ],
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Callback failed");
      await loadSampleWorkspace();
      await inspectGenotypingOrder(orderId);
      showMessage(`Callback applied. updatedAnimals=${data.updatedAnimals}.`, "success");
    }).catch(() => undefined);
  });

  el("downloadProviderTemplateBtn").addEventListener("click", () => {
    downloadProviderTemplate(Number(el("importOrderSelect").value || state.selectedGenotypingOrderId || 0));
  });

  el("genotypingImportForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Provider results import failed", async () => {
      const orderId = Number(el("importOrderSelect").value || 0);
      if (!orderId) throw new Error("Select an order first");
      const file = el("importResultsFile").files[0];
      if (!file) throw new Error("Choose a CSV file");
      const fd = new FormData();
      fd.append("status", el("importOrderStatus").value);
      fd.append("file", file);
      const res = await fetch(`/api/genotyping/orders/${orderId}/import-results`, {
        method: "POST",
        credentials: "same-origin",
        headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Import failed");
      el("importResultsFile").value = "";
      state.selectedGenotypingOrderId = orderId;
      await loadSampleWorkspace();
      await inspectGenotypingOrder(orderId);
      showMessage(`Imported provider results. updatedAnimals=${data.updatedAnimals}.`, "success");
    }).catch(() => undefined);
  });

  el("callbackOrderSelect").addEventListener("change", () => {
    const orderId = Number(el("callbackOrderSelect").value || 0);
    if (!orderId) return;
    if (el("importOrderSelect")) el("importOrderSelect").value = String(orderId);
    withAction("Order detail load failed", () => inspectGenotypingOrder(orderId)).catch(() => undefined);
  });

  el("importOrderSelect").addEventListener("change", () => {
    const orderId = Number(el("importOrderSelect").value || 0);
    if (!orderId) return;
    if (el("callbackOrderSelect")) el("callbackOrderSelect").value = String(orderId);
    withAction("Order detail load failed", () => inspectGenotypingOrder(orderId)).catch(() => undefined);
  });

  el("genoUploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Genotyping upload failed", async () => {
      const fd = new FormData();
      fd.append("file", el("genoFile").files[0]);
      const res = await fetch("/api/genotyping/upload", { method: "POST", credentials: "same-origin", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      showMessage(`Updated ${data.updatedAnimals} animals.`, "success");
    }).catch(() => undefined);
  });

  el("excelImportForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await withAction("Excel import failed", async () => {
      const fd = new FormData();
      fd.append("file", el("excelFile").files[0]);
      const res = await fetch("/api/import/excel", { method: "POST", credentials: "same-origin", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Import failed");
      showMessage(`Imported ${data.created} cages.`, "success");
      await loadCages();
    }).catch(() => undefined);
  });

  el("loadAlertsBtn").addEventListener("click", async () => {
    await withAction("Protocol alerts load failed", async () => {
      const alerts = await api("/api/compliance/protocol-alerts", { headers: headers(false) });
      el("alerts").innerHTML = alerts
        .map((a) => `<div class="cage-card">${esc(a.protocol_number)} | ${esc(a.title)} | Expires ${esc(a.expires_on)}</div>`)
        .join("");
      renderComplianceVisuals(state.alerts, alerts);
    }).catch(() => undefined);
  });

  el("loadAlertFeedBtn").addEventListener("click", async () => {
    await withAction("Active alert feed failed", async () => {
      const alerts = await api("/api/alerts/feed?status=active", { headers: headers(false) });
      el("activeAlerts").innerHTML = alerts.length ? alerts.map(alertCardMarkup).join("") : `<p class="hint">No active alerts.</p>`;
    }).catch(() => undefined);
  });

  el("dispatchAlertsBtn").addEventListener("click", async () => {
    await withAction("Alert dispatch failed", async () => {
      const result = await api("/api/alerts/dispatch", { method: "POST", headers: headers() });
      showMessage(`Dispatch complete. sent=${result.dispatched}, failed=${result.failed}, simulated=${result.simulated}`, "success");
    }).catch(() => undefined);
  });

  el("loadAuditBtn").addEventListener("click", async () => {
    await withAction("Audit load failed", async () => {
      const logs = await api("/api/audit", { headers: headers(false) });
      el("audit").innerHTML = logs
        .slice(0, 40)
        .map((l) => `<div class="cage-card">${esc(l.created_at)} | ${esc(l.actor || "System")} | ${esc(l.entity_type)}#${esc(l.entity_id)} | ${esc(l.action)}</div>`)
        .join("");
    }).catch(() => undefined);
  });

  el("loadRequestsBtn").addEventListener("click", async () => {
    await withAction("Facility request load failed", async () => {
      const rows = await api("/api/requests", { headers: headers(false) });
      el("requests").innerHTML = rows
        .slice(0, 40)
        .map((r) => `<div class="cage-card">${esc(r.created_at)} | ${esc(r.request_type)} | ${esc(r.status)} | ${esc(r.lab_name)}</div>`)
        .join("");
    }).catch(() => undefined);
  });

  el("loadSlaBtn").addEventListener("click", async () => {
    await withAction("SLA load failed", async () => {
      const rows = await api("/api/operations/sla", { headers: headers(false) });
      el("sla").innerHTML = rows
        .slice(0, 40)
        .map((r) => `<div class="cage-card">${esc(r.request_type)} | ${esc(r.status)} | avg ${Number(r.avg_hours || 0).toFixed(1)}h | n=${esc(r.n)}</div>`)
        .join("");
    }).catch(() => undefined);
  });

  el("cageTable").addEventListener("click", (evt) => {
    const node = evt.target.closest("button[data-cage-id]");
    if (!node) return;
    withAction("Cage detail load failed", () => openCageInspector(Number(node.getAttribute("data-cage-id")))).catch(() => undefined);
  });

  el("projectList").addEventListener("click", (evt) => {
    const projectNode = evt.target.closest("button[data-project-id]");
    if (projectNode) {
      withAction("Project detail load failed", () => openProjectInspector(Number(projectNode.getAttribute("data-project-id")))).catch(() => undefined);
      return;
    }
    const cageNode = evt.target.closest("button[data-cage-id]");
    if (cageNode) {
      withAction("Cage detail load failed", () => openCageInspector(Number(cageNode.getAttribute("data-cage-id")))).catch(() => undefined);
    }
  });

  el("projectInspector").addEventListener("click", (evt) => {
    const cageNode = evt.target.closest("button[data-cage-id]");
    if (!cageNode) return;
    withAction("Cage detail load failed", () => openCageInspector(Number(cageNode.getAttribute("data-cage-id")))).catch(() => undefined);
  });

  el("plannerScenarios").addEventListener("click", (evt) => {
    const scenarioNode = evt.target.closest("button[data-planner-scenario-id]");
    if (scenarioNode) {
      const scenarioId = Number(scenarioNode.getAttribute("data-planner-scenario-id"));
      withAction("Planner scenario load failed", () => loadPlannerScenarioInspector(scenarioId)).catch(() => undefined);
      return;
    }
    const evaluateNode = evt.target.closest("button[data-evaluate-planner-id]");
    if (!evaluateNode) return;
    withAction("Planner evaluation failed", () => evaluatePlannerScenario(Number(evaluateNode.getAttribute("data-evaluate-planner-id")))).catch(() => undefined);
  });

  el("plannerInspector").addEventListener("click", (evt) => {
    const projectNode = evt.target.closest("button[data-project-id]");
    if (!projectNode) return;
    withAction("Project detail load failed", () => openProjectInspector(Number(projectNode.getAttribute("data-project-id")))).catch(() => undefined);
  });

  el("providerPresetList").addEventListener("click", (evt) => {
    const presetNode = evt.target.closest("button[data-provider-preset]");
    if (!presetNode) return;
    applyProviderPreset(presetNode.getAttribute("data-provider-preset"));
  });

  el("sampleList").addEventListener("click", (evt) => {
    const sampleNode = evt.target.closest("button[data-sample-id]");
    if (sampleNode) {
      withAction("Sample detail load failed", () => inspectSample(Number(sampleNode.getAttribute("data-sample-id")))).catch(() => undefined);
      return;
    }
    const toggleNode = evt.target.closest("button[data-sample-toggle]");
    if (toggleNode) {
      const sampleId = Number(toggleNode.getAttribute("data-sample-toggle"));
      setSampleSelected(sampleId, !sampleSelected(sampleId));
      renderSampleList(state.samples);
      return;
    }
    const cageNode = evt.target.closest("button[data-sample-cage-id]");
    if (cageNode) {
      withAction("Cage detail load failed", () => openCageInspector(Number(cageNode.getAttribute("data-sample-cage-id")))).catch(() => undefined);
      return;
    }
    const animalNode = evt.target.closest("button[data-sample-animal-id]");
    if (!animalNode) return;
    withAction("Animal pedigree load failed", () => openLearningPedigree(Number(animalNode.getAttribute("data-sample-animal-id")))).catch(() => undefined);
  });

  el("sampleInspector").addEventListener("click", (evt) => {
    const updateNode = evt.target.closest("button[data-sample-update-id]");
    if (updateNode) {
      const sampleId = Number(updateNode.getAttribute("data-sample-update-id"));
      const status = updateNode.getAttribute("data-sample-next-status");
      withAction("Sample status update failed", async () => {
        await api(`/api/samples/${sampleId}/status`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ status }),
        });
        await loadSampleWorkspace();
        await inspectSample(sampleId);
        showMessage(`Sample marked ${status}.`, "success");
      }).catch(() => undefined);
      return;
    }
    const animalNode = evt.target.closest("button[data-sample-animal-id]");
    if (!animalNode) return;
    withAction("Animal pedigree load failed", () => openLearningPedigree(Number(animalNode.getAttribute("data-sample-animal-id")))).catch(() => undefined);
  });

  el("orderList").addEventListener("click", (evt) => {
    const inspectNode = evt.target.closest("button[data-order-id]");
    if (inspectNode) {
      withAction("Order detail load failed", () => inspectGenotypingOrder(Number(inspectNode.getAttribute("data-order-id")))).catch(() => undefined);
      return;
    }
    const submitNode = evt.target.closest("button[data-submit-order-id]");
    if (!submitNode) return;
    const orderId = Number(submitNode.getAttribute("data-submit-order-id"));
    withAction("Order submission failed", async () => {
      await api(`/api/genotyping/orders/${orderId}/submit`, {
        method: "POST",
        headers: headers(),
      });
      await loadSampleWorkspace();
      await inspectGenotypingOrder(orderId);
      showMessage("Genotyping order submitted.", "success");
    }).catch(() => undefined);
  });

  el("orderInspector").addEventListener("click", (evt) => {
    const sampleNode = evt.target.closest("button[data-sample-id]");
    if (sampleNode) {
      withAction("Sample detail load failed", () => inspectSample(Number(sampleNode.getAttribute("data-sample-id")))).catch(() => undefined);
      return;
    }
    const templateNode = evt.target.closest("button[data-order-template-id]");
    if (templateNode) {
      downloadProviderTemplate(Number(templateNode.getAttribute("data-order-template-id")));
      return;
    }
    const submitNode = evt.target.closest("button[data-submit-order-id]");
    if (submitNode) {
      const orderId = Number(submitNode.getAttribute("data-submit-order-id"));
      withAction("Order submission failed", async () => {
        await api(`/api/genotyping/orders/${orderId}/submit`, {
          method: "POST",
          headers: headers(),
        });
        await loadSampleWorkspace();
        await inspectGenotypingOrder(orderId);
        showMessage("Genotyping order submitted.", "success");
      }).catch(() => undefined);
      return;
    }
    const animalNode = evt.target.closest("button[data-sample-animal-id]");
    if (!animalNode) return;
    withAction("Animal pedigree load failed", () => openLearningPedigree(Number(animalNode.getAttribute("data-sample-animal-id")))).catch(() => undefined);
  });

  el("cohortInsights").addEventListener("click", (evt) => {
    const reserveNode = evt.target.closest("button#reserveCohortAnimalsBtn");
    if (reserveNode) {
      const projectId = Number(el("cohortProjectSelect")?.value || state.selectedCohortProjectId || 0);
      withAction("Animal reservation failed", async () => {
        if (!projectId) throw new Error("Select a project first");
        if (!state.selectedCohortAnimalIds.length) throw new Error("Select at least one genotype-ready animal");
        const result = await api(`/api/projects/${projectId}/reserve-animals`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ animalIds: state.selectedCohortAnimalIds }),
        });
        await loadSampleWorkspace();
        showMessage(`Reserved ${result.reserved} animals for the selected project.`, "success");
      }).catch(() => undefined);
      return;
    }
    const releaseNode = evt.target.closest("button#releaseCohortAnimalsBtn");
    if (releaseNode) {
      const projectId = Number(el("cohortProjectSelect")?.value || state.selectedCohortProjectId || 0);
      withAction("Animal release failed", async () => {
        if (!projectId) throw new Error("Select a project first");
        if (!state.selectedCohortAnimalIds.length) throw new Error("Select at least one reserved animal");
        const result = await api(`/api/projects/${projectId}/release-animals`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ animalIds: state.selectedCohortAnimalIds }),
        });
        await loadSampleWorkspace();
        showMessage(`Released ${result.released} animals from the selected project.`, "success");
      }).catch(() => undefined);
      return;
    }
    const saveTargetNode = evt.target.closest("button#saveCohortTargetBtn");
    if (saveTargetNode) {
      const projectId = Number(el("cohortProjectSelect")?.value || state.selectedCohortProjectId || 0);
      withAction("Project genotype target update failed", async () => {
        if (!projectId) throw new Error("Select a project first");
        const pattern = el("cohortTargetPattern").value.trim();
        if (!pattern) throw new Error("Enter a genotype target pattern");
        const current = (state.cohortInsights?.projects || []).find((row) => Number(row.id) === projectId)?.targetRules || [];
        const targets = current.map((row) => ({
          genotypePattern: row.genotypePattern,
          targetCount: row.targetCount,
          priority: row.priority,
          notes: row.notes || "",
        }));
        targets.push({
          genotypePattern: pattern,
          targetCount: Number(el("cohortTargetCount").value || 0),
          priority: targets.length + 1,
          notes: "",
        });
        await api(`/api/projects/${projectId}/genotype-targets`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ targets }),
        });
        el("cohortTargetPattern").value = "";
        await loadSampleWorkspace();
        showMessage("Project genotype target saved.", "success");
      }).catch(() => undefined);
      return;
    }
    const removeTargetNode = evt.target.closest("button[data-target-remove-id]");
    if (removeTargetNode) {
      const targetId = Number(removeTargetNode.getAttribute("data-target-remove-id"));
      const projectId = Number(el("cohortProjectSelect")?.value || state.selectedCohortProjectId || 0);
      withAction("Project genotype target removal failed", async () => {
        if (!projectId) throw new Error("Select a project first");
        const current = (state.cohortInsights?.projects || []).find((row) => Number(row.id) === projectId)?.targetRules || [];
        const targets = current
          .filter((row) => Number(row.id) !== targetId)
          .map((row, idx) => ({
            genotypePattern: row.genotypePattern,
            targetCount: row.targetCount,
            priority: idx + 1,
            notes: row.notes || "",
          }));
        await api(`/api/projects/${projectId}/genotype-targets`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ targets }),
        });
        await loadSampleWorkspace();
        showMessage("Project genotype target removed.", "success");
      }).catch(() => undefined);
      return;
    }
    const toggleNode = evt.target.closest("button[data-cohort-animal-toggle]");
    if (toggleNode) {
      const animalId = Number(toggleNode.getAttribute("data-cohort-animal-toggle"));
      setCohortAnimalSelected(animalId, !cohortAnimalSelected(animalId));
      renderCohortInsights(state.cohortInsights);
      return;
    }
    const projectNode = evt.target.closest("button[data-project-id]");
    if (projectNode) {
      withAction("Project detail load failed", () => openProjectInspector(Number(projectNode.getAttribute("data-project-id")))).catch(() => undefined);
      return;
    }
    const cageNode = evt.target.closest("button[data-sample-cage-id]");
    if (cageNode) {
      withAction("Cage detail load failed", () => openCageInspector(Number(cageNode.getAttribute("data-sample-cage-id")))).catch(() => undefined);
      return;
    }
    const animalNode = evt.target.closest("button[data-sample-animal-id]");
    if (!animalNode) return;
    withAction("Animal pedigree load failed", () => openLearningPedigree(Number(animalNode.getAttribute("data-sample-animal-id")))).catch(() => undefined);
  });

  el("cohortInsights").addEventListener("change", (evt) => {
    const projectSelect = evt.target.closest("select#cohortProjectSelect");
    if (!projectSelect) return;
    state.selectedCohortProjectId = Number(projectSelect.value || 0) || null;
    renderCohortInsights(state.cohortInsights);
  });

  el("recommendationPanel").addEventListener("click", (evt) => {
    const node = evt.target.closest("button[data-recommendation-id]");
    if (!node) return;
    const recommendationId = Number(node.getAttribute("data-recommendation-id"));
    const decision = node.getAttribute("data-recommendation-decision");
    withAction("Recommendation decision failed", async () => {
      await api(`/api/recommendations/${recommendationId}/decision`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ decision }),
      });
      await loadPlannerWorkspace();
      showMessage(`Recommendation marked ${decision}.`, "success");
    }).catch(() => undefined);
  });

  el("dashboardAlerts").addEventListener("click", (evt) => {
    const cageNode = evt.target.closest("button[data-cage-id]");
    if (cageNode) {
      withAction("Cage detail load failed", () => openCageInspector(Number(cageNode.getAttribute("data-cage-id")))).catch(() => undefined);
      return;
    }
    const ackNode = evt.target.closest("button[data-ack-alert]");
    if (!ackNode) return;
    withAction("Alert acknowledge failed", async () => {
      const id = ackNode.getAttribute("data-ack-alert");
      await api(`/api/alerts/${id}/ack`, { method: "POST", headers: headers() });
      await loadActiveAlertFeed();
      await loadDashboard();
    }).catch(() => undefined);
  });

  el("activeAlerts").addEventListener("click", (evt) => {
    const cageNode = evt.target.closest("button[data-cage-id]");
    if (cageNode) {
      withAction("Cage detail load failed", () => openCageInspector(Number(cageNode.getAttribute("data-cage-id")))).catch(() => undefined);
      return;
    }
    const ackNode = evt.target.closest("button[data-ack-alert]");
    if (!ackNode) return;
    withAction("Alert acknowledge failed", async () => {
      const id = ackNode.getAttribute("data-ack-alert");
      await api(`/api/alerts/${id}/ack`, { method: "POST", headers: headers() });
      await loadActiveAlertFeed();
      ackNode.closest(".cage-card")?.remove();
    }).catch(() => undefined);
  });

  el("dashboardLearning").addEventListener("click", (evt) => {
    const toggleNode = evt.target.closest("[data-learning-toggle-module]");
    if (toggleNode) {
      const moduleId = toggleNode.getAttribute("data-learning-toggle-module");
      const complete = !moduleComplete(moduleId);
      setModuleComplete(moduleId, complete);
      renderLearningHub(state.learning);
      showMessage(`Module ${complete ? "completed" : "reopened"}.`, "success");
      return;
    }
    const resetNode = evt.target.closest("[data-learning-reset]");
    if (resetNode) {
      writeLearningProgress({});
      renderLearningHub(state.learning);
      showMessage("Learning progress reset.", "success");
      return;
    }
    const tabNode = evt.target.closest("[data-learning-tab]");
    if (tabNode) {
      withAction("Learning module load failed", () => handleTabOpen(tabNode.getAttribute("data-learning-tab"))).catch(() => undefined);
      return;
    }
    const cageNode = evt.target.closest("[data-learning-cage-id]");
    if (cageNode) {
      withAction("Learning cage open failed", () => openCageInspector(Number(cageNode.getAttribute("data-learning-cage-id")))).catch(() => undefined);
      return;
    }
    const scanNode = evt.target.closest("[data-learning-scan-code]");
    if (scanNode) {
      withAction("Learning scan open failed", () => openLearningScan(scanNode.getAttribute("data-learning-scan-code"))).catch(() => undefined);
      return;
    }
    const animalNode = evt.target.closest("[data-learning-animal-id]");
    if (animalNode) {
      withAction("Learning pedigree open failed", () => openLearningPedigree(Number(animalNode.getAttribute("data-learning-animal-id")))).catch(() => undefined);
      return;
    }
    const projectNode = evt.target.closest("[data-learning-project-id]");
    if (!projectNode) return;
    withAction("Learning project open failed", async () => {
      if (!state.projects.length) await loadProjects();
      await openProjectInspector(Number(projectNode.getAttribute("data-learning-project-id")));
    }).catch(() => undefined);
  });

  try {
    const me = await api("/api/auth/me", { headers: headers(false) });
    setAuth("", me);
    applyRoleAccess();
    activateTab("dashboard");
    await loadCages();
    await loadActiveAlertFeed();
    await loadDashboard();
    await loadAnalytics();
    await loadCalendar();
    await loadProjects();
    try {
      await loadQuotas();
    } catch {
      el("quotaList").innerHTML = `<p class="hint">Quota view requires PI/Admin role.</p>`;
    }
    await flushMutationQueue();
    await openPendingScanIfAny();
  } catch {
    setAuth("", null);
  }

  window.addEventListener("online", () => {
    flushMutationQueue()
      .then((sent) => {
        if (sent) showMessage(`Synced ${sent} queued offline updates.`, "success");
      })
      .catch((err) => handleBackgroundError(err, "Queued update sync failed"));
  });
  setInterval(() => {
    if (!state.user) return;
    loadActiveAlertFeed().catch((err) => handleBackgroundError(err, "Background alert refresh failed"));
  }, 30000);
}

init().catch((e) => console.error(e));
