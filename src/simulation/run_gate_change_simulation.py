"""
run_gate_change_simulation.py -- Adaptive Replanning Demo
==========================================================
Demonstrates the full event-driven pipeline:
  1. Create a plan
  2. Simulate a gate change event
  3. Invalidate and replan
  4. Compare old vs new trip + make Go/No-Go decision
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.planner.passenger_plan import PassengerPlan
from src.simulation.airport_simulator import simulate_trip
from src.simulation.gate_monitor import monitor_gate


def main():
    print("=" * 60)
    print("GATE CHANGE SIMULATION -- Adaptive Replanning")
    print("=" * 60)

    buffer_minutes = 30

    # ---- Original plan ----
    plan = PassengerPlan(
        gate="GATE_B1",
        destination="STARBUCKS_T4",
        terminal=4,
    )

    print(f"\nOriginal plan: {plan.current_gate} -> {plan.destination}")

    original_result = simulate_trip(
        start=plan.current_gate,
        destination=plan.destination,
        stay_minutes=15,
    )
    print(f"Original trip time: {original_result['total_minutes']} min")

    # ---- Force a gate change (probability=1.0 to guarantee it) ----
    changed = monitor_gate(plan, probability=1.0)

    if changed:
        print("\nPlan invalidated. Recomputing trip...")

        new_result = simulate_trip(
            start=plan.current_gate,
            destination=plan.destination,
            stay_minutes=15,
        )

        plan.revalidate()

        print(f"New trip time: {new_result['total_minutes']} min")

        # ---- Compare ----
        print(f"\n{'-' * 40}")
        print(f"Original gate:     {plan.original_gate}")
        print(f"New gate:          {plan.current_gate}")
        print(f"Original time:     {original_result['total_minutes']} min")
        print(f"New time:          {new_result['total_minutes']} min")
        print(f"Buffer available:  {buffer_minutes} min")

        # ---- Go / No-Go decision ----
        if new_result["total_minutes"] <= buffer_minutes:
            decision = "GO"
        else:
            decision = "NO"

        print(f"Decision:          {decision}")
        print(f"Replans so far:    {plan.replan_count}")

    else:
        print("\nNo gate change. Plan remains valid.")
        print(f"Trip time: {original_result['total_minutes']} min")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
