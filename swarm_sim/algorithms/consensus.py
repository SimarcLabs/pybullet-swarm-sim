"""
Distributed Consensus Algorithm — rendezvous and average-consensus.

Each drone moves toward the weighted average of its neighbours' positions.
Under a connected communication graph, this guarantees convergence to a
common meeting point (rendezvous) or to a dispersed configuration (coverage).

References
----------
Olfati-Saber, R., & Murray, R. M. (2004). Consensus problems in networks of
agents with switching topology and time-delays. *IEEE TAC*, 49(9), 1520–1533.

Example
-------
>>> from swarm_sim.algorithms.consensus import ConsensusAlgorithm
>>> consensus = ConsensusAlgorithm(num_drones=6, gain=0.5)
>>> vel_targets = consensus.compute(positions, adjacency_matrix)
"""

from __future__ import annotations

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class ConsensusAlgorithm(BaseAlgorithm):
    """Linear consensus protocol for multi-drone rendezvous.

    Parameters
    ----------
    num_drones : int
        Number of drones.
    gain : float
        Consensus gain (higher → faster convergence, but may overshoot).
    mode : str
        ``"rendezvous"`` — drones converge to a single point.
        ``"coverage"`` — drones spread to maximise inter-drone distance.
    """

    MODES = ("rendezvous", "coverage")

    def __init__(
        self,
        num_drones: int = 6,
        gain: float = 0.5,
        mode: str = "rendezvous",
    ):
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}, got '{mode}'")
        self.num_drones = num_drones
        self.gain = gain
        self.mode = mode
        super().__init__(num_drones=num_drones)

    def compute(
        self,
        state: SwarmState,
    ) -> np.ndarray:
        """Compute velocity targets via the consensus protocol.

        Parameters
        ----------
        state : SwarmState
            The current state of the swarm. Expects 'neighbor_graph' for adjacency.

        Returns
        -------
        np.ndarray
            ``(N, 3)`` velocity targets.
        """
        positions = state.positions
        adjacency = state.neighbor_graph
        N = positions.shape[0]
        vel = np.zeros((N, 3))

        for i in range(N):
            for j in range(N):
                if i == j or adjacency[i, j] == 0:
                    continue
                if self.mode == "rendezvous":
                    vel[i] += self.gain * (positions[j] - positions[i])
                else:  # coverage
                    diff = positions[i] - positions[j]
                    dist = np.linalg.norm(diff)
                    if dist > 1e-6:
                        vel[i] += self.gain * diff / (dist * dist)

        return vel
