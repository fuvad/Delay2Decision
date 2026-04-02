"""
simulation_test.py — Simulation-Based Testing Microservice
============================================================
Runs the full pipeline on the actual data and validates that every
stage produced the expected outputs with correct schemas and
reasonable metric ranges.

ML integration test - acts like CI
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import pandas as pd
import numpy as np
import joblib

from src.utils.config import (
    VALIDATED_SILVER_PATH,
    CONGESTION_FEATURES_PATH,
    CONGESTION_FORECAST_FEATURES_PATH,
    TRAIN_FEATURES_PATH,
    TEST_FEATURES_PATH,
    BUFFER_FEATURES_PATH,
    MODEL_PATH,
    CONGESTION_FORECASTER_PATH,
    ANOMALY_DETECTOR_PATH,
    BUFFER_MODEL_PATH,
    CALIBRATED_MODEL_PATH,
    UNCERTAINTY_PATH,
    DELAY_PREDICTIONS_PATH,
    REPORT_PATH,
    METRICS_PATH,
    DELAY_FEATURES,
    REPORT_DIR,
)


def check(condition, name):
    """Print pass/fail for a test condition."""
    status = "PASS" if condition else "FAIL"
    symbol = "+" if condition else "x"
    print(f"  [{symbol}] {name}")
    return condition


def main():
    print("=" * 60)
    print("SIMULATION TEST — Validating full pipeline outputs")
    print("=" * 60)

    passed = 0
    failed = 0

    def run(cond, name):
        nonlocal passed, failed
        if check(cond, name):
            passed += 1
        else:
            failed += 1

    # ─ 1. Data files exist
    print("\n  1. DATA FILES")
    run(VALIDATED_SILVER_PATH.exists(), "silver_validated.csv exists")
    run(CONGESTION_FEATURES_PATH.exists(), "congestion features exist")
    run(CONGESTION_FORECAST_FEATURES_PATH.exists(), "congestion forecast features exist")
    run(TRAIN_FEATURES_PATH.exists(), "delay train features exist")
    run(TEST_FEATURES_PATH.exists(), "delay test features exist")
    run(BUFFER_FEATURES_PATH.exists(), "buffer features exist")

    # ─ 2. Model files exist 
    print("\n  2. MODEL FILES")
    run(MODEL_PATH.exists(), "delay model exists")
    run(CONGESTION_FORECASTER_PATH.exists(), "congestion forecaster exists")
    run(ANOMALY_DETECTOR_PATH.exists(), "anomaly detector exists")
    run(BUFFER_MODEL_PATH.exists(), "buffer model exists")
    run(CALIBRATED_MODEL_PATH.exists(), "calibrated model exists")
    run(UNCERTAINTY_PATH.exists(), "uncertainty stats exist")

    # ─ 3. Report files exist
    print("\n  3. REPORT FILES")
    run(DELAY_PREDICTIONS_PATH.exists(), "delay predictions exist")
    run(REPORT_PATH.exists(), "layover risk report exists")
    run(METRICS_PATH.exists(), "training metrics exist")
    run((REPORT_DIR / "miss_probability.csv").exists(), "miss probability report exists")

    # ─ 4. Schema validation
    print("\n  4. SCHEMA VALIDATION")

    if TRAIN_FEATURES_PATH.exists():
        train = pd.read_csv(TRAIN_FEATURES_PATH)
        run(set(DELAY_FEATURES + ["is_delayed"]).issubset(train.columns),
            "train features have all expected columns")
        run(len(train) > 100, f"train has sufficient rows ({len(train)})")

    if DELAY_PREDICTIONS_PATH.exists():
        preds = pd.read_csv(DELAY_PREDICTIONS_PATH)
        run("delay_prob" in preds.columns, "predictions have delay_prob")
        run("is_delayed" in preds.columns, "predictions have is_delayed")
        run(preds["delay_prob"].between(0, 1).all(), "delay_prob in [0, 1]")

    if REPORT_PATH.exists():
        risk = pd.read_csv(REPORT_PATH)
        for col in ["delay_prob", "predicted_congestion", "is_anomaly", "buffer_minutes", "risk"]:
            run(col in risk.columns, f"layover risk has '{col}'")
        run(risk["risk"].between(0, 1).all(), "risk score in [0, 1]")

    if (REPORT_DIR / "miss_probability.csv").exists():
        miss = pd.read_csv(REPORT_DIR / "miss_probability.csv")
        run("miss_probability" in miss.columns, "miss report has 'miss_probability'")
        run(miss["miss_probability"].between(0, 1).all(), "miss_probability in [0, 1]")

    # ─ 5. Metric thresholds
    print("\n  5. METRIC THRESHOLDS")

    if METRICS_PATH.exists():
        metrics = json.load(open(METRICS_PATH))
        auc = metrics.get("champion_auc", 0)
        run(auc > 0.55, f"delay AUC > 0.55 (actual: {auc:.4f})")

    if UNCERTAINTY_PATH.exists():
        unc = np.load(UNCERTAINTY_PATH)
        run(unc.shape[0] == 2, "uncertainty has mean + std rows")
        run(unc[1].max() < 0.5, f"max uncertainty < 0.5 (actual: {unc[1].max():.4f})")

    # ─ 6. Model inference smoke test
    print("\n  6. INFERENCE SMOKE TEST")
    if MODEL_PATH.exists() and TEST_FEATURES_PATH.exists():
        model = joblib.load(MODEL_PATH)
        test = pd.read_csv(TEST_FEATURES_PATH)
        X = test[DELAY_FEATURES].head(10)
        try:
            probs = model.predict_proba(X)[:, 1]
            run(len(probs) == 10, "delay model produces 10 predictions")
            run(all(0 <= p <= 1 for p in probs), "all predictions in [0, 1]")
        except Exception as e:
            run(False, f"delay model inference failed: {e}")

    # ─ Summary
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 60}")

    if failed == 0:
        print("  All tests passed!")
    else:
        print("  Some tests failed — check outputs above.")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
