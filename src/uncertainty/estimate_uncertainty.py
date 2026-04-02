"""
estimate_uncertainty.py — Uncertainty Estimation Microservice
==============================================================
Uses bootstrap resampling to estimate prediction uncertainty
for the delay model.  Saves mean probabilities and standard
deviations to a .npy file.

Tells how confident our model is by calculating predict_proba each time

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import joblib

from src.utils.config import (
    MODEL_PATH,
    TEST_FEATURES_PATH,
    DELAY_FEATURES,
    MODEL_DIR,
    UNCERTAINTY_PATH,
)

ITERATIONS = 15     #resampling runs


def main():
    print("=" * 60)
    print("UNCERTAINTY SERVICE - Bootstrap uncertainty estimation")
    print("=" * 60)

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(TEST_FEATURES_PATH)
    X = df[DELAY_FEATURES]

    print(f"  Running {ITERATIONS} bootstrap iterations on {len(X)} samples ...")

    samples = []
    for i in range(ITERATIONS):
        idx = np.random.choice(len(X), len(X), replace=True)
        preds = model.predict_proba(X.iloc[idx])[:, 1]
        samples.append(preds)

    samples = np.vstack(samples)
    mean_prob = samples.mean(axis=0)
    uncertainty = samples.std(axis=0)

    print(f"  Mean uncertainty (std): {uncertainty.mean():.4f}")
    print(f"  Max  uncertainty (std): {uncertainty.max():.4f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    np.save(UNCERTAINTY_PATH, np.vstack([mean_prob, uncertainty]))
    print(f"  Saved -> {UNCERTAINTY_PATH.name}")

    return mean_prob, uncertainty


if __name__ == "__main__":
    main()
