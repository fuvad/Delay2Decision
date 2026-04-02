"""
feature_engineering.py — Feature Engineering Microservice
==========================================================
Takes validated silver data, engineers all features (time,
weather, rolling, congestion, carrier/route averages),
performs a temporal train/test split, and outputs gold-level
train and test CSVs.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from src.utils.config import (
    VALIDATED_SILVER_PATH,
    CONGESTION_FEATURES_PATH,
    TRAIN_FEATURES_PATH,
    TEST_FEATURES_PATH,
    FEATURES,
    TRAIN_RATIO,
)


def main():
    print("=" * 60)
    print("FEATURE ENGINEERING SERVICE - Building gold features")
    print("=" * 60)

    df = pd.read_csv(VALIDATED_SILVER_PATH)
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # ─ Time features
    print("\n -> Time features")
    df["hour"]        = df["CRSDepTime"] // 100
    df["day_of_week"] = df["FlightDate"].dt.dayofweek
    df["is_weekend"]  = df["day_of_week"].isin([5, 6]).astype(int)

    # ─ Weather severity
    print(" -> Weather severity")
    df["weather_severity"] = df["PRCP"].fillna(0) * 2 + df["WDSP"].fillna(0) * 0.5

    # ─ Per-terminal rolling features (past only, no leakage)
    print(" -> Per-terminal rolling features")
    df = df.sort_values(["terminal", "FlightDate", "CRSDepTime"]).reset_index(drop=True)

    df["rolling_origin_delay"] = (
        df.groupby("terminal")["DepDelay"]
        .rolling(window=200, min_periods=20)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["prev_delay"] = df.groupby("terminal")["DepDelay"].shift(1)

    # ─ Congestion score (merge on shared key)
    print(" -> Congestion score merge")
    if CONGESTION_FEATURES_PATH.exists():
        congestion = pd.read_csv(CONGESTION_FEATURES_PATH, parse_dates=["timestamp"])
        df = df.merge(
            congestion[["timestamp", "terminal", "congestion_score"]],
            on=["timestamp", "terminal"],
            how="left",
        )
        print(" Merged via (timestamp, terminal) key")
    else:
        print(" WARNING: congestion features not found — using zeros")
        df["congestion_score"] = 0.0

    # ─ Target variable
    df["is_delayed"] = (df["ArrDelay"] > 15).astype(int)
    print(f" -> Delay rate: {df['is_delayed'].mean():.2%}")

    # ─ Temporal train/test split
    print(f"\n -> Temporal train/test split ({TRAIN_RATIO:.0%} / {1 - TRAIN_RATIO:.0%} by date)")
    dates = sorted(df["FlightDate"].unique())
    split_idx = int(len(dates) * TRAIN_RATIO)
    train_cutoff = dates[split_idx - 1]

    train_df = df[df["FlightDate"] <= train_cutoff].copy()
    test_df  = df[df["FlightDate"] >  train_cutoff].copy()

    print(f"    Train: up to {train_cutoff.date()}  ({len(train_df):,} rows)")
    print(f"    Test:  after {train_cutoff.date()} ({len(test_df):,} rows)")

    # ─ Carrier & route averages (train-only, then map to test)
    print(" -> Carrier / route averages (train-only)")

    carrier_avg = train_df.groupby("Reporting_Airline")["ArrDelay"].mean().rename("carrier_avg_delay")
    train_df = train_df.join(carrier_avg, on="Reporting_Airline")
    test_df  = test_df.join(carrier_avg, on="Reporting_Airline")

    train_df["route"] = train_df["Origin"] + "_" + train_df["Dest"]
    test_df["route"]  = test_df["Origin"]  + "_" + test_df["Dest"]

    route_avg = train_df.groupby("route")["ArrDelay"].mean().rename("route_avg_delay")
    train_df = train_df.join(route_avg, on="route")
    test_df  = test_df.join(route_avg, on="route")

    # ─ Save gold train / test CSVs
    train_clean = train_df[FEATURES + ["is_delayed"]].dropna()
    test_clean  = test_df[FEATURES  + ["is_delayed"]].dropna()

    TRAIN_FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    train_clean.to_csv(TRAIN_FEATURES_PATH, index=False)
    test_clean.to_csv(TEST_FEATURES_PATH, index=False)

    print(f"\n  Train shape: {train_clean.shape}  |  delay rate: {train_clean['is_delayed'].mean():.2%}")
    print(f"  Test  shape: {test_clean.shape}   |  delay rate: {test_clean['is_delayed'].mean():.2%}")
    print(f"  Saved → {TRAIN_FEATURES_PATH.name}, {TEST_FEATURES_PATH.name}")

    return train_clean, test_clean


if __name__ == "__main__":
    main()
