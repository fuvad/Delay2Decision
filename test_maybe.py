import pandas as pd
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
sys.path.insert(0, PROJECT_ROOT)

from src.agents.run_agents import get_scenario
from src.agents.orchestrator import run_full_pipeline

df = pd.read_csv('reports/layover_risk.csv')
vals = get_scenario(df, 'medium', min_buffer=20.0)

for it_min in range(70, 95):
    r = run_full_pipeline(
        gate='GATE_D1', destination='SHAKE_SHACK_T7', terminal=7,
        delay_prob=vals['delay_prob'], uncertainty=vals['uncertainty'],
        buffer_minutes=vals['buffer_minutes'], itinerary_minutes=float(it_min),
        stay_minutes=25.0, walking_speed=0.9
    )
    margin = r.get("effective_buffer", 0) - r.get("required_minutes", 0)
    print(f"Itinerary: {it_min}, Margin: {margin:.2f}, Decision: {r['decision']}")
