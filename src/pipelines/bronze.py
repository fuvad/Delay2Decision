import pandas as pd
from pathlib import Path

RAW = "data/raw/flights/On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_2023_1.csv"
OUT = "data/bronze/flights/jan2023_bronze.csv"

def main():
    df = pd.read_csv(RAW, low_memory=False)

    cols = [
        "FlightDate","Reporting_Airline","Origin","Dest",
        "CRSDepTime","DepTime","CRSArrTime","ArrTime",     #CRSDepTime->Scheduled Departure Time, DepTime->Actual Departure Time
        "DepDelay","ArrDelay","Cancelled"
    ]

    df = df[cols]

    df["FlightDate"] = pd.to_datetime(df["FlightDate"])

    # remove cancelled
    df = df[df["Cancelled"] == 0]

    Path("data/bronze/flights").mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    print("Bronze saved:", len(df))

if __name__ == "__main__":
    main()
