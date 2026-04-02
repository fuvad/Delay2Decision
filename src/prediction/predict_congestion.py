import joblib
import pandas as pd


model = joblib.load("models/congestion_forecaster.pkl")


def predict_future_congestion(feature_dict):

    df = pd.DataFrame([feature_dict])

    pred = model.predict(df)[0]

    return float(pred)


if __name__ == "__main__":

    example = {
        "hour": 15,
        "terminal": 4,
        "time_congestion": 0.7,
        "rolling_congestion": 0.55,
        "rolling_origin_delay": 8.2
    }

    print("Predicted future congestion:", predict_future_congestion(example))
