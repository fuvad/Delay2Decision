"""
go_no_go.py — Deterministic Go / No-Go Decision Engine
========================================================
Pure logic layer (NOT ML). Converts ML outputs into a human decision.

Inputs:
  - required_minutes  : from Indoor Planner (walk + stay + walk back)
  - buffer_minutes    : from Buffer Calculator (ML-predicted safe time)
  - uncertainty       : from Uncertainty Estimator (0–1)
  - risk              : from Risk Engine (0–1, delay probability)

Pipeline:
  Delay Model → Buffer Calculator → Indoor Planner → **Go / No-Go** → Decision
"""

SAFETY_MARGIN = 5  # minutes of extra protection


def decide_action(
    required_minutes,
    usable_time,
    uncertainty,
    risk,
):
    """
    Make a GO / MAYBE / NO decision.

    Steps:
        1. Shrink buffer by uncertainty   →  trust only what's reliable
        2. Shrink further by risk penalty  →  high risk = less buffer
        3. Compare required time against effective buffer

    Returns
    -------
    dict with keys:
        - decision          : "GO" | "MAYBE" | "NO"
        - effective_buffer  : float — buffer after adjustments
        - required_minutes  : float — time needed for the trip
        - margin            : float — how many spare minutes (can be negative)
        - reason            : str   — human-readable explanation
    """
    # 1. Adjust buffer for uncertainty
    effective_buffer = usable_time * (1 - uncertainty)

    # 2. Penalize for high delay risk
    risk_penalty = risk * 0.3
    effective_buffer = effective_buffer * (1 - risk_penalty)

    # 3. Handle Special Cases (No Path Found)
    if required_minutes < 0:
        return {
            "decision": "NO",
            "effective_buffer": round(effective_buffer, 1),
            "required_minutes": 0.0,
            "margin": 0.0,
            "reason": "Destination is in a different terminal. Walking between terminals is not supported.",
            "cross_terminal_error": True,
        }

    # 4. Standard Decision
    margin = effective_buffer - required_minutes

    if margin >= SAFETY_MARGIN:
        decision = "GO"
        reason = (
            f"Safe to go. {margin:.0f} min margin after adjustments "
            f"(buffer {effective_buffer:.0f} min, need {required_minutes:.0f} min)."
        )

    elif margin >= 0:
        decision = "MAYBE"
        reason = (
            f"Tight. Only {margin:.0f} min margin — no safety cushion. "
            f"Proceed with caution."
        )

    else:
        decision = "NO"
        reason = (
            f"Not safe. You need {required_minutes:.0f} min but only have "
            f"{effective_buffer:.0f} min effective buffer. "
            f"Short by {abs(margin):.0f} min."
        )

    return {
        "decision": decision,
        "effective_buffer": round(effective_buffer, 1),
        "required_minutes": round(required_minutes, 1),
        "margin": round(margin, 1),
        "reason": reason,
    }


# ── Example usage ──────────────────────────────────────────────────────
if __name__ == "__main__":
    result = decide_action(
        required_minutes=27,
        usable_time=40,
        uncertainty=0.15,
        risk=0.435,
    )

    print(f"Decision: {result['decision']}")
    print(f"Effective buffer: {result['effective_buffer']} min")
    print(f"Required: {result['required_minutes']} min")
    print(f"Margin: {result['margin']} min")
    print(f"Reason: {result['reason']}")
