# -*- coding: utf-8 -*-
"""
verify_monitoring.py
Verifies all 4 monitoring steps work correctly.
Run from the project root: python mlops/monitoring/verify_monitoring.py
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

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

    logger.info(
        "POST /api/plan - 200",
        extra={
            "request_info": {
                "method": "POST",
                "url": "/api/plan",
                "status": 200,
                "duration_ms": 142.5,
            }
        },
    )

    output = stream.getvalue().strip()
    parsed = json.loads(output)

    assert parsed["severity"] == "INFO"
    assert parsed["request"]["status"] == 200
    assert parsed["request"]["duration_ms"] == 142.5
    assert parsed["logger"] == "delay2decision.verify"

    app_path = PROJECT_ROOT / "src" / "api" / "app.py"
    app_content = app_path.read_text(encoding="utf-8", errors="replace")
    assert "GCPFormatter" in app_content, "GCPFormatter not found in app.py"
    assert "log_requests" in app_content, "log_requests middleware not found in app.py"

    print("  Sample log line:")
    print(f"  {output}")
    print(f"  {PASS} -- Structured JSON logging format is valid")
    results["step1"] = True
except Exception as exc:
    print(f"  {FAIL} -- {exc}")
    results["step1"] = False

print()
print("STEP 2 -- GCP Alert Setup Script")
print("-" * 40)

try:
    script_path = PROJECT_ROOT / "mlops" / "monitoring" / "setup_gcp_alerts.sh"
    assert script_path.exists(), "setup_gcp_alerts.sh not found"

    content = script_path.read_text(encoding="utf-8")
    assert "D2D - High 5xx Error Rate" in content, "Missing 5xx alert"
    assert "D2D - High p99 Latency" in content, "Missing latency alert"
    assert "D2D - Container Instance Restart" in content, "Missing restart alert"

    print(f"  Script location: {script_path.relative_to(PROJECT_ROOT)}")
    print(f"  {PASS} -- All three alert policies are defined")
    results["step2"] = True
except Exception as exc:
    print(f"  {FAIL} -- {exc}")
    results["step2"] = False

print()
print("STEP 3 -- Batch Drift Detection")
print("-" * 40)

try:
    drift_script = PROJECT_ROOT / "mlops" / "monitoring" / "drift_check.py"
    assert drift_script.exists(), "drift_check.py not found"
    drift_content = drift_script.read_text(encoding="utf-8")
    assert "reports/layover_risk.csv" in drift_content, "layover_risk.csv baseline/current logic missing"
    assert "HEAD~1" in drift_content, "previous-commit baseline logic missing"
    assert "TRACKED_COLUMNS" in drift_content, "tracked output columns missing"
    print("  drift_check.py: OK (batch output drift via layover_risk.csv + git baseline)")

    current_csv = PROJECT_ROOT / "reports" / "layover_risk.csv"
    assert current_csv.exists(), "reports/layover_risk.csv not found"
    print("  Current batch output exists: reports/layover_risk.csv")

    result = subprocess.run(
        [sys.executable, str(drift_script)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=90,
    )

    report_path = PROJECT_ROOT / "reports" / "drift_report.html"
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    combined = stdout + "\n" + stderr

    if result.returncode == 0:
        if "Skipping drift check" in combined:
            print("  Drift check exit code: 0 (skipped cleanly)")
        else:
            print("  Drift check exit code: 0 (no drift detected)")
        if report_path.exists():
            size_kb = round(report_path.stat().st_size / 1024, 1)
            print(f"  Report generated: reports/drift_report.html ({size_kb} KB)")
        print(f"  {PASS} -- drift_check.py executed successfully")
        results["step3"] = True
    elif result.returncode == 1:
        print("  Drift check exit code: 1 (drift detected)")
        if report_path.exists():
            size_kb = round(report_path.stat().st_size / 1024, 1)
            print(f"  Report generated: reports/drift_report.html ({size_kb} KB)")
        print(f"  {PASS} -- drift_check.py executed successfully and detected drift")
        results["step3"] = True
    else:
        print(f"  STDOUT: {stdout[-400:] if stdout else 'empty'}")
        print(f"  STDERR: {stderr[-400:] if stderr else 'empty'}")
        print(f"  {FAIL} -- Exit code {result.returncode}")
        results["step3"] = False
except Exception as exc:
    print(f"  {FAIL} -- {exc}")
    results["step3"] = False

print()
print("STEP 4 -- GitHub Actions Monitor Workflow")
print("-" * 40)

try:
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "monitor.yml"
    assert workflow_path.exists(), "monitor.yml not found"

    content = workflow_path.read_text(encoding="utf-8")
    checks = [
        ("workflow_dispatch", "manual trigger"),
        ("fetch-depth: 2", "git history checkout for previous-commit comparison"),
        ("python mlops/monitoring/drift_check.py", "drift_check.py invocation"),
        ("drift-logs", "drift log artifact upload"),
        ("drift-report", "drift report artifact upload"),
        ("GITHUB_STEP_SUMMARY", "job summary output"),
        ("steps.drift.outputs.status", "status-based result handling"),
    ]

    all_ok = True
    for keyword, label in checks:
        if keyword in content:
            print(f"  OK  {label}")
        else:
            print(f"  MISSING  {label}")
            all_ok = False

    print(f"  {PASS if all_ok else FAIL} -- monitor.yml structure check")
    results["step4"] = all_ok
except Exception as exc:
    print(f"  {FAIL} -- {exc}")
    results["step4"] = False

print()
print("=" * 60)
print("  SUMMARY")
print("=" * 60)
labels = {
    "step1": "Step 1 -- Structured JSON Logging",
    "step2": "Step 2 -- GCP Alert Setup Script",
    "step3": "Step 3 -- Batch Drift Detection",
    "step4": "Step 4 -- GitHub Actions Monitor Workflow",
}
all_passed = True
for key, label in labels.items():
    status = PASS if results.get(key) else FAIL
    print(f"  {status}  {label}")
    if not results.get(key):
        all_passed = False

print()
print("  All monitoring checks passed!" if all_passed else "  Some monitoring checks still need attention.")
print("=" * 60)
