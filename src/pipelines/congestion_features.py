import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from pathlib import Path

def main():

    df = pd.read_csv("data/silver/jan2023_jfk_simulation.csv")

    df["hour"] = df["CRSDepTime"] // 100
    df["flight_hour"] = df["hour"]

    hourly = df.groupby("flight_hour").size().rename("hourly_flight_volume")        #Flights per hour
    df = df.join(hourly, on="flight_hour")

    scaler = MinMaxScaler()
    df["time_congestion"] = scaler.fit_transform(df[["hourly_flight_volume"]])      #Normalize Time Congestion

    terminal_hour = df.groupby(["terminal","hour"]).size().rename("terminal_flights").reset_index()     #Flights per terminal per hour
    df = df.merge(terminal_hour, on=["terminal","hour"])

    df["terminal_congestion"] = MinMaxScaler().fit_transform(df[["terminal_flights"]])      #Normalizes terminal load

    coords = df[["x","y"]].values       #For Spatial Density (Gate Crowding)
    density = []

    for i in range(len(coords)):
        d = np.sqrt(((coords - coords[i])**2).sum(axis=1))      #Euclidean distance formula (straight line distance)
        density.append((d < 8).sum())

    df["spatial_density"] = density
    df["spatial_congestion"] = MinMaxScaler().fit_transform(df[["spatial_density"]])

    df["congestion_score"] = (
        df["time_congestion"]*0.4 +
        df["terminal_congestion"]*0.35 +
        df["spatial_congestion"]*0.25
    )

    cols = ["hour","terminal","x","y","congestion_score"]

    Path("data/gold").mkdir(exist_ok=True)
    df[cols].to_csv("data/gold/jfk_congestion_features.csv", index=False)

    print("Congestion gold saved")

if __name__ == "__main__":
    main()
