"""Core abstractions for Swarm Intelligence benchmarking framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

import numpy as np


@dataclass
class SwarmState:
    """Unified, simulation-independent state abstraction for all algorithms.
    
    This acts as the single source of truth passed to algorithms, telemetry,
    and emergence evaluators.
    """
    
    # Kinematic State
    positions: np.ndarray          # (N, 3)
    velocities: np.ndarray         # (N, 3)
    orientations: np.ndarray       # (N, 3) euler angles (roll, pitch, yaw)
    angular_velocities: np.ndarray # (N, 3)
    
    # Relational & Graph State
    neighbor_graph: np.ndarray     # (N, N) boolean adjacency matrix (in sensing range)
    communication_graph: Optional[np.ndarray] = None # (N, N) connectivity matrix
    
    # Internal Status
    active_drones_mask: np.ndarray = field(default_factory=lambda: np.array([])) # (N,) boolean
    battery_levels: np.ndarray = field(default_factory=lambda: np.array([]))     # (N,) floats 0.0 to 1.0
    drone_status: list[str] = field(default_factory=list)                        # ['nominal', 'failed', 'recovering', ...]
    
    # Environment Perception
    sensor_readings: Dict[str, np.ndarray] = field(default_factory=dict)
    targets: Optional[np.ndarray] = None   # (M, 3)
    obstacles: Optional[np.ndarray] = None # (K, 3) or custom objects
    
    @property
    def num_drones(self) -> int:
        return self.positions.shape[0]

    def get_active_positions(self) -> np.ndarray:
        if len(self.active_drones_mask) == self.num_drones:
            return self.positions[self.active_drones_mask]
        return self.positions

    def get_active_velocities(self) -> np.ndarray:
        if len(self.active_drones_mask) == self.num_drones:
            return self.velocities[self.active_drones_mask]
        return self.velocities
