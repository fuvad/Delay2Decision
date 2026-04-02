"""
airport_simulator.py — 2D Airport Trip Simulator
==================================================
Simulates a passenger walking from gate → destination → gate
along the shortest path, tracking actual time step-by-step.

Returns detailed results: path, walk time, stay time, event log.

Pipeline:
  Indoor Planner (estimate) → Simulation (verify) → Go / No-Go
"""

import os
import sys
import networkx as nx

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.simulation.airport_graph import build_airport_graph
from src.simulation.passenger_agent import PassengerAgent

LAYOUT = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")


def simulate_trip(start, destination, stay_minutes=15, walking_speed=1.4, layout_file=None):
    """
    Simulate a full round-trip: gate -> destination -> gate.

    Returns
    -------
    dict with keys:
        - path           : list of nodes (outbound)
        - total_minutes  : total simulated time
        - walk_minutes   : time spent walking
        - stay_minutes   : time spent at destination
        - events         : detailed event log
    """
    if layout_file is None:
        layout_file = LAYOUT

    G = build_airport_graph(layout_file)

    passenger = PassengerAgent(start, walking_speed=walking_speed)

    # Shortest path to destination
    path = nx.shortest_path(G, start, destination, weight="weight")

    # Walk to destination step by step
    for i in range(len(path) - 1):
        from_node = path[i]
        to_node = path[i + 1]
        distance = G[from_node][to_node]["weight"]
        passenger.walk(from_node, to_node, distance)

    # Stay at location
    passenger.stay(destination, stay_minutes)

    # Walk back step by step
    path_back = list(reversed(path))
    for i in range(len(path_back) - 1):
        from_node = path_back[i]
        to_node = path_back[i + 1]
        distance = G[from_node][to_node]["weight"]
        passenger.walk(from_node, to_node, distance)

    results = {
        "path": path,
        "total_minutes": round(passenger.total_time / 60, 2),
        "walk_minutes": round(passenger.walk_time / 60, 2),
        "stay_minutes": round(passenger.stay_time / 60, 2),
        "events": passenger.events,
    }

    return results
