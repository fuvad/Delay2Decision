param(
    [string]$ProjectId = "delay2decision",
    [string]$ServiceName = "backend-service",
    [string]$NotificationChannel = "projects/delay2decision/notificationChannels/REPLACE_WITH_YOUR_CHANNEL_ID"
)

<#
.SYNOPSIS
Creates GCP Cloud Monitoring alert policies for the Delay2Decision backend.

.DESCRIPTION
Windows PowerShell version of setup_gcp_alerts.sh.
Run this after deploying the backend and creating an email notification channel.

.EXAMPLE
.\mlops\monitoring\setup_gcp_alerts.ps1 -NotificationChannel "projects/delay2decision/notificationChannels/1234567890"
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-GcloudInstalled {
    if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
        throw "gcloud CLI is not installed or not available in PATH."
    }
}

function Get-PolicyFilePath {
    $file = New-TemporaryFile
    return [System.IO.Path]::ChangeExtension($file.FullName, ".json")
}

function Write-PolicyFile {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Policy,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $Policy | ConvertTo-Json -Depth 20 | Set-Content -Path $Path -Encoding ascii
}

function New-ThresholdCondition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DisplayName,
        [Parameter(Mandatory = $true)]
        [string]$Filter,
        [Parameter(Mandatory = $true)]
        [array]$Aggregations,
        [Parameter(Mandatory = $true)]
        [string]$Comparison,
        [Parameter(Mandatory = $true)]
        [double]$ThresholdValue,
        [Parameter(Mandatory = $true)]
        [string]$Duration,
        [Parameter(Mandatory = $true)]
        [int]$TriggerCount
    )

    return @{
        displayName = $DisplayName
        conditionThreshold = @{
            filter = $Filter
            aggregations = $Aggregations
            comparison = $Comparison
            thresholdValue = $ThresholdValue
            duration = $Duration
            trigger = @{
                count = $TriggerCount
            }
        }
    }
}

function New-LogMatchCondition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DisplayName,
        [Parameter(Mandatory = $true)]
        [string]$Filter
    )

    return @{
        displayName = $DisplayName
        conditionMatchedLog = @{
            filter = $Filter
        }
    }
}

function New-AlertPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DisplayName,
        [Parameter(Mandatory = $true)]
        [string]$Documentation,
        [Parameter(Mandatory = $true)]
        [hashtable]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Severity,
        [Parameter(Mandatory = $true)]
        [string]$AutoClose,
        [string]$NotificationRateLimitPeriod
    )

    $alertStrategy = @{
        autoClose = $AutoClose
    }
    if ($NotificationRateLimitPeriod) {
        $alertStrategy.notificationRateLimit = @{
            period = $NotificationRateLimitPeriod
        }
    }

    return @{
        displayName = $DisplayName
        documentation = @{
            content = $Documentation
            mimeType = "text/markdown"
        }
        conditions = @($Condition)
        alertStrategy = $alertStrategy
        combiner = "OR"
        notificationChannels = @($NotificationChannel)
        severity = $Severity
    }
}

function Invoke-PolicyCreate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StepLabel,
        [Parameter(Mandatory = $true)]
        [string]$DisplayName,
        [Parameter(Mandatory = $true)]
        [hashtable]$Policy
    )

    $policyListJson = gcloud alpha monitoring policies list --project=$ProjectId --format=json 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud failed while checking for an existing alert policy."
    }
    $existingPolicy = @($policyListJson | ConvertFrom-Json) | Where-Object { $_.displayName -eq $DisplayName }
    if ($existingPolicy) {
        Write-Host $StepLabel
        Write-Host "    Alert already exists, skipping: $DisplayName"
        return "skipped"
    }

    $policyPath = Get-PolicyFilePath
    try {
        Write-Host $StepLabel
        Write-PolicyFile -Policy $Policy -Path $policyPath
        gcloud alpha monitoring policies create --project=$ProjectId --policy-from-file=$policyPath
        if ($LASTEXITCODE -ne 0) {
            throw "gcloud failed while creating alert policy."
        }
        return "created"
    }
    finally {
        if (Test-Path $policyPath) {
            Remove-Item -LiteralPath $policyPath -Force
        }
    }
}

Test-GcloudInstalled

if ($NotificationChannel -match "REPLACE_WITH_YOUR_CHANNEL_ID") {
    throw "Update -NotificationChannel with a real notification channel resource name before running this script."
}

Write-Host "==> Setting up GCP Monitoring alerts for project: $ProjectId"
Write-Host ""

$errorRateCondition = New-ThresholdCondition `
    -DisplayName "5xx request ratio > 5%" `
    -Filter "resource.type=`"cloud_run_revision`" AND resource.labels.service_name=`"$ServiceName`" AND metric.type=`"run.googleapis.com/request_count`" AND metric.labels.response_code_class=`"5xx`"" `
    -Aggregations @(
        @{
            alignmentPeriod = "300s"
            crossSeriesReducer = "REDUCE_SUM"
            perSeriesAligner = "ALIGN_RATE"
        }
    ) `
    -Comparison "COMPARISON_GT" `
    -ThresholdValue 0.05 `
    -Duration "0s" `
    -TriggerCount 1

$errorRatePolicy = New-AlertPolicy `
    -DisplayName "D2D - High 5xx Error Rate" `
    -Documentation "More than 5% of requests to the Delay2Decision backend returned 5xx errors in a 5-minute window. Check Cloud Run logs immediately." `
    -Condition $errorRateCondition `
    -Severity "ERROR" `
    -AutoClose "1800s"

$errorRateResult = Invoke-PolicyCreate -StepLabel "[1/3] Creating: High 5xx Error Rate alert..." -DisplayName "D2D - High 5xx Error Rate" -Policy $errorRatePolicy
Write-Host ("    High 5xx Error Rate alert {0}." -f $errorRateResult)
Write-Host ""

$latencyCondition = New-ThresholdCondition `
    -DisplayName "p99 latency > 3000ms" `
    -Filter "resource.type=`"cloud_run_revision`" AND resource.labels.service_name=`"$ServiceName`" AND metric.type=`"run.googleapis.com/request_latencies`"" `
    -Aggregations @(
        @{
            alignmentPeriod = "300s"
            crossSeriesReducer = "REDUCE_PERCENTILE_99"
            perSeriesAligner = "ALIGN_DELTA"
        }
    ) `
    -Comparison "COMPARISON_GT" `
    -ThresholdValue 3000 `
    -Duration "0s" `
    -TriggerCount 1

$latencyPolicy = New-AlertPolicy `
    -DisplayName "D2D - High p99 Latency" `
    -Documentation "The 99th percentile request latency for Delay2Decision exceeded 3 seconds. This may indicate model inference slowdown or resource exhaustion." `
    -Condition $latencyCondition `
    -Severity "WARNING" `
    -AutoClose "1800s"

$latencyResult = Invoke-PolicyCreate -StepLabel "[2/3] Creating: High Latency alert (p99 > 3s)..." -DisplayName "D2D - High p99 Latency" -Policy $latencyPolicy
Write-Host ("    High Latency alert {0}." -f $latencyResult)
Write-Host ""

$restartCondition = New-LogMatchCondition `
    -DisplayName "Cloud Run system error detected" `
    -Filter "resource.type=`"cloud_run_revision`" AND resource.labels.service_name=`"$ServiceName`" AND log_id(`"varlog/system`") AND severity>=ERROR"

$restartPolicy = New-AlertPolicy `
    -DisplayName "D2D - Container Instance Restart" `
    -Documentation "A Cloud Run system error was logged for Delay2Decision in varlog/system. This commonly indicates an application crash, failed startup, or memory-related termination that can lead to instance replacement." `
    -Condition $restartCondition `
    -Severity "CRITICAL" `
    -AutoClose "1800s" `
    -NotificationRateLimitPeriod "300s"

$restartResult = Invoke-PolicyCreate -StepLabel "[3/3] Creating: Container Restart alert..." -DisplayName "D2D - Container Instance Restart" -Policy $restartPolicy
Write-Host ("    Container Restart alert {0}." -f $restartResult)
Write-Host ""

Write-Host "============================================"
Write-Host " All 3 alert policies created successfully!"
Write-Host " View them at: https://console.cloud.google.com/monitoring/alerting?project=$ProjectId"
Write-Host "============================================"
