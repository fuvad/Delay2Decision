"""
alternative_planner.py — Alternative Recommendation Engine
=============================================================
If a passenger's requested destination is too risky, this module finds
a safe alternative.

It uses a 3-strategy approach:
  1. Alternative store (same category, same terminal) with original speed/stay.
  2. Original store with fast walking speed (2.0 m/s) and reduced stay (e.g. 5 mins).
  3. Alternative store with fast walking speed and reduced stay.
"""

from src.planner.indoor_graph import walking_time_seconds


def _can_visit_helper(gate: str, destination: str, usable_time: float, stay_minutes: float, walking_speed: float, layout_graph) -> tuple[bool, float]:
    """Helper to check if a trip is feasible and return the required minutes."""
    try:
        walk_secs = walking_time_seconds(layout_graph, gate, destination, walking_speed)
        walk_min = walk_secs / 60.0
        required_minutes = (walk_min * 2) + stay_minutes
        feasible = required_minutes <= usable_time
        return feasible, required_minutes
    except Exception:
        return False, float('inf')


def _categorize_destination(node_id: str) -> str:
    """
    Categorize a node ID into a general store type based on keywords.
    """
    node_id_lower = node_id.lower()
    
    if "starbucks" in node_id_lower or "dunkin" in node_id_lower:
        return "coffee"
    elif "mcdonald" in node_id_lower or "shake_shack" in node_id_lower:
        return "food"
    elif "restroom" in node_id_lower:
        return "restroom"
    else:
        return "other"


def _get_alternative_candidates(original_dest: str, terminal: int, category: str, layout_graph) -> list[str]:
    """
    Return all valid nodes in the same terminal and category,
    excluding the original destination.
    """
    candidates = []
    # layout_graph.nodes is a dictionary view where keys are node IDs and values are dictionaries of attributes
    for node, data in layout_graph.nodes(data=True):
        # Skip if not the right terminal
        if data.get("terminal") != terminal:
            continue
            
        # Skip the original destination
        if node == original_dest:
            continue
            
        # Match category
        cand_category = _categorize_destination(node)
        if cand_category == category:
            candidates.append(node)
            
    return candidates


def find_alternative(
    gate: str,
    destination: str,
    terminal: int,
    usable_time: float,
    original_stay: float,
    original_speed: float,
    layout_graph
) -> dict | None:
    """
    Attempt to find a safe way to fulfill the passenger's intent using 3 strategies.
    
    Returns:
        dict: {
            "strategy": 1|2|3,
            "destination": str,
            "stay_minutes": float,
            "walking_speed": float,
            "required_minutes": float,
            "message": str
        }
    """
    category = _categorize_destination(destination)
    if category == "other":
        # Hard to find an alternative if we don't know what it is
        return None
        
    candidates = _get_alternative_candidates(destination, terminal, category, layout_graph)
    
    # Fast parameters for Strategies 2 and 3
    # walking quickly is out of the equation now
    pass
    
    
    # ── Strategy 1: Alternative Store, Original Parameters ──
    best_cand = None
    best_req = float('inf')
    
    for cand in candidates:
        feasible, req_min = _can_visit_helper(gate, cand, usable_time, original_stay, original_speed, layout_graph)
        if feasible and req_min < best_req:
            best_req = req_min
            best_cand = cand
            
    if best_cand:
        name_clean = best_cand.split("_")[0].replace("_", " ").title()
        orig_clean = destination.split("_")[0].replace("_", " ").title()
        msg = (
            f"Going to {orig_clean} is too risky. However, there is a {name_clean} "
            f"in your terminal that fits your schedule perfectly. Would you like to go there instead?"
        )
        return {
            "strategy": 1,
            "destination": best_cand,
            "stay_minutes": original_stay,
            "walking_speed": original_speed,
            "required_minutes": best_req,
            "message": msg
        }
        
        
    # ── Strategy 2: Original Store, Adjusted Parameters ──
    # Calculate maximum feasible stay time with original speed ensuring 10 min spare
    try:
        walk_secs = walking_time_seconds(layout_graph, gate, destination, original_speed)
        walk_min = walk_secs / 60.0
        max_stay = int(usable_time - 10 - (walk_min * 2))
    except Exception:
        max_stay = -1
        
    if max_stay >= 5:
        reduced_stay = min(max_stay, int(original_stay))
        feasible, req_min = _can_visit_helper(gate, destination, usable_time, reduced_stay, original_speed, layout_graph)
        if feasible:
            orig_clean = destination.split("_")[0].replace("_", " ").title()
            if reduced_stay < original_stay:
                msg = (
                    f"Going to {orig_clean} at your current pace is too risky. However, if you "
                    f"reduce your stay to {reduced_stay} minutes, "
                    f"you can safely make it."
                )
            else:
                msg = (
                    f"Going to {orig_clean} at your current pace is too risky. However, if you "
                    f"keep your stay at {reduced_stay} minutes, "
                    f"you can safely make it."
                )
            return {
                "strategy": 2,
                "destination": destination,
                "stay_minutes": reduced_stay,
                "walking_speed": original_speed,
                "required_minutes": req_min,
                "message": msg
            }
        
    
    # ── Strategy 3: Alternative Store, Adjusted Parameters ──
    best_cand = None
    best_req = float('inf')
    best_stay = 0
    
    for cand in candidates:
        try:
            walk_secs = walking_time_seconds(layout_graph, gate, cand, original_speed)
            walk_min = walk_secs / 60.0
            max_cand_stay = int(usable_time - 10 - (walk_min * 2))
        except Exception:
            max_cand_stay = -1
            
        if max_cand_stay >= 5:
            cand_reduced_stay = min(max_cand_stay, int(original_stay))
            feasible, req_min = _can_visit_helper(gate, cand, usable_time, cand_reduced_stay, original_speed, layout_graph)
            if feasible and req_min < best_req:
                best_req = req_min
                best_cand = cand
                best_stay = cand_reduced_stay
            
    if best_cand:
        name_clean = best_cand.split("_")[0].replace("_", " ").title()
        orig_clean = destination.split("_")[0].replace("_", " ").title()
        
        if best_stay < original_stay:
            msg = (
                f"Going to {orig_clean} is too risky. However, if you go to a {name_clean} "
                f"in your terminal and stay for up to {best_stay} minutes, you can make it safely."
            )
        else:
            msg = (
                f"Going to {orig_clean} is too risky. However, if you go to a {name_clean} "
                f"in your terminal, you can still safely stay for {best_stay} minutes."
            )
            
        return {
            "strategy": 3,
            "destination": best_cand,
            "stay_minutes": best_stay,
            "walking_speed": original_speed,
            "required_minutes": best_req,
            "message": msg
        }
        
    # None of the strategies worked
    return None

def find_multi_stop_alternative(
    req_stops: list,
    usable_time: float,
    total_required: float,
    total_walk_time: float,
) -> dict | None:
    """
    If a multi-stop itinerary is too long, we try to evenly cut down the 
    stay times across all destinations to make it fit.
    """
    max_total_stay = int(usable_time - total_walk_time)
    num_stops = len(req_stops)
    
    # We require 10 minutes of spare time for a "GO" decision
    target_usable_time = usable_time - 10
    max_total_stay = int(target_usable_time - total_walk_time)
    num_stops = len(req_stops)
    
    # We require at least 5 minutes per stop to bother recommending it
    if max_total_stay >= num_stops * 5:
        # Calculate how much to cut in total
        total_requested_stay = sum(s.stay_minutes for s in req_stops)
        deficit = total_requested_stay - max_total_stay
        
        if deficit > 0:
            new_stays = [int(s.stay_minutes) for s in req_stops]
            
            # Greedily reduce the largest valid stay by 5 mins until deficit is covered
            while sum(req_stops[i].stay_minutes for i in range(num_stops)) - sum(new_stays) < deficit:
                # Find the stop with the largest current stay that is strictly > 5
                max_val = -1
                max_idx = -1
                for i, val in enumerate(new_stays):
                    if val > 5 and val > max_val:
                        max_val = val
                        max_idx = i
                        
                if max_idx == -1:
                    # Can't reduce any further without dropping something below 5
                    break
                    
                new_stays[max_idx] -= 5
            
            # Re-read actual new total
            actual_new_stay = sum(new_stays)
            if actual_new_stay <= max_total_stay:
                # We found a valid distribution that guarantees a GO
                changed_stops = []
                for i, s in enumerate(req_stops):
                    if new_stays[i] < s.stay_minutes:
                        name = s.destination.split('_')[0].replace('_', ' ').title()
                        orig_stay = int(s.stay_minutes)
                        changed_stops.append(f"staying time at {name} from {orig_stay} min to {new_stays[i]} min")
                
                stop_details = ", ".join(changed_stops)
                msg = (
                    f"Your trip at your current pace takes too long. However, if you "
                    f"reduce the {stop_details}, "
                    f"you can safely make it."
                )
                return {
                    "strategy": "multi-stop-even-cut",
                    "new_stays": new_stays,
                    "message": msg,
                }
    return None
