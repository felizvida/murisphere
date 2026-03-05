const state = {
  token: "",
  user: null,
  cages: [],
  cards: [],
  alerts: [],
  alertsByCage: {},
};
const PENDING_SCAN_KEY = "murisphere_pending_scan";
const SCAN_BASE_KEY = "murisphere_scan_base_url";
const MUTATION_QUEUE_KEY = "murisphere_mutation_queue";
const SEVERITY_RANK = { high: 3, medium: 2, low: 1 };

const el = (id) => document.getElementById(id);

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
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

function mutationQueueKey() {
  return `${MUTATION_QUEUE_KEY}:${state.user?.id || "anon"}`;
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
    } catch {
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
      <thead><tr><th>ID</th><th>Cage</th><th>Alert</th><th>Strain</th><th>Genotype</th><th>Status</th><th>M/F</th><th>Location</th></tr></thead>
      <tbody>
        ${rows
          .map(
            (c) => {
              const alerts = alertsByCage[c.id] || [];
              const rowClass = alerts.length ? `alert-${severityClass(alerts[0].severity)}` : "";
              return `
          <tr class="${rowClass}">
            <td>${esc(c.id)}</td><td>${esc(c.cageCode)}</td><td>${alertBadge(alerts)}</td><td>${esc(c.strain)}</td><td>${esc(c.genotypeSummary)}</td><td>${esc(c.breedingStatus)}</td>
            <td>${esc(c.maleCount)}/${esc(c.femaleCount)}</td><td>${esc(c.room)} / ${esc(c.rack)}</td>
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
            <td>${esc(p.project_code)}</td><td>${esc(p.title)}</td><td>${esc(p.status)}</td>
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
  return `
    <article class="print-card">
      <div class="card-top">
        <strong>${esc(c.cageCode)}</strong>
        <span>${esc(c.location)}</span>
      </div>
      <div class="card-meta">
        <div>Strain: ${esc(c.strain)}</div>
        <div>Genotype: ${esc(c.genotype)}</div>
        <div>PI/Lab: ${esc(c.piLab)}</div>
        <div>Status: ${esc(c.breedingStatus)}</div>
        <div>DOB: ${esc(c.dob || "N/A")}</div>
        <div>M/F: ${esc(c.animalCount.M)}/${esc(c.animalCount.F)}</div>
        <div>Protocol: ${esc(c.protocol || "N/A")}</div>
      </div>
      <div class="scan-block">
        <img class="qrcode" data-qr="${esc(scanUrlForCard(c))}" alt="QR code" />
        <img class="barcode" data-barcode="${esc(c.cageCode)}" alt="Barcode" />
      </div>
      <div class="card-foot">Scan URL: ${esc(scanUrlForCard(c))}</div>
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
    alert("No cages available to print.");
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
    alert("Please allow popups to print cage cards.");
    return;
  }
  win.document.write(`
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <title>Murisphere Cage Cards</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 12px; color: #111; }
          .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(325px, 1fr)); gap: 10px; }
          .print-card { border: 1px solid #222; border-radius: 6px; padding: 8px; break-inside: avoid; min-height: 205px; }
          .card-top { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
          .card-meta { font-size: 11px; line-height: 1.25; margin-bottom: 8px; }
          .scan-block { display: grid; grid-template-columns: 102px minmax(0, 1fr); gap: 8px; align-items: center; }
          .qrcode { width: 98px; height: 98px; border: 1px solid #111; border-radius: 4px; object-fit: contain; background: #fff; }
          .barcode { width: 100%; height: 66px; }
          .card-foot { margin-top: 6px; font-size: 10px; }
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
  el("cageTable").innerHTML = tableFromCages(list, state.alertsByCage);
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
  if (!state.token) return;
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
  }
  renderCageVisuals();
  renderComplianceVisuals(state.alerts, []);
}

function alertCardMarkup(alert) {
  return `<div class="cage-card">
    <strong>${esc(alert.title)}</strong> <span class="alert-pill ${esc(severityClass(alert.severity))}">${esc(alert.severity.toUpperCase())}</span><br/>
    Cage: ${esc(alert.cage_code || "N/A")} | ${esc(alert.category)}<br/>
    ${esc(alert.message)}<br/>
    <button data-ack-alert="${esc(alert.id)}">Acknowledge</button>
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
        alert("Saved with audit log.");
      } catch (err) {
        enqueueMutation(`/api/cages/${c.id}`, req);
        alert(`Network issue: queued locally and will retry automatically. (${err.message})`);
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
  if (!token || !state.token) return;
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
  el("projectList").innerHTML = rows.length ? tableFromProjects(rows) : `<p class="hint">No projects yet.</p>`;
}

async function loadQuotas() {
  const rows = await api("/api/facility/quotas", { headers: headers(false) });
  el("quotaList").innerHTML = rows.length ? tableFromQuotas(rows) : `<p class="hint">No quota data.</p>`;
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

async function init() {
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      activateTab(btn.dataset.tab);
      if (btn.dataset.tab === "analytics") loadAnalytics().catch(console.error);
      if (btn.dataset.tab === "breeding") loadCalendar().catch(console.error);
      if (btn.dataset.tab === "scan") loadPedigreeViz().catch(() => undefined);
      if (btn.dataset.tab === "compliance") {
        loadActiveAlertFeed().catch(() => undefined);
      }
      if (btn.dataset.tab === "projects") {
        loadProjects().catch(console.error);
        loadQuotas().catch(console.error);
      }
    });
  });

  el("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: el("email").value, password: el("password").value }),
      });
      setAuth(data.token, data.user);
      await loadCages();
      await loadActiveAlertFeed();
      await loadProjects();
      await openPendingScanIfAny();
    } catch (err) {
      alert(err.message);
    }
  });

  el("scanBtn").addEventListener("click", runScan);
  el("loadPedigreeBtn").addEventListener("click", loadPedigreeViz);
  el("refreshCages").addEventListener("click", () => loadCages());
  el("searchBtn").addEventListener("click", () => loadCages(el("searchCages").value));
  el("scanBaseUrl").value = normalizedScanBase();
  el("saveScanBaseBtn").addEventListener("click", () => {
    const v = el("scanBaseUrl").value.trim().replace(/\/+$/, "");
    if (!v) {
      alert("Enter a valid reachable base URL.");
      return;
    }
    localStorage.setItem(SCAN_BASE_KEY, v);
    if (v.includes("localhost") || v.includes("127.0.0.1")) {
      alert("Saved, but localhost/127.0.0.1 is not reachable from phones. Use LAN IP or public domain.");
      return;
    }
    alert(`Saved scan base URL: ${v}`);
  });

  el("printCardsBtn").addEventListener("click", generateCards);
  el("quickPrintBtn").addEventListener("click", printCardsDirect);

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
      alert("Breeding event scheduled.");
    } catch (err) {
      enqueueMutation("/api/breeding/events", req);
      alert(`Network issue: event queued locally. (${err.message})`);
    }
  });

  el("projectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
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
    alert("Project created.");
  });
  el("refreshProjectsBtn").addEventListener("click", () => loadProjects());
  el("loadQuotasBtn").addEventListener("click", () => loadQuotas());

  el("genoUploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append("file", el("genoFile").files[0]);
    const res = await fetch("/api/genotyping/upload", { method: "POST", credentials: "same-origin", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    alert(`Updated ${data.updatedAnimals} animals.`);
  });

  el("excelImportForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append("file", el("excelFile").files[0]);
    const res = await fetch("/api/import/excel", { method: "POST", credentials: "same-origin", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Import failed");
    alert(`Imported ${data.created} cages.`);
    await loadCages();
  });

  el("loadAlertsBtn").addEventListener("click", async () => {
    const alerts = await api("/api/compliance/protocol-alerts", { headers: headers(false) });
    el("alerts").innerHTML = alerts
      .map((a) => `<div class="cage-card">${esc(a.protocol_number)} | ${esc(a.title)} | Expires ${esc(a.expires_on)}</div>`)
      .join("");
    renderComplianceVisuals(state.alerts, alerts);
  });

  el("loadAlertFeedBtn").addEventListener("click", async () => {
    const alerts = await api("/api/alerts/feed?status=active", { headers: headers(false) });
    el("activeAlerts").innerHTML = alerts.length ? alerts.map(alertCardMarkup).join("") : `<p class="hint">No active alerts.</p>`;
    el("activeAlerts")
      .querySelectorAll("button[data-ack-alert]")
      .forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-ack-alert");
          await api(`/api/alerts/${id}/ack`, { method: "POST", headers: headers() });
          await loadActiveAlertFeed();
          btn.closest(".cage-card")?.remove();
        });
      });
  });

  el("dispatchAlertsBtn").addEventListener("click", async () => {
    const result = await api("/api/alerts/dispatch", { method: "POST", headers: headers() });
    alert(`Dispatch complete. sent=${result.dispatched}, failed=${result.failed}, simulated=${result.simulated}`);
  });

  el("loadAuditBtn").addEventListener("click", async () => {
    const logs = await api("/api/audit", { headers: headers(false) });
    el("audit").innerHTML = logs
      .slice(0, 40)
      .map((l) => `<div class="cage-card">${esc(l.created_at)} | ${esc(l.actor || "System")} | ${esc(l.entity_type)}#${esc(l.entity_id)} | ${esc(l.action)}</div>`)
      .join("");
  });

  el("loadRequestsBtn").addEventListener("click", async () => {
    const rows = await api("/api/requests", { headers: headers(false) });
    el("requests").innerHTML = rows
      .slice(0, 40)
      .map((r) => `<div class="cage-card">${esc(r.created_at)} | ${esc(r.request_type)} | ${esc(r.status)} | ${esc(r.lab_name)}</div>`)
      .join("");
  });

  el("loadSlaBtn").addEventListener("click", async () => {
    const rows = await api("/api/operations/sla", { headers: headers(false) });
    el("sla").innerHTML = rows
      .slice(0, 40)
      .map((r) => `<div class="cage-card">${esc(r.request_type)} | ${esc(r.status)} | avg ${Number(r.avg_hours || 0).toFixed(1)}h | n=${esc(r.n)}</div>`)
      .join("");
  });

  try {
    const me = await api("/api/auth/me", { headers: headers(false) });
    setAuth("", me);
    await loadCages();
    await loadActiveAlertFeed();
    await loadAnalytics();
    await loadCalendar();
    await loadProjects();
    await flushMutationQueue();
    await openPendingScanIfAny();
  } catch {
    setAuth("", null);
  }

  window.addEventListener("online", () => {
    flushMutationQueue().catch(() => undefined);
  });
  setInterval(() => {
    loadActiveAlertFeed().catch(() => undefined);
  }, 30000);
}

init().catch((e) => console.error(e));
