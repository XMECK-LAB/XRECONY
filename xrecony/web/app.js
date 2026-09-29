const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { page: 1, category: "", view: "source", query: "", generations: [], status: null, polling: null };
const phaseOrder = ["probe", "enumerate", "account", "integrity", "certify"];
let connectionFailures = 0;

function connectionState(mode, message = "") {
  const gate = $("startupGate");
  const retry = $("retryConnection");
  const dot = $("connectionDot");
  if (dot) dot.className = mode;
  if ($("connectionLabel")) $("connectionLabel").textContent =
    mode === "online" ? "LOCAL ONLINE" : mode === "offline" ? "RECONNECTING" : "CONNECTING";
  if (!gate) return;
  if (mode === "online") {
    gate.classList.add("ready");
    window.setTimeout(() => { gate.hidden = true; }, 360);
    return;
  }
  gate.hidden = false;
  gate.classList.remove("ready");
  $("startupTitle").textContent = mode === "offline" ? "Reconnecting XRECONY" : "Starting reconstruction studio";
  $("startupMessage").textContent = message || (mode === "offline"
    ? "The local workspace is restarting. Your source is unchanged."
    : "Connecting the private local workspace…");
  retry.hidden = mode !== "offline";
}

function updateDesktopClock() {
  const clock = $("desktopClock");
  if (!clock) return;
  clock.textContent = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  }).format(new Date());
}
updateDesktopClock();
setInterval(updateDesktopClock, 1000);

async function api(path, options = {}) {
  let response;
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      response = await fetch(path, {
        headers: {"Content-Type": "application/json", ...(options.headers || {})},
        ...options
      });
      connectionFailures = 0;
      connectionState("online");
      break;
    } catch (error) {
      connectionFailures += 1;
      connectionState("offline");
      await new Promise(resolve => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }
  if (!response) throw new Error("XRECONY local service is reconnecting");
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = {error: text}; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("show");
  setTimeout(() => $("toast").classList.remove("show"), 2600);
}

function fmtBytes(n) {
  n = Number(n || 0);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n >= 100 || i === 0 ? n.toFixed(0) : n.toFixed(1)} ${units[i]}`;
}

function fmtSeconds(n) {
  n = Number(n || 0);
  if (n < 60) return `${n.toFixed(2)}s`;
  return `${Math.floor(n / 60)}m ${(n % 60).toFixed(1)}s`;
}

function showPanel(name) {
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.dataset.panel === name));
  document.querySelectorAll(".nav button").forEach(b => b.classList.toggle("active", b.dataset.target === name));
  if (name === "twin") loadRecords();
  if (name === "evolution") loadEvolution();
  if (name === "proof") loadProof();
  if (name === "benchmark") loadBenchmark();
  if (name === "insights") loadInsights();
  if (name === "fabric") loadFabric();
}

document.querySelectorAll(".nav button").forEach(button => button.addEventListener("click", () => showPanel(button.dataset.target)));

async function chooseFolder(target) {
  try {
    const result = await api("/api/dialog/folder", {method: "POST", body: JSON.stringify({purpose: target})});
    if (result.path) {
      $(target).value = result.path;
      if (target === "source") probeSource();
    }
  } catch (error) { $("startError").textContent = error.message; }
}

async function probeSource() {
  const source = $("source").value.trim();
  if (!source) return;
  try {
    const result = await api("/api/source/probe", {method: "POST", body: JSON.stringify({source})});
    $("sourceProbe").innerHTML = result.ok
      ? `<strong>Source ready</strong><br>${esc(result.adapter)} · ${esc(result.filesystem || "filesystem")} · ${result.readable ? "readable" : "not readable"}`
      : `<strong>Source unavailable</strong><br>${esc(result.error || "Check the selected path.")}`;
  } catch (error) { $("sourceProbe").textContent = error.message; }
}

async function openWorkspace() {
  const workspace = $("workspace").value.trim();
  if (!workspace) return;
  try {
    await api("/api/workspace/open", {method: "POST", body: JSON.stringify({workspace})});
    toast("Workspace opened");
    await refreshAll();
  } catch (error) { $("startError").textContent = error.message; }
}

async function startReconstruction() {
  $("startError").textContent = "";
  $("start").disabled = true;
  $("start").textContent = "STARTING…";
  const mode = document.querySelector('input[name="mode"]:checked')?.value || "reference";
  try {
    await api("/api/reconstruct/start", {
      method: "POST",
      body: JSON.stringify({
        source: $("source").value.trim(),
        workspace: $("workspace").value.trim(),
        mode,
        cold_warm_declaration: $("coldWarm").value
      })
    });
    toast("Reconstruction started");
    beginPolling();
  } catch (error) {
    $("startError").textContent = error.message;
    $("start").disabled = false;
    $("start").textContent = "SEAL SCOPE & RECONSTRUCT";
  }
}

async function cancelReconstruction() {
  try {
    await api("/api/reconstruct/cancel", {method: "POST", body: "{}"});
    toast("Cancellation requested");
    $("cancel").disabled = true;
    $("cancel").textContent = "CANCELLING…";
  } catch (error) { $("startError").textContent = error.message; }
}

function updatePhases(stage, running, complete) {
  const mapped = {"queued":"probe", "scope-sealed":"probe", "enumerating":"enumerate", "accounting":"account", "preparing-fabric":"account", "compiling-fabric":"account", "integrity":"integrity", "certifying":"certify", "certified":"certify"}[stage] || stage;
  const current = phaseOrder.indexOf(mapped);
  phaseOrder.forEach((name, i) => {
    const el = document.querySelector(`[data-phase="${name}"]`);
    el.className = "phase";
    if (complete || i < current) el.classList.add("done");
    else if (running && i === current) el.classList.add("live");
  });
}

function updateFlow(s, terminalState) {
  const engine = $("flowEngine");
  const stage = String(s.stage || "ready");
  engine.classList.toggle("running", !!s.running);
  engine.classList.toggle("complete", terminalState === "completed");
  engine.classList.toggle("cancelled", terminalState === "cancelled");
  engine.dataset.stage = stage;
  $("flowStage").textContent = s.running ? stage.replaceAll("-", " ").toUpperCase() : terminalState.toUpperCase();
  $("flowLabel").textContent = s.message || "Scope awaiting seal";
  $("flowPercent").textContent = `${String(Math.round(Number(s.progress_percent || (terminalState === "completed" ? 100 : 0)))).padStart(3, "0")}%`;
  $("flowProtocol").textContent = ({
    enumerating: "METADATA://CAPTURE",
    accounting: "INDEX://ACCOUNT",
    "preparing-fabric": "XRF://PREPARE",
    "compiling-fabric": "XRF://COMPILE",
    integrity: "PROOF://INTEGRITY",
    certifying: "PROOF://CERTIFY",
    certified: "STATE://CERTIFIED",
    completed: "STATE://CERTIFIED",
    cancelled: "STATE://CANCELLED",
    failed: "STATE://FAILED",
  })[stage] || "METADATA://D0-D1";
  $("telemetryMode").textContent = String(s.mode || "normal").toUpperCase();
  $("telemetryAdapter").textContent = s.adapter || "XRF ENGINE";
  $("telemetryClock").textContent = fmtSeconds(s.elapsed_seconds || 0);
}

async function loadStatus() {
  try {
    const s = await api("/api/status");
    state.status = s;
    $("source").value ||= s.source || "";
    $("workspace").value ||= s.workspace || "";
    $("workspaceState").textContent = s.workspace ? `Workspace: ${s.workspace}` : "No workspace opened";
    $("dockWorkspace").textContent = s.workspace ? `WORKSPACE · ${s.workspace}` : "NO WORKSPACE";
    $("dockEngine").textContent = `${String(s.adapter || "XRF ENGINE").toUpperCase()} · ${s.running ? "RUNNING" : "READY"}`;
    const terminalState = s.last_result?.state || s.state || "idle";
    $("state").textContent = s.running ? "RUNNING" : terminalState === "completed" ? "CERTIFIED" : terminalState.toUpperCase();
    const percent = Number(s.progress_percent || (terminalState === "completed" ? 100 : 0));
    $("stage").textContent = s.running ? `${s.message || s.stage || "starting"} — ${percent.toFixed(0)}%` : (s.message || "Ready for a scope-bound reconstruction.");
    $("progressBar").style.width = `${percent}%`;
    $("start").disabled = !!s.running;
    $("start").textContent = s.running ? "RECONSTRUCTION RUNNING" : "SEAL SCOPE & RECONSTRUCT";
    $("cancel").disabled = !s.running;
    $("cancel").textContent = s.running && String(s.message || "").startsWith("Cancellation requested") ? "CANCELLING…" : "CANCEL SAFELY";
    $("rollback").disabled = !!s.running || !s.can_rollback;
    $("rollbackHint").textContent = s.can_rollback ? "An earlier reconstruction is available." : "Create a second reconstruction to unlock rollback.";
    const r = s.last_result || {};
    $("records").textContent = Number(r.records || 0).toLocaleString();
    $("logical").textContent = fmtBytes(r.logical_bytes);
    $("files").textContent = Number(r.files || 0).toLocaleString();
    $("directories").textContent = Number(r.directories || 0).toLocaleString();
    $("rate").textContent = Number(r.records_per_second || 0).toLocaleString(undefined, {maximumFractionDigits: 0});
    $("elapsed").textContent = fmtSeconds(r.elapsed_seconds);
    $("errors").textContent = Number(r.errors || 0).toLocaleString();
    $("integrity").textContent = (r.integrity_state || "—").toUpperCase();
    updateFlow(s, terminalState);
    updatePhases(s.stage, s.running, terminalState === "completed");
    if (!s.running && state.polling) {
      clearInterval(state.polling); state.polling = null;
      await Promise.allSettled([loadEvolution(), loadRecords()]);
    }
    return s;
  } catch (error) {
    $("stage").textContent = "Reconnecting local workspace…";
  }
}

function beginPolling() {
  if (state.polling) return;
  loadStatus();
  state.polling = setInterval(loadStatus, 450);
}

async function loadRecords() {
  try {
    const params = new URLSearchParams({page: state.page, view: state.view, q: state.query});
    if (state.category) params.set("category", state.category);
    const data = await api(`/api/records?${params}`);
    $("resultCount").textContent = `${Number(data.total || 0).toLocaleString()} objects`;
    $("pageLabel").textContent = `Page ${data.page} / ${Math.max(1, data.pages)}`;
    $("prev").disabled = data.page <= 1;
    $("next").disabled = data.page >= data.pages;
    $("recordRows").innerHTML = data.records.map(record => `
      <tr data-id="${esc(record.id)}">
        <td class="path"><strong>${esc(record.name)}</strong><br><small>${esc(record.path)}</small></td>
        <td class="path">${esc(record.reconstructed_path || "—")}</td>
        <td>${esc(record.category)}</td>
        <td>${fmtBytes(record.logical_size ?? record.size)}</td>
        <td>${esc(record.modified_year || "—")}</td>
        <td><span class="status">${esc(record.state || "placed")}</span></td>
      </tr>`).join("");
    $("recordRows").querySelectorAll("tr").forEach(row => row.addEventListener("click", () => loadRecordDetail(row.dataset.id)));
    renderFacets(data.facets || {});
    const selected = state.category;
    $("category").innerHTML = `<option value="">All categories</option>` +
      Object.entries(data.facets || {}).sort((a,b) => b[1] - a[1]).map(([name,count]) =>
        `<option value="${esc(name)}">${esc(name)} (${Number(count).toLocaleString()})</option>`).join("");
    $("category").value = selected;
  } catch (error) {
    $("recordRows").innerHTML = `<tr><td colspan="6">${esc(error.message)}</td></tr>`;
  }
}

function renderFacets(facets) {
  const total = Object.values(facets).reduce((a, b) => a + Number(b), 0);
  const items = [["", "All objects", total], ...Object.entries(facets).sort((a,b) => b[1] - a[1]).map(([name,count]) => [name, name, count])];
  $("facets").innerHTML = `<div class="section-label">Facets</div>` + items.map(([key, label, count]) =>
    `<button class="facet ${state.category === key ? "active" : ""}" data-category="${esc(key)}"><span>${esc(label)}</span><strong>${Number(count).toLocaleString()}</strong></button>`
  ).join("");
  $("facets").querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    state.category = b.dataset.category; state.page = 1; loadRecords();
  }));
}

async function loadRecordDetail(id) {
  try {
    const r = await api(`/api/records/${encodeURIComponent(id)}`);
    const fields = [["Object", r.name], ["Source path", r.path], ["Reconstructed path", r.reconstructed_path], ["Category", r.category], ["Logical size", fmtBytes(r.logical_size ?? r.size)], ["Modified", r.modified_utc || r.mtime], ["Evidence", r.evidence || "metadata"]];
    $("recordDetail").innerHTML = `<div class="section-label">Object evidence</div><div class="detail-list">${fields.map(([k,v]) => `<div><small>${esc(k)}</small><strong>${esc(v ?? "—")}</strong></div>`).join("")}</div>`;
  } catch (error) { $("recordDetail").textContent = error.message; }
}

async function loadEvolution() {
  try {
    const data = await api("/api/generations");
    state.generations = data.generations || [];
    $("generationCount").textContent = `${state.generations.length} saved`;
    $("generations").innerHTML = state.generations.length ? state.generations.map(g => `
      <div class="generation ${g.active ? "active" : ""}">
        <div><strong>${esc(g.generation_id)}</strong><small>${Number(g.accounting?.records || 0).toLocaleString()} records · ${esc(g.created_utc || "")}</small></div>
        ${g.active ? '<span class="status">Active</span>' : `<button class="button ghost activate" data-id="${esc(g.generation_id)}">Activate</button>`}
      </div>`).join("") : `<div class="detail-empty">No saved reconstruction yet.</div>`;
    document.querySelectorAll(".activate").forEach(b => b.addEventListener("click", () => activateGeneration(b.dataset.id)));
    const options = state.generations.map(g => `<option value="${esc(g.generation_id)}">${esc(g.generation_id)}</option>`).join("");
    $("diffFrom").innerHTML = options;
    $("diffTo").innerHTML = options;
    if (state.generations.length > 1) $("diffFrom").selectedIndex = 1;
    await loadAudit();
  } catch (error) { $("generations").textContent = error.message; }
}

async function activateGeneration(id) {
  try {
    await api("/api/generations/activate", {method:"POST", body: JSON.stringify({generation_id: id})});
    toast("Generation activated"); await refreshAll();
  } catch (error) { toast(error.message); }
}

async function rollback() {
  try {
    await api("/api/generations/rollback", {method:"POST", body:"{}"});
    toast("Active view rolled back"); await refreshAll();
  } catch (error) { toast(error.message); }
}

async function compareGenerations() {
  try {
    const data = await api("/api/generations/diff", {method:"POST", body: JSON.stringify({from: $("diffFrom").value, to: $("diffTo").value})});
    const rows = [
      ...(data.added || []).map(path => ({type:"added", path, fields:{}})),
      ...(data.removed || []).map(path => ({type:"removed", path, fields:{}})),
      ...(data.changed || []).map(item => ({type:"changed", ...item}))
    ];
    $("diffResult").innerHTML = `<div class="diff-grid">
      <div class="diff-box"><strong>${data.counts?.added || 0}</strong><small>Added</small></div>
      <div class="diff-box"><strong>${data.counts?.removed || 0}</strong><small>Removed</small></div>
      <div class="diff-box"><strong>${data.counts?.changed || 0}</strong><small>Changed</small></div>
    </div><div class="delta-list">${rows.slice(0,100).map(item => `
      <div class="delta-row ${item.type}"><span>${esc(item.type)}</span><strong>${esc(item.path)}</strong>
      <small>${esc(Object.entries(item.fields || {}).map(([key,value]) => `${key}: ${value.before} → ${value.after}`).join(" · ") || "path state change")}</small></div>`).join("") || '<p class="detail-empty">No structural changes.</p>'}</div>`;
  } catch (error) { $("diffResult").textContent = error.message; }
}

async function loadAudit() {
  try {
    const data = await api("/api/audit");
    $("auditEvents").innerHTML = (data.events || []).map(e => `
      <div class="audit-item"><strong>${esc(e.event || e.action || "event")}</strong><small>${esc(e.timestamp_utc || e.created_utc || "")} · ${esc(e.details?.generation_id || e.details?.to || "")}</small></div>`).join("") || `<div class="detail-empty">No audit events yet.</div>`;
  } catch (error) { $("auditEvents").textContent = error.message; }
}

async function loadProof() {
  try {
    const [receipt, human] = await Promise.all([api("/api/receipt"), api("/api/receipt/human")]);
    $("receipt").textContent = JSON.stringify(receipt, null, 2);
    $("humanReceipt").textContent = [
      human.title,
      `Generation: ${human.generation_id}`,
      `Source: ${human.source}`,
      "",
      human.accounting_equation,
      `Accounting verified: ${human.verified_accounting ? "YES" : "NO"}`,
      `Source integrity: ${human.source_integrity?.state || "unknown"}`,
      `Source changed by XRECONY: ${human.source_mutation_performed ? "YES" : "NO"}`,
      `Elapsed: ${fmtSeconds(human.elapsed_seconds)}`,
      `Adapter: ${human.adapter}`,
      "",
      "Status: ready to verify"
    ].join("\n");
    $("receiptGeneration").textContent = receipt.generation_id || "No generation";
  } catch (error) {
    $("receipt").textContent = error.message; $("humanReceipt").textContent = "Create a reconstruction first.";
  }
}

async function verifyReceipt() {
  try {
    const result = await api("/api/receipt/verify", {method:"POST", body:"{}"});
    $("verifyResult").textContent = result.valid ? "✓ Receipt, accounting, stream hash and source evidence verified" : `Verification failed: ${result.reason || "unknown"}`;
  } catch (error) { $("verifyResult").textContent = error.message; }
}

async function loadBenchmark() {
  try {
    const b = await api("/api/benchmark");
    $("benchmarkSummary").innerHTML = `
      <div class="benchmark-hero">
        <div><div class="eyebrow">Observed run</div><div class="benchmark-number">${Number(b.timing?.records_per_second || 0).toLocaleString(undefined,{maximumFractionDigits:0})}<span> rec/s</span></div><p>${Number(b.accounting?.records || 0).toLocaleString()} records in ${fmtSeconds(b.timing?.elapsed_seconds)}</p></div>
        <div class="performance-mark"><strong>${Number(b.accounting?.errors || 0)}</strong><small>errors</small></div>
      </div>
      <div class="benchmark-grid">
        <div class="metric"><strong>${fmtBytes(b.source?.logical_bytes)}</strong><small>Logical data</small></div>
        <div class="metric"><strong>${Number(b.source?.files || 0).toLocaleString()}</strong><small>Files</small></div>
        <div class="metric"><strong>${esc(b.cold_warm_declaration || "unspecified")}</strong><small>Cache declaration</small></div>
        <div class="metric"><strong>${esc(b.environment?.adapter || "reference")}</strong><small>Adapter</small></div>
      </div>`;
    $("claimBoundary").textContent = b.claim_boundary || "";
  } catch (error) { $("benchmarkSummary").textContent = "Run a reconstruction to see its performance."; }
}

async function loadInsights() {
  try {
    const data = await api("/api/intelligence");
    const summary = data.summary || {};
    $("insightSummary").innerHTML = [
      ["Duplicate groups", summary.duplicate_candidate_groups || 0],
      ["Version families", summary.version_family_candidates || 0],
      ["Empty folders", summary.empty_folders || 0],
      ["Categories", summary.categories || 0]
    ].map(([label,value]) => `<div class="metric"><strong>${Number(value).toLocaleString()}</strong><small>${esc(label)}</small></div>`).join("");
    $("duplicateCandidates").innerHTML = (data.duplicate_candidates || []).slice(0,100).map(group =>
      `<div class="delta-row changed"><span>${group.count} files</span><strong>${fmtBytes(group.size)} · ${esc(group.extension || "no extension")}</strong><small>${esc(group.paths.slice(0,5).join(" · "))}</small></div>`
    ).join("") || '<p class="detail-empty">No metadata duplicate candidates.</p>';
    $("versionFamilies").innerHTML = (data.version_families || []).slice(0,100).map(group =>
      `<div class="delta-row changed"><span>${group.count} files</span><strong>${esc(group.signature)}</strong><small>${esc(group.paths.slice(0,5).join(" · "))}</small></div>`
    ).join("") || '<p class="detail-empty">No filename-family candidates.</p>';
    const largest = (data.largest_files || []).slice(0,20);
    const empty = (data.empty_folders || []).slice(0,20);
    $("storageSignals").innerHTML = `<div><p class="section-label">Largest objects</p>${largest.map(item => `<div class="signal-row"><strong>${esc(item.path)}</strong><span>${fmtBytes(item.size)}</span></div>`).join("")}</div>
      <div><p class="section-label">Empty folders</p>${empty.map(path => `<div class="signal-row"><strong>${esc(path)}</strong><span>empty</span></div>`).join("") || '<p class="detail-empty">None observed.</p>'}</div>`;
  } catch (error) {
    $("insightSummary").innerHTML = `<div class="card card-pad">${esc(error.message)}</div>`;
  }
}

async function loadFabric() {
  try {
    const [graph, universe, events, connectors] = await Promise.all([
      api("/api/v1/graph"), api("/api/v1/universe"), api("/api/v1/events"), api("/api/v1/connectors")
    ]);
    const header = graph.header || {};
    $("fabricState").textContent = "CERTIFIED";
    $("fabricHeadline").textContent = `${Number(header.node_count || 0).toLocaleString()} objects · ${Number(header.relationship_count || 0).toLocaleString()} relationships`;
    $("fabricBoundary").textContent = `${header.evidence_depth || "D0/D1"} · source unchanged · graph ${String(header.graph_sha256 || "").slice(0,16)}…`;
    $("fabricMetrics").innerHTML = [
      ["Objects", header.node_count || 0], ["Relationships", header.relationship_count || 0],
      ["Diagnostics", header.diagnostic_count || 0], ["Realities", (header.realities || []).length]
    ].map(([label,value]) => `<div class="metric"><strong>${Number(value).toLocaleString()}</strong><small>${esc(label)}</small></div>`).join("");
    $("realityList").innerHTML = (header.realities || []).map((name, index) =>
      `<div class="reality"><span>0${index + 1}</span><strong>${esc(name)} view</strong><small>${index === 0 ? "original structure" : "reconstructed arrangement"}</small></div>`
    ).join("");
    $("fabricEvents").innerHTML = (events.events || []).slice().reverse().map(e =>
      `<div class="audit-item"><strong>${esc(e.sequence_event)}</strong><small>${esc(e.timestamp_utc)} · ${esc(JSON.stringify(e.details || {}))}</small></div>`
    ).join("") || '<p class="detail-empty">No reconstruction activity yet.</p>';
    $("connectorList").innerHTML = (connectors.connectors || []).map(c =>
      `<div class="connector"><div><strong>${esc(c.name)}</strong><small>${esc(c.transport)}</small></div><span class="${c.state.startsWith("operational") ? "connector-live" : "connector-contract"}">${c.state.startsWith("operational") ? "AVAILABLE" : "COMING SOON"}</span></div>`
    ).join("");
    const categories = Object.entries(universe.dimensions?.categories || {}).sort((a,b) => b[1]-a[1]).slice(0,12);
    const max = Math.max(1, ...categories.map(item => item[1]));
    $("universeDimensions").innerHTML = categories.map(([name,count]) =>
      `<div class="universe-row"><strong>${esc(name)}</strong><div><i style="width:${Math.max(2, count/max*100)}%"></i></div><span>${Number(count).toLocaleString()}</span></div>`
    ).join("");
  } catch (error) {
    $("fabricState").textContent = "IDLE";
    $("fabricHeadline").textContent = "Create or open a reconstruction";
    $("fabricBoundary").textContent = error.message;
  }
}

async function refreshAll() {
  await loadStatus();
  await Promise.allSettled([loadEvolution(), loadRecords(), loadProof(), loadBenchmark(), loadInsights(), loadFabric()]);
}

$("browseSource").addEventListener("click", () => chooseFolder("source"));
$("browseWorkspace").addEventListener("click", () => chooseFolder("workspace"));
$("source").addEventListener("change", probeSource);
$("openWorkspace").addEventListener("click", openWorkspace);
$("start").addEventListener("click", startReconstruction);
$("cancel").addEventListener("click", cancelReconstruction);
$("refresh").addEventListener("click", loadRecords);
$("prev").addEventListener("click", () => { state.page--; loadRecords(); });
$("next").addEventListener("click", () => { state.page++; loadRecords(); });
$("view").addEventListener("change", e => { state.view = e.target.value; state.page = 1; loadRecords(); });
$("category").addEventListener("change", e => { state.category = e.target.value; state.page = 1; loadRecords(); });
$("search").addEventListener("input", e => { state.query = e.target.value; state.page = 1; clearTimeout(state.searchTimer); state.searchTimer = setTimeout(loadRecords, 220); });
$("rollback").addEventListener("click", rollback);
$("compare").addEventListener("click", compareGenerations);
$("refreshAudit").addEventListener("click", loadAudit);
$("verify").addEventListener("click", verifyReceipt);
$("retryConnection").addEventListener("click", async () => {
  connectionState("connecting");
  await refreshAll();
});

connectionState("connecting");
refreshAll();
