"""
drift_check.py — Lightweight Data Drift Monitor for Delay2Decision
====================================================================
Compares the distribution of recent API request features against
a reference baseline (gold dataset) using Evidently AI.

Usage:
    python mlops/monitoring/drift_check.py

Outputs:
    - reports/drift_report.html   → Visual HTML drift report
    - Exits with code 1 if drift is detected (for CI alerting)
    - Exits with code 0 if no drift detected

Requirements:
    pip install evidently pandas
"""

import sys
import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── Setup ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_CSV = PROJECT_ROOT / "data" / "gold" / "delay_features_train.csv"
REQUEST_LOG   = PROJECT_ROOT / "mlops" / "monitoring" / "request_log.jsonl"
REPORT_DIR    = PROJECT_ROOT / "reports"
REPORT_PATH   = REPORT_DIR / "drift_report.html"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("drift_check")

# Features we log at prediction time that map to reference data columns.
# Format: { logged_feature_name: reference_csv_column_name }
FEATURE_MAP = {
    "delay_prob":       "carrier_avg_delay",   # API logs delay_prob (0-1 scale)
    "uncertainty":      "weather_severity",     # uncertainty proxy = weather risk
    "buffer_minutes":   "rolling_origin_delay", # buffer ~ historical origin delay
}


def load_reference(csv_path: Path, feature_map: dict) -> pd.DataFrame:
    """Load the reference (training) dataset and keep only tracked features."""
    log.info(f"Loading reference data from: {csv_path}")
    if not csv_path.exists():
        log.error(f"Reference CSV not found: {csv_path}")
        sys.exit(2)

    df = pd.read_csv(csv_path)

    # Rename reference columns to match the names we log in production
    rename_map = {ref_col: log_col for log_col, ref_col in feature_map.items() if ref_col in df.columns}
    df = df.rename(columns=rename_map)

    available = [col for col in feature_map.keys() if col in df.columns]
    missing   = [col for col in feature_map.keys() if col not in df.columns]
    if missing:
        log.warning(f"Features not mappable from reference data (skipping): {missing}")

    if not available:
        log.error("None of the tracked features could be mapped from the reference CSV.")
        sys.exit(2)

    return df[available].dropna()


def load_current(jsonl_path: Path, features: list) -> pd.DataFrame | None:
    """Load recent requests from the JSONL request log."""
    if not jsonl_path.exists() or jsonl_path.stat().st_size == 0:
        log.warning(f"No request log found at {jsonl_path}. Skipping drift check.")
        return None

    records = []
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if len(records) < 20:
        log.warning(
            f"Only {len(records)} requests logged -- need at least 20 for a "
            "meaningful drift check. Skipping."
        )
        return None

    df = pd.DataFrame(records)
    available = [f for f in features if f in df.columns]
    return df[available].dropna() if available else None


def run_drift_check(reference: pd.DataFrame, current: pd.DataFrame) -> bool:
    """
    Run Evidently drift report.
    Returns True if drift is detected, False otherwise.
    """
    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset
        evidently_mode = "modern"
    except ImportError:
        try:
            from evidently.report import Report
            from evidently.metric_preset import DataDriftPreset
            from evidently import ColumnMapping
            evidently_mode = "legacy"
        except ImportError:
            try:
                from evidently.legacy.report import Report
                from evidently.legacy.metric_preset import DataDriftPreset
                from evidently.legacy.pipeline.column_mapping import ColumnMapping
                evidently_mode = "legacy"
            except ImportError:
                log.error(
                    "Evidently is installed, but this script could not find a compatible API. "
                    "If you use Evidently >= 0.7, keep the modern imports; if you use older "
                    "versions, pin to 0.6.7 or earlier."
                )
                sys.exit(2)

    log.info(
        f"Running drift check: {len(reference)} reference rows vs "
        f"{len(current)} current rows across features: {list(reference.columns)}"
    )

    # Only keep columns that exist in both dataframes
    shared_cols = [c for c in reference.columns if c in current.columns]
    reference = reference[shared_cols]
    current   = current[shared_cols]

    if not shared_cols:
        log.error(
            "No shared columns found between reference and current data for drift checking."
        )
        sys.exit(2)

    if evidently_mode == "modern":
        report = Report([DataDriftPreset(columns=shared_cols)])
        snapshot = report.run(current, reference)
    else:
        column_mapping = ColumnMapping(numerical_features=shared_cols)
        report = Report(metrics=[DataDriftPreset()])
        report.run(
            reference_data=reference,
            current_data=current,
            column_mapping=column_mapping,
        )
        snapshot = report

    # Save HTML report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot.save_html(str(REPORT_PATH))
    log.info(f"Drift report saved to: {REPORT_PATH}")

    # Extract drift verdict from report JSON
    result_json = snapshot.dict() if evidently_mode == "modern" else snapshot.as_dict()

    def _has_dataset_drift(value) -> bool:
        if isinstance(value, dict):
            if value.get("dataset_drift") is True:
                return True
            return any(_has_dataset_drift(v) for v in value.values())
        if isinstance(value, list):
            return any(_has_dataset_drift(item) for item in value)
        return False

    drift_detected = _has_dataset_drift(result_json)
    if not drift_detected:
        log.info("No dataset_drift=true flag found in Evidently output; treating as no drift.")

    return drift_detected


def main():
    log.info("=" * 60)
    log.info("Delay2Decision — Data Drift Check")
    log.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    log.info("=" * 60)

    reference = load_reference(REFERENCE_CSV, FEATURE_MAP)
    current   = load_current(REQUEST_LOG, list(FEATURE_MAP.keys()))

    if current is None:
        log.info("Not enough production data to run drift check. Exiting cleanly.")
        sys.exit(0)

    drift_detected = run_drift_check(reference, current)

    if drift_detected:
        log.warning("⚠️  DATA DRIFT DETECTED — Input distribution has shifted from baseline!")
        log.warning(f"   Review the report at: {REPORT_PATH}")
        sys.exit(1)   # Non-zero exit → GitHub Actions flags it as a failure
    else:
        log.info("✅ No significant drift detected. Model inputs look healthy.")
        sys.exit(0)


if __name__ == "__main__":
    main()
