import pandas as pd
from pathlib import Path

def main():

    congestion = pd.read_csv("data/gold/jfk_congestion_features.csv")
    delay = pd.read_csv("data/gold/jfk_delay_features.csv")

    full = congestion.merge(
    delay,
    on=["hour"],
    how="inner"
    )

    BASE = 15       #Min buffer

    full["congestion_penalty"] = full["congestion_score"] * 25      #Converts to minutes (Max 25)
    full["ops_penalty"] = full["rolling_origin_delay"].clip(lower=0) * 0.3      #Historical dep delay x 0.3

    full["buffer_minutes"] = (
        BASE +
        full["congestion_penalty"] +
        full["ops_penalty"]
    ).clip(upper=60)

    Path("data/gold").mkdir(exist_ok=True)
    full[[
    "hour",
    "terminal",
    "x","y",
    "congestion_score",
    "rolling_origin_delay",
    "buffer_minutes"
    ]].to_csv("data/gold/jfk_buffer_features.csv", index=False)

    print("Buffer gold saved")

if __name__ == "__main__":
    main()
