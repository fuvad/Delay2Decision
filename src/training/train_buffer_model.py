"""
train_buffer_model.py — Buffer Time Regression Training Microservice
=====================================================================
Trains an XGBoost regressor to predict adaptive buffer times
based on congestion and operational features.

Run standalone:
    python src/training/train_buffer_model.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor
import mlflow
import mlflow.sklearn

from src.utils.config import (
    BUFFER_FEATURES_PATH,
    MODEL_DIR,
    BUFFER_MODEL_PATH,
    TRAIN_RATIO,
)
from src.utils.mlflow_config import init_mlflow


def main():
    print("=" * 60)
    print("BUFFER MODEL SERVICE — Training")
    print("=" * 60)

    init_mlflow("buffer-model")

    df = pd.read_csv(BUFFER_FEATURES_PATH)

    X = df.drop(columns=["buffer_minutes"])
    y = df["buffer_minutes"]

    split = int(len(X) * TRAIN_RATIO)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    print(f"  Train: {len(X_train)}  |  Test: {len(X_test)}")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model", XGBRegressor(
            max_depth=4,
            n_estimators=300,
            learning_rate=0.05,
            random_state=42,
        )),
    ])

    print("  Training XGBoost buffer model ...")

    with mlflow.start_run(run_name="buffer-model-training"):
        mlflow.log_param("max_depth", 4)
        mlflow.log_param("n_estimators", 300)
        mlflow.log_param("learning_rate", 0.05)
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("test_rows", len(X_test))

        pipe.fit(X_train, y_train)

        preds = pipe.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)

        print(f"  RMSE : {rmse:.2f} min")
        print(f"  MAE  : {mae:.2f} min")
        print(f"  R2   : {r2:.4f}")

        mlflow.log_metric("rmse", round(rmse, 4))
        mlflow.log_metric("mae", round(mae, 4))
        mlflow.log_metric("r2", round(r2, 4))
        mlflow.sklearn.log_model(pipe, "buffer_model")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, BUFFER_MODEL_PATH)
    print(f"  Model saved -> {BUFFER_MODEL_PATH.name}")

    return pipe


if __name__ == "__main__":
    main()

