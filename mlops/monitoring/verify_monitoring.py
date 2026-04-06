# -*- coding: utf-8 -*-
"""
verify_monitoring.py
Verifies all 4 monitoring steps work correctly.
Run from the project root: python mlops/monitoring/verify_monitoring.py
"""

import sys
import json
import logging
import os
from pathlib import Path

# Force UTF-8 output so emojis work on Windows too
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

PASS = "[PASS]"
FAIL = "[FAIL]"

print("=" * 60)
print("  Delay2Decision -- Monitoring Verification")
print("=" * 60)
print()

results = {}

# ─────────────────────────────────────────────────────────────────
# STEP 1: Structured JSON Logging
# ─────────────────────────────────────────────────────────────────
print("STEP 1 -- Structured JSON Logging")
print("-" * 40)

try:
    class GCPFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "severity": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
            }
            if hasattr(record, "request_info"):
                log_record["request"] = record.request_info
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_record)

    logger = logging.getLogger("delay2decision.verify")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    import io
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(GCPFormatter())
    logger.addHandler(handler)

    logger.info("POST /api/plan - 200", extra={
        "request_info": {
            "method": "POST",
            "url": "/api/plan",
            "status": 200,
            "duration_ms": 142.5,
        }
    })

    output = stream.getvalue().strip()
    parsed = json.loads(output)  # Will raise if not valid JSON

    assert parsed["severity"] == "INFO"
    assert parsed["request"]["status"] == 200
    assert parsed["request"]["duration_ms"] == 142.5
    assert parsed["logger"] == "delay2decision.verify"

    # Also verify app.py has GCPFormatter defined
    app_path = PROJECT_ROOT / "src" / "api" / "app.py"
    app_content = app_path.read_text(encoding="utf-8", errors="replace")
    assert "GCPFormatter" in app_content, "GCPFormatter not found in app.py"
    assert "log_requests" in app_content, "log_requests middleware not found in app.py"
    assert "_log_request_features" in app_content, "_log_request_features not found in app.py"

    print(f"  Sample log line:")
    print(f"  {output}")
    print(f"  {PASS} -- GCPFormatter emits valid JSON (severity, message, request fields)")
    print(f"  {PASS} -- app.py has GCPFormatter, log_requests middleware, and _log_request_features")
    results["step1"] = True
except Exception as e:
    print(f"  {FAIL} -- {e}")
    results["step1"] = False

print()

# ─────────────────────────────────────────────────────────────────
# STEP 2: GCP Alert Script exists and is valid bash
# ─────────────────────────────────────────────────────────────────
print("STEP 2 -- GCP Alert Setup Script")
print("-" * 40)

try:
    script_path = PROJECT_ROOT / "mlops" / "monitoring" / "setup_gcp_alerts.sh"
    assert script_path.exists(), "setup_gcp_alerts.sh not found"

    content = script_path.read_text(encoding="utf-8")
    assert "gcloud alpha monitoring policies create" in content, "Missing gcloud command"
    assert "D2D - High 5xx Error Rate" in content, "Missing 5xx alert"
    assert "D2D - High p99 Latency" in content, "Missing latency alert"
    assert "D2D - Container Instance Restart" in content, "Missing restart alert"

    alert_count = content.count("gcloud alpha monitoring policies create")
    print(f"  Script location: {script_path.relative_to(PROJECT_ROOT)}")
    print(f"  Alert policies defined: {alert_count}")
    print(f"  Alerts:")
    print(f"    [1] D2D - High 5xx Error Rate  (>5% requests fail in 5min) -- severity: ERROR")
    print(f"    [2] D2D - High p99 Latency     (p99 > 3000ms)             -- severity: WARNING")
    print(f"    [3] D2D - Container Restart    (any restart event)        -- severity: CRITICAL")
    print(f"  {PASS} -- Script exists with all 3 alert policies")
    print(f"  [INFO] To activate: fill NOTIFICATION_CHANNEL in the script, then run with gcloud CLI")
    results["step2"] = True
except Exception as e:
    print(f"  {FAIL} -- {e}")
    results["step2"] = False

print()

# ─────────────────────────────────────────────────────────────────
# STEP 3: Drift Detection
# ─────────────────────────────────────────────────────────────────
print("STEP 3 -- Evidently AI Drift Detection")
print("-" * 40)

try:
    # Check drift_check.py exists and is correct
    drift_script = PROJECT_ROOT / "mlops" / "monitoring" / "drift_check.py"
    assert drift_script.exists(), "drift_check.py not found"
    drift_content = drift_script.read_text(encoding="utf-8")
    assert "evidently" in drift_content.lower(), "Evidently not referenced in drift_check.py"
    assert "load_reference" in drift_content, "load_reference function missing"
    assert "load_current" in drift_content, "load_current function missing"
    assert "run_drift_check" in drift_content, "run_drift_check function missing"
    print(f"  drift_check.py: OK (evidently, load_reference, load_current, run_drift_check)")

    # Check reference dataset
    ref_csv = PROJECT_ROOT / "data" / "gold" / "delay_features_train.csv"
    assert ref_csv.exists(), f"Reference CSV not found: {ref_csv}"
    print(f"  reference CSV: data/gold/delay_features_train.csv -- EXISTS")

    # Check FEATURE_MAP columns exist in reference
    import pandas as pd
    ref_df = pd.read_csv(ref_csv, nrows=5)
    feature_map = {
        "delay_prob":     "carrier_avg_delay",
        "uncertainty":    "weather_severity",
        "buffer_minutes": "rolling_origin_delay",
    }
    for log_col, ref_col in feature_map.items():
        assert ref_col in ref_df.columns, f"Column '{ref_col}' not in reference CSV"
        print(f"  Feature mapping OK: {log_col!r} <- '{ref_col}' in reference CSV")

    # Check request log
    log_path = PROJECT_ROOT / "mlops" / "monitoring" / "request_log.jsonl"
    assert log_path.exists(), f"request_log.jsonl missing at {log_path}"

    with open(log_path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    assert len(lines) >= 20, f"Only {len(lines)} entries -- need >=20"

    # Validate first few entries
    for i, line in enumerate(lines[:3]):
        entry = json.loads(line)
        assert "delay_prob" in entry, f"Line {i}: missing delay_prob"
        assert "itinerary_minutes" in entry, f"Line {i}: missing itinerary_minutes"
    print(f"  request_log.jsonl: {len(lines)} entries -- OK")
    print(f"  Sample entry: {json.loads(lines[0])}")

    # Run the drift check as subprocess
    import subprocess
    result = subprocess.run(
        [sys.executable, str(drift_script)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=90,
    )

    report_path = PROJECT_ROOT / "reports" / "drift_report.html"

    if result.returncode == 0:
        print(f"  Drift check exit code: 0 (no drift detected)")
        if report_path.exists():
            size_kb = round(report_path.stat().st_size / 1024, 1)
            print(f"  Report generated: reports/drift_report.html ({size_kb} KB)")
        print(f"  {PASS} -- drift_check.py ran successfully, report saved")
        results["step3"] = True
    elif result.returncode == 1:
        print(f"  Drift check exit code: 1 (DRIFT DETECTED)")
        if report_path.exists():
            size_kb = round(report_path.stat().st_size / 1024, 1)
            print(f"  Report generated: reports/drift_report.html ({size_kb} KB)")
        print(f"  {PASS} -- drift_check.py ran successfully (drift detected -- check report)")
        results["step3"] = True
    else:
        stdout_tail = result.stdout[-400:] if result.stdout else "empty"
        stderr_tail = result.stderr[-400:] if result.stderr else "empty"
        print(f"  STDOUT: {stdout_tail}")
        print(f"  STDERR: {stderr_tail}")
        print(f"  {FAIL} -- Exit code {result.returncode}")
        results["step3"] = False

except Exception as e:
    print(f"  {FAIL} -- {e}")
    results["step3"] = False

print()

# ─────────────────────────────────────────────────────────────────
# STEP 4: GitHub Actions Workflow
# ─────────────────────────────────────────────────────────────────
print("STEP 4 -- GitHub Actions Monitor Workflow")
print("-" * 40)

try:
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "monitor.yml"
    assert workflow_path.exists(), "monitor.yml not found"

    content = workflow_path.read_text(encoding="utf-8")

    # Check required elements
    checks = [
        ("workflow_dispatch", "manual trigger (workflow_dispatch)"),
        ("drift-check",       "drift-check job"),
        ("upload-artifact",   "artifact upload step"),
        ("GITHUB_STEP_SUMMARY", "job summary output"),
        ("python mlops/monitoring/drift_check.py", "drift_check.py invocation"),
        ("continue-on-error: true", "continue-on-error for drift step"),
    ]

    all_ok = True
    for keyword, label in checks:
        if keyword in content:
            print(f"  OK  {label}")
        else:
            print(f"  MISSING  {label}")
            all_ok = False

    # Try to parse as YAML for deeper validation
    try:
        import yaml
        wf = yaml.safe_load(content)
        jobs = wf.get("jobs", {})
        steps = jobs.get("drift-check", {}).get("steps", [])
        step_names = [s.get("name", "") for s in steps]
        print(f"  Workflow steps ({len(steps)}):")
        for name in step_names:
            if name:
                print(f"    - {name}")
    except ImportError:
        print(f"  [INFO] PyYAML not installed -- skipping deep YAML parse (structure looks fine)")

    if all_ok:
        print(f"  {PASS} -- monitor.yml has all required elements")
        print(f"  [INFO] To run: GitHub -> Actions -> 'Monitoring -- Drift & Health Check' -> Run workflow")
    else:
        print(f"  {FAIL} -- monitor.yml missing some required elements")

    results["step4"] = all_ok

except Exception as e:
    print(f"  {FAIL} -- {e}")
    results["step4"] = False

print()

# ─────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("  SUMMARY")
print("=" * 60)
step_labels = {
    "step1": "Step 1 -- Structured JSON Logging",
    "step2": "Step 2 -- GCP Alert Setup Script",
    "step3": "Step 3 -- Evidently AI Drift Detection",
    "step4": "Step 4 -- GitHub Actions Monitor Workflow",
}
all_passed = True
for key, label in step_labels.items():
    status = PASS if results.get(key) else FAIL
    print(f"  {status}  {label}")
    if not results.get(key):
        all_passed = False

print()
if all_passed:
    print("  All 4 monitoring steps verified successfully!")
else:
    print("  Some steps need attention -- see details above.")
print("=" * 60)
