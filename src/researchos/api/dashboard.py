"""A single-file, no-build web dashboard.

Served by FastAPI at ``/``. Pure HTML + vanilla JS calling the existing JSON API — no
Node, no bundler, verifiable in CI. It covers the "project view + reasoning-trace
timeline" use case; a full React SPA remains a roadmap item.
"""

from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ResearchOS</title>
<style>
  :root { --bg:#0f1117; --panel:#171a23; --line:#262b38; --fg:#e5e7eb; --muted:#8b93a7;
          --accent:#6ea8fe; --green:#4ade80; --yellow:#fbbf24; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--fg); }
  header { padding:16px 24px; border-bottom:1px solid var(--line); display:flex;
           align-items:center; gap:12px; }
  header h1 { font-size:18px; margin:0; } header .tag { color:var(--muted); font-size:12px; }
  .wrap { display:grid; grid-template-columns:340px 1fr; gap:16px; padding:16px 24px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px; }
  .panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.05em;
              color:var(--muted); margin:0 0 10px; }
  input, button, select { font:inherit; }
  input[type=text] { width:100%; padding:8px 10px; border-radius:8px; border:1px solid var(--line);
                     background:#0d0f16; color:var(--fg); }
  button { margin-top:8px; padding:8px 12px; border:none; border-radius:8px;
           background:var(--accent); color:#0b1020; font-weight:600; cursor:pointer; }
  button.secondary { background:transparent; color:var(--fg); border:1px solid var(--line); }
  .row { padding:8px; border-radius:8px; cursor:pointer; border:1px solid transparent; }
  .row:hover { background:#0d0f16; border-color:var(--line); }
  .row small { color:var(--muted); }
  .tabs { display:flex; gap:6px; margin-bottom:10px; }
  .tabs button { margin:0; background:transparent; color:var(--muted); border:1px solid var(--line); }
  .tabs button.active { color:var(--fg); border-color:var(--accent); }
  .ev { display:flex; gap:8px; padding:4px 0; border-bottom:1px solid #1e2230; }
  .ev .actor { color:var(--accent); min-width:80px; } .ev .type { color:var(--green); min-width:120px; }
  .ev .pl { color:var(--muted); word-break:break-word; }
  .muted { color:var(--muted); } a { color:var(--accent); }
  .pill { font-size:11px; padding:1px 7px; border-radius:99px; border:1px solid var(--line); color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>ResearchOS</h1><span class="tag">Autonomous AI Research OS · dashboard</span>
</header>
<div class="wrap">
  <div>
    <div class="panel">
      <h2>New run</h2>
      <input id="goal" type="text" placeholder="e.g. long-term memory for LLM agents"/>
      <div style="display:flex;gap:8px">
        <button onclick="startRun()">Discover</button>
        <span id="status" class="muted" style="align-self:center"></span>
      </div>
    </div>
    <div class="panel" style="margin-top:16px">
      <h2>Runs</h2>
      <div id="runs" class="muted">loading…</div>
    </div>
  </div>
  <div class="panel">
    <div class="tabs">
      <button data-tab="trace" class="active" onclick="tab('trace')">Reasoning trace</button>
      <button data-tab="papers" onclick="tab('papers')">Papers</button>
      <button data-tab="memory" onclick="tab('memory')">Memory</button>
      <button data-tab="graph" onclick="tab('graph')">Graph</button>
    </div>
    <div id="trace" class="muted">Select a run to see its reasoning trace.</div>
    <div id="papers" style="display:none" class="muted">—</div>
    <div id="memory" style="display:none" class="muted">—</div>
    <div id="graph" style="display:none" class="muted">—</div>
  </div>
</div>
<script>
const PROJECT = "default";
async function j(u, opt) { const r = await fetch(u, opt); if(!r.ok) throw new Error(r.status); return r.json(); }

async function loadRuns() {
  try {
    const runs = await j("/runs");
    const el = document.getElementById("runs");
    if(!runs.length){ el.innerHTML = '<span class="muted">No runs yet.</span>'; return; }
    el.innerHTML = runs.map(r =>
      `<div class="row" onclick="openRun('${r.run_id}')">
         <div>${r.goal}</div>
         <small>${r.run_id} · <span class="pill">${r.status}</span> · ${r.project_id}</small>
       </div>`).join("");
  } catch(e){ document.getElementById("runs").textContent = "error: "+e; }
}

async function openRun(id) {
  tab('trace');
  const el = document.getElementById("trace");
  el.innerHTML = "loading…";
  const evs = await j(`/runs/${id}/events`);
  el.innerHTML = evs.map(e =>
    `<div class="ev"><span class="actor">${e.actor}</span>
      <span class="type">${e.type}</span>
      <span class="pl">${escapeHtml(JSON.stringify(e.payload))}</span></div>`).join("");
}

async function loadPapers() {
  const el = document.getElementById("papers");
  const ps = await j(`/projects/${PROJECT}/papers`);
  el.innerHTML = ps.length ? ps.map(p =>
    `<div class="row"><a href="${p.url}" target="_blank">${p.title}</a>
       <small> — ${p.source} ${p.published||''}</small></div>`).join("")
    : '<span class="muted">No papers yet.</span>';
}

async function loadMemory() {
  const el = document.getElementById("memory");
  const ms = await j(`/projects/${PROJECT}/memory`);
  el.innerHTML = ms.length ? ms.map(m =>
    `<div class="row"><span class="pill">${m.ref_type}</span>
       ${m.pinned?'📌 ':''}<b>${m.salience.toFixed(2)}</b> — ${escapeHtml(m.content)}</div>`).join("")
    : '<span class="muted">No memory items yet.</span>';
}

const GRAPH_COLORS = {paper:"#6ea8fe", concept:"#4ade80", method:"#fbbf24", dataset:"#c084fc", venue:"#f472b6", default:"#8b93a7"};
async function loadGraph() {
  const el = document.getElementById("graph");
  el.innerHTML = "loading…";
  const g = await j(`/projects/${PROJECT}/graph/viz`);
  const nodes = g.nodes.slice(0, 120);
  if(!nodes.length){ el.innerHTML = '<span class="muted">No graph yet — run a discovery first.</span>'; return; }
  const ids = new Set(nodes.map(n => n.id));
  const edges = g.edges.filter(e => ids.has(e.source) && ids.has(e.target));
  const W = 640, H = 480, cx = W/2, cy = H/2, R = Math.min(cx, cy) - 44;
  const pos = {};
  nodes.forEach((n, i) => { const a = 2*Math.PI*i/nodes.length - Math.PI/2; pos[n.id] = [cx + R*Math.cos(a), cy + R*Math.sin(a)]; });
  const lines = edges.map(e => { const [x1, y1] = pos[e.source], [x2, y2] = pos[e.target];
    return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="#262b38" stroke-width="1"/>`; }).join("");
  const dots = nodes.map(n => { const [x, y] = pos[n.id]; const c = GRAPH_COLORS[n.node_type] || GRAPH_COLORS.default;
    return `<g><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="${c}"><title>${escapeHtml(n.label)}</title></circle>
      <text x="${x.toFixed(1)}" y="${(y-10).toFixed(1)}" text-anchor="middle" font-size="9" fill="#8b93a7">${escapeHtml(n.label.slice(0, 26))}</text></g>`; }).join("");
  el.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${lines}${dots}</svg>
    <div class="muted" style="margin-top:8px">${nodes.length} nodes · ${edges.length} edges · nodes colored by type (paper/concept/…)</div>`;
}

function tab(name) {
  for(const t of ["trace","papers","memory","graph"]) document.getElementById(t).style.display = t===name?"block":"none";
  document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab===name));
  if(name==="papers") loadPapers(); if(name==="memory") loadMemory(); if(name==="graph") loadGraph();
}

async function startRun() {
  const goal = document.getElementById("goal").value.trim();
  if(!goal) return;
  const s = document.getElementById("status"); s.textContent = "running… (this can take ~30s)";
  try {
    const res = await j(`/projects/${PROJECT}/runs`, {
      method:"POST", headers:{"content-type":"application/json"},
      body: JSON.stringify({goal, limit:15, top_cards:3})
    });
    s.textContent = `done · ${res.papers} papers · score ${res.summary?'':''}`;
    await loadRuns(); openRun(res.run_id);
  } catch(e){ s.textContent = "error: "+e; }
}

function escapeHtml(x){ return (x||"").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
loadRuns();
</script>
</body>
</html>
"""
