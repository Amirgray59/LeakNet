"""
LeakNet API — FastAPI backend
اجرای محلی:  uvicorn backend.main:app --reload --port 8000
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="LeakNet — Water Network Leak Localization", version="1.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

ms.load_models()


# ----------------------------- API -----------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "models_loaded": len(ms.available_models())}


@app.get("/api/network")
def network():
    """توپولوژی کامل شبکه (گره‌ها، لوله‌ها، مختصات، مخزن)"""
    return topology_payload()


@app.get("/api/models")
def models():
    return {"models": ms.available_models(),
            "metrics": ms.metrics(),
            "demo_mode": len(ms.available_models()) == 0}


@app.post("/api/models/reload")
def reload_models():
    ms.load_models()
    return {"models_loaded": len(ms.available_models())}


@app.post("/api/predict")
def predict(payload: dict = Body(...)):
    """
    ورودی: {"pressures": {"n1":..., "n2":...} | [..], "model": "rfr|xgboost|mlp|svr|all"}
    خروجی: پیش‌بینی Lx, Ly, Lz, Emitter + نزدیک‌ترین لوله و نقطه نمایش روی نقشه
    """
    pressures = payload.get("pressures")
    if pressures is None:
        return JSONResponse({"error": "pressures required"}, status_code=400)
    model = payload.get("model", "all")

    if model == "all":
        results = ms.predict_all(pressures)
        best = results.get("ensemble") or next(
            (v for v in results.values() if isinstance(v, dict) and "Lx" in v), None)
    else:
        try:
            results = {model: ms.predict(model, pressures)}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        best = results[model]

    if best is None or "Lx" not in best:
        return JSONResponse({"error": "no prediction available",
                             "results": results}, status_code=400)

    # نگاشت مختصات پیش‌بینی‌شده به فضای نقشه
    lx, ly = best["Lx"], best["Ly"]
    map_pt = _to_map_space(lx, ly)
    pipe_hit = nearest_pipe(map_pt["x"], map_pt["y"])

    return {
        "results": results,
        "primary": best,
        "leak_map": {
            "raw": {"Lx": lx, "Ly": ly, "Lz": best.get("Lz"),
                    "Emitter": best.get("Emitter")},
            "map": map_pt,
            "nearest_pipe": pipe_hit["pipe"],
            "pipe_nodes": [pipe_hit["node_a"], pipe_hit["node_b"]],
            "marker": {"x": pipe_hit["x"], "y": pipe_hit["y"]},
        },
    }


@app.get("/api/sample-real")
def sample_real():
    """یک سطر تصادفی از داده واقعی (bench2-realdatatest.xlsx)"""
    s = ms.random_real_sample()
    if s is None:
        return JSONResponse({"error": "no real dataset found in /app/data"},
                            status_code=404)
    return {"sample": s}


@app.get("/api/real-data")
def real_data(limit: int = 50):
    return {"rows": ms.real_rows(limit)}


@app.post("/api/predict-file")
async def predict_file(file: UploadFile = File(...), model: str = "all"):
    """آپلود xlsx/csv شامل ستون‌های فشار → پیش‌بینی گروهی"""
    content = await file.read()
    name = (file.filename or "").lower()
    try:
        df = pd.read_excel(io.BytesIO(content)) if name.endswith((".xlsx", ".xls")) \
            else pd.read_csv(io.BytesIO(content))
    except Exception as e:
        return JSONResponse({"error": f"cannot parse file: {e}"}, status_code=400)

    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    out = []
    for _, row in df.iterrows():
        pressures = {str(c): float(v) for c, v in row.items()}
        try:
            r = ms.predict_all(pressures) if model == "all" else {model: ms.predict(model, pressures)}
            best = r.get("ensemble") or next(
                (v for v in r.values() if isinstance(v, dict) and "Lx" in v), {})
            mp = _to_map_space(best.get("Lx", 0), best.get("Ly", 0))
            hit = nearest_pipe(mp["x"], mp["y"])
            out.append({"input": pressures, "prediction": best,
                        "nearest_pipe": hit["pipe"],
                        "marker": {"x": hit["x"], "y": hit["y"]}})
        except Exception as e:
            out.append({"input": pressures, "error": str(e)})
    return {"count": len(out), "predictions": out}


# ------------------------- helpers -------------------------

def _to_map_space(lx: float, ly: float):
    """
    اگر metadata شامل بازه Lx/Ly دیتاست آموزشی باشد، نگاشت affine به
    باکس شبکه انجام می‌شود؛ در غیر این صورت مختصات خام استفاده می‌شود.
    """
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

    if math.isfinite(lx) and math.isfinite(ly) and \
       bx0 - 500 <= lx <= bx1 + 500 and by0 - 500 <= ly <= by1 + 500:
        return {"x": lx, "y": ly, "calibrated": False}
    return {"x": (bx0 + bx1) / 2, "y": (by0 + by1) / 2, "calibrated": False}


# ------------------------- frontend -------------------------
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
