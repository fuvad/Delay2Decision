"""
congestion_features.py — Congestion Feature Engineering
=========================================================
Reads validated silver data, computes congestion features (time, spatial,
terminal), builds forecast features with rolling/future targets, and saves
gold-level datasets for both the congestion forecaster and anomaly detector.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

from src.utils.config import (
    VALIDATED_SILVER_PATH,
    CONGESTION_FEATURES_PATH,
    CONGESTION_FORECAST_FEATURES_PATH,
)


def main():
    print("=" * 60)
    print("CONGESTION FE SERVICE — Building congestion features")
    print("=" * 60)

    df = pd.read_csv(VALIDATED_SILVER_PATH)
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = df.sort_values(["terminal", "timestamp"]).reset_index(drop=True)
    df["hour"] = df["CRSDepTime"] // 100

    # Per-terminal rolling delay
    print("  -> Rolling origin delay")
    df["rolling_origin_delay"] = (
        df.groupby("terminal")["DepDelay"]
        .rolling(window=200, min_periods=20)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["prev_delay"] = df.groupby("terminal")["DepDelay"].shift(1)

    # Airport-wide time congestion
    print("  -> Time congestion (airport-wide hourly volume)")
    airport_hourly = (
        df.groupby(["FlightDate", "hour"])
        .size()
        .rename("airport_hourly_volume")
        .reset_index()
    )
    df = df.merge(airport_hourly, on=["FlightDate", "hour"])
    df["time_congestion"] = MinMaxScaler().fit_transform(df[["airport_hourly_volume"]])

    # Terminal congestion
    print("  -> Terminal congestion")
    terminal_hour = (
        df.groupby(["FlightDate", "terminal", "hour"])
        .size()
        .rename("terminal_flights")
        .reset_index()
    )
    df = df.merge(terminal_hour, on=["FlightDate", "terminal", "hour"])
    df["terminal_congestion"] = MinMaxScaler().fit_transform(df[["terminal_flights"]])

    # Spatial congestion (per terminal)
    print("  -> Spatial congestion (per-terminal gate density)")
    df["spatial_density"] = 0
    for terminal, group in df.groupby("terminal"):
        coords = group[["x", "y"]].values
        local_density = []
        for i in range(len(coords)):
            d = np.sqrt(((coords - coords[i]) ** 2).sum(axis=1))
            local_density.append((d < 8).sum())
        df.loc[group.index, "spatial_density"] = local_density

    df["spatial_congestion"] = MinMaxScaler().fit_transform(df[["spatial_density"]])

    # Final congestion score
    df["congestion_score"] = (
        df["time_congestion"] * 0.4
        + df["terminal_congestion"] * 0.35
        + df["spatial_congestion"] * 0.25
    )

    # Save base congestion features
    base_cols = [
        "timestamp", "hour", "terminal", "x", "y",
        "time_congestion", "rolling_origin_delay", "congestion_score",
    ]
    CONGESTION_FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[base_cols].to_csv(CONGESTION_FEATURES_PATH, index=False)
    print(f"  Saved -> {CONGESTION_FEATURES_PATH.name}")

    # Build congestion forecast features
    print("  -> Building congestion forecast features")
    df["rolling_congestion"] = (
        df.groupby("terminal")["congestion_score"]
        .rolling(20, min_periods=5)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["future_congestion"] = df.groupby("terminal")["congestion_score"].shift(-1)

    forecast_cols = [
        "hour", "terminal", "time_congestion",
        "rolling_congestion", "rolling_origin_delay", "future_congestion",
    ]
    forecast_df = df[forecast_cols].dropna()
    forecast_df.to_csv(CONGESTION_FORECAST_FEATURES_PATH, index=False)
    print(f"  Saved -> {CONGESTION_FORECAST_FEATURES_PATH.name}  ({len(forecast_df)} rows)")

    print(f"\n  Congestion score range: [{df['congestion_score'].min():.3f}, {df['congestion_score'].max():.3f}]")
    return df


if __name__ == "__main__":
    main()
