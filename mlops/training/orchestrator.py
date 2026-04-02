"""
orchestrator.py — MLOps Master Pipeline Orchestrator
======================================================
Runs all microservices in dependency order, replacing the old
monolithic retrain_and_evaluate.py as the single entry point.

Stages:
   1. Data Ingestion           →  validated silver
   2. Congestion FE            →  congestion gold
   3. Delay FE                 →  delay train/test gold
   4. Buffer FE                →  buffer gold
   5. Delay Model Training     →  delay model pkl
   6. Congestion Forecaster    →  congestion model pkl
   7. Anomaly Detector         →  anomaly model pkl
   8. Buffer Model             →  buffer model pkl
   9. Calibration              →  calibrated model pkl
  10. Uncertainty Estimation   →  uncertainty stats
  11. Delay Prediction         →  delay predictions csv
  12. SHAP Explainability      →  SHAP reports
  13. Failure Analysis         →  failure reports
  14. Layover Risk Scoring     →  unified risk csv
  15. Miss Probability         →  miss probability csv
  16. Delay Model Evaluation   →  console metrics
  17. Simulation Test          →  pipeline validation

Run from project root (Delay2Decision/):
    python mlops/training/orchestrator.py
"""

import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import warnings
warnings.filterwarnings("ignore")

import mlflow
from src.utils.mlflow_config import init_mlflow

# ── Service imports ───────────────────────────────────────────────────────
from src.ingestion.load_silver_data import main as run_ingestion
from src.features.congestion_feature_engineering import main as run_congestion_fe
from src.features.feature_engineering import main as run_delay_fe
from src.features.buffer_feature_engineering import main as run_buffer_fe
from src.training.train_delay_model import main as run_delay_training
from src.training.train_congestion_forecaster import main as run_congestion_training
from src.training.train_anomaly_detector import main as run_anomaly_training
from src.training.train_buffer_model import main as run_buffer_training
from src.calibration.calibrate_model import main as run_calibration
from src.uncertainty.estimate_uncertainty import main as run_uncertainty
from src.prediction.predict_delay import main as run_prediction
from src.explainability.shap_analysis import main as run_shap
from src.explainability.failure_analysis import main as run_failure_analysis
from src.decision_engine.layover_risk_scoring import main as run_risk_scoring
from src.risk_engine.miss_probability import main as run_miss_probability
from src.evaluation.evaluate_model import main as run_evaluation
from src.simulation.simulation_test import main as run_simulation


STAGES = [
    # ── Phase 1: Data & Features ──────────────────────────────────────────
    (" 1/17  Data Ingestion",             run_ingestion),
    (" 2/17  Congestion Feature Eng.",     run_congestion_fe),
    (" 3/17  Delay Feature Eng.",          run_delay_fe),
    (" 4/17  Buffer Feature Eng.",         run_buffer_fe),

    # ── Phase 2: Model Training ───────────────────────────────────────────
    (" 5/17  Delay Model Training",        run_delay_training),
    (" 6/17  Congestion Forecaster",       run_congestion_training),
    (" 7/17  Anomaly Detector",            run_anomaly_training),
    (" 8/17  Buffer Model Training",       run_buffer_training),

    # ── Phase 3: Post-Training ────────────────────────────────────────────
    (" 9/17  Calibration",                 run_calibration),
    ("10/17  Uncertainty Estimation",      run_uncertainty),
    ("11/17  Delay Prediction",            run_prediction),
    ("12/17  SHAP Explainability",         run_shap),
    ("13/17  Failure Analysis",            run_failure_analysis),

    # ── Phase 4: Decision Layer ───────────────────────────────────────────
    ("14/17  Layover Risk Scoring",        run_risk_scoring),
    ("15/17  Miss Probability",            run_miss_probability),

    # ── Phase 5: Evaluation ───────────────────────────────────────────────
    ("16/17  Model Evaluation",            run_evaluation),
    ("17/17  Simulation Test",             run_simulation),
]


def main():
    print()
    print("  Delay2Decision - MLOps Pipeline Orchestrator")
    print("  " + "=" * 50)
    print(f"  Stages: {len(STAGES)}")
    print()

    init_mlflow("pipeline-orchestrator")

    overall_start = time.time()
    stage_durations = {}

    for label, stage_fn in STAGES:
        print(f"\n{'_' * 60}")
        print(f"  >>  Stage {label}")
        print(f"{'_' * 60}\n")

        stage_start = time.time()
        try:
            stage_fn()
        except Exception as e:
            print(f"\n  !!  Stage {label} FAILED: {e}")
            raise
        elapsed = time.time() - stage_start
        stage_durations[label.strip()] = round(elapsed, 2)
        print(f"\n  <<  {label} completed in {elapsed:.1f}s")

    total = time.time() - overall_start

    # Log all durations in a single orchestrator run (after services finish their own runs)
    with mlflow.start_run(run_name="full-pipeline-run"):
        mlflow.log_param("total_stages", len(STAGES))
        for stage_label, duration in stage_durations.items():
            # Sanitize label for metric name
            metric_name = stage_label.replace("/", "_").replace(" ", "_").replace(".", "").lower()
            mlflow.log_metric(f"duration_{metric_name}", duration)
        mlflow.log_metric("total_duration_seconds", round(total, 2))

    print(f"\n{'_' * 60}")
    print(f"  All {len(STAGES)} stages completed in {total:.1f}s")
    print(f"{'_' * 60}")


if __name__ == "__main__":
    main()

