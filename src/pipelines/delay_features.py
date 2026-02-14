import pandas as pd
from pathlib import Path

def main():

    df = pd.read_csv("data/silver/jan2023_jfk_simulation.csv")
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])

    df["hour"] = df["CRSDepTime"] // 100
    df["day_of_week"] = df["FlightDate"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5,6]).astype(int)

    df["weather_severity"] = df["PRCP"].fillna(0)*2 + df["WDSP"].fillna(0)*0.5      #Precipitation weighted more, Wind weighted less

    df = df.sort_values("FlightDate")       #imp for rolling averages

    df["rolling_origin_delay"] = (
        df["DepDelay"]
        .rolling(window=200, min_periods=20)
        .mean()
    )

    df["prev_delay"] = df["DepDelay"].shift(1)      #To get recent delay

    df["is_delayed"] = (df["ArrDelay"] > 15).astype(int)

    features = [
        "hour","day_of_week","is_weekend",
        "weather_severity","rolling_origin_delay","prev_delay"
    ]

    gold = df[features + ["is_delayed"]].dropna()

    Path("data/gold").mkdir(exist_ok=True)
    gold.to_csv("data/gold/jfk_delay_features.csv", index=False)

    print("Delay gold saved")

if __name__ == "__main__":
    main()
