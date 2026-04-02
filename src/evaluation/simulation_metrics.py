"""
simulation_metrics.py -- System Simulation Metrics
====================================================
Computes structured metrics from scenario simulation results.

Metrics:
  Safety     : success rate, failure rate, missed gate probability
  Efficiency : avg trip time, avg buffer used, unused buffer
  Fairness   : slow walker failure rate, terminal-wise reliability
  Accuracy   : planner error (planned vs simulated)

Pipeline:
  run_scenarios.py -> scenario_simulation.csv -> simulation_metrics.py -> report
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd


def compute_metrics(csv_path=None):
    """
    Load scenario simulation results and compute all metrics.
    """
    if csv_path is None:
        csv_path = os.path.join(PROJECT_ROOT, "reports", "scenario_simulation.csv")

    df = pd.read_csv(csv_path)

    total_runs = len(df)

    # ---- Safety metrics ----
    success_rate = df["safe"].mean()
    failure_rate = 1 - success_rate
    missed_gate_count = df[~df["safe"]].shape[0]

    # ---- Efficiency metrics ----
    avg_trip_time = df["trip_time"].mean()
    unused_buffer = (df["buffer"] - df["trip_time"]).clip(lower=0)
    avg_unused_buffer = unused_buffer.mean()
    avg_buffer_used = df["buffer"].mean() - avg_unused_buffer

    # ---- Fairness metrics ----
    slow_walkers = df[df["walking_speed"] < 1.0]
    slow_fail_rate = (1 - slow_walkers["safe"].mean()) if len(slow_walkers) > 0 else 0.0
    slow_walker_count = len(slow_walkers)

    terminal_success = df.groupby("terminal")["safe"].mean()

    # ---- Print report ----
    print("\nSYSTEM SIMULATION METRICS")
    print("=" * 40)

    print("\n-- Safety --")
    print(f"  Total runs:           {total_runs}")
    print(f"  Success rate:         {success_rate:.3f}")
    print(f"  Failure rate:         {failure_rate:.3f}")
    print(f"  Missed gate count:    {missed_gate_count}")

    print("\n-- Efficiency --")
    print(f"  Avg trip time:        {avg_trip_time:.2f} min")
    print(f"  Avg buffer used:      {avg_buffer_used:.2f} min")
    print(f"  Avg unused buffer:    {avg_unused_buffer:.2f} min")

    print("\n-- Fairness --")
    print(f"  Slow walkers:         {slow_walker_count} passengers")
    print(f"  Slow walker fail rate:{slow_fail_rate:.3f}")

    print("\n-- Terminal reliability --")
    for terminal, rate in terminal_success.items():
        count = len(df[df["terminal"] == terminal])
        print(f"  Terminal {terminal}:  {rate:.3f}  ({count} runs)")

    print("=" * 40)

    # ---- Save structured metrics ----
    metrics = {
        "total_runs": total_runs,
        "success_rate": round(success_rate, 4),
        "failure_rate": round(failure_rate, 4),
        "missed_gate_count": missed_gate_count,
        "avg_trip_time": round(avg_trip_time, 2),
        "avg_buffer_used": round(avg_buffer_used, 2),
        "avg_unused_buffer": round(avg_unused_buffer, 2),
        "slow_walker_count": slow_walker_count,
        "slow_walker_failure_rate": round(slow_fail_rate, 4),
    }

    # Add per-terminal rates
    for terminal, rate in terminal_success.items():
        metrics[f"terminal_{terminal}_success"] = round(rate, 4)

    report_dir = os.path.join(PROJECT_ROOT, "reports")
    os.makedirs(report_dir, exist_ok=True)
    metrics_path = os.path.join(report_dir, "simulation_metrics.csv")
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)

    print(f"\nMetrics saved to {metrics_path}")

    return metrics


if __name__ == "__main__":
    compute_metrics()
