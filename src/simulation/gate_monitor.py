"""
gate_monitor.py -- Gate Change Detection & Plan Invalidation
=============================================================
Monitors for gate changes and invalidates the passenger plan
when a change is detected.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.simulation.gate_change_events import generate_gate_change


def monitor_gate(plan, probability=0.15):
    """
    Check if a gate change has occurred. If so:
      1. Invalidate the plan
      2. Update the gate

    Returns
    -------
    bool -- True if gate changed
    """
    new_gate = generate_gate_change(
        current_gate=plan.current_gate,
        terminal=plan.terminal,
        probability=probability,
    )

    if new_gate != plan.current_gate:
        print(f"\n[!] Gate change detected!")
        print(f"    Old gate: {plan.current_gate}")
        print(f"    New gate: {new_gate}")

        plan.invalidate()
        plan.update_gate(new_gate)

        return True

    return False
