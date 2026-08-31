import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
import joblib
import time

# ================================
# Load Data
# ================================
print("Uploading excel data...")
data = pd.read_excel('C:/PouRia/SUTECH/article2-uniformed/Udata_generation/a1-bench3-Udata-nd5.xlsx')
start_time = time.time()

# y = Leak coordinates and Emitter
y = data.iloc[:, 0:4]   # Lx, Ly, Lz, Emitter

# X = nodes pressure
X = data.iloc[:, 4:]    # n1, n2, ..., n32

# Scaling
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ================================
# RF Hyperparameters
# ================================
params = {
    'n_estimators': [200],
    'max_depth': [10, None],
    'min_samples_split': [2],
    'min_samples_leaf': [1],
    'bootstrap': [True, False]
}

# Train/Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)

# ================================
# Train Separate Models for Each Target
# ================================
target_names = ['Lx', 'Ly', 'Lz', 'Emitter']
grid_models = []

for i in range(y.shape[1]):
    print(f"\n🔹 Training RF for {target_names[i]}")

    rf = RandomForestRegressor(random_state=42)

    grid = GridSearchCV(
        rf,
        params,
        cv=3,
        scoring='r2',
        n_jobs=-1
    )

    grid.fit(X_train, y_train.iloc[:, i])
    model = grid.best_estimator_
    grid_models.append(model)

    # Predictions
    pred_train = model.predict(X_train)
    pred_test = model.predict(X_test)

    # Metrics
    mse_train = mean_squared_error(y_train.iloc[:, i], pred_train)
    r2_train = r2_score(y_train.iloc[:, i], pred_train)
    mse_test = mean_squared_error(y_test.iloc[:, i], pred_test)
    r2_test = r2_score(y_test.iloc[:, i], pred_test)

    print(f" Train → MSE: {mse_train:.4f} | R2: {r2_train:.4f}")
    print(f" Test  → MSE: {mse_test:.4f} | R2: {r2_test:.4f}")

# ================================
# Save Models + Scaler
# ================================
for name, model in zip(target_names, grid_models):
    joblib.dump(model, f'rf_model_{name}.pkl')

joblib.dump(scaler, 'scaler.pkl')

end_time = time.time()
print(f"\n⏱ Total time: {end_time - start_time:.2f} sec")
print("✅ RF models and scaler saved.")

#%%

import pandas as pd
import numpy as np
import joblib

print("🧪 Testing Random Forest on real data ...")

# Load real pressure data
real_data = pd.read_excel(
    'C:/PouRia/SUTECH/payanameh/MLE-computation/bench3/bench3-rdata-n20.xlsx',
    header=None
)

print("Real data shape:", real_data.shape)

# Load scaler (only because training used scaled X)
scaler = joblib.load('scaler.pkl')

# Feature check
assert real_data.shape[1] == scaler.n_features_in_, \
    "❌ Feature count mismatch!"

# Normalize
real_scaled = scaler.transform(real_data)

# Load RF models
target_names = ['Lx', 'Ly', 'Lz', 'Emitter']
models = [joblib.load(f'rf_model_{t}.pkl') for t in target_names]

# Predict
preds = [model.predict(real_scaled) for model in models]
output = np.column_stack(preds)

print("📍 Random Forest prediction [Lx, Ly, Lz, Emitter]:")
print(output)

