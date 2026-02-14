import pandas as pd
import joblib
from pathlib import Path
from sklearn.metrics import confusion_matrix


def main():

    print("Loading model...")
    model = joblib.load("models/champion_delay_model.pkl")

    print("Loading gold features...")
    df = pd.read_csv("data/gold/jfk_delay_features_v2.csv")

    X = df.drop(columns=["is_delayed"])
    y = df["is_delayed"]

    print("Running predictions...")
    probs = model.predict_proba(X)[:,1]
    preds = (probs > 0.5).astype(int)

    analysis = X.copy()
    analysis["actual"] = y.values
    analysis["pred"] = preds
    analysis["prob"] = probs

    Path("reports").mkdir(exist_ok=True)

    print("Saving full prediction table...")
    analysis.to_csv("reports/predictions_full.csv", index=False)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y, preds).ravel()

    metrics = {
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "true_positive": tp
    }

    pd.DataFrame([metrics]).to_csv("reports/confusion_matrix.csv", index=False)

    # Failure subsets
    false_neg = analysis[(analysis["actual"]==1) & (analysis["pred"]==0)]
    false_pos = analysis[(analysis["actual"]==0) & (analysis["pred"]==1)]

    false_neg.to_csv("reports/false_negatives.csv", index=False)
    false_pos.to_csv("reports/false_positives.csv", index=False)

    print("\nConfusion Matrix:")
    print(metrics)

    print("\nFalse negatives:", len(false_neg))
    print("False positives:", len(false_pos))

    print("\nFailure analysis complete.")
    print("Saved to reports/")


if __name__ == "__main__":
    main()
