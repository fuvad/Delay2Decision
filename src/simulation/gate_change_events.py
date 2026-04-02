"""
gate_change_events.py -- Gate Change Event Generator
=====================================================
Simulates real-time gate change events.
Gates are extracted from the layout CSV (not hardcoded).
"""

import os
import sys
import random
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

LAYOUT = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")


def get_gates_by_terminal(layout_file=None):
    """
    Extract gate node_ids from the layout CSV, grouped by terminal.

    Returns
    -------
    dict  {terminal_id: [gate_id, ...]}
    """
    if layout_file is None:
        layout_file = LAYOUT

    df = pd.read_csv(layout_file)
    gates = df[df["type"] == "gate"]

    return gates.groupby("terminal")["node_id"].apply(list).to_dict()


def generate_gate_change(current_gate, terminal, probability=0.15, layout_file=None):
    """
    Simulate a gate change within the same terminal.

    Parameters
    ----------
    current_gate : str  -- current gate node_id
    terminal     : int  -- terminal number (gate changes stay within terminal)
    probability  : float -- chance of a gate change occurring (0-1)

    Returns
    -------
    str -- new gate (same as current if no change)
    """
    if random.random() >= probability:
        return current_gate

    gates_by_terminal = get_gates_by_terminal(layout_file)
    terminal_gates = gates_by_terminal.get(terminal, [])

    # pick a different gate in the same terminal
    other_gates = [g for g in terminal_gates if g != current_gate]

    if not other_gates:
        return current_gate

    return random.choice(other_gates)
