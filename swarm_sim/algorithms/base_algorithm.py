"""Base algorithm interface for Swarm Intelligence benchmarking framework."""

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from swarm_sim.core.state import SwarmState


class BaseAlgorithm(ABC):
    """Abstract base class for all swarm algorithms in the framework."""

    def __init__(self, num_drones: int):
        self.num_drones = num_drones

    @abstractmethod
    def compute(self, state: SwarmState) -> np.ndarray:
        """Compute the target velocity vectors for the swarm.

        Parameters
        ----------
        state : SwarmState
            The current state of the swarm (positions, velocities, etc.).

        Returns
        -------
        np.ndarray
            Shape (N, 3) target velocity vectors for the active drones.
        """
        pass
