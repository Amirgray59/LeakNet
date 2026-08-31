import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.svm import SVR
import joblib
import time

# --------------------------------------
# Load Data
# --------------------------------------
print("Uploading excel data...")
data = pd.read_excel('C:/PouRia/SUTECH/article2-uniformed/Udata_generation/a1-bench3-Udata-nd50.xlsx')
start_time = time.time()

# y = Lx, Ly, Lz, Emitter
y = data.iloc[:, 0:4]

# X = pressures
X = data.iloc[:, 4:]

# --------------------------------------
# Normalize X
# --------------------------------------
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# --------------------------------------
# Train/Test split
# --------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)

# --------------------------------------
# SVR setup
# --------------------------------------
params = {
    'C': [1, 10, 100, 500],
    'epsilon': [0.01, 0.1, 0.5],
    'gamma': ['scale', 'auto', 0.01, 0.001],
    'kernel': ['rbf']
}

target_names = ['Lx', 'Ly', 'Lz', 'Emitter']
svr_models = []

# --------------------------------------
# Train separate model for each output
# --------------------------------------
for i in range(y.shape[1]):
    print(f"\n🔹 Training SVR for {target_names[i]}")

    svr = SVR()
    grid = GridSearchCV(svr, params, cv=5, scoring='r2')
    grid.fit(X_train, y_train.iloc[:, i])

    model = grid.best_estimator_
    svr_models.append(model)

    # Predictions
    pred_train = model.predict(X_train)
    pred_test = model.predict(X_test)

    # Metrics
    mse_train = mean_squared_error(y_train.iloc[:, i], pred_train)
    r2_train = r2_score(y_train.iloc[:, i], pred_train)

    mse_test = mean_squared_error(y_test.iloc[:, i], pred_test)
    r2_test = r2_score(y_test.iloc[:, i], pred_test)

    print(f"Train → MSE: {mse_train:.6f} | R2: {r2_train:.6f}")
    print(f"Test  → MSE: {mse_test:.6f} | R2: {r2_test:.6f}")

# --------------------------------------
# End time
# --------------------------------------
end_time = time.time()
print(f"\n⏱ Execution time: {end_time - start_time:.2f} sec")

# --------------------------------------
# Save models & scaler
# --------------------------------------
for name, model in zip(target_names, svr_models):
    joblib.dump(model, f'svr_model_{name}.pkl')

joblib.dump(scaler, 'scaler_svr.pkl')
print("✅ SVR models and scaler saved.")

#%%
import pandas as pd
import numpy as np
import joblib

print("🧪 Testing SVR on real data ...")

# Load real pressure data (1 row, no header)
real_data = pd.read_excel(
    'C:/PouRia/SUTECH/payanameh/MLE-computation/bench3/bench3-rdata-n20.xlsx',
    header=None
)

print("Real data shape:", real_data.shape)

# Load scaler (SVR NEEDS scaling)
scaler = joblib.load('scaler.pkl')

# Feature check
assert real_data.shape[1] == scaler.n_features_in_, \
    "❌ Feature count mismatch!"

# Normalize
real_scaled = scaler.transform(real_data)

# Load SVR models
target_names = ['Lx', 'Ly', 'Lz', 'Emitter']
models = [joblib.load(f'svr_model_{t}.pkl') for t in target_names]

# Predict
preds = [model.predict(real_scaled) for model in models]
output = np.column_stack(preds)

print("📍 SVR prediction [Lx, Ly, Lz, Emitter]:")
print(output)
