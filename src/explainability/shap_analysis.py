"""
shap_analysis.py — SHAP Explainability Microservice
=====================================================
Computes SHAP values for the champion delay model, generates
a beeswarm plot and feature importance bar chart, and saves
raw SHAP values to CSV.


"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import joblib
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.utils.config import (
    MODEL_PATH,
    TEST_FEATURES_PATH,
    DELAY_FEATURES,
    REPORT_DIR,
)


def main():
    print("=" * 60)
    print("SHAP SERVICE — Model explainability analysis")
    print("=" * 60)

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(TEST_FEATURES_PATH)
    X = df[DELAY_FEATURES]

    # Sample for speed
    X_sample = X.sample(n=min(2000, len(X)), random_state=42)
    print(f"  Running SHAP on {len(X_sample)} samples ...")

    explainer = shap.Explainer(model.predict_proba, X_sample)
    shap_values = explainer(X_sample)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ─ Raw SHAP values (positive class)
    pd.DataFrame(
        shap_values.values[:, :, 1],
        columns=X_sample.columns,
    ).to_csv(REPORT_DIR / "shap_values.csv", index=False)

    # ─ Beeswarm plo
    shap.plots.beeswarm(shap_values[:, :, 1], show=False)
    plt.tight_layout()
    plt.savefig(REPORT_DIR / "shap_summary.png", dpi=150)
    plt.close()

    # ─ Feature importance bar
    shap.plots.bar(shap_values[:, :, 1], show=False)
    plt.tight_layout()
    plt.savefig(REPORT_DIR / "shap_feature_importance.png", dpi=150)
    plt.close()

    print("  SHAP analysis complete.")
    print(f"  Saved -> shap_values.csv, shap_summary.png, shap_feature_importance.png")

    return shap_values


if __name__ == "__main__":
    main()
