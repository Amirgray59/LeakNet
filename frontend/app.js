/* LeakNet frontend — ساده‌شده: فقط SVR */
const $ = (s) => document.querySelector(s);
const SVGNS = "http://www.w3.org/2000/svg";

let NETWORK = null;
let SENSOR_COLS = [];
let MODEL_METRICS = {};

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

  for (const p of pipes) {
    const a = nmap[p.a], b = nmap[p.b];
    svg.appendChild(el("line", {
      x1: a.x, y1: flipY(a.y), x2: b.x, y2: flipY(b.y),
      class: "pipe-line", id: `pipe-${p.id}`,
    }));
  }
  for (const p of pipes) {
    const a = nmap[p.a], b = nmap[p.b];
    const mx = (a.x + b.x) / 2, my = (flipY(a.y) + flipY(b.y)) / 2;
    const dx = b.x - a.x, dy = flipY(b.y) - flipY(a.y);
    const len = Math.hypot(dx, dy) || 1;
    const t = el("text", { x: mx + (-dy / len) * 14, y: my + (dx / len) * 14, class: "pipe-label" });
    t.textContent = p.id;
    svg.appendChild(t);
  }
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
  svg.appendChild(el("rect", { x: x - 12, y: y - 55, width: 130, height: 80, class: "rsv-box" }));
  svg.appendChild(el("polygon", {
    points: `${x + 30},${y - 55} ${x + 42},${y - 55} ${x + 36},${y - 46}`,
    fill: "none", stroke: "#38bdf8", "stroke-width": 2,
  }));
  const t = el("text", { x: x + 90, y: y - 62, class: "rsv-label" });
  t.textContent = "100 m";
  svg.appendChild(t);
  svg.appendChild(el("circle", { cx: x, cy: y, r: 18, class: "node-circle reservoir" }));
  const tl = el("text", { x, y: y + 5, class: "node-label" });
  tl.textContent = "1";
  svg.appendChild(tl);
}

/* ---------- نشتی روی نقشه ---------- */
function clearLeaks() {
  const svg = $("#netmap");
  svg.querySelectorAll(".leak-marker,.leak-pulse").forEach((e) => e.remove());
  svg.querySelectorAll(".pipe-line.leaking").forEach((e) => e.classList.remove("leaking"));
}

function showLeak(marker, pipeId) {
  clearLeaks();
  if (!marker) return;
  const svg = $("#netmap");
  const y = flipY(marker.y);
  svg.appendChild(el("circle", { cx: marker.x, cy: y, r: 8, class: "leak-pulse" }));
  svg.appendChild(el("circle", { cx: marker.x, cy: y, r: 9, class: "leak-marker" }));
  if (pipeId) $(`#pipe-${pipeId}`)?.classList.add("leaking");
}

/* ---------- سنسورها ---------- */
function buildSensorInputs() {
  const box = $("#sensors");
  box.innerHTML = "";
  SENSOR_COLS.forEach((c) => {
    const d = document.createElement("div");
    d.className = "sensor";
    d.innerHTML = `<label>${c}</label>
      <input id="in-${c}" type="number" step="0.001" placeholder="—">`;
    box.appendChild(d);
  });
}

function fillSensors(values) {
  SENSOR_COLS.forEach((c) => {
    const inp = $(`#in-${c}`);
    if (inp && values[c] !== undefined) {
      inp.value = (+values[c]).toFixed(3);
      inp.classList.add("filled");
    }
  });
  $("#btnPredict").disabled = !SENSOR_COLS.every((c) => $(`#in-${c}`).value !== "");
}

function readPressures() {
  const obj = {};
  SENSOR_COLS.forEach((c) => { obj[c] = parseFloat($(`#in-${c}`).value) || 0; });
  return obj;
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

/* ---------- آپلود فایل ---------- */
$("#btnUpload").addEventListener("click", async () => {
  const f = $("#fileInput").files[0];
  if (!f) return setStatus("ابتدا فایل انتخاب کنید", "err");
  const fd = new FormData();
  fd.append("file", f);
  try {
    setStatus("در حال خواندن فایل…");
    const j = await api("/api/upload-sensors", { method: "POST", body: fd });
    fillSensors(j.values);
    const info = $("#uploadInfo");
    info.hidden = false;
    info.textContent = `✓ ${j.n_rows} سطر خوانده شد — سطر آخر در پنل سنسورها قرار گرفت (${j.columns.length} ستون)`;
    setStatus("مقادیر سنسورها بارگذاری شد ✓", "ok");
  } catch (e) {
    setStatus("خطا: " + e.message, "err");
  }
});

/* فعال‌سازی دکمه پیش‌بینی وقتی همه سنسورها پر شدند */
$("#sensors").addEventListener("input", () => {
  $("#btnPredict").disabled = !SENSOR_COLS.every((c) => $(`#in-${c}`).value.trim() !== "");
});

/* ---------- پیش‌بینی ---------- */
$("#btnPredict").addEventListener("click", async () => {
  try {
    setStatus("در حال پیش‌بینی با SVR…");
    const data = await api("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pressures: readPressures() }),
    });
    renderResult(data);
    showLeak(data.leak_map.marker, data.leak_map.nearest_pipe);
    setStatus("نشتی شناسایی شد ✓", "ok");
  } catch (e) {
    setStatus("خطا: " + e.message, "err");
  }
});

function renderResult(data) {
  const card = $("#resultCard");
  card.hidden = false;
  const p = data.prediction, lm = data.leak_map;

  let html = `<div class="pipe-hit">🔴 نشتی روی لوله ${lm.nearest_pipe}
    (بین گره ${lm.pipe_nodes[0]} و گره ${lm.pipe_nodes[1]})</div>`;
  html += `<div class="kv">
    <div class="item leakval"><span>Lx (m)</span><b>${p.Lx.toFixed(1)}</b></div>
    <div class="item leakval"><span>Ly (m)</span><b>${p.Ly.toFixed(1)}</b></div>
    <div class="item"><span>Lz / تراز (m)</span><b>${(p.Lz ?? 0).toFixed(2)}</b></div>
    <div class="item"><span>شدت نشتی (Emitter)</span><b>${(p.Emitter ?? 0).toFixed(1)}</b></div>
  </div>`;

  // دقت مدل SVR
  const m = MODEL_METRICS;
  if (m && m.Lx) {
    const f = (t) => (m[t]?.r2_test ?? NaN);
    html += `<div class="accuracy">
      <b>📊 دقت مدل SVR (R² تست)</b><br>
      Lx: <b>${f("Lx").toFixed(3)}</b> ·
      Ly: <b>${f("Ly").toFixed(3)}</b> ·
      Lz: <b>${f("Lz").toFixed(3)}</b> ·
      Emitter: <b>${f("Emitter").toFixed(3)}</b>
    </div>`;
  }
  $("#resultBody").innerHTML = html;
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- شروع ---------- */
(async function init() {
  try {
    NETWORK = await api("/api/network");
    SENSOR_COLS = NETWORK.sensor_columns;
    drawMap();
    buildSensorInputs();           // خالی — منتظر ورودی کاربر
    const m = await api("/api/models");
    if (m.models.length && m.models[0].metrics) MODEL_METRICS = m.models[0].metrics;
    setStatus(m.demo_mode ? "مدل SVR یافت نشد — ابتدا آموزش دهید" : "متصل ✓ (SVR فعال)",
              m.demo_mode ? "err" : "ok");
  } catch (e) {
    setStatus("خطا در اتصال به سرور: " + e.message, "err");
  }
})();
