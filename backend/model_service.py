"""
سرویس بارگذاری و استفاده از مدل‌های آموزش‌دیده (RFR / XGBoost / MLP / SVR)
مدل‌ها از پوشه MODELS_DIR خوانده می‌شوند؛ هر مدل ۴ فایل (Lx, Ly, Lz, Emitter)
+ یک scaler دارد. اگر مدلی موجود نباشد، حالت دمو فعال می‌شود.
"""
import os
import json
import glob
import joblib
import numpy as np
import pandas as pd

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.environ.get(
    "MODELS_DIR",
    "/app/models" if os.path.isdir("/app/models") else os.path.join(_BASE, "models"))
DATA_DIR = os.environ.get(
    "DATA_DIR",
    "/app/data" if os.path.isdir("/app/data") else os.path.join(_BASE, "data"))

TARGETS = ["Lx", "Ly", "Lz", "Emitter"]
ALGOS = {"rfr": "Random Forest", "xgboost": "XGBoost",
         "mlp": "MLP", "svr": "SVR"}

# ------------------------- registry -------------------------
_registry = {}          # algo -> {"models": {target: model}, "scaler": scaler}
_metadata = {}          # metadata.json (feature names, y min/max)
_metrics = {}           # metrics.json
_real_df = None         # bench2-realdatatest.xlsx cache


def _scaler_path(algo):
    for cand in (f"scaler_{algo}.pkl", "scaler.pkl"):
        p = os.path.join(MODELS_DIR, cand if algo == "rfr" else cand)
        if os.path.exists(p):
            return p
    return None


def load_models():
    _registry.clear()
    for algo in ALGOS:
        models = {}
        for t in TARGETS:
            p = os.path.join(MODELS_DIR, f"{algo}_model_{t}.pkl")
            if os.path.exists(p):
                models[t] = joblib.load(p)
        sp = _scaler_path(algo)
        if len(models) == len(TARGETS) and sp:
            _registry[algo] = {"models": models, "scaler": joblib.load(sp)}

    global _metadata, _metrics
    mp = os.path.join(MODELS_DIR, "metadata.json")
    _metadata = json.load(open(mp)) if os.path.exists(mp) else {}
    tp = os.path.join(MODELS_DIR, "metrics.json")
    _metrics = json.load(open(tp)) if os.path.exists(tp) else {}


def available_models():
    return [{"id": a, "name": ALGOS[a],
             "n_features": int(getattr(_registry[a]["scaler"], "n_features_in_", 0)),
             "metrics": _metrics.get(a, {})}
            for a in _registry]


def _features_from(payload: dict, n_expected: int):
    """استخراج بردار فشار به ترتیب n1..nN"""
    if isinstance(payload, dict):
        keys = [f"n{i}" for i in range(1, n_expected + 1)]
        if all(k in payload for k in keys):
            return np.array([[float(payload[k]) for k in keys]])
        vals = [payload[k] for k in sorted(payload, key=lambda s: int(s[1:]))]
        return np.array([vals], dtype=float)
    arr = np.array(payload, dtype=float).reshape(1, -1)
    return arr


def predict(algo: str, pressures):
    """پیش‌بینی با یک الگوریتم؛ خروجی: dict با Lx Ly Lz Emitter"""
    if algo not in _registry:
        raise ValueError(f"model '{algo}' not loaded")
    reg = _registry[algo]
    n = int(getattr(reg["scaler"], "n_features_in_", 0))
    X = _features_from(pressures, n)
    if X.shape[1] != n:
        raise ValueError(f"expected {n} pressure features, got {X.shape[1]}")
    Xs = reg["scaler"].transform(X)
    out = {t: float(reg["models"][t].predict(Xs)[0]) for t in TARGETS}
    out["demo"] = False
    return out


def demo_predict(pressures):
    """
    حالت دمو (وقتی مدل آموزش داده نشده): مرکز ثقل وزن‌دار افت فشار
    روی گره‌های سنسور → تخمین تقریبی محل نشتی. demo=True
    """
    from .network_topology import NODES, SENSOR_NODES
    vals = np.array(list(pressures.values()) if isinstance(pressures, dict)
                    else pressures, dtype=float)[:len(SENSOR_NODES)]
    if len(vals) < len(SENSOR_NODES):
        vals = np.pad(vals, (0, len(SENSOR_NODES) - len(vals)),
                      constant_values=vals.mean() if len(vals) else 30.0)
    pmax = vals.max() if vals.max() > 0 else 1.0
    w = np.clip(pmax - vals, 0, None) + 1e-6
    xs = np.array([NODES[n][0] for n in SENSOR_NODES])
    ys = np.array([NODES[n][1] for n in SENSOR_NODES])
    return {"Lx": float((w * xs).sum() / w.sum()),
            "Ly": float((w * ys).sum() / w.sum()),
            "Lz": 0.0,
            "Emitter": float(w.max() / (w.sum() + 1e-9)),
            "demo": True}


def predict_all(pressures):
    """پیش‌بینی با همه مدل‌های موجود + میانگین (ensemble)"""
    res = {}
    for a in _registry:
        try:
            res[a] = predict(a, pressures)
        except Exception as e:
            res[a] = {"error": str(e)}
    if not res:  # هیچ مدلی نیست → دمو
        res["demo"] = demo_predict(pressures)
    ok = [v for v in res.values() if isinstance(v, dict) and "Lx" in v]
    if ok:
        res["ensemble"] = {t: float(np.mean([v[t] for v in ok])) for t in TARGETS}
        res["ensemble"]["demo"] = all(v.get("demo") for v in ok)
    return res


# ------------------------- real data samples -------------------------
def _load_real():
    global _real_df
    if _real_df is not None:
        return _real_df
    for f in glob.glob(os.path.join(DATA_DIR, "*realdatatest*.xlsx")) + \
              glob.glob(os.path.join(DATA_DIR, "*.xlsx")):
        try:
            df = pd.read_excel(f)
            df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
            if df.shape[1] >= 4:
                _real_df = df
                return df
        except Exception:
            continue
    return None


def random_real_sample():
    df = _load_real()
    if df is None:
        return None
    row = df.sample(1).iloc[0]
    return {str(c): float(v) for c, v in row.items()}


def real_rows(limit=50):
    df = _load_real()
    if df is None:
        return []
    return df.head(limit).to_dict(orient="records")


def metadata():
    return _metadata


def metrics():
    return _metrics
