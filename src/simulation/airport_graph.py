"""
airport_graph.py — Airport Walking Graph for Simulation
========================================================
Builds a networkx graph from the airport layout CSV.
Same logic as planner/indoor_graph.py but dedicated to the
simulation module for independent use.
"""

import pandas as pd
import networkx as nx
import numpy as np

WALKING_SPEED = 1.4  # meters per second


def build_airport_graph(layout_file):
    """
    Read an airport layout CSV and return a networkx Graph.
    Nodes within the same terminal are fully connected.
    Edge weight = Euclidean distance between (x, y) coordinates.
    """
    df = pd.read_csv(layout_file)

    G = nx.Graph()

    # add nodes
    for _, row in df.iterrows():
        G.add_node(
            row["node_id"],
            type=row["type"],
            terminal=row["terminal"],
            x=row["x"],
            y=row["y"],
        )

    # connect nodes within same terminal
    for i, r1 in df.iterrows():
        for j, r2 in df.iterrows():
            if i >= j:
                continue
            if r1["terminal"] == r2["terminal"]:
                distance = np.sqrt(
                    (r1["x"] - r2["x"]) ** 2
                    + (r1["y"] - r2["y"]) ** 2
                )
                G.add_edge(
                    r1["node_id"],
                    r2["node_id"],
                    weight=distance,
                )

    return G
