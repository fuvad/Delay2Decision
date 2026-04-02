"""
run_agents.py -- Run the Full Orchestrated Pipeline
=====================================================
Uses the orchestrator to run all layers and display results.
"""

import os
import sys
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.agents.orchestrator import run_full_pipeline

# ── Load real ML predictions
RISK_CSV = os.path.join(PROJECT_ROOT, "reports", "layover_risk.csv")

def get_scenario(df, risk_level, min_buffer=15.0):
    """Fetch a realistic flight based on risk_level."""
    subset = df[(df["risk_level"] == risk_level) & (df["buffer_balanced"] >= min_buffer)]
    if len(subset) == 0:
        # Fallback to the flight with the maximum buffer in this risk level
        subset = df[df["risk_level"] == risk_level].nlargest(1, "buffer_balanced")
    
    sample = subset.sample(1, random_state=42).iloc[0]
    return {
        "delay_prob": float(sample["delay_prob"]),
        "uncertainty": float(sample["uncertainty"]),
        "buffer_minutes": float(sample["buffer_balanced"])
    }

def main():
    print("=" * 60)
    print("DELAY2DECISION -- Full Pipeline (w/ Real ML Predictions)")
    print("=" * 60)

    try:
        df = pd.read_csv(RISK_CSV)
    except Exception as e:
        print(f"Error loading {RISK_CSV}: {e}")
        return

    # ---- Scenario 1: Safe trip ----
    print("\n--- Scenario 1: Safe trip (Low Risk Flight) ---")
    vals = get_scenario(df, "low", min_buffer=21.0)
    r = run_full_pipeline(
        gate="GATE_B1", destination="STARBUCKS_T4", terminal=4,
        delay_prob=vals["delay_prob"], uncertainty=vals["uncertainty"],
        buffer_minutes=vals["buffer_minutes"], itinerary_minutes=120.0, stay_minutes=25.0, walking_speed=1.4,
    )
    print(f"  Decision:  {r['decision']}")
    print(f"  Risk:      {r['risk_level']}")
    print(f"  Action:    {r['suggested_action']}")
    print(f"  Planner:   {r['planner']}")
    print(f"  Sim:       {r['simulation']}")
    print(f"\n  {r['context']}")
    print(f"\n  {r['guardian']}")
    print(f"\n  {r['explanation']}")

    # ---- Scenario 2: Risky trip ----
    print("\n\n--- Scenario 2: Risky trip (High Risk Flight w/ Tight Layover) ---")
    vals = get_scenario(df, "high", min_buffer=18.0)
    r = run_full_pipeline(
        gate="GATE_B1", destination="MC_DONALDS_T4", terminal=4,
        delay_prob=vals["delay_prob"], uncertainty=vals["uncertainty"],
        buffer_minutes=vals["buffer_minutes"], itinerary_minutes=60.0, stay_minutes=20.0, walking_speed=1.4,
    )
    print(f"  Decision:  {r['decision']}")
    print(f"  Risk:      {r['risk_level']}")
    print(f"  Action:    {r['suggested_action']}")
    print(f"\n  {r['guardian']}")
    print(f"\n  {r['explanation']}")

    # ---- Scenario 3: Slow walker ----
    print("\n\n--- Scenario 3: Slow walker (Medium Risk Flight) ---")
    vals = get_scenario(df, "medium", min_buffer=20.0)
    r = run_full_pipeline(
        gate="GATE_D1", destination="SHAKE_SHACK_T7", terminal=7,
        delay_prob=vals["delay_prob"], uncertainty=vals["uncertainty"],
        buffer_minutes=vals["buffer_minutes"], itinerary_minutes=70.0, stay_minutes=25.0, walking_speed=0.9,
    )
    print(f"  Decision:  {r['decision']}")
    print(f"  Risk:      {r['risk_level']}")
    print(f"  Action:    {r['suggested_action']}")
    print(f"\n  {r['guardian']}")
    print(f"\n  {r['explanation']}")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
