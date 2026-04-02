"""
config.py — Shared constants for all Delay2Decision microservices.
=================================================================
Every service imports paths and feature lists from here
instead of hardcoding them.
"""

from pathlib import Path

# ── Project root (Delay2Decision/) ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ─────────────────────────────────────────────────────────────────────────
# DATA PATHS
# ─────────────────────────────────────────────────────────────────────────

# Silver (source of truth)
SILVER_DATA_PATH      = PROJECT_ROOT / "data" / "silver" / "jan2023_jfk_simulation.csv"

# Processed
VALIDATED_SILVER_PATH = PROJECT_ROOT / "data" / "processed" / "silver_validated.csv"

# Gold — Delay
TRAIN_FEATURES_PATH   = PROJECT_ROOT / "data" / "gold" / "delay_features_train.csv"
TEST_FEATURES_PATH    = PROJECT_ROOT / "data" / "gold" / "delay_features_test.csv"

# Gold — Congestion
CONGESTION_FEATURES_PATH          = PROJECT_ROOT / "data" / "gold" / "jfk_congestion_features.csv"
CONGESTION_FORECAST_FEATURES_PATH = PROJECT_ROOT / "data" / "gold" / "jfk_congestion_forecast_features.csv"

# Gold — Buffer
BUFFER_FEATURES_PATH  = PROJECT_ROOT / "data" / "gold" / "jfk_buffer_training.csv"

# ─────────────────────────────────────────────────────────────────────────
# MODEL PATHS
# ─────────────────────────────────────────────────────────────────────────
MODEL_DIR                = PROJECT_ROOT / "models"
MODEL_PATH               = MODEL_DIR / "delay_model_fixed.pkl"
CALIBRATED_MODEL_PATH    = MODEL_DIR / "delay_model_calibrated.pkl"
CONGESTION_FORECASTER_PATH = MODEL_DIR / "congestion_forecaster.pkl"
ANOMALY_DETECTOR_PATH    = MODEL_DIR / "anomaly_detector.pkl"
BUFFER_MODEL_PATH        = MODEL_DIR / "buffer_model.pkl"
UNCERTAINTY_PATH         = MODEL_DIR / "uncertainty_stats.npy"

# ─────────────────────────────────────────────────────────────────────────
# REPORT PATHS
# ─────────────────────────────────────────────────────────────────────────
REPORT_DIR              = PROJECT_ROOT / "reports"
DELAY_PREDICTIONS_PATH  = REPORT_DIR / "delay_predictions.csv"
REPORT_PATH             = REPORT_DIR / "layover_risk.csv"
METRICS_PATH            = REPORT_DIR / "training_metrics.json"

# ─────────────────────────────────────────────────────────────────────────
# FEATURE LISTS
# ─────────────────────────────────────────────────────────────────────────

# Delay model features
DELAY_FEATURES = [
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

# Congestion forecaster features
CONGESTION_FORECAST_FEATURES = [
    "hour",
    "terminal",
    "time_congestion",
    "rolling_congestion",
    "rolling_origin_delay",
]

# Congestion anomaly detector features
ANOMALY_FEATURES = [
    "hour",
    "rolling_origin_delay",
    "congestion_score",
]

# ─────────────────────────────────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────────────────────────────────
TRAIN_RATIO = 0.80

# ─────────────────────────────────────────────────────────────────────────
# MLFLOW
# ─────────────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI = (PROJECT_ROOT / "mlruns").as_uri()

# Legacy alias (for backward compatibility)
FEATURES = DELAY_FEATURES
