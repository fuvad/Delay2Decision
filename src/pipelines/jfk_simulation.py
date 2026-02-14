import pandas as pd
import random
from pathlib import Path

def assign_gate(row, layout):

    gates = layout[
        (layout["airport"] == row["Origin"]) &
        (layout["terminal"] == row["terminal"])
    ]

    if gates.empty:
        return pd.Series([None,None,None])

    gate = gates.sample(1).iloc[0]
    return pd.Series([gate["gate"], gate["x"], gate["y"]])


def main():

    silver = pd.read_csv("data/silver/jan2023_silver.csv")

    # JFK only
    silver = silver[silver["Origin"] == "JFK"].copy()

    terminal_map = pd.read_csv("data/raw/airports/airline_terminal_map.csv")        #airline_terminal_map.csv should already be there
    layout = pd.read_csv("data/raw/airports/layouts/jfk_layout.csv")        #jfk_layout.csv should already be there

    silver = silver.merge(
        terminal_map,
        left_on=["Origin","Reporting_Airline"],
        right_on=["airport","airline"],
        how="left"
    )       #Attach Terminal Info

    silver[["gate","x","y"]] = silver.apply(assign_gate, axis=1, layout=layout)     #x & y are coordinates of gates

    Path("data/silver").mkdir(exist_ok=True)
    silver.to_csv("data/silver/jan2023_jfk_simulation.csv", index=False)

    print("JFK simulation saved:", len(silver))

if __name__ == "__main__":
    main()
