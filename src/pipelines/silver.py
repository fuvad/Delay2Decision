import pandas as pd
from meteostat import Daily, Stations
#stations → finds nearby weather stations using latitude/longitude
#Daily → fetches daily weather data
from datetime import datetime
from pathlib import Path

def main():

    flights = pd.read_csv("data/bronze/flights/jan2023_bronze.csv")
    flights["FlightDate"] = pd.to_datetime(flights["FlightDate"])

    airports = pd.read_csv("data/raw/weather/airports.csv")     #airports.csv should be there already
    airports = airports[["iata_code","latitude_deg","longitude_deg"]].dropna()
    airports.rename(columns={
        "iata_code":"Origin",
        "latitude_deg":"lat",
        "longitude_deg":"lon"
    }, inplace=True)

    flights = flights.merge(airports, on="Origin", how="left")      #Adds latitude and longitude to each flight using Origin airport

    start = datetime(2023,1,1)
    end = datetime(2023,1,31)

    records = []        #For Weather Collection

    for airport in flights["Origin"].unique()[:10]:

        row = flights[flights["Origin"] == airport].iloc[0]     #Takes one sample row to get that airport’s lat/lon

        stations = Stations().nearby(row["lat"], row["lon"])        #Finds closest Meteostat weather station to the airport
        station = stations.fetch(1)     #Fetch only nearest one

        if station.empty:
            continue

        data = Daily(station, start, end).fetch()       #Temp, precip, wind
        data["Origin"] = airport
        records.append(data.reset_index())

    weather = pd.concat(records)

    weather = weather.rename(columns={
        "time":"FlightDate",
        "tavg":"TEMP",
        "wspd":"WDSP",
        "prcp":"PRCP"
    })

    weather = weather[["Origin","FlightDate","TEMP","WDSP","PRCP"]]

    silver = flights.merge(weather, on=["Origin","FlightDate"], how="left")

    Path("data/silver").mkdir(exist_ok=True)
    silver.to_csv("data/silver/jan2023_silver.csv", index=False)

    print("Silver saved:", len(silver))

if __name__ == "__main__":
    main()
