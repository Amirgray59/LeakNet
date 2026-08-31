import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import time
from xgboost import XGBRegressor

# data import
print("uploading excel data")
data = pd.read_excel('C:/PouRia/SUTECH/article2-uniformed/Udata_generation/a1-bench3-Udata-nd50.xlsx')
start_time = time.time()

# y = Leak coordinates (Lx, Ly, Lz) + Emitter
y = data.iloc[:, 0:4]  # Lx Ly Lz Emitter

# X = nodes pressure
X = data.iloc[:, 4:]  # n1 n2 n3 ...

# normalization
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# XGBoost setup
xgb = XGBRegressor(objective='reg:squarederror', random_state=42)
params = {
    'n_estimators': [50, 100],
    'learning_rate': [0.01, 0.1],
    'max_depth': [3, 5],
    'subsample': [0.8, 1.0],
    'colsample_bytree': [0.8, 1.0]
}

# train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)

# GridSearchCV for each target (Lx, Ly, Lz, Emitter)
grid_models = []
preds = []
target_names = ['Lx', 'Ly', 'Lz', 'Emitter']
for i in range(y.shape[1]):
    grid = GridSearchCV(xgb, params, cv=5, scoring='r2')
    grid.fit(X_train, y_train.iloc[:, i])
    model = grid.best_estimator_
    grid_models.append(model)

    # PREDICTION
    pred_test = model.predict(X_test)
    pred_train = model.predict(X_train)

    # METRICS
    mse_train = mean_squared_error(y_train.iloc[:, i], pred_train)
    r2_train = r2_score(y_train.iloc[:, i], pred_train)

    mse_test = mean_squared_error(y_test.iloc[:, i], pred_test)
    r2_test = r2_score(y_test.iloc[:, i], pred_test)

    print(f"🔹 {target_names[i]}:")
    print(" Train → MSE:", mse_train, " | R2:", r2_train)
    print(" Test  → MSE:", mse_test,  " | R2:", r2_test)


end_time = time.time()
execution_time = end_time - start_time
print(f"⏱ wasted time: {execution_time:.2f} sec")

# Save models and scaler
for name, model in zip(target_names, grid_models):
    joblib.dump(model, f'xgb_model_{name}.pkl')
joblib.dump(scaler, 'scaler.pkl')
print("✅ Models and scaler saved.")

#%%
# === Load real pressure data ===
real_data = pd.read_excel(
    'C:/PouRia/SUTECH/payanameh/MLE-computation/bench3/bench3-rdata-n1.xlsx',
    header=None
)

print("Real data shape:", real_data.shape)

# Check feature count
assert real_data.shape[1] == X.shape[1], "❌ Feature count mismatch!"

# Assign column names
real_data.columns = X.columns

# Scale
real_scaled = scaler.transform(real_data)

# Predict
real_preds = []
for model in grid_models:
    real_preds.append(model.predict(real_scaled))

real_output = np.column_stack(real_preds)

print("📍 Predicted [Lx, Ly, Lz, Emitter]:")
print(real_output)
