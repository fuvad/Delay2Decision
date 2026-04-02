"""
train_delay_model.py — Model Training Microservice
======================================================
Reads gold-level train/test CSVs, trains three candidate
classifiers (GradientBoosting, RandomForest, LogisticRegression),
selects the champion by AUC, and saves the model + metrics.

"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib
import mlflow
import mlflow.sklearn

from src.utils.config import (
    TRAIN_FEATURES_PATH,
    TEST_FEATURES_PATH,
    FEATURES,
    MODEL_DIR,
    MODEL_PATH,
    METRICS_PATH,
)
from src.utils.mlflow_config import init_mlflow


def main():
    print("=" * 60)
    print("TRAINING SERVICE - Training & selecting champion model")
    print("=" * 60)

    init_mlflow("delay-model")

    # ─ Load gold data
    train_clean = pd.read_csv(TRAIN_FEATURES_PATH)
    test_clean  = pd.read_csv(TEST_FEATURES_PATH)

    X_train = train_clean[FEATURES]
    y_train = train_clean["is_delayed"]
    X_test  = test_clean[FEATURES]
    y_test  = test_clean["is_delayed"]

    print(f"  Train shape: {X_train.shape}  |  delay rate: {y_train.mean():.2%}")
    print(f"  Test  shape: {X_test.shape}   |  delay rate: {y_test.mean():.2%}")

    # ─ Classifiers
    print("\n Training candidates …")
    candidates = {
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=20,
            random_state=42,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=20,
            random_state=42,
            n_jobs=-1,
        ),
        "LogisticRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, C=1.0, random_state=42)),
        ]),
    }

    best_model = None
    best_auc   = 0.0
    best_name  = ""
    results    = {}

    with mlflow.start_run(run_name="delay-champion-selection"):
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("test_rows", len(X_test))
        mlflow.log_param("features", FEATURES)

        for name, model in candidates.items():
            model.fit(X_train, y_train)
            prob = model.predict_proba(X_test)[:, 1]
            auc  = roc_auc_score(y_test, prob)
            results[name] = round(auc, 4)
            print(f"    {name:<22} AUC = {auc:.4f}")

            mlflow.log_metric(f"auc_{name}", round(auc, 4))

            if auc > best_auc:
                best_auc   = auc
                best_model = model
                best_name  = name

        print(f"\n  Champion: {best_name}  (AUC = {best_auc:.4f})")

        mlflow.log_param("champion", best_name)
        mlflow.log_metric("champion_auc", round(best_auc, 4))
        mlflow.sklearn.log_model(best_model, "delay_model")

    # ─ Save model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)
    print(f"  Model saved -> {MODEL_PATH.name}")

    # ─ Save training metrics
    metrics = {
        "champion": best_name,
        "champion_auc": round(best_auc, 4),
        "all_results": results,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Metrics saved → {METRICS_PATH.name}")

    return best_model, best_name, best_auc


if __name__ == "__main__":
    main()

