"""Base benchmark definition."""

from abc import ABC, abstractmethod
from typing import Any, Dict

import numpy as np

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.core.state import SwarmState


class BaseBenchmark(ABC):
    """Abstract base class for a benchmarking scenario."""

    def __init__(self, num_drones: int, duration: float, ctrl_freq: int = 48, gui: bool = False):
        self.num_drones = num_drones
        self.duration = duration
        self.ctrl_freq = ctrl_freq
        self.gui = gui
        
        self.env: BaseSwarmEnv = None
        self.metric_weights: Dict[str, float] = {}
        
    @abstractmethod
    def setup_environment(self) -> BaseSwarmEnv:
        """Create and configure the pybullet environment for this scenario."""
        pass
        
    def setup_faults(self):
        """Optionally schedule faults to occur during the scenario."""
        pass
        
    @abstractmethod
    def get_metric_weights(self) -> Dict[str, float]:
        """Return the weights for calculating the Swarm Health Score.
        
        Example: {'coverage': 0.8, 'cohesion': 0.2}
        """
        pass
        
    def get_state(self) -> SwarmState:
        """Extract the SwarmState from the current environment."""
        return SwarmState(
            positions=self.env.pos.copy(),
            velocities=self.env.vel.copy(),
            orientations=self.env.rpy.copy(),
            angular_velocities=self.env.ang_v.copy(),
            neighbor_graph=np.array([]), # To be computed by an evaluator
            communication_graph=np.array([]),
            active_drones_mask=np.arange(self.num_drones),
            battery_levels=np.ones(self.num_drones),
            drone_status=["nominal"] * self.num_drones
        )
