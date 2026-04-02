import joblib
import pandas as pd

model = joblib.load("models/congestion_anomaly_detector.pkl")


def detect_anomaly(feature_dict):

    df = pd.DataFrame([feature_dict])

    score = model.decision_function(df)[0]   # higher = more normal
    pred = model.predict(df)[0]              # -1 = anomaly, 1 = normal

    return {
        "anomaly_score": float(score),
        "is_anomaly": int(pred == -1)
    }


if __name__ == "__main__":

    example = {
        "hour": 17,
        "terminal": 4,
        "congestion_score": 0.85,
        "rolling_origin_delay": 12
    }

    print(detect_anomaly(example))
