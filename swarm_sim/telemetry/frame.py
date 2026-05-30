"""Telemetry frame snapshot definition."""

from dataclasses import dataclass
from typing import Dict, Any, List

import numpy as np


@dataclass
class FrameSnapshot:
    """A snapshot of the entire simulation state at a specific timestamp.
    
    This is the single source of truth for replay, analysis, reporting,
    and visualization.
    """
    timestamp: float
    
    # Kinematics
    positions: np.ndarray          # (N, 3)
    velocities: np.ndarray         # (N, 3)
    orientations: np.ndarray       # (N, 3) euler angles
    angular_velocities: np.ndarray # (N, 3)
    
    # Graphs
    neighbor_graph: np.ndarray     # (N, N)
    communication_graph: np.ndarray# (N, N)
    
    # Environment
    targets: np.ndarray            # (M, 3)
    obstacles: np.ndarray          # (K, 3)
    
    # Status
    active_mask: np.ndarray        # (N,)
    battery_levels: np.ndarray     # (N,)
    drone_status: List[str]        # N items
    
    # Metrics computed live (if any)
    live_metrics: Dict[str, float]
