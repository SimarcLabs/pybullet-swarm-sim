"""
Abstract base class for per-drone agents.

Every agent receives the current drone state and a target, and returns
motor RPM commands.  Subclass this to create PID controllers, RL policies,
or heuristic strategies.

Example
-------
>>> class MyAgent(BaseAgent):
...     def compute_action(self, obs, target):
...         return np.zeros(4)  # do nothing
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class BaseAgent(ABC):
    """Interface that all per-drone agents must implement.

    Parameters
    ----------
    drone_id : int
        Index of the drone this agent controls (for multi-agent bookkeeping).
    """

    def __init__(self, drone_id: int = 0):
        self.drone_id = drone_id

    @abstractmethod
    def compute_action(
        self,
        obs: np.ndarray,
        target: np.ndarray,
        dt: float = 1 / 240,
    ) -> np.ndarray:
        """Compute motor RPM commands given current observation and target.

        Parameters
        ----------
        obs : np.ndarray
            ``(20,)`` drone state vector (pos, quat, rpy, vel, ang_vel, last_rpm).
        target : np.ndarray
            ``(3,)`` desired XYZ position.
        dt : float
            Control timestep in seconds.

        Returns
        -------
        np.ndarray
            ``(4,)`` RPM commands for motors [0..3].
        """
        ...

    def reset(self):
        """Reset any internal state (integrators, buffers, etc.)."""
        pass
