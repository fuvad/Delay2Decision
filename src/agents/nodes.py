"""
nodes.py -- Agent Nodes for the LangGraph Workflow
=====================================================
3 core agents that observe, enforce safety, and explain.
They do NOT replace the models or planner.

Agent flow:
  context_monitor -> risk_guardian -> explanation
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ────────────────────────────────────────────────────────────────────
# Node 1: Context Monitor Agent
# ────────────────────────────────────────────────────────────────────
def context_monitor_agent(state: dict) -> dict:
    """
    Observe the environment and build a structured situation summary.
    Turns raw system outputs into a clear context description.
    This runs FIRST so all downstream agents have full context.
    """
    delay_prob = state.get("delay_prob", 0.0)
    uncertainty = state.get("uncertainty", 0.15)
    buffer_minutes = state.get("buffer_minutes", 30.0)
    itinerary_minutes = state.get("itinerary_minutes", 120.0)
    usable_time = max(0.0, itinerary_minutes - buffer_minutes)
    
    gate = state.get("gate", "unknown")
    destination = state.get("destination", "unknown")
    terminal = state.get("terminal", "?")
    walking_speed = state.get("walking_speed", 1.4)
    stay_minutes = state.get("stay_minutes", 15.0)

    # Classify delay level
    if delay_prob >= 0.7:
        delay_level = "high"
    elif delay_prob >= 0.4:
        delay_level = "moderate"
    else:
        delay_level = "low"

    # Classify congestion from uncertainty
    if uncertainty >= 0.4:
        congestion_level = "high"
    elif uncertainty >= 0.2:
        congestion_level = "moderate"
    else:
        congestion_level = "low"

    # Classify walking speed
    if walking_speed < 1.0:
        speed_label = "slow"
    elif walking_speed > 1.6:
        speed_label = "fast"
    else:
        speed_label = "normal"

    summary = (
        f"Context Summary (Terminal {terminal})\n"
        f"  Flight delay probability: {delay_prob:.2f} ({delay_level})\n"
        f"  Terminal congestion:      {congestion_level}\n"
        f"  System uncertainty:       {uncertainty:.2f}\n"
        f"  Itinerary layover:        {itinerary_minutes:.0f} minutes\n"
        f"  AI safety penalty:        -{buffer_minutes:.0f} minutes\n"
        f"  Total usable time:        {usable_time:.0f} minutes\n"
        f"  Passenger walking speed:  {speed_label} ({walking_speed:.1f} m/s)\n"
        f"  Route:                    {gate} -> {destination}\n"
        f"  Stay time:                {stay_minutes:.0f} minutes"
    )

    return {
        "context_summary": summary,
    }


# ────────────────────────────────────────────────────────────────────
# Node 2: Risk Guardian Agent
# ────────────────────────────────────────────────────────────────────
def risk_guardian_agent(state: dict) -> dict:
    """
    Safety inspector that prevents bad recommendations.
    Checks risk thresholds, buffer adequacy, congestion, and anomalies.
    If something looks unsafe, it blocks the trip outright.
    """
    delay_prob = state.get("delay_prob", 0.0)
    uncertainty = state.get("uncertainty", 0.15)
    buffer_minutes = state.get("buffer_minutes", 30.0)
    itinerary_minutes = state.get("itinerary_minutes", 120.0)
    usable_time = max(0.0, itinerary_minutes - buffer_minutes)
    walking_speed = state.get("walking_speed", 1.4)

    alerts = []
    override = False

    # Check 1: Is risk too high?
    if delay_prob >= 0.75:
        alerts.append(f"Delay probability is very high ({delay_prob:.0%}). Recommend staying at gate.")
        override = True

    # Check 2: Is usable time dangerously small?
    if usable_time < 15:
        alerts.append(f"Usable layover time is only {usable_time:.0f} min. Too risky to leave gate.")
        override = True

    # Check 3: Is uncertainty extreme?
    if uncertainty >= 0.5:
        alerts.append(f"Uncertainty is extreme ({uncertainty:.0%}). System predictions unreliable.")
        override = True

    # Check 4: Is passenger a slow walker with tight usable time?
    if walking_speed < 1.0 and usable_time < 25:
        alerts.append(f"Slow walker ({walking_speed:.1f} m/s) with tight ({usable_time:.0f} min) time. High miss risk.")
        override = True

    # Check 5: Combined risk (high delay + high uncertainty)
    if delay_prob >= 0.5 and uncertainty >= 0.3:
        alerts.append("Both delay and uncertainty are elevated. Caution advised.")
        if not override:
            override = True

    if alerts:
        alert_text = "GUARDIAN ALERTS:\n" + "\n".join(f"  [!] {a}" for a in alerts)
    else:
        alert_text = "GUARDIAN: All safety checks passed."

    return {
        "guardian_alert": alert_text,
        "guardian_override": override,
    }


# ────────────────────────────────────────────────────────────────────
# Node 3: Explanation Agent  (Ollama LLM + SHAP)
# ────────────────────────────────────────────────────────────────────

SHAP_CSV = os.path.join(PROJECT_ROOT, "reports", "shap_values.csv")
OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


def _load_shap_summary():
    """
    Load SHAP values and return the top-5 most impactful features
    with their mean |SHAP| values.
    """
    try:
        import pandas as pd
        df = pd.read_csv(SHAP_CSV)
        mean_abs = df.abs().mean().sort_values(ascending=False)
        top = mean_abs.head(5)
        lines = [f"  {feat}: {val:.4f}" for feat, val in top.items()]
        return "\n".join(lines)
    except Exception:
        return "  (SHAP values not available)"


def _call_ollama(prompt):
    """
    Call the local Ollama API to generate a natural language explanation.
    Returns the generated text, or None if Ollama is unavailable.
    """
    import json
    try:
        import urllib.request
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 200},
        }).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "").strip()
    except Exception:
        return None


def _build_fallback_explanation(state):
    """Template-based fallback when Ollama is not running."""
    delay_prob = state.get("delay_prob", 0.0)
    uncertainty = state.get("uncertainty", 0.15)
    buffer_minutes = state.get("buffer_minutes", 30.0)
    walking_speed = state.get("walking_speed", 1.4)
    gate = state.get("gate", "your gate")
    destination = state.get("destination", "your destination")
    guardian_override = state.get("guardian_override", False)

    parts = []
    if delay_prob >= 0.7:
        parts.append(f"Your flight has a high chance of delay ({delay_prob:.0%}), which means departure timing is unpredictable.")
    elif delay_prob >= 0.4:
        parts.append(f"There is a moderate delay risk ({delay_prob:.0%}). The flight might depart later than scheduled.")
    else:
        parts.append(f"Your flight is likely on time (delay risk: {delay_prob:.0%}).")

    if uncertainty >= 0.4:
        parts.append("Terminal congestion is currently high, adding uncertainty to walking times.")
    elif uncertainty >= 0.2:
        parts.append("There is moderate congestion in the terminal.")
    else:
        parts.append("The terminal is relatively clear right now.")

    parts.append(f"The system recommends staying within a {buffer_minutes:.0f}-minute walking distance from {gate}.")

    if walking_speed < 1.0:
        parts.append("Note: Your walking pace is slower than average.")

    if guardian_override:
        parts.append(f"IMPORTANT: The safety system recommends staying at {gate}.")

    return " ".join(parts)


def explanation_agent(state: dict) -> dict:
    """
    Generate a natural language explanation using:
      1. SHAP values — to explain which features drove the delay prediction
      2. Ollama LLM  — to produce fluent, passenger-friendly language

    Falls back to template-based explanation if Ollama is unavailable.
    """
    delay_prob = state.get("delay_prob", 0.0)
    uncertainty = state.get("uncertainty", 0.15)
    buffer_minutes = state.get("buffer_minutes", 30.0)
    walking_speed = state.get("walking_speed", 1.4)
    gate = state.get("gate", "?")
    destination = state.get("destination", "?")
    terminal = state.get("terminal", "?")
    guardian_override = state.get("guardian_override", False)

    # Read the ACTUAL decision made by the orchestrator
    decision = state.get("decision", "UNKNOWN")
    required_minutes = state.get("required_minutes", 0.0)
    effective_buffer = state.get("effective_buffer", 0.0)

    usable_time = state.get("usable_time", 0.0)
    cross_terminal_error = state.get("cross_terminal_error", False)

    # Load SHAP feature importances
    shap_summary = _load_shap_summary()

    # Build the prompt for Ollama
    if decision == "GO":
        decision_text = f"GO -- it IS safe to walk to {destination} and back"
    elif decision == "MAYBE":
        decision_text = f"MAYBE -- it might be safe but it is tight"
    else:
        decision_text = f"NO -- it is NOT safe to leave the gate"

    terminal_rule = (
        "- CRITICAL: The passenger requested a trip to a DIFFERENT TERMINAL. Walking between terminals is strictly NOT ALLOWED. You MUST explicitly state this as the main reason for rejection.\n"
        if cross_terminal_error else ""
    )

    prompt = (
        "You are an airport layover assistant. A passenger is waiting at their gate "
        "for a flight. They asked if they can WALK to a nearby store or restaurant "
        "INSIDE the airport terminal during their layover.\n\n"
        "The system has ALREADY made a decision. Your ONLY job is to explain WHY "
        "that decision was made. Do NOT contradict the decision.\n\n"
        "RULES:\n"
        "- The 'destination' is a STORE inside the terminal, NOT a flight destination.\n"
        "- Flight delay probability affects how much buffer time is available.\n"
        "- Be concise: 2-3 sentences max. Be friendly.\n"
        "- You MUST agree with the decision below.\n"
        f"{terminal_rule}\n"
        f"DECISION MADE: {decision_text}\n\n"
        f"Facts:\n"
        f"  Gate: {gate} (Terminal {terminal})\n"
        f"  Store: {destination}\n"
        f"  Trip time needed: {required_minutes:.0f} minutes (walk + stay + walk back)\n"
        f"  Usable time available: {effective_buffer:.0f} minutes\n"
        f"  Flight delay probability: {delay_prob:.0%}\n"
        f"  Walking speed: {walking_speed:.1f} m/s\n"
        f"  Cross-terminal violation: {'Yes' if cross_terminal_error else 'No'}\n"
        f"  Guardian blocked: {'Yes' if guardian_override else 'No'}\n\n"
        f"Explain the {decision} decision to the passenger in 2-3 friendly sentences."
        f" Focus only on time, safety, and whether they can make it back in time. Do NOT mention SHAP, ML models, or technical analysis."
    )

    # ── Cross-terminal trips: bypass LLM with deterministic explanation ──
    if cross_terminal_error:
        # Extract destination terminal from node_id (e.g. STARBUCKS_T5 → T5)
        dest_terminal = destination.split("_")[-1] if "_" in destination else "another terminal"
        explanation = (
            f"Your trip was rejected because {destination.replace('_', ' ').title()} "
            f"is located in {dest_terminal}, while your departure gate ({gate.replace('_', ' ')}) "
            f"is in Terminal {terminal}. Walking between different terminals is not supported "
            f"in our system — you would need to pass through security again, which is "
            f"too risky during a layover. Please choose a destination within Terminal {terminal}."
        )
        return {"human_explanation": explanation}

    # Try Ollama first, fall back to templates
    llm_response = _call_ollama(prompt)

    if llm_response:
        explanation = llm_response.strip()
    else:
        fallback = _build_fallback_explanation(state)
        explanation = fallback.strip()

    return {
        "human_explanation": explanation,
    }
