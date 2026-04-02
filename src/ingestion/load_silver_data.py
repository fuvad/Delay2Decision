"""
load_silver_data.py — Data Ingestion Microservice
==================================================
Loads the silver "single source of truth" CSV, parses dates,
creates the timestamp column, and writes a validated version
to data/processed/silver_validated.csv.

"""

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from src.utils.config import SILVER_DATA_PATH, VALIDATED_SILVER_PATH


def main():
    print("=" * 60)
    print("INGESTION SERVICE — Loading silver data")
    print("=" * 60)

    df = pd.read_csv(SILVER_DATA_PATH)

    # Parse dates and build timestamp
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])
    df["timestamp"] = (
        df["FlightDate"]
        + pd.to_timedelta(df["CRSDepTime"] // 100, unit="h")
        + pd.to_timedelta(df["CRSDepTime"] % 100, unit="m")
    )

    print(f"  Loaded {len(df):,} rows spanning "
          f"{df['FlightDate'].min().date()} -> {df['FlightDate'].max().date()}")
    print(f"  Terminals: {sorted(df['terminal'].dropna().unique().tolist())}")

    # Save validated output
    VALIDATED_SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(VALIDATED_SILVER_PATH, index=False)
    print(f"  Saved → {VALIDATED_SILVER_PATH.relative_to(VALIDATED_SILVER_PATH.parents[2])}")

    return df


if __name__ == "__main__":
    main()
