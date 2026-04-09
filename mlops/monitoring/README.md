# Delay2Decision - Monitoring & Observability

This folder contains the monitoring infrastructure for Delay2Decision.

---

## Overview

| Component | File | Purpose |
|---|---|---|
| Structured Logging | `src/api/app.py` | JSON logs -> Google Cloud Logging |
| GCP Alert Setup | `setup_gcp_alerts.sh` / `setup_gcp_alerts.ps1` | Create Cloud Monitoring alert policies |
| Batch Drift Detection | `drift_check.py` | Compare the newly generated `layover_risk.csv` against a baseline |
| Request Log | `request_log.jsonl` | Optional live-request log from the API (not the main batch drift source) |
| GitHub Action | `.github/workflows/monitor.yml` | Manual monitoring workflow with drift report + logs artifacts |

---

## Step 1 - Structured Logging

The backend (`src/api/app.py`) emits structured JSON logs to stdout:
- every HTTP request: method, path, status, duration_ms
- every LLM call attempt (Groq or Ollama)
- every pipeline failure with traceback

When deployed to Cloud Run, these logs are indexed in Google Cloud Logging.

---

## Step 2 - GCP Cloud Monitoring Alerts

Use `setup_gcp_alerts.sh` or `setup_gcp_alerts.ps1` to create these alert policies:
- `D2D - High 5xx Error Rate`
- `D2D - High p99 Latency`
- `D2D - Container Instance Restart`

These alerts matter after deployment, when the container is running on GCP.

---

## Step 3 - Batch Drift Detection

The current project is batch-oriented:
1. you receive a new raw dataset
2. you run the data pipeline locally
3. the pipeline generates a new `reports/layover_risk.csv`
4. Docker copies that finished CSV into the container
5. you deploy the container to GCP

Because of that, drift detection belongs before deployment.

### What the script checks

By default, `drift_check.py` compares:
- current batch output: `reports/layover_risk.csv`
- reference baseline:
  - `HEAD:reports/layover_risk.csv` if the file has local changes, or
  - `HEAD~1:reports/layover_risk.csv` if you are running in CI after a push

This makes the script useful in both places:
- local pre-deployment check after regenerating `layover_risk.csv`
- GitHub Actions check after committing a new batch output

### Tracked columns

The drift check focuses on deployment-relevant numeric outputs such as:
- `delay_prob`
- `uncertainty`
- `predicted_congestion`
- `is_anomaly`
- `buffer_minutes`
- `risk`
- `buffer_conservative`
- `buffer_balanced`
- `buffer_aggressive`

### Run locally

```bash
pip install evidently pandas
python mlops/monitoring/drift_check.py
```

Optional explicit reference file:

```bash
python mlops/monitoring/drift_check.py --reference reports/layover_risk_baseline.csv
```

### Exit codes

- `0` = passed or skipped cleanly
- `1` = drift detected
- `2` = setup or tooling error

---

## Step 4 - GitHub Actions Manual Trigger

Go to:

```text
GitHub -> your repo -> Actions -> "Monitoring - Drift & Health Check" -> Run workflow
```

The workflow will:
1. fetch enough git history to compare against the previous commit
2. run `drift_check.py`
3. upload `drift_report.html` when generated
4. upload `drift_check.log` as a debugging artifact
5. write a summary showing `PASSED`, `DRIFT DETECTED`, `SKIPPED`, or `ERROR`
6. fail the workflow only for real drift or real setup errors

---

## Files in this folder

```text
mlops/monitoring/
|-- setup_gcp_alerts.sh    # GCP alert setup (bash)
|-- setup_gcp_alerts.ps1   # GCP alert setup (PowerShell)
|-- drift_check.py         # Batch drift check for layover_risk.csv
|-- request_log.jsonl      # Optional API request log (gitignored)
`-- README.md              # This file
```

`request_log.jsonl` is still useful if you later want live-request observability, but the main drift check for this project now follows the batch pipeline output you actually deploy.
