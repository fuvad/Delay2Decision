"""
outdoor_planner.py — Outdoor Feasibility Planner
==================================================
Simple time-based check: can the passenger leave the airport
and return safely within the available layover / buffer time?

No graph needed — just accounts for:
  - Security re-entry time (buffer to get back through security)
  - Minimum time needed outside to make the trip worthwhile

Pipeline:  Delay Model → Buffer Calculator → Outdoor Planner → Go / No-Go
"""

# ── Configurable thresholds (minutes) ─────────────────────────────────
SECURITY_REENTRY_MINUTES = 45   # time to get back through security
MIN_USEFUL_OUTSIDE_MINUTES = 60 # minimum time outside to be worthwhile (1 hour)
BOARDING_BUFFER_MINUTES = 15    # be at gate this many minutes before departure


def can_go_outside(
    usable_time,
    departure_time_str=None,
):
    """
    Determine if a passenger has enough layover time to leave the airport.

    Parameters
    ----------
    usable_time : float
        Base itinerary layover time minus AI safety penalty.
    departure_time_str : str or None
        Departure time as "HH:MM" (24h format). If provided, computes
        the latest return-by time. Optional.

    Returns
    -------
    dict with keys:
        - feasible        : bool   — can the passenger go outside?
        - buffer_minutes  : float  — total buffer available
        - time_outside    : float  — usable minutes outside (0 if not feasible)
        - return_by       : str    — latest time to re-enter airport (if departure given)
        - reason          : str    — human-readable explanation
    """
    overhead = SECURITY_REENTRY_MINUTES + BOARDING_BUFFER_MINUTES
    time_outside = usable_time - overhead

    if time_outside < MIN_USEFUL_OUTSIDE_MINUTES:
        return {
            "feasible": False,
            "usable_time": round(usable_time, 1),
            "time_outside": 0,
            "return_by": None,
            "reason": (
                f"Not enough time. You have {usable_time:.0f} min usable time, "
                f"but {overhead} min is needed for security + boarding, "
                f"leaving only {max(time_outside, 0):.0f} min outside "
                f"(minimum {MIN_USEFUL_OUTSIDE_MINUTES} min required)."
            ),
        }

    # Compute return-by time if departure is provided
    return_by = None
    if departure_time_str:
        h, m = map(int, departure_time_str.split(":"))
        total_min = h * 60 + m
        return_min = total_min - overhead
        rh, rm = divmod(return_min, 60)
        return_by = f"{rh:02d}:{rm:02d}"

    return {
        "feasible": True,
        "usable_time": round(usable_time, 1),
        "time_outside": round(time_outside, 1),
        "return_by": return_by,
        "reason": (
            f"You have {time_outside:.0f} min outside the airport. "
            f"Return by {return_by} to clear security and reach your gate."
            if return_by
            else f"You have {time_outside:.0f} min outside the airport."
        ),
    }


# ── Example usage ──────────────────────────────────────────────────────
if __name__ == "__main__":
    # Scenario 1: plenty of time
    result = can_go_outside(usable_time=180, departure_time_str="18:30")
    print("=== Long layover ===")
    print(f"Can go outside? {result['feasible']}")
    print(f"Time outside:   {result['time_outside']} min")
    print(f"Return by:      {result['return_by']}")
    print(f"Reason:         {result['reason']}")
    print()

    # Scenario 2: tight layover
    result = can_go_outside(usable_time=70, departure_time_str="14:00")
    print("=== Tight layover ===")
    print(f"Can go outside? {result['feasible']}")
    print(f"Reason:         {result['reason']}")
