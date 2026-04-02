"""
predict_delay.py — Prediction Microservice
============================================
Loads the champion model, runs predictions on the held-out
test set, generates risk buckets, and saves the predictions
with ground-truth labels to reports/delay_predictions.csv.

Run standalone:
    python src/prediction/predict_delay.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import joblib
from sklearn.metrics import roc_auc_score, classification_report

from src.utils.config import (
    TEST_FEATURES_PATH,
    DELAY_FEATURES,
    MODEL_PATH,
    REPORT_DIR,
    DELAY_PREDICTIONS_PATH,
)


def main():
    print("=" * 60)
    print("PREDICTION SERVICE — Scoring test set & saving predictions")
    print("=" * 60)

    # ─ Load model and test data
    model = joblib.load(MODEL_PATH)
    test_clean = pd.read_csv(TEST_FEATURES_PATH)

    X_test = test_clean[DELAY_FEATURES]
    y_test = test_clean["is_delayed"]

    # ─ Generate predictions
    test_probs = model.predict_proba(X_test)[:, 1]
    test_preds = (test_probs >= 0.25).astype(int)

    # ─ Detailed evaluation output
    auc = roc_auc_score(y_test, test_probs)
    print(f"\n  AUC-ROC : {auc:.4f}")
    print("\n  Classification Report (threshold = 0.25):")
    print(classification_report(y_test, test_preds, target_names=["on-time", "delayed"]))

    # ─ Risk bucket analysis
    bucket_df = pd.DataFrame({"delay_prob": test_probs, "is_delayed": y_test.values})
    bucket_df["bucket"] = pd.cut(
        bucket_df["delay_prob"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["low", "medium", "high"],
    )
    print("  Delay rate by risk bucket:")
    print(bucket_df.groupby("bucket")["is_delayed"].mean().to_string())
    print()

    # ─ Save predictions
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    risk_out = test_clean[["is_delayed"]].copy().reset_index(drop=True)
    risk_out["delay_prob"] = test_probs

    risk_out.to_csv(DELAY_PREDICTIONS_PATH, index=False)
    print(f"  Predictions saved -> {DELAY_PREDICTIONS_PATH.name}  (is_delayed label included)")

    return risk_out


if __name__ == "__main__":
    main()
