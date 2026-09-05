"""
سرویس مدل — فقط XGBoost
مدل: models/xgboost_model_{Lx,Ly,Lz,Emitter}.pkl + scaler_xgboost.pkl
"""
import os
import json
import joblib
import numpy as np

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.environ.get(
    "MODELS_DIR",
    "/app/models" if os.path.isdir("/app/models") else os.path.join(_BASE, "models"))

TARGETS = ["Lx", "Ly", "Lz", "Emitter"]

_models = {}
_scaler = None
_metadata = {}
_metrics = {}

MODEL = "svr_model"


def load_models():
    global _models, _scaler, _metadata, _metrics
    _models = {}
    for t in TARGETS:
        p = os.path.join(MODELS_DIR, f"{MODEL}_{t}.pkl")
        if os.path.exists(p):
            _models[t] = joblib.load(p)
    sp = os.path.join(MODELS_DIR, "scaler_xgboost.pkl")
    _scaler = joblib.load(sp) if os.path.exists(sp) else None

    mp = os.path.join(MODELS_DIR, "metadata.json")
    _metadata = json.load(open(mp)) if os.path.exists(mp) else {}
    tp = os.path.join(MODELS_DIR, "metrics.json")
    all_m = json.load(open(tp)) if os.path.exists(tp) else {}
    _metrics = all_m.get("svr", {}) if isinstance(all_m, dict) else {}


def available_models():
    if len(_models) == len(TARGETS) and _scaler is not None:
        return [{"id": "svr", "name": "SVR",
                 "n_features": int(getattr(_scaler, "n_features_in_", 0)),
                 "metrics": _metrics}]
    return []


def _features_from(payload, n_expected):
    if isinstance(payload, dict):
        keys = [f"n{i}" for i in range(1, n_expected + 1)]
        if all(k in payload for k in keys):
            return np.array([[float(payload[k]) for k in keys]])
        vals = [payload[k] for k in sorted(payload, key=lambda s: int(str(s)[1:]))]
        return np.array([vals], dtype=float)
    return np.array(payload, dtype=float).reshape(1, -1)


def predict(algo, pressures):
    if algo != "svr":
        raise ValueError("only svr is available")
    if len(_models) != len(TARGETS) or _scaler is None:
        raise ValueError("model not loaded — train svr first")
    n = int(getattr(_scaler, "n_features_in_", 0))
    X = _features_from(pressures, n)
    if X.shape[1] != n:
        raise ValueError(f"expected {n} pressure features, got {X.shape[1]}")
    Xs = _scaler.transform(X)
    return {t: float(_models[t].predict(Xs)[0]) for t in TARGETS}


def metadata():
    return _metadata


def metrics():
    return _metrics
