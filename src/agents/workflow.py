"""
workflow.py -- LangGraph Agent Workflow (3 Core Agents)
=========================================================
Builds and compiles the LangGraph workflow with only the 3 real agents:

  context_monitor -> risk_guardian -> explanation -> END

The decision-making logic (delay analysis, risk scoring, planner,
go/no-go) is handled by existing modules in src/decision_engine/
and src/planner/. The orchestrator calls those directly.

Agents only: observe, enforce safety, and explain.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langgraph.graph import StateGraph, END
from src.agents.state import FlightState
from src.agents.nodes import (
    context_monitor_agent,
    risk_guardian_agent,
    explanation_agent,
)


def build_workflow():
    """
    Build and compile the LangGraph agent workflow.
    Only 3 agents — they observe, guard, and explain.
    """
    graph = StateGraph(FlightState)

    # 3 core agents
    graph.add_node("context_monitor", context_monitor_agent)
    graph.add_node("risk_guardian", risk_guardian_agent)
    graph.add_node("explanation", explanation_agent)

    # Linear flow
    graph.set_entry_point("context_monitor")
    graph.add_edge("context_monitor", "risk_guardian")
    graph.add_edge("risk_guardian", "explanation")
    graph.add_edge("explanation", END)

    workflow = graph.compile()
    return workflow


def run_workflow(flight_input: dict) -> dict:
    """
    Run the 3-agent workflow on a flight scenario.
    Expects the decision to already be made by the orchestrator.
    """
    workflow = build_workflow()
    result = workflow.invoke(flight_input)
    return result
