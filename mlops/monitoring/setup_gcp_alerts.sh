#!/bin/bash
# =============================================================================
# setup_gcp_alerts.sh
# Creates GCP Cloud Monitoring alert policies for the Delay2Decision backend.
# Run this ONCE after deploying to Cloud Run.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Project set: gcloud config set project delay2decision
#   - An email notification channel already created in GCP Console
#     (Monitoring -> Alerting -> Notification channels -> Add Email)
#     Then paste the channel ID into NOTIFICATION_CHANNEL below.
# =============================================================================

set -e

PROJECT_ID="delay2decision"
SERVICE_NAME="backend-service"
REGION="us-central1"

# REQUIRED: Paste your notification channel resource name here
# Format: projects/delay2decision/notificationChannels/1234567890
# Find it: gcloud alpha monitoring channels list --project=$PROJECT_ID
NOTIFICATION_CHANNEL="projects/${PROJECT_ID}/notificationChannels/17508564039215475261"

create_policy_if_missing() {
  local display_name="$1"
  local step_label="$2"
  local policy_json="$3"

  echo "$step_label"
  local existing_policy
  existing_policy="$(gcloud alpha monitoring policies list \
    --project="$PROJECT_ID" \
    --format="value(displayName)" | grep -Fx "$display_name" || true)"

  if [[ -n "$existing_policy" ]]; then
    echo "    Alert already exists, skipping: $display_name"
    echo ""
    echo "skipped"
    return 0
  fi

  gcloud alpha monitoring policies create \
    --project="$PROJECT_ID" \
    --policy="$policy_json"
  echo "created"
}

echo "==> Setting up GCP Monitoring alerts for project: $PROJECT_ID"
echo ""

error_rate_result="$(create_policy_if_missing "D2D - High 5xx Error Rate" "[1/3] Creating: High 5xx Error Rate alert..." '{
  "displayName": "D2D - High 5xx Error Rate",
  "documentation": {
    "content": "More than 5% of requests to the Delay2Decision backend returned 5xx errors in a 5-minute window. Check Cloud Run logs immediately.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "5xx request ratio > 5%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"'"$SERVICE_NAME"'\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "crossSeriesReducer": "REDUCE_SUM",
            "perSeriesAligner": "ALIGN_RATE"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0.05,
        "duration": "0s",
        "trigger": { "count": 1 }
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "1800s"
  },
  "combiner": "OR",
  "notificationChannels": ["'"$NOTIFICATION_CHANNEL"'"],
  "severity": "ERROR"
}')"
echo "$error_rate_result"
echo "    High 5xx Error Rate alert processed."
echo ""

latency_result="$(create_policy_if_missing "D2D - High p99 Latency" "[2/3] Creating: High Latency alert (p99 > 3s)..." '{
  "displayName": "D2D - High p99 Latency",
  "documentation": {
    "content": "The 99th percentile request latency for Delay2Decision exceeded 3 seconds. This may indicate model inference slowdown or resource exhaustion.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "p99 latency > 3000ms",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"'"$SERVICE_NAME"'\" AND metric.type=\"run.googleapis.com/request_latencies\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "crossSeriesReducer": "REDUCE_PERCENTILE_99",
            "perSeriesAligner": "ALIGN_DELTA"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 3000,
        "duration": "0s",
        "trigger": { "count": 1 }
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "1800s"
  },
  "combiner": "OR",
  "notificationChannels": ["'"$NOTIFICATION_CHANNEL"'"],
  "severity": "WARNING"
}')"
echo "$latency_result"
echo "    High Latency alert processed."
echo ""

restart_result="$(create_policy_if_missing "D2D - Container Instance Restart" "[3/3] Creating: Container Restart alert..." '{
  "displayName": "D2D - Container Instance Restart",
  "documentation": {
    "content": "A Cloud Run system error was logged for Delay2Decision in varlog/system. This commonly indicates an application crash, failed startup, or memory-related termination that can lead to instance replacement.",
    "mimeType": "text/markdown"
  },
  "conditions": [
    {
      "displayName": "Cloud Run system error detected",
      "conditionMatchedLog": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"'"$SERVICE_NAME"'\" AND log_id(\"varlog/system\") AND severity>=ERROR"
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "1800s",
    "notificationRateLimit": {
      "period": "300s"
    }
  },
  "combiner": "OR",
  "notificationChannels": ["'"$NOTIFICATION_CHANNEL"'"],
  "severity": "CRITICAL"
}')"
echo "$restart_result"
echo "    Container Restart alert processed."
echo ""

echo "============================================"
echo " Alert policy setup completed."
echo " View them at: https://console.cloud.google.com/monitoring/alerting?project=$PROJECT_ID"
echo "============================================"
