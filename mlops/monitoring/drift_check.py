"""
drift_check.py - Batch drift monitor for Delay2Decision.

This script is designed for the current Delay2Decision workflow:
1. You receive a new raw dataset
2. You run the data pipeline locally
3. The pipeline generates a new reports/layover_risk.csv
4. You compare that new output against the previously committed version
5. If the output distribution shifted too much, you review it before deployment

Default behavior:
- Current dataset: reports/layover_risk.csv in the working tree
- Reference dataset:
  * HEAD:reports/layover_risk.csv if the current file has local changes
  * otherwise HEAD~1:reports/layover_risk.csv

This makes the check useful both:
- locally before you commit a freshly generated layover_risk.csv
- in GitHub Actions after a push, comparing the latest commit to the previous one
"""

from __future__ import annotations

import argparse
import io
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURRENT_CSV = PROJECT_ROOT / "reports" / "layover_risk.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "drift_report.html"
MIN_ROWS = 20

# These are the batch output columns that matter for deployment behavior.
TRACKED_COLUMNS = [
    "delay_prob",
    "uncertainty",
    "predicted_congestion",
    "is_anomaly",
    "buffer_minutes",
    "risk",
    "buffer_conservative",
    "buffer_balanced",
    "buffer_aggressive",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("drift_check")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch drift detection for Delay2Decision.")
    parser.add_argument(
        "--current",
        default=str(DEFAULT_CURRENT_CSV),
        help="Path to the freshly generated batch output CSV to evaluate.",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Optional explicit reference CSV. If omitted, git history is used.",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="Path where the Evidently HTML report should be saved.",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=MIN_ROWS,
        help="Minimum rows required in both reference and current datasets.",
    )
    return parser.parse_args()


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def to_project_relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return path


def load_csv(path: Path, label: str) -> pd.DataFrame | None:
    if not path.exists():
        log.warning(f"Skipping drift check: {label} not found at {path}")
        return None

    df = pd.read_csv(path)
    if df.empty:
        log.warning(f"Skipping drift check: {label} is empty at {path}")
        return None

    log.info(f"Loaded {label}: {path} ({len(df)} rows)")
    return df


def load_git_csv(git_ref: str, relative_path: Path) -> pd.DataFrame | None:
    result = run_git(["show", f"{git_ref}:{relative_path.as_posix()}"])
    if result.returncode != 0:
        return None

    try:
        return pd.read_csv(io.StringIO(result.stdout))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(f"Skipping drift check: could not read {relative_path} from {git_ref}: {exc}")
        return None


def current_file_has_local_changes(relative_path: Path) -> bool:
    result = run_git(["status", "--porcelain", "--", relative_path.as_posix()])
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def resolve_reference(current_path: Path, explicit_reference: Path | None) -> tuple[pd.DataFrame | None, str | None]:
    if explicit_reference is not None:
        reference_df = load_csv(explicit_reference, "reference dataset")
        return reference_df, str(explicit_reference)

    relative_current = to_project_relative(current_path)
    if relative_current == current_path:
        log.warning("Skipping drift check: current CSV is outside the git project root.")
        return None, None

    candidate_refs: list[tuple[str, str]] = []
    if current_file_has_local_changes(relative_current):
        candidate_refs.append(("HEAD", "last committed version"))
    candidate_refs.append(("HEAD~1", "previous commit version"))

    for git_ref, label in candidate_refs:
        reference_df = load_git_csv(git_ref, relative_current)
        if reference_df is not None and not reference_df.empty:
            log.info(
                f"Loaded reference dataset from git: {git_ref}:{relative_current.as_posix()} "
                f"({label}, {len(reference_df)} rows)"
            )
            return reference_df, f"{git_ref}:{relative_current.as_posix()}"

    log.warning(
        "Skipping drift check: no reference version of reports/layover_risk.csv is available "
        "in git history yet."
    )
    return None, None


def select_compare_columns(reference: pd.DataFrame, current: pd.DataFrame) -> list[str]:
    preferred = [col for col in TRACKED_COLUMNS if col in reference.columns and col in current.columns]
    if preferred:
        return preferred

    shared = [col for col in reference.columns if col in current.columns]
    numeric_shared: list[str] = []
    for col in shared:
        ref_numeric = pd.to_numeric(reference[col], errors="coerce")
        cur_numeric = pd.to_numeric(current[col], errors="coerce")
        if ref_numeric.notna().any() and cur_numeric.notna().any():
            numeric_shared.append(col)
    return numeric_shared


def prepare_dataset(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    prepared = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    return prepared


def run_evidently(reference: pd.DataFrame, current: pd.DataFrame, report_path: Path) -> bool:
    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset
        mode = "modern"
    except ImportError:
        try:
            from evidently.report import Report
            from evidently.metric_preset import DataDriftPreset
            from evidently import ColumnMapping
            mode = "legacy"
        except ImportError:
            try:
                from evidently.legacy.report import Report
                from evidently.legacy.metric_preset import DataDriftPreset
                from evidently.legacy.pipeline.column_mapping import ColumnMapping
                mode = "legacy"
            except ImportError:
                log.error(
                    "Evidently is installed, but no compatible API was found. "
                    "For Evidently >= 0.7 use the modern API; older versions need the legacy API."
                )
                sys.exit(2)

    log.info(
        f"Running drift check: {len(reference)} reference rows vs {len(current)} current rows "
        f"across columns {list(reference.columns)}"
    )

    if mode == "modern":
        report = Report([DataDriftPreset(columns=list(reference.columns))])
        snapshot = report.run(current, reference)
        result_json = snapshot.dict()
    else:
        column_mapping = ColumnMapping(numerical_features=list(reference.columns))
        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=reference, current_data=current, column_mapping=column_mapping)
        snapshot = report
        result_json = snapshot.as_dict()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.save_html(str(report_path))
    log.info(f"Drift report saved to: {report_path}")

    def has_dataset_drift(value) -> bool:
        if isinstance(value, dict):
            if value.get("dataset_drift") is True:
                return True
            return any(has_dataset_drift(v) for v in value.values())
        if isinstance(value, list):
            return any(has_dataset_drift(item) for item in value)
        return False

    return has_dataset_drift(result_json)


def main() -> None:
    args = parse_args()
    current_path = Path(args.current)
    if not current_path.is_absolute():
        current_path = PROJECT_ROOT / current_path

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path

    explicit_reference = Path(args.reference) if args.reference else None
    if explicit_reference is not None and not explicit_reference.is_absolute():
        explicit_reference = PROJECT_ROOT / explicit_reference

    log.info("=" * 60)
    log.info("Delay2Decision - Batch Drift Check")
    log.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    log.info("=" * 60)

    current_df = load_csv(current_path, "current batch output")
    if current_df is None:
        log.info("Skipping drift check: current layover_risk.csv is not available.")
        sys.exit(0)

    reference_df, reference_source = resolve_reference(current_path, explicit_reference)
    if reference_df is None:
        log.info("Skipping drift check: no usable reference dataset is available.")
        sys.exit(0)

    compare_columns = select_compare_columns(reference_df, current_df)
    if not compare_columns:
        log.warning("Skipping drift check: no comparable numeric columns were found.")
        sys.exit(0)

    log.info(f"Comparing columns: {compare_columns}")
    log.info(f"Reference source: {reference_source}")

    reference_prepared = prepare_dataset(reference_df, compare_columns)
    current_prepared = prepare_dataset(current_df, compare_columns)

    if len(reference_prepared) < args.min_rows or len(current_prepared) < args.min_rows:
        log.warning(
            "Skipping drift check: not enough comparable rows after cleaning "
            f"(reference={len(reference_prepared)}, current={len(current_prepared)}, min={args.min_rows})."
        )
        sys.exit(0)

    drift_detected = run_evidently(reference_prepared, current_prepared, report_path)
    if drift_detected:
        log.warning("DATA DRIFT DETECTED - Output distribution shifted from the deployment baseline.")
        log.warning(f"Review the report at: {report_path}")
        sys.exit(1)

    log.info("No significant drift detected. Batch output looks stable against the baseline.")
    sys.exit(0)


if __name__ == "__main__":
    main()
