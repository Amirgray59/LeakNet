"""
آموزش XGBoost روی دیتاست — تنها مدل مورد استفاده برنامه
خروجی: models/xgboost_model_{Lx,Ly,Lz,Emitter}.pkl + scaler_xgboost.pkl + metadata.json + metrics.json
"""
import os, json, time, joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from xgboost import XGBRegressor

DATA = os.environ.get("TRAIN_DATA", "data/a1-bench2-Udata-nd10.xlsx")
OUT = "models"
os.makedirs(OUT, exist_ok=True)

TARGETS = ["Lx", "Ly", "Lz", "Emitter"]

print(f"📥 Loading {DATA} ...")
data = pd.read_excel(DATA)
t0 = time.time()

y = data.iloc[:, 0:4]
X = data.iloc[:, 4:]
print(f"   rows={len(data)}  features={X.shape[1]}")

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
X_tr, X_te, y_tr, y_te = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

metrics = {}
print("\n===== XGBOOST =====")
for i, target in enumerate(TARGETS):
    m = XGBRegressor(n_estimators=200, learning_rate=0.1, max_depth=6,
                     subsample=0.8, colsample_bytree=0.8,
                     objective="reg:squarederror", random_state=42, n_jobs=-1)
    m.fit(X_tr, y_tr.iloc[:, i])
    pr_tr, pr_te = m.predict(X_tr), m.predict(X_te)
    metrics[target] = {
        "mse_train": float(mean_squared_error(y_tr.iloc[:, i], pr_tr)),
        "r2_train": float(r2_score(y_tr.iloc[:, i], pr_tr)),
        "mse_test": float(mean_squared_error(y_te.iloc[:, i], pr_te)),
        "r2_test": float(r2_score(y_te.iloc[:, i], pr_te)),
    }
    print(f"  {target}: R2_test={metrics[target]['r2_test']:.4f}  MSE_test={metrics[target]['mse_test']:.4f}")
    joblib.dump(m, os.path.join(OUT, f"xgboost_model_{target}.pkl"))

joblib.dump(scaler, os.path.join(OUT, "scaler_xgboost.pkl"))

metadata = {
    "feature_names": list(X.columns),
    "n_features": int(X.shape[1]),
    "n_rows": int(len(data)),
    "y_range": {
        "Lx": [float(y.iloc[:, 0].min()), float(y.iloc[:, 0].max())],
        "Ly": [float(y.iloc[:, 1].min()), float(y.iloc[:, 1].max())],
        "Lz": [float(y.iloc[:, 2].min()), float(y.iloc[:, 2].max())],
    },
    "source_file": os.path.basename(DATA),
}
json.dump(metadata, open(os.path.join(OUT, "metadata.json"), "w"), ensure_ascii=False, indent=2)
json.dump({"xgboost": metrics}, open(os.path.join(OUT, "metrics.json"), "w"), ensure_ascii=False, indent=2)
print(f"\n✅ Done in {time.time() - t0:.1f}s → models saved to '{OUT}/'")
