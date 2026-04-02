"""
constraint_checker.py — Safety Constraint Satisfaction Layer
=============================================================
Hard safety rules that MUST be satisfied before any recommendation
is given to the passenger. If ANY constraint breaks → REJECTED.

Constraints:
  1. Gate reachability  — passenger must reach gate before boarding closes
  2. Security clearance — enough time to pass through security (if re-entering)
  3. Delay resilience   — enough spare margin to survive a short delay (>= 5 min)

No unsafe suggestions. Ever.

Pipeline:
  Go/No-Go Decision → **Constraint Checker** → Final Recommendation
"""

BOARDING_CLOSE_BEFORE_DEPARTURE = 30  # gates close 30 min before departure
SECURITY_CLEARANCE_MINUTES = 20       # minimum time to clear security
SAFETY_MARGIN = 5                     # spare minutes required for delay resilience


def check_constraints(
    required_minutes,
    usable_time,
    needs_security=False,
    boarding_close_minutes=BOARDING_CLOSE_BEFORE_DEPARTURE,
    effective_buffer=None,
):
    """
    Validate all hard safety constraints.

    Parameters
    ----------
    required_minutes    : float — total trip time (walk + stay + walk back)
    usable_time         : float — base itinerary layover time minus AI safety penalty
    needs_security      : bool  — does the passenger need to re-enter security?
                                  (True for outdoor trips, False for indoor)
    boarding_close_minutes : float — how many min before departure the gate closes

    Returns
    -------
    dict with keys:
        - safe          : bool  — True only if ALL constraints pass
        - constraints   : list  — individual constraint results
        - violated      : list  — names of broken constraints (empty if safe)
        - reason        : str   — human-readable summary
    """
    constraints = []
    violated = []

    # ── Constraint 1: Gate reachability ─────────────────────────────────
    # Compare against effective_buffer (the risk-adjusted window shown as "Usable Min").
    # This ensures the constraint tick is consistent with the number the user sees.
    gate_check_val = effective_buffer if effective_buffer is not None else usable_time
    gate_ok = required_minutes <= gate_check_val

    constraints.append({
        "name": "gate_reachability",
        "passed": gate_ok,
        "detail": (
            f"Need {required_minutes:.0f} min, "
            f"have {gate_check_val:.0f} min available."
        ),
    })
    if not gate_ok:
        violated.append("Gate Reachability")

    # ── Constraint 2: Security clearance ───────────────────────────────
    if needs_security:
        time_after_trip = boarding_buffer - required_minutes
        security_ok = time_after_trip >= SECURITY_CLEARANCE_MINUTES

        constraints.append({
            "name": "security_clearance",
            "passed": security_ok,
            "detail": (
                f"{time_after_trip:.0f} min left after trip for security "
                f"(need {SECURITY_CLEARANCE_MINUTES} min)."
            ),
        })
        if not security_ok:
            violated.append("Security Clearance")
    else:
        constraints.append({
            "name": "security_clearance",
            "passed": True,
            "detail": "No security re-entry needed (indoor trip).",
        })

    # ── Constraint 3: Delay Resilience ────────────────────────────────────
    # Is there enough spare margin (≥ SAFETY_MARGIN) to absorb a short delay?
    # Green = comfortable GO cushion. Red = trip is too tight (MAYBE or NO).
    eff = effective_buffer if effective_buffer is not None else usable_time
    margin = eff - required_minutes
    resilience_ok = margin >= SAFETY_MARGIN

    constraints.append({
        "name": "delay_resilience",
        "passed": resilience_ok,
        "detail": (
            f"{margin:.0f} min spare after trip "
            f"(need {SAFETY_MARGIN} min safety cushion)."
        ),
    })
    if not resilience_ok:
        violated.append("Delay Resilience")


    # ── Final verdict ──────────────────────────────────────────────────
    safe = len(violated) == 0

    if safe:
        reason = "All safety constraints satisfied."
    else:
        reason = (
            f"REJECTED — {len(violated)} constraint(s) violated: "
            f"{', '.join(violated)}. Recommendation is unsafe."
        )

    return {
        "safe": safe,
        "constraints": constraints,
        "violated": violated,
        "reason": reason,
    }


# ── Example usage ──────────────────────────────────────────────────────
if __name__ == "__main__":
    # Safe indoor trip
    print("=== Safe indoor trip ===")
    result = check_constraints(
        required_minutes=27,
        usable_time=50,
        needs_security=False,
    )
    print(f"Safe: {result['safe']}")
    print(f"Reason: {result['reason']}")
    for c in result["constraints"]:
        status = "✓" if c["passed"] else "✗"
        print(f"  {status} {c['name']}: {c['detail']}")
    print()

    # Unsafe outdoor trip — not enough time for security
    print("=== Unsafe outdoor trip ===")
    result = check_constraints(
        required_minutes=40,
        usable_time=50,
        needs_security=True,
    )
    print(f"Safe: {result['safe']}")
    print(f"Reason: {result['reason']}")
    for c in result["constraints"]:
        status = "✓" if c["passed"] else "✗"
        print(f"  {status} {c['name']}: {c['detail']}")
