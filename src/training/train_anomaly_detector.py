"""
train_anomaly_detector.py — Congestion Anomaly Detector Training Microservice
==============================================================================
Trains an Isolation Forest to detect anomalous congestion
patterns at JFK terminals.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import mlflow
import mlflow.sklearn

from src.utils.config import (
    CONGESTION_FEATURES_PATH,
    ANOMALY_FEATURES,
    MODEL_DIR,
    ANOMALY_DETECTOR_PATH,
)
from src.utils.mlflow_config import init_mlflow


def main():
    print("=" * 60)
    print("ANOMALY DETECTOR SERVICE — Training")
    print("=" * 60)

    init_mlflow("anomaly-detector")

    df = pd.read_csv(CONGESTION_FEATURES_PATH)
    X = df[ANOMALY_FEATURES].dropna()

    print(f"  Training on {len(X)} rows  |  features: {ANOMALY_FEATURES}")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model", IsolationForest(contamination=0.05, random_state=42)),
    ])

    with mlflow.start_run(run_name="anomaly-detector-training"):
        mlflow.log_param("contamination", 0.05)
        mlflow.log_param("training_rows", len(X))
        mlflow.log_param("features", ANOMALY_FEATURES)

        pipe.fit(X)

        # For quick summary
        preds = pipe.predict(X)
        n_anomalies = (preds == -1).sum()
        anomaly_pct = n_anomalies / len(X)
        print(f"  Anomalies detected: {n_anomalies} ({anomaly_pct:.1%})")

        mlflow.log_metric("anomaly_count", int(n_anomalies))
        mlflow.log_metric("anomaly_pct", round(float(anomaly_pct), 4))
        mlflow.sklearn.log_model(pipe, "anomaly_detector")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, ANOMALY_DETECTOR_PATH)
    print(f"  Model saved -> {ANOMALY_DETECTOR_PATH.name}")

    return pipe


if __name__ == "__main__":
    main()

