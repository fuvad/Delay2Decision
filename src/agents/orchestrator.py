"""
orchestrator.py -- Full Pipeline Orchestrator
================================================
Connects all layers into one end-to-end pipeline:

  Models (math)           -- delay prediction, risk scoring
       |
  Planner (optimization)  -- indoor_planner, go_no_go, constraints
       |
  Simulation (validation) -- airport_simulator
       |
  Agents (3 core)         -- context_monitor, risk_guardian, explanation
       |
  Final Recommendation

The orchestrator calls the existing decision engine modules directly.
Agents only observe, enforce safety, and explain.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.planner.indoor_planner import can_visit
from src.simulation.airport_simulator import simulate_trip
from src.decision_engine.go_no_go import decide_action
from src.decision_engine.constraint_checker import check_constraints, BOARDING_CLOSE_BEFORE_DEPARTURE
from src.agents.workflow import run_workflow
from src.decision_engine.alternative_planner import find_alternative
from src.planner.indoor_graph import build_graph


def validate_state(result):
    """
    Post-pipeline safety checks.
    Ensures agent outputs are consistent and no agent overrode safety logic.
    """
    errors = []

    if result.get("guardian_override") and result.get("decision") != "NO":
        errors.append("Guardian override is True but decision is not NO")

    if not result.get("constraints_safe", True) and result.get("decision") == "GO":
        errors.append("Constraints violated but decision is GO")

    if result.get("decision") not in ("GO", "MAYBE", "NO"):
        errors.append(f"Invalid decision value: {result.get('decision')}")

    if not result.get("human_explanation"):
        errors.append("No explanation generated")

    return {"valid": len(errors) == 0, "errors": errors}


def run_full_pipeline(
    gate,
    destination,
    terminal,
    delay_prob,
    uncertainty=0.15,
    buffer_minutes=35.0, # ML prediction representing the necessary safety margin
    itinerary_minutes=120.0, # Scheduled layover time
    stay_minutes=15.0,
    walking_speed=1.4,
):
    """
    Run the complete Delay2Decision pipeline.

    Layers:
      1. Planner     -- can_visit() trip feasibility
      2. Go/No-Go    -- decide_action() + check_constraints()
      3. Simulation  -- simulate_trip() actual walking time
      4. Agents      -- 3 core agents (monitor, guard, explain)
      5. Safety      -- post-pipeline validation
    """

    # ──────────────────────────────────────────────────────────────
    # Layer 0: Calculate Usable Time
    # ──────────────────────────────────────────────────────────────
    # Usable time is total layover minus the ML delay penalty AND the fixed boarding closure time.
    usable_time = max(0.0, itinerary_minutes - buffer_minutes - BOARDING_CLOSE_BEFORE_DEPARTURE)

    # ──────────────────────────────────────────────────────────────
    # Layer 1: PLANNER (optimization)
    # ──────────────────────────────────────────────────────────────
    feasible, required_minutes = can_visit(
        gate=gate,
        destination=destination,
        usable_time=usable_time,
        stay_minutes=stay_minutes,
        walking_speed=walking_speed,
    )

    # ──────────────────────────────────────────────────────────────
    # Layer 2: DECISION ENGINE (go/no-go + constraints)
    # ──────────────────────────────────────────────────────────────
    # Risk score
    risk_score = min(1.0, 0.6 * delay_prob + 0.4 * uncertainty)
    if risk_score >= 0.6:
        risk_level = "high"
    elif risk_score >= 0.3:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Go/No-Go
    go_result = decide_action(
        required_minutes=required_minutes,
        usable_time=usable_time,
        uncertainty=uncertainty,
        risk=risk_score,
    )

    # Constraint check
    constraint_result = check_constraints(
        required_minutes=required_minutes,
        usable_time=usable_time,
        needs_security=False,
        effective_buffer=go_result.get("effective_buffer"),
    )

    # Force fail constraints if no path exists
    if required_minutes < 0:
        constraint_result = {
            "safe": False,
            "violated": ["Gate Reachability", "Security Clearance", "Buffer Safety"]
        }

    decision = go_result["decision"]
    if not constraint_result["safe"]:
        decision = "NO"

    # ──────────────────────────────────────────────────────────────
    # Layer 3: SIMULATION (validation)
    # ──────────────────────────────────────────────────────────────
    sim_result = {}
    try:
        sim = simulate_trip(
            start=gate,
            destination=destination,
            stay_minutes=stay_minutes,
            walking_speed=walking_speed,
        )
        sim_result = {
            "total_minutes": round(sim["total_minutes"], 1),
            "walk_minutes": round(sim["walk_minutes"], 1),
            "stay_minutes": round(sim["stay_minutes"], 1),
        }
    except Exception as e:
        sim_result = {"error": str(e)}

    # ──────────────────────────────────────────────────────────────
    # Layer 4: AGENT LAYER (3 core agents)
    # Pass all computed values so agents can observe and explain
    # ──────────────────────────────────────────────────────────────
    state_in = {
        "gate": gate,
        "destination": destination,
        "terminal": terminal,
        "stay_minutes": stay_minutes,
        "walking_speed": walking_speed,
        
        "delay_prob": delay_prob,
        "uncertainty": uncertainty,
        "buffer_minutes": buffer_minutes,
        "itinerary_minutes": itinerary_minutes,
        
        "risk_score": risk_score,
        "risk_level": risk_level,
        "required_minutes": required_minutes,
        "usable_time": usable_time,
        "effective_buffer": go_result.get("effective_buffer", 0),
        "cross_terminal_error": go_result.get("cross_terminal_error", False),
        
        "decision": decision,
        "constraints_safe": constraint_result["safe"],
        "violated_constraints": constraint_result["violated"],
        "recommendation": go_result["reason"],
    }
    agent_state = run_workflow(state_in)

    # Guardian can override decision to NO
    if agent_state.get("guardian_override"):
        decision = "NO"

    # ──────────────────────────────────────────────────────────────
    # Layer 5: SAFETY VALIDATION
    # ──────────────────────────────────────────────────────────────
    final_state = {**agent_state, "decision": decision}
    safety = validate_state(final_state)

    # ──────────────────────────────────────────────────────────────
    # Build clean final output + Alternatives
    # ──────────────────────────────────────────────────────────────
    
    # Run Alternative Planner if trip is risky
    alternative_rec = None
    if decision in ["NO", "MAYBE"]:
        layout_csv = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")
        try:
            G = build_graph(layout_csv)
            alternative_rec = find_alternative(
                gate=gate,
                destination=destination,
                terminal=terminal,
                usable_time=usable_time,
                original_stay=stay_minutes,
                original_speed=walking_speed,
                layout_graph=G
            )
        except Exception as e:
            # Fallback cleanly if finding alternative fails
            pass

    if decision == "GO":
        action = f"Safe to visit {destination}. You have enough time."
    elif decision == "MAYBE":
        action = f"Tight timing. Visit {destination} only if nearby."
    else:
        action = f"Stay at {gate}. Not enough time for a safe trip."

    explanation = agent_state.get("human_explanation", "")

    # Append Alternative Message
    if alternative_rec:
        action += "\n\n" + alternative_rec["message"]
        if explanation:
            explanation += "\n\n" + alternative_rec["message"]

    return {
        "decision": decision,
        "risk_level": risk_level,
        "buffer_minutes": buffer_minutes,
        "suggested_action": action,
        "reason": go_result["reason"],
        "explanation": explanation,
        "context": agent_state.get("context_summary", ""),
        "guardian": agent_state.get("guardian_alert", ""),
        "planner": {"feasible": feasible, "required_minutes": round(required_minutes, 1)},
        "simulation": sim_result,
        "constraints": {"safe": constraint_result["safe"], "violated": constraint_result["violated"]},
        "go_result": go_result,
        "safety_validation": safety,
    }


# ──────────────────────────────────────────────────────────────────
# Demo
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    scenarios = [
        {
            "name": "Safe trip",
            "gate": "GATE_B1", "destination": "STARBUCKS_T4", "terminal": 4,
            "delay_prob": 0.15, "uncertainty": 0.10,
            "buffer_minutes": 35.0, "stay_minutes": 15.0, "walking_speed": 1.4,
        },
        {
            "name": "Risky trip with Alternative Store inside Terminal 4",
            "gate": "GATE_B1", "destination": "SHAKE_SHACK_T7", "terminal": 4,
            "delay_prob": 0.75, "uncertainty": 0.35,
            "buffer_minutes": 25.0, "stay_minutes": 15.0, "walking_speed": 1.4,
        },
        {
            "name": "Risky trip with Adjusted Speed/Stay Needed",
            "gate": "GATE_D1", "destination": "SHAKE_SHACK_T7", "terminal": 7,
            "delay_prob": 0.40, "uncertainty": 0.20,
            "buffer_minutes": 20.0, "stay_minutes": 15.0, "walking_speed": 0.9,
        },
    ]

    for s in scenarios:
        name = s.pop("name")
        print("=" * 60)
        print(f"SCENARIO: {name}")
        print("=" * 60)

        r = run_full_pipeline(**s)

        print(f"\n  Decision:     {r['decision']}")
        print(f"  Risk:         {r['risk_level']}")
        print(f"  Buffer:       {r['buffer_minutes']} min")
        print(f"  Action:       {r['suggested_action']}")
        print(f"  Reason:       {r['reason']}")
        print(f"\n  Planner:      {r['planner']}")
        print(f"  Simulation:   {r['simulation']}")
        print(f"  Constraints:  {r['constraints']}")
        print(f"  Safety:       {r['safety_validation']}")
        print(f"\n  Context:\n  {r['context']}")
        print(f"\n  Guardian:\n  {r['guardian']}")
        print(f"\n  Explanation:\n  {r['explanation']}")
        print()

