"""
evaluate_model.py — Evaluation Microservice
=============================================
Reads the saved delay predictions and prints AUC, risk-bucket
analysis, and a classification report.

Run standalone:
    python src/evaluation/evaluate_model.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from sklearn.metrics import roc_auc_score, classification_report
import mlflow

from src.utils.config import DELAY_PREDICTIONS_PATH
from src.utils.mlflow_config import init_mlflow


def main():
    print("=" * 60)
    print("EVALUATION SERVICE — Delay model evaluation")
    print("=" * 60)

    init_mlflow("evaluation")

    risk = pd.read_csv(DELAY_PREDICTIONS_PATH)

    if "is_delayed" not in risk.columns:
        raise ValueError(
            "'is_delayed' column not found. Re-run the Prediction Service first."
        )

    # ─ AUC
    auc = roc_auc_score(risk["is_delayed"], risk["delay_prob"])
    print(f"\n  Delay Model AUC: {auc:.4f}")

    # ─ Risk bucket analysis
    risk["bucket"] = pd.cut(
        risk["delay_prob"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["low", "medium", "high"],
    )
    bucket_rates = risk.groupby("bucket")["is_delayed"].mean()
    print("\n  Delay rate by risk bucket:")
    print(bucket_rates.to_string())

    # ─ Classification report
    risk["predicted"] = (risk["delay_prob"] >= 0.5).astype(int)
    print("\n  Classification Report (threshold=0.5):")
    print(classification_report(
        risk["is_delayed"], risk["predicted"],
        target_names=["on-time", "delayed"],
    ))

    with mlflow.start_run(run_name="delay-evaluation"):
        mlflow.log_metric("final_auc", round(auc, 4))
        for bucket_name, rate in bucket_rates.items():
            mlflow.log_metric(f"delay_rate_{bucket_name}", round(float(rate), 4))


if __name__ == "__main__":
    main()

