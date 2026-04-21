"""Predefined pickup, drop-off, and home waypoints for XOPS city."""

from typing import Dict, List

PICKUP_POINTS: Dict[str, Dict[str, float]] = {
    "pickup_alpha": {"x": -8.0, "y": 6.0, "z": 0.35},
    "pickup_bravo": {"x": 10.0, "y": 8.0, "z": 0.35},
    "pickup_charlie": {"x": -6.5, "y": -9.5, "z": 0.35},
    "pickup_golf": {"x": 7.0, "y": -13.0, "z": 0.35},
    "pickup_hotel": {"x": -12.0, "y": 12.0, "z": 0.35},
}

DROPOFF_POINTS: Dict[str, Dict[str, float]] = {
    "drop_delta": {"x": 14.5, "y": -7.5, "z": 0.35},
    "drop_echo": {"x": -14.0, "y": -5.5, "z": 0.35},
    "drop_foxtrot": {"x": 4.0, "y": 15.0, "z": 0.35},
    "drop_india": {"x": 16.0, "y": 5.0, "z": 0.35},
    "drop_juliet": {"x": -4.0, "y": -16.0, "z": 0.35},
}

HOME_POINTS: Dict[str, Dict[str, float]] = {
    "Drone1": {"x": 0.0, "y": 0.0, "z": 0.15},
    "Drone2": {"x": 2.6, "y": -1.7, "z": 0.15},
    "Drone3": {"x": -2.6, "y": 1.7, "z": 0.15},
    "Drone4": {"x": -2.6, "y": -1.7, "z": 0.15},
}


def list_location_options() -> Dict[str, List[Dict[str, object]]]:
    return {
        "pickup": [
            {"id": location_id, "label": location_id.replace("_", " ").title(), "position": position}
            for location_id, position in PICKUP_POINTS.items()
        ],
        "dropoff": [
            {"id": location_id, "label": location_id.replace("_", " ").title(), "position": position}
            for location_id, position in DROPOFF_POINTS.items()
        ],
    }


def resolve_location(location_id: str, location_type: str) -> Dict[str, float]:
    table = PICKUP_POINTS if location_type == "pickup" else DROPOFF_POINTS
    if location_id not in table:
        raise KeyError(f"Unknown {location_type} location: {location_id}")
    return dict(table[location_id])
