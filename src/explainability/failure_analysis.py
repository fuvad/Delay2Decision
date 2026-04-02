"""
failure_analysis.py — Failure Analysis Microservice
=====================================================
Runs the delay model on the test set, identifies false negatives
and false positives, and saves detailed error analysis reports.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import joblib
from sklearn.metrics import confusion_matrix

from src.utils.config import (
    MODEL_PATH,
    TEST_FEATURES_PATH,
    DELAY_FEATURES,
    REPORT_DIR,
)


def main():
    print("=" * 60)
    print("FAILURE ANALYSIS SERVICE — Error analysis")
    print("=" * 60)

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(TEST_FEATURES_PATH)

    X = df[DELAY_FEATURES]
    y = df["is_delayed"]

    probs = model.predict_proba(X)[:, 1]
    preds = (probs > 0.5).astype(int)

    # ─ Full predictions
    analysis = X.copy()
    analysis["actual"] = y.values
    analysis["pred"] = preds
    analysis["prob"] = probs

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    analysis.to_csv(REPORT_DIR / "predictions_full.csv", index=False)

    # ─ Confusion matrix 
    tn, fp, fn, tp = confusion_matrix(y, preds).ravel()
    metrics = {
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }
    pd.DataFrame([metrics]).to_csv(REPORT_DIR / "confusion_matrix.csv", index=False)

    # ─ False negatives / positives 
    false_neg = analysis[(analysis["actual"] == 1) & (analysis["pred"] == 0)]
    false_pos = analysis[(analysis["actual"] == 0) & (analysis["pred"] == 1)]

    false_neg.to_csv(REPORT_DIR / "false_negatives.csv", index=False)
    false_pos.to_csv(REPORT_DIR / "false_positives.csv", index=False)

    print(f"  Confusion: TP={tp}  TN={tn}  FP={fp}  FN={fn}")
    print(f"  False negatives: {len(false_neg)}  |  False positives: {len(false_pos)}")
    print(f"  Saved -> predictions_full.csv, confusion_matrix.csv, false_negatives.csv, false_positives.csv")

    return metrics


if __name__ == "__main__":
    main()
