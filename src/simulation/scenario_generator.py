"""
scenario_generator.py -- Randomized Airport Scenario Generator
================================================================
Generates realistic random airport situations for stress-testing.
Destinations and gates are extracted from the layout CSV (not hardcoded).
"""

import os
import sys
import random
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

LAYOUT = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")


def _load_nodes(layout_file=None):
    """Load and categorize nodes from the layout CSV."""
    if layout_file is None:
        layout_file = LAYOUT

    df = pd.read_csv(layout_file)

    gates = df[df["type"] == "gate"]["node_id"].tolist()
    destinations = df[df["type"].isin(["restaurant", "restroom"])]["node_id"].tolist()

    # Group gates by terminal for same-terminal routing
    gates_by_terminal = df[df["type"] == "gate"].groupby("terminal")["node_id"].apply(list).to_dict()
    dests_by_terminal = df[df["type"].isin(["restaurant", "restroom"])].groupby("terminal")["node_id"].apply(list).to_dict()

    return gates, destinations, gates_by_terminal, dests_by_terminal


def generate_scenario(layout_file=None):
    """
    Generate one random airport scenario.

    Returns
    -------
    dict with:
        - gate              : starting gate
        - destination       : target (restaurant/restroom) in same terminal
        - terminal          : terminal number
        - walking_speed     : randomized speed (m/s)
        - stay_minutes      : time at destination
        - congestion_multiplier : slowdown factor
        - gate_change       : whether a gate change occurs
    """
    _, _, gates_by_terminal, dests_by_terminal = _load_nodes(layout_file)

    # Pick a terminal that has both gates and destinations
    valid_terminals = [t for t in gates_by_terminal if t in dests_by_terminal]
    terminal = random.choice(valid_terminals)

    gate = random.choice(gates_by_terminal[terminal])
    destination = random.choice(dests_by_terminal[terminal])

    scenario = {
        "gate": gate,
        "destination": destination,
        "terminal": terminal,
        "walking_speed": max(0.5, random.normalvariate(1.4, 0.25)),
        "stay_minutes": random.randint(5, 20),
        "congestion_multiplier": random.uniform(0.8, 1.5),
        "gate_change": random.random() < 0.15,
    }

    return scenario
