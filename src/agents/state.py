"""
state.py -- Shared Agent State
================================
Defines the TypedDict that flows through the LangGraph workflow.
Every agent node reads from and writes to this shared state.
"""

from typing import TypedDict, Optional


class FlightState(TypedDict):
    """
    State dictionary that flows through the agent graph.
    """
    # ── Input Parameters ────────────────────────────────────────────────
    gate: str              # e.g., "GATE_B1"
    destination: str       # e.g., "STARBUCKS_T4"
    terminal: int          # e.g., 4
    stay_minutes: float    # time spent at the destination
    walking_speed: float   # passenger walking speed (m/s)
    
    # ── ML Predictions ──────────────────────────────────────────────────
    delay_prob: float      # output from delay model (0.0 to 1.0)
    uncertainty: float     # prediction volatility based on std. dev
    buffer_minutes: float  # extra safe margin predicted by ML (penalty)
    itinerary_minutes: float # actual scheduled layover time in minutes
    guardian_override: bool          # True if guardian blocks the trip

    # ---- Context monitor agent ----
    context_summary: str            # structured situation description

    # ---- Risk guardian agent ----
    guardian_alert: str              # safety warning (empty if safe)

    # ---- Explanation agent ----
    human_explanation: str           # natural language explanation for passenger

    # ---- Delay prediction agent ----
    delay_prob: float               # 0-1 probability
    delay_assessment: str           # human-readable summary

    # ---- Risk computation agent ----
    risk_score: float               # 0-1 unified risk
    uncertainty: float              # 0-1
    risk_level: str                 # low / medium / high
    risk_assessment: str

    # ---- Planner agent ----
    required_minutes: float         # total trip time from planner
    effective_buffer: float         # buffer after adjustments
    buffer_minutes: float           # raw buffer from ML
    planner_assessment: str
    cross_terminal_error: bool      # True if destination is in a different terminal

    # ---- Recommendation agent ----
    decision: str                   # GO / MAYBE / NO
    constraints_safe: bool          # all constraints passed?
    violated_constraints: list      # which constraints failed
    recommendation: str             # final human-readable recommendation
