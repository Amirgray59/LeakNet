/* LeakNet frontend — اتصال به FastAPI */
const $ = (s) => document.querySelector(s);
const SVGNS = "http://www.w3.org/2000/svg";

let NETWORK = null;
let SENSOR_COLS = [];
let DEMO = false;

/* ---------- شبیه‌سازی flip محور y برای نمایش ---------- */
const flipY = (y) => 1000 - y;

/* ---------- رسم نقشه ---------- */
function el(tag, attrs = {}) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

function drawMap() {
  const svg = $("#netmap");
  svg.innerHTML = "";
  const { nodes, pipes } = NETWORK;
  const nmap = Object.fromEntries(nodes.map((n) => [n.id, n]));

  // لوله‌ها
  for (const p of pipes) {
    const a = nmap[p.a], b = nmap[p.b];
    svg.appendChild(el("line", {
      x1: a.x, y1: flipY(a.y), x2: b.x, y2: flipY(b.y),
      class: "pipe-line", id: `pipe-${p.id}`,
    }));
  }
  // برچسب لوله‌ها
  for (const p of pipes) {
    const a = nmap[p.a], b = nmap[p.b];
    const mx = (a.x + b.x) / 2, my = (flipY(a.y) + flipY(b.y)) / 2;
    const dx = b.x - a.x, dy = flipY(b.y) - flipY(a.y);
    const len = Math.hypot(dx, dy) || 1;
    const ox = (-dy / len) * 14, oy = (dx / len) * 14;
    const t = el("text", { x: mx + ox, y: my + oy, class: "pipe-label" });
    t.textContent = p.id;
    svg.appendChild(t);
  }
  // گره‌ها
  for (const n of nodes) {
    if (n.is_reservoir) { drawReservoir(svg, n); continue; }
    const c = el("circle", {
      cx: n.x, cy: flipY(n.y), r: 18,
      class: "node-circle sensor", "data-node": n.id,
    });
    c.addEventListener("click", () => highlightSensor(n.id));
    svg.appendChild(c);
    const t = el("text", { x: n.x, y: flipY(n.y) + 5, class: "node-label" });
    t.textContent = n.id;
    svg.appendChild(t);
  }
}

function drawReservoir(svg, n) {
  const x = n.x, y = flipY(n.y);
  svg.appendChild(el("rect", {
    x: x - 12, y: y - 55, width: 130, height: 80, class: "rsv-box",
  }));
  const tri = el("polygon", {
    points: `${x + 30},${y - 55} ${x + 42},${y - 55} ${x + 36},${y - 46}`,
    fill: "none", stroke: "#38bdf8", "stroke-width": 2,
  });
  svg.appendChild(tri);
  const t = el("text", { x: x + 90, y: y - 62, class: "rsv-label" });
  t.textContent = "100 m";
  svg.appendChild(t);
  const c = el("circle", { cx: x, cy: y, r: 18, class: "node-circle reservoir" });
  svg.appendChild(c);
  const tl = el("text", { x, y: y + 5, class: "node-label" });
  tl.textContent = "1";
  svg.appendChild(tl);
}

/* ---------- نشتی روی نقشه ---------- */
function showLeak(marker, pipeId) {
  const svg = $("#netmap");
  svg.querySelectorAll(".leak-marker,.leak-pulse").forEach((e) => e.remove());
  svg.querySelectorAll(".pipe-line.leaking").forEach((e) => e.classList.remove("leaking"));
  if (!marker) return;
  const y = flipY(marker.y);
  svg.appendChild(el("circle", { cx: marker.x, cy: y, r: 8, class: "leak-pulse" }));
  svg.appendChild(el("circle", { cx: marker.x, cy: y, r: 9, class: "leak-marker" }));
  if (pipeId) $(`#pipe-${pipeId}`)?.classList.add("leaking");
}

/* ---------- ورودی سنسورها ---------- */
function buildSensorInputs() {
  const box = $("#sensors");
  box.innerHTML = "";
  SENSOR_COLS.forEach((c, i) => {
    const d = document.createElement("div");
    d.className = "sensor";
    d.innerHTML = `<label>${c}</label>
      <input id="in-${c}" type="number" step="0.001" value="${(30 - i * 0.9).toFixed(2)}">`;
    box.appendChild(d);
  });
}

function readPressures() {
  const obj = {};
  SENSOR_COLS.forEach((c) => {
    obj[c] = parseFloat($(`#in-${c}`).value) || 0;
  });
  return obj;
}

function fillPressures(sample) {
  const keys = Object.keys(sample);
  SENSOR_COLS.forEach((c, i) => {
    const v = sample[c] ?? sample[keys[i]];
    if (v !== undefined) $(`#in-${c}`).value = (+v).toFixed(3);
  });
}

function highlightSensor(nodeId) {
  const idx = NETWORK.sensor_nodes.indexOf(nodeId);
  if (idx >= 0) $(`#in-n${idx + 1}`)?.focus();
}

/* ---------- API ---------- */
async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

function setStatus(txt, cls) {
  const s = $("#status");
  s.textContent = txt;
  s.className = `status ${cls || ""}`;
}

function renderResult(data) {
  const card = $("#resultCard");
  card.hidden = false;
  const p = data.primary, lm = data.leak_map;
  let html = "";
  if (p.demo) html += `<div class="badge">⚠️ حالت دمو — مدل هنوز آموزش داده نشده</div>`;
  html += `<div class="pipe-hit">🔴 نشتی روی لوله ${lm.nearest_pipe}
    (بین گره ${lm.pipe_nodes[0]} و ${lm.pipe_nodes[1]})</div>`;
  html += `<div class="kv">
    <div class="item leakval"><span>Lx</span><b>${p.Lx.toFixed(2)}</b></div>
    <div class="item leakval"><span>Ly</span><b>${p.Ly.toFixed(2)}</b></div>
    <div class="item"><span>Lz</span><b>${(p.Lz ?? 0).toFixed(2)}</b></div>
    <div class="item"><span>Emitter</span><b>${(p.Emitter ?? 0).toFixed(3)}</b></div>
  </div>`;
  const keys = Object.keys(data.results).filter(
    (k) => data.results[k] && data.results[k].Lx !== undefined);
  if (keys.length > 1) {
    html += `<table class="cmp"><tr><th>مدل</th><th>Lx</th><th>Ly</th><th>Lz</th><th>Emitter</th></tr>`;
    for (const k of keys) {
      const r = data.results[k];
      html += `<tr><td>${k}</td><td>${r.Lx.toFixed(1)}</td><td>${r.Ly.toFixed(1)}</td>
        <td>${(r.Lz ?? 0).toFixed(1)}</td><td>${(r.Emitter ?? 0).toFixed(3)}</td></tr>`;
    }
    html += `</table>`;
  }
  $("#resultBody").innerHTML = html;
}

function renderMetrics(models) {
  const withM = models.filter((m) => m.metrics && Object.keys(m.metrics).length);
  if (!withM.length) return;
  $("#metricsCard").hidden = false;
  let html = `<table class="cmp"><tr><th>مدل</th><th>Lx</th><th>Ly</th><th>Lz</th><th>Emitter</th></tr>`;
  for (const m of withM) {
    const g = (t) => (m.metrics[t]?.r2_test ?? NaN);
    html += `<tr><td>${m.name}</td>` +
      ["Lx", "Ly", "Lz", "Emitter"].map((t) => {
        const v = g(t);
        return `<td>${isNaN(v) ? "—" : v.toFixed(3)}</td>`;
      }).join("") + `</tr>`;
  }
  html += `</table>`;
  $("#metricsBody").innerHTML = html;
}

/* ---------- رویدادها ---------- */
$("#btnPredict").addEventListener("click", async () => {
  try {
    setStatus("در حال پیش‌بینی…");
    const data = await api("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pressures: readPressures(),
        model: $("#modelSel").value,
      }),
    });
    renderResult(data);
    showLeak(data.leak_map.marker, data.leak_map.nearest_pipe);
    setStatus("پیش‌بینی انجام شد ✓", "ok");
  } catch (e) {
    setStatus("خطا: " + e.message);
  }
});

$("#btnSample").addEventListener("click", async () => {
  try {
    const j = await api("/api/sample-real");
    fillPressures(j.sample);
    setStatus("نمونه واقعی بارگذاری شد ✓", "ok");
  } catch (e) {
    setStatus("داده واقعی موجود نیست");
  }
});

$("#btnFill").addEventListener("click", () => buildSensorInputs());

$("#btnBatch").addEventListener("click", async () => {
  const f = $("#fileInput").files[0];
  if (!f) return setStatus("ابتدا فایل انتخاب کنید");
  const fd = new FormData();
  fd.append("file", f);
  try {
    setStatus("در حال پردازش فایل…");
    const j = await api(`/api/predict-file?model=${$("#modelSel").value}`, {
      method: "POST", body: fd,
    });
    // نمایش همه نشتی‌های فایل روی نقشه
    const svg = $("#netmap");
    svg.querySelectorAll(".leak-marker,.leak-pulse").forEach((e) => e.remove());
    svg.querySelectorAll(".pipe-line.leaking").forEach((e) => e.classList.remove("leaking"));
    let shown = 0;
    for (const pr of j.predictions) {
      if (!pr.marker) continue;
      const y = flipY(pr.marker.y);
      svg.appendChild(el("circle", { cx: pr.marker.x, cy: y, r: 7, class: "leak-marker" }));
      if (pr.nearest_pipe) $(`#pipe-${pr.nearest_pipe}`)?.classList.add("leaking");
      shown++;
    }
    $("#resultCard").hidden = false;
    $("#resultBody").innerHTML =
      `<div class="pipe-hit">📄 ${j.count} سطر پردازش شد — ${shown} نشتی روی نقشه نمایش داده شد</div>`;
    setStatus("پردازش فایل کامل شد ✓", "ok");
  } catch (e) {
    setStatus("خطا: " + e.message);
  }
});

/* ---------- شروع ---------- */
(async function init() {
  try {
    NETWORK = await api("/api/network");
    SENSOR_COLS = NETWORK.sensor_columns;
    drawMap();
    buildSensorInputs();
    const m = await api("/api/models");
    DEMO = m.demo_mode;
    renderMetrics(m.models);
    setStatus(DEMO ? "حالت دمو — مدل‌ها آموزش داده نشده‌اند" : "متصل ✓", DEMO ? "demo" : "ok");
  } catch (e) {
    setStatus("خطا در اتصال به سرور: " + e.message);
  }
})();
