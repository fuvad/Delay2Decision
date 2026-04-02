"""
run_scenarios.py -- Scenario Simulation Runner
================================================
Stress-tests the decision system by running many randomized
airport situations and measuring system reliability.

Outputs:
  - Success rate
  - Failure rate
  - Avg trip time
  - Slow walker failure rate
  - Per-terminal breakdown
  - CSV report saved to reports/scenario_simulation.csv
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from src.simulation.scenario_generator import generate_scenario
from src.simulation.airport_simulator import simulate_trip


def run_scenarios(n=500, buffer_minutes=35):
    """
    Run n randomized airport scenarios and compute reliability metrics.
    """
    print("=" * 60)
    print(f"SCENARIO SIMULATION -- {n} runs, buffer={buffer_minutes} min")
    print("=" * 60)

    results = []

    for i in range(n):
        scenario = generate_scenario()

        # Apply congestion multiplier to walking speed
        effective_speed = scenario["walking_speed"] / scenario["congestion_multiplier"]

        sim = simulate_trip(
            start=scenario["gate"],
            destination=scenario["destination"],
            stay_minutes=scenario["stay_minutes"],
            walking_speed=effective_speed,
        )

        trip_time = sim["total_minutes"]
        safe = trip_time <= buffer_minutes

        results.append({
            "run": i + 1,
            "gate": scenario["gate"],
            "destination": scenario["destination"],
            "terminal": scenario["terminal"],
            "walking_speed": round(scenario["walking_speed"], 2),
            "congestion": round(scenario["congestion_multiplier"], 2),
            "stay_minutes": scenario["stay_minutes"],
            "gate_change": scenario["gate_change"],
            "trip_time": round(trip_time, 2),
            "buffer": buffer_minutes,
            "safe": safe,
        })

    df = pd.DataFrame(results)

    # ---- Metrics ----
    success_rate = df["safe"].mean()
    failure_rate = 1 - success_rate
    avg_trip = df["trip_time"].mean()

    slow_walkers = df[df["walking_speed"] < 1.0]
    slow_failure_rate = (1 - slow_walkers["safe"].mean()) if len(slow_walkers) > 0 else 0

    print(f"\n{'─' * 40}")
    print(f"  Total runs:          {n}")
    print(f"  Success rate:        {success_rate:.1%}")
    print(f"  Failure rate:        {failure_rate:.1%}")
    print(f"  Avg trip time:       {avg_trip:.1f} min")
    print(f"  Slow walker fails:   {slow_failure_rate:.1%} (speed < 1.0 m/s)")

    # Per-terminal breakdown
    print(f"\n  Per-terminal success:")
    for terminal, group in df.groupby("terminal"):
        rate = group["safe"].mean()
        print(f"    Terminal {terminal}: {rate:.1%} ({len(group)} runs)")

    print(f"{'─' * 40}")

    # ---- Save report ----
    report_dir = os.path.join(PROJECT_ROOT, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "scenario_simulation.csv")
    df.to_csv(report_path, index=False)
    print(f"\n  Report saved -> {report_path}")
    print("=" * 60)

    return df


if __name__ == "__main__":
    run_scenarios(1000)
