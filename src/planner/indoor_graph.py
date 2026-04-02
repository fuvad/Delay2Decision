"""
indoor_graph.py — Airport Indoor Walking Graph
================================================
Models the airport terminal as a graph where:
  - Nodes  = gates, shops, restaurants, restrooms, security checkpoints
  - Edges  = walking paths (weighted by Euclidean distance in meters)

Uses Dijkstra's shortest path to compute walking time.

Pipeline:  layout CSV  ->  networkx Graph  ->  walking_time_seconds()
"""

import pandas as pd
import networkx as nx
import numpy as np

WALKING_SPEED = 1.4  # meters per second (avg human)


def build_graph(layout_csv):
    """
    Read an airport layout CSV and return a networkx Graph.

    Nodes inside the same terminal are fully connected.
    Edge weight = Euclidean distance between (x, y) coordinates.
    """
    df = pd.read_csv(layout_csv)

    G = nx.Graph()

    # Add nodes
    for _, row in df.iterrows():
        G.add_node(
            row["node_id"],
            type=row["type"],
            terminal=row["terminal"],
            x=row["x"],
            y=row["y"],
        )

    # Fully connect nodes inside same terminal
    for i, row1 in df.iterrows():
        for j, row2 in df.iterrows():
            if i >= j:
                continue
            
            # Same terminal: linear cartesian distance
            if row1["terminal"] == row2["terminal"]:
                distance = np.sqrt(
                    (row1["x"] - row2["x"]) ** 2
                    + (row1["y"] - row2["y"]) ** 2
                )
                G.add_edge(
                    row1["node_id"],
                    row2["node_id"],
                    weight=distance,
                )

    return G


def walking_time_seconds(G, start_node, end_node, walking_speed=1.4):
    """
    Compute the shortest-path walking time (in seconds) between two nodes.
    Uses Dijkstra on the edge weights (distance in meters).
    """
    distance = nx.shortest_path_length(
        G,
        source=start_node,
        target=end_node,
        weight="weight",
    )

    return distance / walking_speed
