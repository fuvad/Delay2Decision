"""
schemas.py — Pydantic Request/Response Models for the API
===========================================================
"""

from pydantic import BaseModel, Field
from typing import Optional, List


# ── Request Models ─────────────────────────────────────────────────

class PlanRequest(BaseModel):
    """Request body for /api/plan and /api/replan"""
    gate: str = Field(..., example="GATE_B1", description="Departure gate ID")
    destination: str = Field(..., example="STARBUCKS_T4", description="Destination node ID")
    terminal: int = Field(..., example=4, description="Terminal number")
    stay_minutes: float = Field(15.0, ge=1, le=120, description="Time to spend at destination")
    walking_speed: float = Field(1.4, ge=0.5, le=2.5, description="Passenger walking speed m/s")
    itinerary_minutes: float = Field(120.0, ge=10, le=720, description="Total layover time from itinerary")
    delay_prob: Optional[float] = Field(None, ge=0, le=1, description="Override delay probability (auto if None)")
    uncertainty: Optional[float] = Field(None, ge=0, le=1, description="Override uncertainty (auto if None)")
    buffer_minutes: Optional[float] = Field(None, description="Override ML buffer penalty (auto if None)")
    airline: Optional[str] = Field(None, description="Airline IATA code (e.g. 'DL', 'B6')")
    experience: Optional[str] = Field("normal", description="User layover experience level (beginner, normal, experienced)")


class ChatRequest(BaseModel):
    """Request body for /api/chat"""
    message: str = Field(..., description="User message to the chatbot")
    context: Optional[dict] = Field(None, description="Current plan context for the LLM")


class MultiStop(BaseModel):
    """A single stop in a multi-stop trip."""
    destination: str = Field(..., example="STARBUCKS_T4", description="Destination node ID")
    stay_minutes: float = Field(15.0, ge=1, le=120, description="Minutes to spend at this stop")


class MultiPlanRequest(BaseModel):
    """Request body for /api/plan-multi"""
    gate: str = Field(..., example="GATE_B1", description="Departure gate ID")
    terminal: int = Field(..., example=4, description="Terminal number")
    stops: List[MultiStop] = Field(..., description="Ordered list of stops to visit")
    walking_speed: float = Field(1.4, ge=0.5, le=2.5, description="Passenger walking speed m/s")
    itinerary_minutes: float = Field(120.0, ge=10, le=720, description="Total layover time from itinerary")
    delay_prob: Optional[float] = Field(None, ge=0, le=1)
    uncertainty: Optional[float] = Field(None, ge=0, le=1)
    buffer_minutes: Optional[float] = Field(None)
    airline: Optional[str] = Field(None, description="Airline IATA code (e.g. 'DL', 'B6')")
    experience: Optional[str] = Field("normal", description="User layover experience level (beginner, normal, experienced)")


# ── Response Models ────────────────────────────────────────────────

class PlannerResult(BaseModel):
    feasible: bool
    required_minutes: float


class ConstraintsResult(BaseModel):
    safe: bool
    violated: List[str]


class SimulationResult(BaseModel):
    total_minutes: Optional[float] = None
    walk_minutes: Optional[float] = None
    stay_minutes: Optional[float] = None
    error: Optional[str] = None


class PlanResponse(BaseModel):
    decision: str  # GO / MAYBE / NO
    risk_level: str  # low / medium / high
    buffer_minutes: float
    itinerary_minutes: float
    usable_time: float
    suggested_action: str
    reason: str
    explanation: str
    context: str
    guardian: str
    planner: PlannerResult
    simulation: SimulationResult
    constraints: ConstraintsResult


class LayoutNode(BaseModel):
    node_id: str
    type: str
    terminal: int
    x: float
    y: float


class ChatResponse(BaseModel):
    reply: str
    decision: Optional[str] = None
    plan_result: Optional[dict] = None


class LegResult(BaseModel):
    """Breakdown for a single leg of a multi-stop trip."""
    from_node: str
    to_node: str
    walk_minutes: float
    stay_minutes: float  # 0 for the final return leg


class MultiPlanResponse(BaseModel):
    """Response for /api/plan-multi"""
    decision: str              # GO / MAYBE / NO
    risk_level: str
    usable_time: float
    total_required: float      # sum of all legs
    buffer_minutes: float
    itinerary_minutes: float
    suggested_action: str
    reason: str
    explanation: str
    legs: List[LegResult]      # per-leg breakdown
