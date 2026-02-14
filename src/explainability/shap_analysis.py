import pandas as pd
import joblib
import shap
import matplotlib.pyplot as plt
from pathlib import Path


def main():

    print("Loading model...")
    model = joblib.load("models/champion_delay_model.pkl")

    print("Loading gold features...")
    df = pd.read_csv("data/gold/jfk_delay_features_v2.csv")

    X = df.drop(columns=["is_delayed"])

    # Limit rows for speed (optional)
    X_sample = X.sample(n=min(2000, len(X)), random_state=42)

    print("Running SHAP (model-agnostic)...")
    explainer = shap.Explainer(model.predict_proba, X_sample)
    shap_values = explainer(X_sample)

    Path("reports").mkdir(exist_ok=True)

    # Save raw SHAP values
    print("Saving SHAP values...")
    pd.DataFrame(
        shap_values.values[:,:,1],
        columns=X_sample.columns
    ).to_csv("reports/shap_values.csv", index=False)


    # Global summary plot
    print("Generating SHAP summary plot...")
    shap.plots.beeswarm(shap_values[:,:,1], show=False)
    plt.tight_layout()
    plt.savefig("reports/shap_summary.png", dpi=150)
    plt.close()

    # Feature importance bar
    shap.plots.bar(shap_values[:,:,1], show=False)
    plt.tight_layout()
    plt.savefig("reports/shap_feature_importance.png", dpi=150)
    plt.close()

    print("SHAP analysis complete.")
    print("Saved to reports/")



if __name__ == "__main__":
    main()
