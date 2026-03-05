const state = {
  token: "",
  user: null,
  cages: [],
  cards: [],
};
const PENDING_SCAN_KEY = "murisphere_pending_scan";
const SCAN_BASE_KEY = "murisphere_scan_base_url";

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
  if (token) {
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

function tableFromCages(rows) {
  return `
    <table class="table">
      <thead><tr><th>ID</th><th>Cage</th><th>Strain</th><th>Genotype</th><th>Status</th><th>M/F</th><th>Location</th></tr></thead>
      <tbody>
        ${rows
          .map(
            (c) => `
          <tr>
            <td>${esc(c.id)}</td><td>${esc(c.cageCode)}</td><td>${esc(c.strain)}</td><td>${esc(c.genotypeSummary)}</td><td>${esc(c.breedingStatus)}</td>
            <td>${esc(c.maleCount)}/${esc(c.femaleCount)}</td><td>${esc(c.room)} / ${esc(c.rack)}</td>
          </tr>`
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
  el("cageTable").innerHTML = tableFromCages(list);
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
        ${esc(c.room)} / ${esc(c.rack)}
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
      await api(`/api/cages/${c.id}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({
          maleCount: Number(el("uMale").value),
          femaleCount: Number(el("uFemale").value),
          breedingStatus: el("uStatus").value,
          notes: el("uNotes").value,
        }),
      });
      await loadCages();
      alert("Saved with audit log.");
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
}

async function loadCalendar() {
  const events = await api("/api/calendar", { headers: headers(false) });
  el("calendarList").innerHTML = events
    .map((e) => `<div class="cage-card">${esc(e.event_date)} | Cage ${esc(e.cage_code)} | ${esc(e.event_type)}</div>`)
    .join("");
}

async function loadProjects() {
  const rows = await api("/api/projects", { headers: headers(false) });
  el("projectList").innerHTML = rows.length ? tableFromProjects(rows) : `<p class="hint">No projects yet.</p>`;
}

async function loadQuotas() {
  const rows = await api("/api/facility/quotas", { headers: headers(false) });
  el("quotaList").innerHTML = rows.length ? tableFromQuotas(rows) : `<p class="hint">No quota data.</p>`;
}

async function init() {
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      activateTab(btn.dataset.tab);
      if (btn.dataset.tab === "analytics") loadAnalytics().catch(console.error);
      if (btn.dataset.tab === "breeding") loadCalendar().catch(console.error);
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
      await loadProjects();
      await openPendingScanIfAny();
    } catch (err) {
      alert(err.message);
    }
  });

  el("scanBtn").addEventListener("click", runScan);
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
    await api("/api/breeding/events", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        cageId: Number(el("breedCageId").value),
        eventType: el("breedType").value,
        eventDate: el("breedDate").value,
      }),
    });
    await loadCalendar();
    alert("Breeding event scheduled.");
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
  });

  el("loadAuditBtn").addEventListener("click", async () => {
    const logs = await api("/api/audit", { headers: headers(false) });
    el("audit").innerHTML = logs
      .slice(0, 40)
      .map((l) => `<div class="cage-card">${esc(l.created_at)} | ${esc(l.actor || "System")} | ${esc(l.entity_type)}#${esc(l.entity_id)} | ${esc(l.action)}</div>`)
      .join("");
  });

  try {
    const me = await api("/api/auth/me", { headers: headers(false) });
    setAuth("", me);
    await loadCages();
    await loadProjects();
    await openPendingScanIfAny();
  } catch {
    setAuth("", null);
  }
}

init().catch((e) => console.error(e));
