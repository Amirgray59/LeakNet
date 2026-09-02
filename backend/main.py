"""
LeakNet API — FastAPI backend (ساده‌شده: فقطf {MODEL})
"""
import os
import io
import math
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .network_topology import topology_payload, nearest_pipe, NODES
from . import model_service as ms

from .model_service import MODEL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="LeakNet MODEL", version="2.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

ms.load_models()


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": any(m.get("id") == f"{MODEL}" for m in ms.available_models())}


@app.get("/api/network")
def network():
    p = topology_payload()
    md = ms.metadata()
    if isinstance(md, dict) and md.get("y_range"):
        p["y_range"] = md["y_range"]
    return p


@app.get("/api/models")
def models():
    m = ms.available_models()
    return {"models": m, "metrics": ms.metrics(),
            "demo_mode": len(m) == 0}


@app.post("/api/models/reload")
def reload_models():
    ms.load_models()
    return {"model_loaded": any(m.get("id") == f"{MODEL}" for m in ms.available_models())}


@app.post("/api/predict")
def predict(payload: dict = Body(...)):
    """پیش‌بینی {MODEL}: {"pressures": {"n1":..,"n31":..}}"""
    pressures = payload.get("pressures")
    if pressures is None:
        return JSONResponse({"error": "pressures required"}, status_code=400)
    try:
        result = ms.predict(f"{MODEL}", pressures)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    lx, ly = result["Lx"], result["Ly"]
    map_pt = _to_map_space(lx, ly)
    hit = nearest_pipe(map_pt["x"], map_pt["y"])
    return {
        "prediction": result,
        "leak_map": {
            "raw": {"Lx": lx, "Ly": ly, "Lz": result.get("Lz"),
                    "Emitter": result.get("Emitter")},
            "map": map_pt,
            "nearest_pipe": hit["pipe"],
            "pipe_nodes": [hit["node_a"], hit["node_b"]],
            "marker": {"x": hit["x"], "y": hit["y"]},
        },
    }


@app.post("/api/upload-sensors")
async def upload_sensors(file: UploadFile = File(...)):
    """
    آپلود اکسل/CSV شامل ستون‌های n1..n31.
    سطر آخر برگردانده می‌شود تا فرانت مقادیر سنسور را پر کند.
    """
    content = await file.read()
    name = (file.filename or "").lower()
    try:
        df = pd.read_excel(io.BytesIO(content)) if name.endswith((".xlsx", ".xls")) \
            else pd.read_csv(io.BytesIO(content))
    except Exception as e:
        return JSONResponse({"error": f"cannot parse file: {e}"}, status_code=400)

    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    if df.empty:
        return JSONResponse({"error": "file is empty"}, status_code=400)

    # فقط ستون‌های n1..n31 به ترتیب عددی
    cols = [c for c in df.columns if str(c).strip().lower().startswith("n")]
    try:
        cols = sorted(cols, key=lambda c: int(str(c).strip()[1:]))
    except Exception:
        pass
    if not cols:
        return JSONResponse({"error": "no n1..n31 columns found"}, status_code=400)

    last = df.iloc[-1]          # همیشه سطر آخر
    values = {str(c): float(last[c]) for c in cols if pd.notna(last[c])}
    return {"n_rows": len(df), "columns": [str(c) for c in cols], "values": values}


# ------------------------- helpers -------------------------
def _to_map_space(lx: float, ly: float):
    md = ms.metadata()
    xs = [xy[0] for xy in NODES.values()]
    ys = [xy[1] for xy in NODES.values()]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)

    rng = md.get("y_range") if isinstance(md, dict) else None
    if rng and all(k in rng for k in ("Lx", "Ly")):
        (x0, x1) = rng["Lx"]
        (y0, y1) = rng["Ly"]
        if x1 > x0 and y1 > y0:
            mx = bx0 + (lx - x0) / (x1 - x0) * (bx1 - bx0)
            my = by0 + (ly - y0) / (y1 - y0) * (by1 - by0)
            return {"x": float(mx), "y": float(my), "calibrated": True}
    if math.isfinite(lx) and math.isfinite(ly):
        return {"x": lx, "y": ly, "calibrated": False}
    return {"x": (bx0 + bx1) / 2, "y": (by0 + by1) / 2, "calibrated": False}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
