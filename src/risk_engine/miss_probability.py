"""
miss_probability.py — Probability of Missing Flight Microservice
==================================================================
Estimates the probability that a traveler misses a connecting flight
based on predicted delay, buffer time, congestion, and terminal
transfer time.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
from src.utils.config import REPORT_DIR, REPORT_PATH

# ─ Transfer time assumptions (minutes)
MIN_CONNECTION_TIME = 45       # FAA minimum connection at JFK
TERMINAL_TRANSFER_TIME = 15    # average inter-terminal transfer
SAME_TERMINAL_TRANSFER = 5     # same terminal walk


def sigmoid(x):
    """Numerically stable sigmoid."""
    return np.where(x >= 0, 1 / (1 + np.exp(-x)), np.exp(x) / (1 + np.exp(x)))


def main():
    print("=" * 60)
    print("MISS PROBABILITY SERVICE — Estimating flight miss risk")
    print("=" * 60)

    risk = pd.read_csv(REPORT_PATH)

    # ─ Estimate effective delay (in minutes) from delay probability
    # Map delay_prob to expected delay duration using a reasonable transform:
    #   delay_prob close to 0 -> ~0 min delay, delay_prob close to 1 -> 60 min delay
    risk["expected_delay_min"] = risk["delay_prob"] * 60

    # ─ Congestion adds transfer overhead
    risk["transfer_time"] = (
        SAME_TERMINAL_TRANSFER
        + risk["predicted_congestion"] * (TERMINAL_TRANSFER_TIME - SAME_TERMINAL_TRANSFER)
    )

    # ─ Effective slack = buffer - expected_delay - transfer        #how many minutes you really have left after accounting for likely delay and walking
    risk["effective_slack"] = (
        risk["buffer_minutes"] - risk["expected_delay_min"] - risk["transfer_time"]
    )       # +:you still have time left, 0:exactly on the edge, -:you’re already late

    # ─ P(miss) via sigmoid: negative slack → high miss probability
    #   Scale factor controls sharpness (10 min = moderate sensitivity)
    risk["miss_probability"] = sigmoid(-risk["effective_slack"] / 10)       #probability of missing the flight

    # ─ Risk band classification
    risk["miss_risk_band"] = pd.cut(
        risk["miss_probability"],
        bins=[0, 0.15, 0.40, 1.0],
        labels=["safe", "caution", "danger"],
    )

    # ─ Save
    out_path = REPORT_DIR / "miss_probability.csv"
    risk.to_csv(out_path, index=False)

    print(f"\n  Mean miss probability: {risk['miss_probability'].mean():.3f}")      #On average, passengers have this much chance of missing their connection
    print(f"\n  Risk band distribution:")
    print(risk["miss_risk_band"].value_counts().to_string())
    print(f"\n  Saved -> {out_path.name}  ({len(risk)} rows)")

    return risk


if __name__ == "__main__":
    main()
