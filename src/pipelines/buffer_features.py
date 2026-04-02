"""
buffer_features.py — Buffer Feature Engineering Microservice
========================================================================
Merges congestion features with delay features to compute the
buffer-time training target, and saves the gold buffer dataset.

"""

import sys
from pathlib import Path

# Fix python path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from src.utils.config import (
    CONGESTION_FEATURES_PATH,
    TRAIN_FEATURES_PATH,
    BUFFER_FEATURES_PATH,
)


def main():
    print("=" * 60)
    print("BUFFER FE SERVICE — Building buffer training features")
    print("=" * 60)

    congestion = pd.read_csv(CONGESTION_FEATURES_PATH)
    delay = pd.read_csv(TRAIN_FEATURES_PATH)

    # Drop columns from delay that duplicate congestion columns to avoid
    # suffix collisions (_x / _y) after merge.
    overlap_cols = [c for c in congestion.columns if c in delay.columns and c != "hour"]
    delay_clean = delay.drop(columns=overlap_cols, errors="ignore")     #emove duplicates from delay, congestion becomes source of truth

    # Merge on 'hour' (shared key between congestion and delay features)
    full = congestion.merge(delay_clean, on=["hour"], how="inner")

    # ─ Buffer target: base + congestion penalty + ops penalty
    BASE = 15  # minimum buffer in minutes

    full["congestion_penalty"] = full["congestion_score"] * 25
    full["ops_penalty"] = full["rolling_origin_delay"].clip(lower=0) * 0.3

    full["buffer_minutes"] = (
        BASE + full["congestion_penalty"] + full["ops_penalty"]
    ).clip(upper=60)

    # ─ Save buffer training features
    out_cols = [
        "hour", "terminal", "x", "y",
        "congestion_score", "rolling_origin_delay",
        "buffer_minutes",
    ]
    out = full[out_cols].dropna()

    BUFFER_FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(BUFFER_FEATURES_PATH, index=False)

    print(f"  Buffer features saved -> {BUFFER_FEATURES_PATH.name}  ({len(out)} rows)")
    print(f"  Buffer range: [{out['buffer_minutes'].min():.1f}, {out['buffer_minutes'].max():.1f}] minutes")

    return out


if __name__ == "__main__":
    main()
