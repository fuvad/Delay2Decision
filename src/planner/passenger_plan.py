"""
passenger_plan.py -- Active Passenger Plan Object
===================================================
Stores the current active plan for a passenger.
Can be invalidated and updated when airport events occur.
"""


class PassengerPlan:

    def __init__(self, gate, destination, terminal):
        self.original_gate = gate
        self.current_gate = gate
        self.destination = destination
        self.terminal = terminal
        self.valid = True
        self.replan_count = 0

    def invalidate(self):
        """Mark the current plan as invalid (needs recomputation)."""
        self.valid = False

    def update_gate(self, new_gate):
        """Update the gate and increment replan counter."""
        self.current_gate = new_gate
        self.replan_count += 1

    def revalidate(self):
        """Mark the plan as valid again after replanning."""
        self.valid = True

    def __repr__(self):
        status = "VALID" if self.valid else "INVALID"
        return (
            f"PassengerPlan({self.current_gate} -> {self.destination}, "
            f"terminal={self.terminal}, status={status}, "
            f"replans={self.replan_count})"
        )
