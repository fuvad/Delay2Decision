"""
app.py — FastAPI Backend for Delay2Decision
=============================================
REST API that wraps the ML + Agent orchestrator pipeline.
Serves the React frontend with plan decisions, chatbot, and layout data.
"""

import os
import sys
import csv

# ── Project root setup ─────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    PlanRequest, PlanResponse, PlannerResult, ConstraintsResult, SimulationResult,
    ChatRequest, ChatResponse, LayoutNode,
    MultiPlanRequest, MultiPlanResponse, LegResult, MultiStop,
)
from src.agents.orchestrator import run_full_pipeline

# ── Constants ──────────────────────────────────────────────────────
LAYOUT_CSV  = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")
RISK_CSV    = os.path.join(PROJECT_ROOT, "reports", "layover_risk.csv")
AIRLINE_CSV = os.path.join(PROJECT_ROOT, "data", "raw", "airports", "airline_terminal_map.csv")

# ── FastAPI App ────────────────────────────────────────────────────
app = FastAPI(
    title="Delay2Decision API",
    description="AI-powered layover trip planner for JFK Airport",
    version="1.0.0",
)

# Allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper: get ML predictions from CSV ────────────────────────────
# Full airline name lookup for better chatbot context
_AIRLINE_NAMES = {
    "9E": "Endeavor Air", "AA": "American Airlines", "AS": "Alaska Airlines",
    "B6": "JetBlue Airways", "DL": "Delta Air Lines", "HA": "Hawaiian Airlines",
    "YX": "Republic Airline", "OO": "SkyWest Airlines",
}

# Per-carrier historical delay rates computed from silver_validated.csv
_CARRIER_DELAY_PROB = {
    "9E": 0.300,  # Endeavor Air
    "AA": 0.159,  # American Airlines
    "AS": 0.140,  # Alaska Airlines
    "B6": 0.244,  # JetBlue Airways
    "DL": 0.219,  # Delta Air Lines
    "HA": 0.500,  # Hawaiian Airlines (highest risk)
    "OO": 0.376,  # SkyWest Airlines
    "YX": 0.156,  # Republic Airline
}

def _delay_prob_to_risk_level(delay_prob: float) -> str:
    """Convert a delay probability into a low/medium/high label."""
    if delay_prob >= 0.35:
        return "high"
    elif delay_prob >= 0.20:
        return "medium"
    else:
        return "low"

def _get_ml_predictions(risk_level="medium", airline: str | None = None):
    """
    Return ML predictions for the given risk level.
    If an airline code is provided, `delay_prob` is replaced with the
    carrier's real historical delay rate from the dataset.
    """
    try:
        df = pd.read_csv(RISK_CSV)
        subset = df[df["risk_level"] == risk_level]
        if subset.empty:
            subset = df
        delay_prob = float(subset["delay_prob"].median())
        uncertainty = float(subset["uncertainty"].median())
        buffer_minutes = float(subset["buffer_minutes"].median())

        # Override delay_prob with real carrier history if airline selected
        if airline and airline in _CARRIER_DELAY_PROB:
            delay_prob = _CARRIER_DELAY_PROB[airline]

        return {
            "delay_prob": delay_prob,
            "uncertainty": uncertainty,
            "buffer_minutes": buffer_minutes,
        }
    except Exception:
        return {"delay_prob": 0.30, "uncertainty": 0.15, "buffer_minutes": 10.0}


from src.decision_engine.constraint_checker import BOARDING_CLOSE_BEFORE_DEPARTURE

# ── Endpoint: POST /api/plan ───────────────────────────────────────
@app.post("/api/plan", response_model=PlanResponse)
def create_plan(req: PlanRequest):
    """
    Submit a trip plan. Returns GO / MAYBE / NO decision
    with full agent analysis, risk breakdown, and LLM explanation.
    """
    # Use overrides if provided, otherwise use carrier-aware ML predictions
    ml = _get_ml_predictions("medium", airline=req.airline)

    # ── PERSONALIZATION: map experience → profile multiplier ──
    from src.decision_engine.personalization import PROFILES
    exp_map = {"beginner": "conservative", "normal": "balanced", "experienced": "aggressive"}
    profile_key = exp_map.get(req.experience, "balanced")
    experience_multiplier = PROFILES[profile_key]["buffer_multiplier"]

    delay_prob = req.delay_prob if req.delay_prob is not None else ml["delay_prob"]
    uncertainty = req.uncertainty if req.uncertainty is not None else ml["uncertainty"]
    buffer_minutes = req.buffer_minutes if req.buffer_minutes is not None else ml["buffer_minutes"]

    # Derive risk_level from the actual delay_prob so it reflects the carrier
    effective_risk_level = _delay_prob_to_risk_level(delay_prob)

    try:
        result = run_full_pipeline(
            gate=req.gate,
            destination=req.destination,
            terminal=req.terminal,
            delay_prob=delay_prob,
            uncertainty=uncertainty,
            buffer_minutes=buffer_minutes,
            itinerary_minutes=req.itinerary_minutes,
            stay_minutes=req.stay_minutes,
            walking_speed=req.walking_speed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    go_result = result.get("go_result", {})
    raw_usable = go_result.get("effective_buffer", max(0.0, req.itinerary_minutes - buffer_minutes - BOARDING_CLOSE_BEFORE_DEPARTURE))

    # Apply experience modifier to usable time for a meaningful visible difference.
    # PROFILES multiplies the buffer penalty, so we use the inverse when scaling usable_time:
    #   Experienced (buffer x0.8) → usable_time ÷0.8 = ×1.25 (+25%)
    #   Normal      (buffer x1.0) → usable_time unchanged
    #   Beginner    (buffer x1.2) → usable_time ÷1.2 = ×0.83 (-17%)
    usable_time = round(raw_usable / experience_multiplier, 1)
    
    # Cap usable time so it never exceeds the absolute physical limit before boarding
    max_physical_time = max(0.0, req.itinerary_minutes - BOARDING_CLOSE_BEFORE_DEPARTURE)
    usable_time = min(usable_time, max_physical_time)

    # Build simulation sub-model
    sim_raw = result.get("simulation", {})
    sim = SimulationResult(
        total_minutes=sim_raw.get("total_minutes"),
        walk_minutes=sim_raw.get("walk_minutes"),
        stay_minutes=sim_raw.get("stay_minutes"),
        error=sim_raw.get("error"),
    )

    planner_raw = result.get("planner", {})
    planner = PlannerResult(
        feasible=planner_raw.get("feasible", False),
        required_minutes=planner_raw.get("required_minutes", 0),
    )

    constraints_raw = result.get("constraints", {})
    constraints = ConstraintsResult(
        safe=constraints_raw.get("safe", False),
        violated=constraints_raw.get("violated", []),
    )

    return PlanResponse(
        decision=result["decision"],
        risk_level=effective_risk_level,
        buffer_minutes=buffer_minutes,
        itinerary_minutes=req.itinerary_minutes,
        usable_time=round(usable_time, 1),
        suggested_action=result["suggested_action"],
        reason=result["reason"],
        explanation=result.get("explanation", ""),
        context=result.get("context", ""),
        guardian=result.get("guardian", ""),
        planner=planner,
        simulation=sim,
        constraints=constraints,
    )


# ── Endpoint: POST /api/replan ─────────────────────────────────────
@app.post("/api/replan", response_model=PlanResponse)
def replan(req: PlanRequest):
    """
    Re-plan with updated parameters (e.g., gate change).
    Same logic as /api/plan — exists as a semantic alias.
    """
    return create_plan(req)


# ── Endpoint: POST /api/plan-multi ────────────────────────────────
@app.post("/api/plan-multi", response_model=MultiPlanResponse)
def create_multi_plan(req: MultiPlanRequest):
    """
    Plan a multi-stop trip: gate → stop1 → stop2 → ... → gate.
    Computes total required time from walking time between each stop
    plus each stop's stay duration.
    """
    import networkx as nx
    from src.planner.indoor_graph import build_graph, walking_time_seconds
    from src.decision_engine.constraint_checker import BOARDING_CLOSE_BEFORE_DEPARTURE
    from src.decision_engine.go_no_go import decide_action

    ml = _get_ml_predictions("medium", airline=req.airline)

    # ── PERSONALIZATION: map experience → profile multiplier ──
    from src.decision_engine.personalization import PROFILES
    exp_map = {"beginner": "conservative", "normal": "balanced", "experienced": "aggressive"}
    profile_key = exp_map.get(req.experience, "balanced")
    experience_multiplier = PROFILES[profile_key]["buffer_multiplier"]

    delay_prob = req.delay_prob if req.delay_prob is not None else ml["delay_prob"]
    uncertainty = req.uncertainty if req.uncertainty is not None else ml["uncertainty"]
    buffer_minutes = req.buffer_minutes if req.buffer_minutes is not None else ml["buffer_minutes"]

    LAYOUT = os.path.join(PROJECT_ROOT, "data", "layout", "jfk_layout.csv")
    G = build_graph(LAYOUT)

    risk_score = min(1.0, 0.6 * delay_prob + 0.4 * uncertainty)
    
    if risk_score >= 0.6:
        risk_level = "high"
    elif risk_score >= 0.3:
        risk_level = "medium"
    else:
        risk_level = "low"

    raw_usable = max(0.0, req.itinerary_minutes - buffer_minutes - BOARDING_CLOSE_BEFORE_DEPARTURE)
    go_result = decide_action(
        required_minutes=0,   # dummy — we only need effective_buffer
        usable_time=raw_usable,
        uncertainty=uncertainty,
        risk=risk_score,
    )
    # Apply experience modifier to the full effective buffer for a visible difference.
    # Use inverse of buffer multiplier so Experienced gets MORE usable time.
    usable_time = round(go_result["effective_buffer"] / experience_multiplier, 1)
    
    # Cap usable time to avoid exceeding physical constraints
    max_physical_time = max(0.0, req.itinerary_minutes - BOARDING_CLOSE_BEFORE_DEPARTURE)
    usable_time = min(usable_time, max_physical_time)

    # Build the node chain: gate → stop1 → stop2 → ... → gate
    chain = [req.gate] + [s.destination for s in req.stops] + [req.gate]
    stay_chain = [s.stay_minutes for s in req.stops] + [0]  # 0 stay on final return

    legs: list[LegResult] = []
    total_required = 0.0

    for i in range(len(chain) - 1):
        from_node = chain[i]
        to_node = chain[i + 1]
        stay = stay_chain[i]

        try:
            walk_secs = walking_time_seconds(G, from_node, to_node, walking_speed=req.walking_speed)
            walk_min = round(walk_secs / 60, 2)
        except nx.NetworkXNoPath:
            raise HTTPException(
                status_code=422,
                detail=f"No walking path between {from_node} and {to_node}. They may be in different terminals."
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        legs.append(LegResult(
            from_node=from_node,
            to_node=to_node,
            walk_minutes=walk_min,
            stay_minutes=stay,
        ))
        total_required += walk_min + stay

    total_required = round(total_required, 1)
    spare = round(usable_time - total_required, 1)

    # GO / MAYBE / NO logic (same thresholds as single-stop)
    if total_required > usable_time:
        decision = "NO"
        action = f"Not enough time. You need {total_required:.0f} min but only have {usable_time:.0f} min."
        reason = "Total trip time exceeds usable layover window."
    elif spare < 9.5:
        decision = "MAYBE"
        action = f"Tight timing. Only {spare:.0f} min spare — proceed only if everything goes smoothly."
        reason = "Less than 10 minutes spare — higher risk if delays occur."
    else:
        decision = "GO"
        action = f"Safe to proceed. {spare:.0f} min spare after {len(req.stops)}-stop trip."
        reason = f"All stops fit within usable time with {spare:.0f} min to spare."

    stops_text = " → ".join(s.destination for s in req.stops)
    explanation = (
        f"Your {len(req.stops)}-stop trip (Gate {req.gate} → {stops_text} → back) "
        f"requires {total_required:.1f} minutes of your {usable_time:.0f} min usable window, "
        f"leaving {max(0, spare):.0f} minutes as a buffer. {action}"
    )

    alternative_rec = None
    if decision in ["NO", "MAYBE"] and req.stops:
        try:
            if len(req.stops) == 1:
                from src.decision_engine.alternative_planner import find_alternative
                first_stop = req.stops[0]
                alternative_rec = find_alternative(
                    gate=req.gate,
                    destination=first_stop.destination,
                    terminal=req.terminal,
                    usable_time=usable_time,
                    original_stay=first_stop.stay_minutes,
                    original_speed=req.walking_speed,
                    layout_graph=G
                )
            else:
                from src.decision_engine.alternative_planner import find_multi_stop_alternative
                total_walk = sum([leg.walk_minutes for leg in legs])
                alternative_rec = find_multi_stop_alternative(
                    req_stops=req.stops,
                    usable_time=usable_time,
                    total_required=total_required,
                    total_walk_time=total_walk
                )
        except Exception as e:
            print("Failed alternative planning:", e)
            pass
            
    if alternative_rec:
        action += "\n\n" + alternative_rec["message"]
        explanation += "\n\n" + alternative_rec["message"]

    return MultiPlanResponse(
        decision=decision,
        risk_level=risk_level,
        usable_time=round(usable_time, 1),
        total_required=total_required,
        buffer_minutes=buffer_minutes,
        itinerary_minutes=req.itinerary_minutes,
        suggested_action=action,
        reason=reason,
        explanation=explanation,
        legs=legs,
    )


# ── Endpoint: GET /api/layout ──────────────────────────────────────
@app.get("/api/layout", response_model=list[LayoutNode])
def get_layout():
    """Return the JFK airport layout (gates, restaurants, restrooms)."""
    nodes = []
    try:
        with open(LAYOUT_CSV, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nodes.append(LayoutNode(
                    node_id=row["node_id"],
                    type=row["type"],
                    terminal=int(row["terminal"]),
                    x=float(row["x"]),
                    y=float(row["y"]),
                ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Layout load error: {e}")
    return nodes


# ── Endpoint: GET /api/airlines ────────────────────────────────────
@app.get("/api/airlines")
def get_airlines():
    """Return list of airlines with their terminal at JFK."""
    try:
        df = pd.read_csv(AIRLINE_CSV)
        airlines = []
        for _, row in df.iterrows():
            code = row["airline"]
            airlines.append({
                "code": code,
                "name": _AIRLINE_NAMES.get(code, code),
                "terminal": int(row["terminal"]),
            })
        return airlines
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Airline data load error: {e}")


# ── Endpoint: POST /api/chat ───────────────────────────────────────

def _load_node_ids():
    """Load all node IDs from jfk_layout.csv for intent matching."""
    try:
        df = pd.read_csv(LAYOUT_CSV)
        return df.to_dict("records")
    except Exception:
        return []

# Gate letter → terminal mapping
_GATE_TERMINAL_MAP = {"A": 8, "B": 4, "C": 5, "D": 7}

def _extract_trip_intent(message: str, nodes: list, default_gate: str | None = None) -> dict | None:

    """
    Extract trip intent from a natural language message.
    Returns a dict with:
      - gate, terminal, walking_speed, itinerary_minutes  (single values)
      - stops: list of { destination, stay_minutes }      (ordered)
    or None if no trip intent is detected.
    """
    import re
    msg = message.lower()

    # ── Quick check: does this look like a trip request? ──
    trip_keywords = ["go to", "walk to", "visit", "want to go", "like to go",
                     "head to", "get to", "from gate", "from terminal"]
    if not any(kw in msg for kw in trip_keywords):
        return None

    # ── Extract departure gate ──
    gate_match = re.search(r'gate\s*([a-d])\s*(\d+)', msg, re.IGNORECASE)
    gate_id = None
    gate_terminal = None
    if gate_match:
        letter = gate_match.group(1).upper()
        number = gate_match.group(2)
        gate_id = f"GATE_{letter}{number}"
        gate_terminal = _GATE_TERMINAL_MAP.get(letter)
    elif default_gate and default_gate != "N/A":
        gate_id = default_gate
        if "_" in gate_id:
            letter = gate_id.split("_")[1][0]
            gate_terminal = _GATE_TERMINAL_MAP.get(letter)

    # ── Destination keyword → node_prefix map ──
    dest_keywords = {
        "starbucks": "STARBUCKS",
        "mcdonald": "MC_DONALDS",
        "dunkin": "DUNKIN",
        "shake shack": "SHAKE_SHACK",
        "restroom": "RESTROOM",
        "bathroom": "RESTROOM",
        "toilet": "RESTROOM",
    }

    # ── Find all destination mentions in message order ──
    # Build list of (position_in_msg, node_prefix, keyword)
    occurrences = []
    for keyword, node_prefix in dest_keywords.items():
        pos = msg.find(keyword)
        while pos != -1:
            occurrences.append((pos, node_prefix, keyword))
            pos = msg.find(keyword, pos + 1)

    # Also detect gate destinations like "go to gate C1"
    for gate_dest_match in re.finditer(r'(?:go\s+to|head\s+to|then\s+to)\s+gate\s*([a-d])\s*(\d+)', msg, re.IGNORECASE):
        letter = gate_dest_match.group(1).upper()
        number = gate_dest_match.group(2)
        dest_gate_id = f"GATE_{letter}{number}"
        occurrences.append((gate_dest_match.start(), f"GATE_DEST:{dest_gate_id}", "gate"))

    if not occurrences:
        return None

    # Sort by position in message (preserves user's intended order)
    occurrences.sort(key=lambda x: x[0])

    # Deduplicate consecutive identical prefixes (e.g. "mcdonald's mcdonald's")
    seen_prefixes = []
    unique_occs = []
    for occ in occurrences:
        if occ[1] not in seen_prefixes:
            seen_prefixes.append(occ[1])
            unique_occs.append(occ)
    occurrences = unique_occs

    # ── Extract global parameters ──
    walking_speed = 1.4
    speed_match = re.search(
        r'(?:walk(?:ing)?(?:\s*speed)?|speed)\s*(?:is\s*|of\s*|at\s*)?(\d+\.?\d*)\s*(?:m/?s)?',
        msg, re.IGNORECASE
    )
    if speed_match:
        walking_speed = float(speed_match.group(1))
    elif "slow" in msg:
        walking_speed = 0.8
    elif "fast" in msg:
        walking_speed = 2.0

    itinerary_minutes = 120.0
    layover_match = re.search(
        r'(?:(?:layover|connection)\s*(?:duration\s*)?(?:is\s*|of\s*)?(\d+)\s*(?:hours?|min(?:utes?)?)'
        r'|(?:have\s*a\s*)?(\d+)\s*(?:hours?|min(?:utes?)?)?\s*(?:layover|connection))',
        msg, re.IGNORECASE
    )
    if layover_match:
        raw = layover_match.group(1) or layover_match.group(2)
        if raw:
            val = float(raw)
            if re.search(r'\d+\s*hours?', layover_match.group(0), re.IGNORECASE):
                val *= 60
            itinerary_minutes = val

    # ── Per-stop: extract stay duration from the text segment around each occurrence ──
    # Strategy: slice the message into segments between each destination mention
    # then search for a stay duration within that slice
    stay_pattern = re.compile(
        # Matches: "stay there for 25 min", "stay ther for 25", "stay 25 min", "for 25 minutes"
        r'(?:stay(?:ing)?(?:\s+\w{1,6})?\s+(?:for\s+)?(\d+)'
        r'|(?:for\s+)(\d+))\s*(?:hours?|min(?:utes?)?)',
        re.IGNORECASE
    )

    def _extract_stay_from_segment(segment: str, default: float = 15.0) -> float:
        m = stay_pattern.search(segment)
        if m:
            raw = m.group(1) or m.group(2)
            val = float(raw)
            if re.search(r'\d+\s*hours?', m.group(0), re.IGNORECASE):
                val *= 60
            return val
        return default

    # Slice message into segments: [before_stop1 | stop1 ... before_stop2 | stop2 ... end]
    stops = []
    for idx, (pos, node_prefix, keyword) in enumerate(occurrences):
        # Text from this occurrence up to the next (or end of message)
        if idx + 1 < len(occurrences):
            segment = msg[pos: occurrences[idx + 1][0]]
        else:
            segment = msg[pos:]

        stay_min = _extract_stay_from_segment(segment)

        # Handle direct gate destinations like "GATE_DEST:GATE_C1"
        if node_prefix.startswith("GATE_DEST:"):
            dest_id = node_prefix[len("GATE_DEST:"):]
            stops.append({"destination": dest_id, "stay_minutes": stay_min})
            continue

        # Find the terminal for this stop from the local segment
        dest_terminal = None
        term_match = re.search(r'(?:terminal|t)\s*(\d+)', segment, re.IGNORECASE)
        if term_match:
            dest_terminal = int(term_match.group(1))

        # Resolve node_id from layout
        dest_id = None
        for node in nodes:
            if node["node_id"].startswith(node_prefix):
                node_terminal = int(node["terminal"])
                if dest_terminal and node_terminal == dest_terminal:
                    dest_id = node["node_id"]
                    break
                elif not dest_terminal and gate_terminal and node_terminal == gate_terminal:
                    dest_id = node["node_id"]
                    break
        # Fallback: first match
        if not dest_id:
            for node in nodes:
                if node["node_id"].startswith(node_prefix):
                    dest_id = node["node_id"]
                    break

        if dest_id:
            stops.append({"destination": dest_id, "stay_minutes": stay_min})

    if not stops or not gate_id:
        return None

    return {
        "gate": gate_id,
        "terminal": gate_terminal or 4,
        "walking_speed": walking_speed,
        "itinerary_minutes": itinerary_minutes,
        "stops": stops,
        # Backward-compat single-stop fields
        "destination": stops[0]["destination"],
        "stay_minutes": stops[0]["stay_minutes"],
    }

def _call_llm(prompt: str, json_format: bool = False, timeout: int = 30) -> str | None:
    """
    Unified LLM caller. Uses Groq/Cloud API if GROQ_API_KEY is set, 
    otherwise falls back to local Ollama (localhost:11434).
    """
    import os
    import requests as _req
    
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant",  # Fast, free tier model on Groq
            "messages": [{"role": "user", "content": prompt}]
        }
        if json_format:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            resp = _req.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Groq API error: {e}")
            return None
            
    # Fallback to local Ollama
    try:
        payload = {"model": "llama3.2:3b", "prompt": prompt, "stream": False}
        if json_format:
            payload["format"] = "json"
            
        resp = _req.post("http://host.docker.internal:11434/api/generate", json=payload, timeout=timeout)
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception as e:
        print(f"Ollama local error: {e}")
        return None
    return None

def _extract_trip_intent_via_llm(
    message: str,
    nodes: list,
    default_gate: str | None,
) -> dict | None:
    """
    Tier-2 fallback intent extractor.
    Calls llama3.2:3b locally and asks it to return a structured JSON
    object describing the trip. Used only when the regex fast-path fails.
    Returns the same dict shape as `_extract_trip_intent`, or None.
    """
    import json
    import requests as _req

    # Build lists of valid node IDs to embed in the prompt
    dest_node_ids = [
        n["node_id"] for n in nodes if not str(n["node_id"]).startswith("GATE_")
    ]
    gate_node_ids = [
        n["node_id"] for n in nodes if str(n["node_id"]).startswith("GATE_")
    ]
    # Keep prompt size reasonable
    dest_list_str = ", ".join(dest_node_ids[:50])
    gate_list_str = ", ".join(gate_node_ids[:40])

    default_hint = (
        f"The user's departure gate from the UI is: {default_gate}. "
        "Use it if no gate is mentioned in the message."
        if default_gate
        else "No default gate is set. If no gate is mentioned, return null for gate."
    )

    prompt = (
        "You are a structured data extractor for JFK Airport layover trip planning.\n"
        "Extract the user's trip intent from their message and return ONLY a valid JSON object.\n"
        "Do NOT include any explanation, markdown, or extra text — only the raw JSON.\n\n"
        f"{default_hint}\n\n"
        "Valid destination node IDs you may use:\n"
        f"{dest_list_str}\n\n"
        "Valid departure gate node IDs:\n"
        f"{gate_list_str}\n\n"
        "Return exactly this structure:\n"
        "{\n"
        '  "gate": "<GATE_XX or null>",\n'
        '  "terminal": <integer or null>,\n'
        '  "walking_speed": <float, default 1.4 m/s>,\n'
        '  "itinerary_minutes": <float, default 120.0>,\n'
        '  "stops": [\n'
        '    {"destination": "<exact node_id from the list above>", "stay_minutes": <float, default 15.0>}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Only include stops the user explicitly mentions.\n"
        "- Map colloquial names: 'coffee' -> STARBUCKS or DUNKIN, 'burger'/'fast food' -> MC_DONALDS or SHAKE_SHACK, "
        "'bathroom'/'toilet'/'loo' -> RESTROOM.\n"
        "- 'slow' walking = 0.8, 'fast' walking = 2.0, default = 1.4.\n"
        "- Convert hours to minutes for all durations.\n"
        "- If the message is NOT describing a trip (e.g. a general question), return: {\"not_a_trip\": true}\n\n"
        f"User message: \"{message}\"\n\nJSON:"
    )

    try:
        raw = _call_llm(prompt, json_format=True, timeout=20)
        if not raw:
            return None

        raw = raw.strip()
        # Strip markdown code fences if the model wraps the JSON
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        # Model says it's not a trip → treat as Q&A
        if data.get("not_a_trip"):
            return None

        gate = data.get("gate") or default_gate
        if not gate:
            return None

        stops = data.get("stops", [])
        if not stops:
            return None

        # Validate: only keep stops whose node_id actually exists in the layout
        valid_ids = {str(n["node_id"]) for n in nodes}
        valid_stops = [
            {"destination": str(s["destination"]), "stay_minutes": float(s.get("stay_minutes") or 15.0)}
            for s in stops
            if str(s.get("destination", "")) in valid_ids
        ]
        if not valid_stops:
            return None

        # Derive terminal from gate letter if not supplied by the model
        terminal = data.get("terminal")
        if not terminal and "_" in gate:
            letter = gate.split("_")[1][0] if len(gate.split("_")) > 1 else None
            terminal = _GATE_TERMINAL_MAP.get(letter) if letter else 4
        terminal = int(terminal) if terminal else 4

        return {
            "gate": gate,
            "terminal": terminal,
            "walking_speed": float(data.get("walking_speed") or 1.4),
            "itinerary_minutes": float(data.get("itinerary_minutes") or 120.0),
            "stops": valid_stops,
            # Backward-compat single-stop fields
            "destination": valid_stops[0]["destination"],
            "stay_minutes": valid_stops[0]["stay_minutes"],
        }

    except Exception:
        return None


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Chatbot endpoint. If the user describes a trip, extract intent and
    run the full feasibility pipeline. Otherwise, answer as a Q&A assistant.
    """
    import requests as http_requests

    def _rewrite_with_llm(preset_text: str, decision: str, stops_summary: str = "", experience: str = "normal") -> str:
        stops_hint = (
            f"The passenger's trip includes these stops in order: {stops_summary}.\n"
            if stops_summary else ""
        )
        exp_hint = (
            f"The passenger has '{experience}' layover experience. "
            f"{'Give beginner tips if appropriate. ' if experience == 'beginner' else ''}"
            f"{'Acknowledge them as a frequent flyer. ' if experience == 'experienced' else ''}\n"
        )
        prompt = (
            f"You are a helpful and polite conversational layover assistant for JFK Airport.\n"
            f"The system calculated this exact response for the passenger:\n\n"
            f"EXPLANATION: {preset_text}\n\n"
            f"{stops_hint}"
            f"{exp_hint}"
            f"Please rewrite this explanation to be natural and empathetic (2-3 sentences max). "
            f"You MUST mention ALL stops the passenger plans to visit (from the stops list above). "
            f"Keep all numbers identical to the explanation above. "
            f"Do not ask the user any follow-up questions."
        )
        try:
            new_reply = _call_llm(prompt, json_format=False, timeout=15)
            if new_reply: return new_reply.strip()
        except Exception:
            pass
        return preset_text

    nodes = _load_node_ids()
    ctx = req.context or {}
    default_gate = ctx.get('gate')
    context_airline = ctx.get('airline')  # airline from the UI dropdown
    context_experience = ctx.get('experience', 'normal')  # user experience level
    intent = _extract_trip_intent(req.message, nodes, default_gate=default_gate)

    # ── Tier-2 fallback: LLM-based extraction when regex finds nothing ──
    llm_fallback_used = False
    if intent is None:
        intent = _extract_trip_intent_via_llm(req.message, nodes, default_gate)
        if intent is not None:
            llm_fallback_used = True

    plan_result_dict = None

    # ── If trip intent detected, run the full pipeline ──
    if intent:
        stops = intent.get("stops", [])
        is_multi = len(stops) > 1

        try:
            ml = _get_ml_predictions("medium", airline=context_airline)
            buffer_minutes = ml["buffer_minutes"]
            BOARDING = BOARDING_CLOSE_BEFORE_DEPARTURE
            usable_time = max(0.0, intent["itinerary_minutes"] - buffer_minutes - BOARDING)

            def _to_native(obj):
                if isinstance(obj, dict):
                    return {k: _to_native(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_to_native(i) for i in obj]
                if isinstance(obj, (np.bool_,)):
                    return bool(obj)
                if isinstance(obj, (np.integer,)):
                    return int(obj)
                if isinstance(obj, (np.floating,)):
                    return float(obj)
                return obj

            if is_multi:
                # ── Multi-stop: delegate entirely to the real plan-multi endpoint ──
                # This guarantees identical results to using the Plan Your Trip form
                multi_req = MultiPlanRequest(
                    gate=intent["gate"],
                    terminal=intent["terminal"],
                    stops=[MultiStop(destination=s["destination"], stay_minutes=s["stay_minutes"]) for s in stops],
                    walking_speed=intent["walking_speed"],
                    itinerary_minutes=intent["itinerary_minutes"],
                    airline=context_airline,
                    experience=context_experience,
                )
                multi_result = create_multi_plan(multi_req)

                legs_out = [{"from_node": l.from_node, "to_node": l.to_node, "walk_minutes": l.walk_minutes, "stay_minutes": l.stay_minutes} for l in multi_result.legs]

                plan_result_dict = _to_native({
                    "decision": multi_result.decision,
                    "risk_level": multi_result.risk_level,
                    "buffer_minutes": multi_result.buffer_minutes,
                    "itinerary_minutes": multi_result.itinerary_minutes,
                    "usable_time": multi_result.usable_time,
                    "total_required": multi_result.total_required,
                    "suggested_action": multi_result.suggested_action,
                    "reason": multi_result.reason,
                    "explanation": multi_result.explanation,
                    "legs": legs_out,
                    "constraints": {"safe": multi_result.decision != "NO", "violated": []},
                    "request_params": {
                        "gate": intent["gate"],
                        "terminal": intent["terminal"],
                        "walking_speed": intent["walking_speed"],
                        "itinerary_minutes": intent["itinerary_minutes"],
                        "stops": stops,
                        "_multi": True,
                        "airline": context_airline,
                        "experience": context_experience,
                    },
                })
                reply_preset = multi_result.explanation
                stops_summary = " then ".join([s["destination"] for s in stops])
                reply = _rewrite_with_llm(reply_preset, multi_result.decision, stops_summary, context_experience)


            else:
                # ── Single-stop: use the original ML pipeline ──
                result = run_full_pipeline(
                    gate=intent["gate"],
                    destination=intent["destination"],
                    terminal=intent["terminal"],
                    delay_prob=ml["delay_prob"],
                    uncertainty=ml["uncertainty"],
                    buffer_minutes=buffer_minutes,
                    itinerary_minutes=intent["itinerary_minutes"],
                    stay_minutes=intent["stay_minutes"],
                    walking_speed=intent["walking_speed"],
                )
                go_result = result.get("go_result", {})
                usable_time = go_result.get("effective_buffer", usable_time)
                sim_raw = result.get("simulation", {})
                planner_raw = result.get("planner", {})
                constraints_raw = result.get("constraints", {})

                plan_result_dict = _to_native({
                    "decision": result["decision"],
                    "risk_level": result["risk_level"],
                    "buffer_minutes": buffer_minutes,
                    "itinerary_minutes": intent["itinerary_minutes"],
                    "usable_time": round(usable_time, 1),
                    "suggested_action": result["suggested_action"],
                    "reason": result["reason"],
                    "explanation": result.get("explanation", ""),
                    "context": result.get("context", ""),
                    "guardian": result.get("guardian", ""),
                    "request_params": {
                        "gate": intent["gate"],
                        "destination": intent["destination"],
                        "terminal": intent["terminal"],
                        "stay_minutes": intent["stay_minutes"],
                        "walking_speed": intent["walking_speed"],
                        "itinerary_minutes": intent["itinerary_minutes"],
                        "airline": context_airline,
                        "experience": context_experience,
                    },
                    "planner": {
                        "feasible": planner_raw.get("feasible", False),
                        "required_minutes": planner_raw.get("required_minutes", 0),
                    },
                    "simulation": {
                        "total_minutes": sim_raw.get("total_minutes"),
                        "walk_minutes": sim_raw.get("walk_minutes"),
                        "stay_minutes": sim_raw.get("stay_minutes"),
                        "error": sim_raw.get("error"),
                    },
                    "constraints": {
                        "safe": constraints_raw.get("safe", False),
                        "violated": constraints_raw.get("violated", []),
                    },
                })
                reply_preset = result.get("explanation", "") or result.get("reason", "Trip analyzed.")
                stops_summary = intent["destination"]
                reply = _rewrite_with_llm(reply_preset, result["decision"], stops_summary, context_experience)


            return ChatResponse(
                reply=reply,
                decision=plan_result_dict.get("decision"),
                plan_result=plan_result_dict,
            )

        except Exception as e:
            return ChatResponse(
                reply=f"I tried to analyze that trip but encountered an error: {str(e)}",
                decision=None,
                plan_result=None,
            )

    # ── No trip intent → normal Q&A chatbot ──
    try:
        ctx = req.context or {}
        decision = ctx.get('decision', 'N/A')
        gate = ctx.get('gate', 'N/A')
        destination = ctx.get('destination', 'N/A')
        explanation = ctx.get('explanation', '')
        airline_code = ctx.get('airline', None)
        airline_name = _AIRLINE_NAMES.get(airline_code, airline_code) if airline_code else None

        prompt = (
            f"You are an AI assistant embedded in the Delay2Decision app — an airport layover trip planner for JFK Airport.\n"
            f"Your ONLY job is to help passengers decide whether they have time to visit a store or restaurant INSIDE JFK Airport during their layover.\n\n"
            f"STRICT RULES:\n"
            f"- You ONLY discuss JFK Airport layover decisions. NEVER give travel advice, flight tips, or city recommendations.\n"
            f"- If the passenger asks an entirely unrelated question about a city, country, or tourist spot outside JFK, politely reply: 'I can only help with layover decisions inside JFK Airport.'\n"
            f"- Do NOT mention SHAP, ML models, or any technical internals.\n"
            f"- Be concise: 2-3 sentences max. Be friendly.\n\n"
        )

        if airline_name:
            prompt += f"The passenger is flying: {airline_name} ({airline_code}).\n\n"

        if ctx and gate != 'N/A':
            prompt += (
                f"The system has analyzed the following trip:\n"
                f"  Gate: {gate}, Destination: {destination}, Decision: {decision}\n"
                f"  Explanation: {explanation}\n\n"
                f"RULES: You MUST agree with the system's {decision} decision for this trip.\n\n"
            )

        prompt += f"Passenger message: \"{req.message}\"\n\nRespond in 2-3 sentences."

        raw = _call_llm(prompt, json_format=False, timeout=30)
        if raw:
            reply = raw.strip()
        else:
            reply = "The AI assistant log is currently unavailable. Please check your API key or localhost connection."

    except Exception:
        reply = "The AI assistant is currently offline. Please check your API key or localhost connection."

    return ChatResponse(reply=reply, decision=None)


# ── Endpoint: GET /api/status ──────────────────────────────────────
@app.get("/api/status")
def status():
    import os
    import requests

    provider = "unknown"
    llm_ok = False

    if os.environ.get("GROQ_API_KEY"):
        provider = "groq"
        llm_ok = True
    else:
        try:
            r = requests.get("http://host.docker.internal:11434/api/tags", timeout=3)
            if r.status_code == 200:
                provider = "ollama"
                llm_ok = True
        except:
            provider = "none"

    return {
        "status": "healthy",
        "llm_available": llm_ok,
        "llm_provider": provider,
        "layout_nodes": sum(1 for _ in open(LAYOUT_CSV)) - 1 if os.path.exists(LAYOUT_CSV) else 0,
        "risk_csv_exists": os.path.exists(RISK_CSV),
    }


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


#CI/CD test