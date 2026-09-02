"""
آموزش یکپارچه ۴ مدل (RFR / XGBoost / MLP / SVR) روی دیتاست اکسل
خروجی: models/<algo>_model_{Lx,Ly,Lz,Emitter}.pkl + scaler + metadata.json + metrics.json

مثال:
  python training/train_all.py --data data/a1-bench2-Udata-nd2.xlsx --models rfr,xgboost,mlp,svr
"""
import os
import json
import time
import argparse
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score

TARGETS = ["Lx", "Ly", "Lz", "Emitter"]


def get_algo(name):
    if name == "rfr":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(random_state=42), {
            "n_estimators": [200], "max_depth": [10, None],
            "min_samples_split": [2], "min_samples_leaf": [1],
            "bootstrap": [True, False]}, 3
    if name == "xgboost":
        from xgboost import XGBRegressor
        return XGBRegressor(objective="reg:squarederror", random_state=42), {
            "n_estimators": [50, 100], "learning_rate": [0.01, 0.1],
            "max_depth": [3, 5], "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0]}, 5
    if name == "mlp":
        from sklearn.neural_network import MLPRegressor
        return MLPRegressor(random_state=42), {
            "hidden_layer_sizes": [(128, 64)], "activation": ["relu"],
            "solver": ["adam"], "alpha": [1e-4, 1e-3],
            "learning_rate_init": [0.001, 0.005],
            "max_iter": [500], "early_stopping": [True]}, 5
    if name == "svr":
        from sklearn.svm import SVR
        return SVR(), {"C": [1, 10, 100, 500],
                       "epsilon": [0.01, 0.1, 0.5],
                       "gamma": ["scale", "auto", 0.01, 0.001],
                       "kernel": ["rbf"]}, 5
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="مسیر فایل اکسل دیتاست")
    ap.add_argument("--models", default="rfr,xgboost,mlp,svr")
    ap.add_argument("--out", default="models")
    ap.add_argument("--test-size", type=float, default=0.2)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    print(f"📥 Loading {args.data} ...")
    data = pd.read_excel(args.data)
    t0 = time.time()

    y = data.iloc[:, 0:4]          # Lx Ly Lz Emitter
    X = data.iloc[:, 4:]           # n1 n2 ... pressures
    print(f"   rows={len(data)}  features={X.shape[1]}")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_scaled, y, test_size=args.test_size, random_state=42)

    all_metrics = {}
    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"\n===== {name.upper()} =====")
        est, grid_params, cv = get_algo(name)
        algo_metrics = {}
        for i, target in enumerate(TARGETS):
            grid = GridSearchCV(est, grid_params, cv=cv, scoring="r2",
                                n_jobs=-1 if name == "rfr" else None)
            grid.fit(X_tr, y_tr.iloc[:, i])
            model = grid.best_estimator_

            pr_tr, pr_te = model.predict(X_tr), model.predict(X_te)
            m = {
                "mse_train": float(mean_squared_error(y_tr.iloc[:, i], pr_tr)),
                "r2_train": float(r2_score(y_tr.iloc[:, i], pr_tr)),
                "mse_test": float(mean_squared_error(y_te.iloc[:, i], pr_te)),
                "r2_test": float(r2_score(y_te.iloc[:, i], pr_te)),
                "best_params": {k: (str(v) if not isinstance(
                    v, (int, float, str, bool, type(None))) else v)
                    for k, v in grid.best_params_.items()},
            }
            algo_metrics[target] = m
            print(f"  {target}: R2_test={m['r2_test']:.4f}  MSE_test={m['mse_test']:.4f}")

            joblib.dump(model, os.path.join(args.out, f"{name}_model_{target}.pkl"))
        joblib.dump(scaler, os.path.join(args.out, f"scaler_{name}.pkl"))
        all_metrics[name] = algo_metrics

    metadata = {
        "feature_names": list(X.columns),
        "n_features": int(X.shape[1]),
        "n_rows": int(len(data)),
        "y_range": {"Lx": [float(y.iloc[:, 0].min()), float(y.iloc[:, 0].max())],
                    "Ly": [float(y.iloc[:, 1].min()), float(y.iloc[:, 1].max())],
                    "Lz": [float(y.iloc[:, 2].min()), float(y.iloc[:, 2].max())]},
        "source_file": os.path.basename(args.data),
    }
    json.dump(metadata, open(os.path.join(args.out, "metadata.json"), "w"),
              ensure_ascii=False, indent=2)
    json.dump(all_metrics, open(os.path.join(args.out, "metrics.json"), "w"),
              ensure_ascii=False, indent=2)
    print(f"\n✅ Done in {time.time() - t0:.1f}s → models saved to '{args.out}/'")


if __name__ == "__main__":
    main()
