"""
layover_risk_scoring.py — Layover Risk Scoring Microservice
=============================================================
Combines all model outputs (delay, congestion forecast, anomaly,
buffer) into a unified layover risk score, then applies a
personalization layer to adjust buffer by traveller profile.

Pipeline:  ML models → risk + buffer → personalization → final buffer
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import MinMaxScaler

from src.decision_engine.personalization import personalize_all_profiles

from src.utils.config import (
    VALIDATED_SILVER_PATH,
    CONGESTION_FEATURES_PATH,
    DELAY_FEATURES,
    MODEL_PATH,
    CONGESTION_FORECASTER_PATH,
    ANOMALY_DETECTOR_PATH,
    BUFFER_MODEL_PATH,
    ANOMALY_FEATURES,
    REPORT_DIR,
    REPORT_PATH,
)


def main():
    print("=" * 60)
    print("LAYOVER RISK SERVICE — Computing unified risk score")
    print("=" * 60)

    # ─ Load all models
    delay_model = joblib.load(MODEL_PATH)
    congestion_model = joblib.load(CONGESTION_FORECASTER_PATH)
    anomaly_model = joblib.load(ANOMALY_DETECTOR_PATH)
    buffer_model = joblib.load(BUFFER_MODEL_PATH)
    print("  All 4 models loaded")

    # ─ Load congestion features (base dataset)
    base = pd.read_csv(CONGESTION_FEATURES_PATH)
    base["timestamp"] = pd.to_datetime(base["timestamp"])

    # ─ Load validated silver for delay features
    silver = pd.read_csv(VALIDATED_SILVER_PATH)
    silver["FlightDate"] = pd.to_datetime(silver["FlightDate"])
    silver["timestamp"] = pd.to_datetime(silver["timestamp"])
    silver["hour"] = silver["CRSDepTime"] // 100
    silver["day_of_week"] = silver["FlightDate"].dt.dayofweek
    silver["is_weekend"] = silver["day_of_week"].isin([5, 6]).astype(int)
    silver["weather_severity"] = silver["PRCP"].fillna(0) * 2 + silver["WDSP"].fillna(0) * 0.5
    silver = silver.sort_values(["terminal", "FlightDate", "CRSDepTime"]).reset_index(drop=True)
    silver["rolling_origin_delay"] = (
        silver.groupby("terminal")["DepDelay"]
        .rolling(window=200, min_periods=20).mean()
        .reset_index(level=0, drop=True)
    )
    silver["prev_delay"] = silver.groupby("terminal")["DepDelay"].shift(1)
    silver["is_delayed"] = (silver["ArrDelay"] > 15).astype(int)

    # Merge congestion score AND time_congestion into silver
    silver = silver.merge(
        base[["timestamp", "terminal", "congestion_score", "time_congestion"]],
        on=["timestamp", "terminal"], how="left",
    )

    # Compute carrier/route averages (global - ok for inference)
    carrier_avg = silver.groupby("Reporting_Airline")["ArrDelay"].mean().rename("carrier_avg_delay")
    silver = silver.join(carrier_avg, on="Reporting_Airline")
    silver["route"] = silver["Origin"] + "_" + silver["Dest"]
    route_avg = silver.groupby("route")["ArrDelay"].mean().rename("route_avg_delay")
    silver = silver.join(route_avg, on="route")

    # ─ Delay predictions
    print("  -> Delay predictions")
    delay_X = silver[DELAY_FEATURES].dropna()
    silver = silver.loc[delay_X.index].copy()
    silver["delay_prob"] = delay_model.predict_proba(delay_X)[:, 1]

    # ─ Congestion forecast
    print("  -> Congestion forecast")
    silver["rolling_congestion"] = (
        silver.groupby("terminal")["congestion_score"]
        .rolling(20, min_periods=5).mean()
        .reset_index(level=0, drop=True)
    )
    cong_X = silver[["hour", "terminal", "time_congestion", "rolling_congestion", "rolling_origin_delay"]].copy()

    cong_X = cong_X.dropna()
    silver = silver.loc[cong_X.index].copy()
    predicted_congestion = congestion_model.predict(cong_X)
    silver["predicted_congestion"] = MinMaxScaler().fit_transform(
        predicted_congestion.reshape(-1, 1)
    )

    # ─ Anomaly detection
    print("  -> Anomaly detection")
    anom_X = silver[ANOMALY_FEATURES]
    silver["is_anomaly"] = (anomaly_model.predict(anom_X) == -1).astype(int)

    # ─ Buffer prediction
    print("  -> Buffer prediction")
    buffer_feature_order = buffer_model.feature_names_in_
    buffer_X = silver[buffer_feature_order]
    silver["buffer_minutes"] = buffer_model.predict(buffer_X)

    # ─ Unified risk score
    print("  -> Computing unified risk score")
    silver["uncertainty"] = (
        pd.Series(silver["delay_prob"])
        .rolling(50, min_periods=10).std().fillna(0.20)
    )
    silver["risk"] = np.clip(
        0.45 * silver["delay_prob"]
        + 0.20 * silver["uncertainty"]
        + 0.25 * silver["predicted_congestion"]
        + 0.10 * silver["is_anomaly"],
        0, 1,
    )

    # ─ Risk thresholds → actionable labels
    silver["risk_level"] = pd.cut(
        silver["risk"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["low", "medium", "high"],
        include_lowest=True,
    )
    silver["action"] = silver["risk_level"].map({
        "low":    "Safe — proceed normally",
        "medium": "Be careful — allow extra buffer",
        "high":   "Don't move — high risk of missed connection",
    })

    # ─ Personalization layer (domain logic, NOT ML)
    print("  -> Applying personalization layer")
    silver = personalize_all_profiles(silver)

    # ─ Save
    out_cols = [
        "is_delayed", "delay_prob", "uncertainty", "predicted_congestion",
        "is_anomaly", "buffer_minutes", "risk", "risk_level", "action",
        "buffer_conservative", "buffer_balanced", "buffer_aggressive",
    ]
    out = silver[out_cols]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORT_PATH, index=False)

    print(f"\n  Risk score range: [{out['risk'].min():.3f}, {out['risk'].max():.3f}]")
    print(f"  Mean buffer (ML raw):      {out['buffer_minutes'].mean():.1f} min")
    print(f"  Mean buffer (conservative): {out['buffer_conservative'].mean():.1f} min")
    print(f"  Mean buffer (balanced):     {out['buffer_balanced'].mean():.1f} min")
    print(f"  Mean buffer (aggressive):   {out['buffer_aggressive'].mean():.1f} min")
    print(f"  Anomalies: {out['is_anomaly'].sum()} ({out['is_anomaly'].mean():.1%})")
    print(f"  Risk breakdown: {out['risk_level'].value_counts().to_dict()}")
    print(f"  Saved -> {REPORT_PATH.name}  ({len(out)} rows)")

    return out


if __name__ == "__main__":
    main()
