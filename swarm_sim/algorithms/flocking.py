"""
Reynolds Flocking (Boids) — separation, alignment, cohesion.

Classic decentralized swarm behaviour where each drone independently applies
three local rules based on its neighbours' positions and velocities.

References
----------
Reynolds, C. W. (1987). Flocks, herds, and schools: A distributed behavioral
model. *SIGGRAPH '87*, 25–34.

Example
-------
>>> from swarm_sim.algorithms.flocking import FlockingAlgorithm
>>> flock = FlockingAlgorithm(num_drones=10)
>>> velocity_targets = flock.compute(state)
"""

from __future__ import annotations

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class FlockingAlgorithm(BaseAlgorithm):
    """Reynolds boids flocking with configurable radii and weights.

    Parameters
    ----------
    num_drones : int
        Number of drones in the swarm.
    r_separation : float
        Radius (m) within which drones repel each other.
    r_alignment : float
        Radius (m) within which drones match velocity.
    r_cohesion : float
        Radius (m) within which drones move toward group centre.
    w_separation : float
        Weight for the separation rule.
    w_alignment : float
        Weight for the alignment rule.
    w_cohesion : float
        Weight for the cohesion rule.
    max_speed : float
        Maximum velocity magnitude (m/s).
    """

    def __init__(
        self,
        num_drones: int = 10,
        r_separation: float = 0.3,
        r_alignment: float = 1.0,
        r_cohesion: float = 1.5,
        w_separation: float = 2.0,
        w_alignment: float = 1.0,
        w_cohesion: float = 1.0,
        max_speed: float = 1.0,
    ):
        self.num_drones = num_drones
        self.r_sep = r_separation
        self.r_align = r_alignment
        self.r_coh = r_cohesion
        self.w_sep = w_separation
        self.w_align = w_alignment
        self.w_coh = w_cohesion
        self.max_speed = max_speed
        super().__init__(num_drones=num_drones)

    def compute(
        self,
        state: SwarmState,
    ) -> np.ndarray:
        """Compute desired velocity for every drone using boid rules.

        Parameters
        ----------
        state : SwarmState
            The current state of the swarm.

        Returns
        -------
        np.ndarray
            ``(N, 3)`` target velocity vectors (pass to PID as velocity setpoint).
        """
        positions = state.positions
        velocities = state.velocities
        N = positions.shape[0]
        targets = np.zeros((N, 3))

        for i in range(N):
            sep = np.zeros(3)
            align = np.zeros(3)
            coh = np.zeros(3)
            n_sep = n_align = n_coh = 0

            for j in range(N):
                if i == j:
                    continue
                diff = positions[i] - positions[j]
                dist = np.linalg.norm(diff)

                # Separation: steer away from very close neighbours
                if dist < self.r_sep and dist > 1e-6:
                    sep += diff / (dist * dist)  # inversely proportional
                    n_sep += 1

                # Alignment: match velocity of nearby neighbours
                if dist < self.r_align:
                    align += velocities[j]
                    n_align += 1

                # Cohesion: steer toward centre of mass of local group
                if dist < self.r_coh:
                    coh += positions[j]
                    n_coh += 1

            if n_sep > 0:
                sep /= n_sep
            if n_align > 0:
                align /= n_align
            if n_coh > 0:
                coh = (coh / n_coh) - positions[i]

            target = (
                self.w_sep * sep
                + self.w_align * align
                + self.w_coh * coh
            )

            # Clamp to max speed
            speed = np.linalg.norm(target)
            if speed > self.max_speed:
                target = target / speed * self.max_speed

            targets[i] = target

        return targets
