"""
indoor_planner.py — Indoor Feasibility Planner
================================================
Answers: "Can the passenger physically visit a destination and return
to their gate within the available buffer time?"

Pipeline:  Delay Model → Buffer Calculator → Indoor Planner → Go / No-Go
"""

import os
import sys

# ── make project root importable when running as a script ──────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.planner.indoor_graph import build_graph, walking_time_seconds

LAYOUT = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")


def can_visit(
    gate,
    destination,
    usable_time,
    stay_minutes=15,
    walking_speed=1.4,
):
    """
    Determine if a passenger can walk to `destination`, stay for
    `stay_minutes`, and walk back to `gate` within `usable_time`.

    Returns
    -------
    (feasible : bool, total_minutes : float)
    """
    G = build_graph(LAYOUT)

    import networkx as nx

    try:
        # walking there and back
        go_time = walking_time_seconds(G, gate, destination, walking_speed=walking_speed)
        return_time = walking_time_seconds(G, destination, gate, walking_speed=walking_speed)
    except nx.NetworkXNoPath:
        # User tried to route between disconnected terminals (e.g. T4 to T5)
        return False, -1.0

    total_seconds = go_time + return_time + stay_minutes * 60
    total_minutes = total_seconds / 60

    return total_minutes <= usable_time, round(total_minutes, 2)


# ── Example usage
if __name__ == "__main__":
    ok, needed = can_visit(
        gate="GATE_B1",
        destination="STARBUCKS_T4",
        usable_time=40,
    )

    print("Can go?", ok)
    print("Minutes required:", needed)
