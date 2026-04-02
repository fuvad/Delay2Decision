"""
calibrate_model.py — Model Calibration Microservice
=====================================================
Applies Platt scaling (sigmoid calibration) to the champion
delay model so that predicted probabilities are well-calibrated.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss
import mlflow
import mlflow.sklearn

from src.utils.config import (
    MODEL_PATH,
    TEST_FEATURES_PATH,
    DELAY_FEATURES,
    MODEL_DIR,
    CALIBRATED_MODEL_PATH,
)
from src.utils.mlflow_config import init_mlflow


def main():
    print("=" * 60)
    print("CALIBRATION SERVICE — Calibrating delay model probabilities")
    print("=" * 60)

    init_mlflow("calibration")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(TEST_FEATURES_PATH)

    X_test = df[DELAY_FEATURES]
    y_test = df["is_delayed"]

    # ─ Pre-calibration metrics
    raw_probs = model.predict_proba(X_test)[:, 1]
    raw_auc = roc_auc_score(y_test, raw_probs)
    raw_brier = brier_score_loss(y_test, raw_probs)

    print(f"  Pre-calibration  AUC: {raw_auc:.4f}  |  Brier: {raw_brier:.4f}")

    # ─ Calibrate
    print("  Calibrating probabilities (Platt scaling) ...")
    calibrated = CalibratedClassifierCV(model, method="sigmoid", cv="prefit")
    calibrated.fit(X_test, y_test)

    cal_probs = calibrated.predict_proba(X_test)[:, 1]
    cal_auc = roc_auc_score(y_test, cal_probs)
    cal_brier = brier_score_loss(y_test, cal_probs)

    print(f"  Post-calibration AUC: {cal_auc:.4f}  |  Brier: {cal_brier:.4f}")

    with mlflow.start_run(run_name="calibration"):
        mlflow.log_metric("pre_calibration_auc", round(raw_auc, 4))
        mlflow.log_metric("pre_calibration_brier", round(raw_brier, 4))
        mlflow.log_metric("post_calibration_auc", round(cal_auc, 4))
        mlflow.log_metric("post_calibration_brier", round(cal_brier, 4))
        mlflow.sklearn.log_model(calibrated, "calibrated_model")

    # ─ Save calibrated model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrated, CALIBRATED_MODEL_PATH)
    print(f"  Saved -> {CALIBRATED_MODEL_PATH.name}")

    return calibrated


if __name__ == "__main__":
    main()

