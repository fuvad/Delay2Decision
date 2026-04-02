"""
run_simulation.py — Run the Airport Simulation with Time Tracking
==================================================================
Simulates passenger trips and shows detailed time breakdown + event log.
Also compares planned vs simulated time for planner accuracy evaluation.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.simulation.airport_simulator import simulate_trip
from src.planner.indoor_planner import can_visit


def main():
    print("=" * 60)
    print("AIRPORT SIMULATION — Path & Time Tracking")
    print("=" * 60)

    gate = "GATE_B1"
    destination = "STARBUCKS_T4"
    stay = 15

    # ── Simulate
    result = simulate_trip(
        start=gate,
        destination=destination,
        stay_minutes=stay,
    )

    print(f"\nPath taken:    {' -> '.join(result['path'])}")
    print(f"Total time:    {result['total_minutes']} min")
    print(f"Walking time:  {result['walk_minutes']} min")
    print(f"Stay time:     {result['stay_minutes']} min")

    print("\nEvent log:")
    for e in result["events"]:
        if e["event"] == "walk":
            print(f"  [WALK]  {e['from']} -> {e['to']}  "
                  f"({e['distance']}m, {e['time_seconds']}s)")
        else:
            print(f"  [STAY]  {e['location']}  "
                  f"({e['time_seconds']}s)")

    # ── Planned vs Simulated comparison
    _, planned_time = can_visit(
        gate=gate,
        destination=destination,
        buffer_minutes=60,
        stay_minutes=stay,
    )

    simulated_time = result["total_minutes"]
    error = simulated_time - planned_time

    print(f"\n{'─' * 40}")
    print(f"Planned time (planner):    {round(planned_time, 2)} min")
    print(f"Simulated time (sim):      {simulated_time} min")
    print(f"Error (sim - planned):     {round(error, 2)} min")
    print(f"{'─' * 40}")
    print("=" * 60)


if __name__ == "__main__":
    main()
