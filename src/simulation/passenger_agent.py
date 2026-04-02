"""
passenger_agent.py — Simulated Passenger Agent
================================================
Represents a person moving inside the airport.
Tracks position, walking time, stay time, path history, and event log.
"""


class PassengerAgent:

    def __init__(self, start_gate, walking_speed=1.4):
        self.position = start_gate
        self.walking_speed = walking_speed
        self.total_time = 0  # seconds

        # detailed tracking
        self.walk_time = 0
        self.stay_time = 0
        self.path_history = []
        self.events = []

    def walk(self, from_node, to_node, distance):
        """Walk from one node to another. Returns time taken in seconds."""
        time = distance / self.walking_speed

        self.walk_time += time
        self.total_time += time
        self.position = to_node

        self.path_history.append((from_node, to_node))

        self.events.append({
            "event": "walk",
            "from": from_node,
            "to": to_node,
            "distance": round(distance, 2),
            "time_seconds": round(time, 2),
        })

        return time

    def stay(self, location, minutes):
        """Stay at current location for given minutes. Returns seconds."""
        seconds = minutes * 60

        self.stay_time += seconds
        self.total_time += seconds

        self.events.append({
            "event": "stay",
            "location": location,
            "time_seconds": seconds,
        })

        return seconds
