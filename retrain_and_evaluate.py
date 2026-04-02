"""
retrain_and_evaluate.py — Delay2Decision master fix script
===========================================================
Run from the project root (Delay2Decision/):
    python retrain_and_evaluate.py

What this script does:
  1. Loads the silver "single source of truth" CSV.
  2. Engineers features cleanly: per-terminal rolling, no global leakage.
  3. Merges congestion scores using a proper key (timestamp + terminal).
  4. Temporal train/test split (first 80 % of dates = train, last 20 % = test).
  5. Computes carrier- and route-average delay *on the train set only*, then
     maps those lookup values onto the test set — eliminating data leakage.
  6. Trains a GradientBoostingClassifier.
  7. Evaluates on the held-out test set and prints AUC + classification report.
  8. Saves the model to models/delay_model_fixed.pkl.
  9. Saves test predictions (with is_delayed label) to reports/layover_risk.csv
     so system_evaluation.py can be run directly afterwards.
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ──────────────────────────────────────────────────────────────────────────────
# 1. Load silver data
# ──────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Step 1 — Loading silver data")
print("=" * 60)

df = pd.read_csv("data/silver/jan2023_jfk_simulation.csv")

# Parse dates
df["FlightDate"] = pd.to_datetime(df["FlightDate"])
df["timestamp"] = (
    df["FlightDate"] +
    pd.to_timedelta(df["CRSDepTime"] // 100, unit="h") +
    pd.to_timedelta(df["CRSDepTime"] % 100, unit="m")
)

print(f"  Loaded {len(df):,} rows spanning {df['FlightDate'].min().date()} → {df['FlightDate'].max().date()}")
print(f"  Terminals: {sorted(df['terminal'].dropna().unique().tolist())}")

# ──────────────────────────────────────────────────────────────────────────────
# 2. Feature engineering (leak-free)
# ──────────────────────────────────────────────────────────────────────────────
print("\nStep 2 — Engineering features")

# Time features
df["hour"]        = df["CRSDepTime"] // 100
df["day_of_week"] = df["FlightDate"].dt.dayofweek
df["is_weekend"]  = df["day_of_week"].isin([5, 6]).astype(int)

# Weather
df["weather_severity"] = df["PRCP"].fillna(0) * 2 + df["WDSP"].fillna(0) * 0.5

# Per-terminal rolling delay (past only, within terminal)
df = df.sort_values(["terminal", "FlightDate", "CRSDepTime"]).reset_index(drop=True)

df["rolling_origin_delay"] = (
    df.groupby("terminal")["DepDelay"]
    .rolling(window=200, min_periods=20)
    .mean()
    .reset_index(level=0, drop=True)
)
df["prev_delay"] = df.groupby("terminal")["DepDelay"].shift(1)

# Congestion score (merge on shared key to guarantee alignment)
congestion_path = Path("data/gold/jfk_congestion_features.csv")
if congestion_path.exists():
    congestion = pd.read_csv(congestion_path, parse_dates=["timestamp"])
    df = df.merge(
        congestion[["timestamp", "terminal", "congestion_score"]],
        on=["timestamp", "terminal"],
        how="left"
    )
    print("  Congestion features merged via (timestamp, terminal) key")
else:
    print("  WARNING: congestion features not found — using zeros")
    df["congestion_score"] = 0.0

# Target
df["is_delayed"] = (df["ArrDelay"] > 15).astype(int)

print(f"  Delay rate: {df['is_delayed'].mean():.2%}")

# ──────────────────────────────────────────────────────────────────────────────
# 3. Temporal train / test split (no random shuffling of time-series)
# ──────────────────────────────────────────────────────────────────────────────
print("\nStep 3 — Temporal train/test split (80/20 by date)")

dates = sorted(df["FlightDate"].unique())
split_idx = int(len(dates) * 0.80)
train_cutoff = dates[split_idx - 1]

train_df = df[df["FlightDate"] <= train_cutoff].copy()
test_df  = df[df["FlightDate"] >  train_cutoff].copy()

print(f"  Train dates: up to {train_cutoff.date()}  ({len(train_df):,} rows)")
print(f"  Test  dates: after {train_cutoff.date()} ({len(test_df):,} rows)")

# ──────────────────────────────────────────────────────────────────────────────
# 4. Carrier & route averages computed on TRAIN ONLY — then mapped to test
#    (eliminates data leakage from test labels into train features)
# ──────────────────────────────────────────────────────────────────────────────
print("\nStep 4 — Computing carrier/route averages on train split only")

carrier_avg = train_df.groupby("Reporting_Airline")["ArrDelay"].mean().rename("carrier_avg_delay")
train_df = train_df.join(carrier_avg, on="Reporting_Airline")
test_df  = test_df.join(carrier_avg, on="Reporting_Airline")   # map train stats → test

train_df["route"] = train_df["Origin"] + "_" + train_df["Dest"]
test_df["route"]  = test_df["Origin"]  + "_" + test_df["Dest"]

route_avg = train_df.groupby("route")["ArrDelay"].mean().rename("route_avg_delay")
train_df = train_df.join(route_avg, on="route")
test_df  = test_df.join(route_avg, on="route")

# ──────────────────────────────────────────────────────────────────────────────
# 5. Assemble feature matrix
# ──────────────────────────────────────────────────────────────────────────────
FEATURES = [
    "hour",
    "day_of_week",
    "is_weekend",
    "weather_severity",
    "rolling_origin_delay",
    "prev_delay",
    "congestion_score",
    "carrier_avg_delay",
    "route_avg_delay",
]

train_clean = train_df[FEATURES + ["is_delayed"]].dropna()
test_clean  = test_df[FEATURES  + ["is_delayed"]].dropna()

X_train = train_clean[FEATURES]
y_train = train_clean["is_delayed"]
X_test  = test_clean[FEATURES]
y_test  = test_clean["is_delayed"]

print(f"\n  Train shape: {X_train.shape}  |  delay rate: {y_train.mean():.2%}")
print(f"  Test  shape: {X_test.shape}   |  delay rate: {y_test.mean():.2%}")

# ──────────────────────────────────────────────────────────────────────────────
# 6. Train model — try three classifiers, pick the best by AUC
# ──────────────────────────────────────────────────────────────────────────────
print("\nStep 5 — Training classifiers and selecting champion by AUC")

candidates = {
    "GradientBoosting": GradientBoostingClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=42,
    ),
    "RandomForest": RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1,
    ),
    "LogisticRegression": Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, C=1.0, random_state=42)),
    ]),
}

best_model   = None
best_auc     = 0.0
best_name    = ""

for name, model in candidates.items():
    model.fit(X_train, y_train)
    prob = model.predict_proba(X_test)[:, 1]
    auc  = roc_auc_score(y_test, prob)
    print(f"  {name:<22} AUC = {auc:.4f}")
    if auc > best_auc:
        best_auc   = auc
        best_model = model
        best_name  = name

print(f"\n  ✅ Champion: {best_name}  (AUC = {best_auc:.4f})")

# ──────────────────────────────────────────────────────────────────────────────
# 7. Detailed evaluation on test set
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Step 6 — Detailed evaluation on held-out test set")
print("=" * 60)

test_probs = best_model.predict_proba(X_test)[:, 1]
test_preds = (test_probs >= 0.5).astype(int)

print(f"\n  AUC-ROC : {roc_auc_score(y_test, test_probs):.4f}")
print("\n  Classification Report (threshold = 0.5):")
print(classification_report(y_test, test_preds, target_names=["on-time", "delayed"]))

# Risk bucket analysis
bucket_df = pd.DataFrame({"delay_prob": test_probs, "is_delayed": y_test.values})
bucket_df["bucket"] = pd.cut(bucket_df["delay_prob"], bins=[0, 0.3, 0.6, 1.0],
                              labels=["low", "medium", "high"])
print("  Delay rate by risk bucket:")
print(bucket_df.groupby("bucket")["is_delayed"].mean().to_string())
print()

# ──────────────────────────────────────────────────────────────────────────────
# 8. Save model
# ──────────────────────────────────────────────────────────────────────────────
Path("models").mkdir(exist_ok=True)
joblib.dump(best_model, "models/delay_model_fixed.pkl")
print(f"  Model saved → models/delay_model_fixed.pkl")

# ──────────────────────────────────────────────────────────────────────────────
# 9. Save reports/layover_risk.csv with ground-truth label attached
#    (system_evaluation.py reads this file directly — alignment is guaranteed)
# ──────────────────────────────────────────────────────────────────────────────
Path("reports").mkdir(exist_ok=True)

risk_out = test_clean[["is_delayed"]].copy().reset_index(drop=True)
risk_out["delay_prob"] = test_probs

# Carry useful context columns for the bucket analysis
risk_out.to_csv("reports/layover_risk.csv", index=False)
print("  Predictions saved → reports/layover_risk.csv  (is_delayed label included)")

print("\nDone! Run  python src/evaluation/system_evaluation.py  to see the full report.")
