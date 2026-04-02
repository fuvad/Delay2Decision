"""
train_congestion_forecaster.py — Congestion Forecaster Training Microservice
==============================================================================
Trains an XGBoost regressor to predict future terminal congestion
from current congestion features.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.metrics import mean_squared_error, r2_score
from xgboost import XGBRegressor
import mlflow
import mlflow.sklearn

from src.utils.config import (
    CONGESTION_FORECAST_FEATURES_PATH,
    CONGESTION_FORECAST_FEATURES,
    MODEL_DIR,
    CONGESTION_FORECASTER_PATH,
    TRAIN_RATIO,
)
from src.utils.mlflow_config import init_mlflow


def main():
    print("=" * 60)
    print("CONGESTION FORECASTER SERVICE — Training")
    print("=" * 60)

    init_mlflow("congestion-forecaster")

    df = pd.read_csv(CONGESTION_FORECAST_FEATURES_PATH)

    X = df[CONGESTION_FORECAST_FEATURES]
    y = df["future_congestion"]

    split = int(len(X) * TRAIN_RATIO)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    print(f"  Train: {len(X_train)}  |  Test: {len(X_test)}")

    # ─ Pipeline with mixed preprocessing
    num_cols = ["hour", "time_congestion", "rolling_congestion", "rolling_origin_delay"]
    cat_cols = ["terminal"]

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ])

    pipe = Pipeline([
        ("prep", preprocessor),
        ("model", XGBRegressor(
            max_depth=4,
            n_estimators=200,
            learning_rate=0.05,
            random_state=42,
        )),
    ])

    print("  Training XGBoost congestion forecaster ...")

    with mlflow.start_run(run_name="congestion-forecaster-training"):
        mlflow.log_param("max_depth", 4)
        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("learning_rate", 0.05)
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("test_rows", len(X_test))

        pipe.fit(X_train, y_train)

        preds = pipe.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2 = r2_score(y_test, preds)

        print(f"  RMSE : {rmse:.4f}")
        print(f"  R2   : {r2:.4f}")

        mlflow.log_metric("rmse", round(rmse, 4))
        mlflow.log_metric("r2", round(r2, 4))
        mlflow.sklearn.log_model(pipe, "congestion_forecaster")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, CONGESTION_FORECASTER_PATH)
    print(f"  Model saved -> {CONGESTION_FORECASTER_PATH.name}")

    return pipe


if __name__ == "__main__":
    main()

