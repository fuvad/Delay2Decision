import pandas as pd
import os

def create_delay_features(input_path: str, output_path: str):
    print(f"Loading silver data from {input_path}...")
    df = pd.read_csv(input_path)
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])

    print("Generating basic time features...")
    df["hour"] = df["CRSDepTime"] // 100
    df["day_of_week"] = df["FlightDate"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

    print("Calculating weather severity...")
    # Rain (PRCP) has a x2 multiplier, Wind (WDSP) has a 0.5 multiplier
    df["weather_severity"] = (
        df["PRCP"].fillna(0) * 2 +
        df["WDSP"].fillna(0) * 0.5
    )

    print("Calculating historical congestion proxy...")
    df["flight_hour"] = df["hour"]
    hourly_counts = (
        df.groupby("flight_hour")
          .size()
          .rename("hourly_flight_volume")
    )
    df = df.join(hourly_counts, on="flight_hour")

    print("Calculating rolling origin delay (last 200 flights)...")
    # Sort so that rolling statistics only see past flights
    df = df.sort_values("FlightDate")
    df["rolling_origin_delay"] = (
        df["DepDelay"]
        .rolling(window=200, min_periods=20)
        .mean()
    )

    print("Calculating previous flight delay...")
    df["prev_delay"] = df["DepDelay"].shift(1)

    print("Setting target variable (ArrDelay > 15)...")
    df["is_delayed"] = (df["ArrDelay"] > 15).astype(int)

    # Select final feature set
    features = [
        "hour",
        "day_of_week",
        "is_weekend",
        "weather_severity",
        "hourly_flight_volume",
        "rolling_origin_delay",
        "prev_delay"
    ]
    target = "is_delayed"

    # Drop fully empty/NaN rows created by the rolling features
    gold = df[features + [target]].dropna()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Saving final gold dataset ({len(gold)} rows) to {output_path}...")
    gold.to_csv(output_path, index=False)
    print("Success!")

if __name__ == "__main__":
    # Default paths matching the original notebook
    INPUT_CSV = "data/silver/jan2023_jfk_simulation.csv"
    OUTPUT_CSV = "data/gold/jfk_delay_features.csv"
    
    create_delay_features(INPUT_CSV, OUTPUT_CSV)
