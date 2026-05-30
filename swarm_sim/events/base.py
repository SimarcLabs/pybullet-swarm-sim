"""Event tracking system for the swarm intelligence framework."""

from dataclasses import dataclass
from typing import Any, Dict, List
import json
from pathlib import Path


@dataclass
class SwarmEvent:
    """Standardized event triggered during the simulation."""
    timestamp: float
    event_type: str
    payload: Dict[str, Any]


class EventLogger:
    """Manages the collection and serialization of swarm events."""
    
    def __init__(self):
        self.events: List[SwarmEvent] = []
        
    def log(self, timestamp: float, event_type: str, payload: Dict[str, Any]):
        """Record an event."""
        self.events.append(SwarmEvent(timestamp, event_type, payload))
        
    def save(self, output_dir: str):
        """Serialize events to events.json."""
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        event_dicts = [
            {"timestamp": e.timestamp, "type": e.event_type, "payload": e.payload}
            for e in self.events
        ]
        
        with open(path / "events.json", "w") as f:
            json.dump(event_dicts, f, indent=4)
