"""
Artificial Potential Fields (APF) Algorithm.

Each drone experiences attractive forces towards a target and repulsive forces
from other drones (which act as dynamic obstacles) and the ground.

References
----------
Khatib, O. (1986). Real-time obstacle avoidance for manipulators and mobile robots.
*The international journal of robotics research*, 5(1), 90-98.
"""

from __future__ import annotations

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class APFAlgorithm(BaseAlgorithm):
    """Artificial Potential Fields for collision-free target navigation.

    Parameters
    ----------
    num_drones : int
        Number of drones in the swarm.
    k_att : float
        Attractive force gain (pulls towards target).
    k_rep : float
        Repulsive force gain (pushes away from obstacles/drones).
    d0 : float
        Influence distance (m) for repulsion. Obstacles further than this are ignored.
    target : tuple[float, float, float]
        The 3D global target coordinate that all drones want to reach.
    max_speed : float
        Maximum output velocity (m/s).
    """

    def __init__(
        self,
        num_drones: int = 10,
        k_att: float = 0.5,
        k_rep: float = 2.0,
        d0: float = 0.8,
        target: tuple[float, float, float] = (0.0, 0.0, 1.0),
        max_speed: float = 1.0,
    ):
        self.num_drones = num_drones
        self.k_att = k_att
        self.k_rep = k_rep
        self.d0 = d0
        self.target = np.array(target)
        self.max_speed = max_speed
        super().__init__(num_drones=num_drones)

    def compute(
        self,
        state: SwarmState,
    ) -> np.ndarray:
        """Compute the net force (desired velocity) for every drone.

        Parameters
        ----------
        state : SwarmState
            The current state of the swarm.

        Returns
        -------
        np.ndarray
            ``(N, 3)`` target velocity vectors.
        """
        positions = state.positions
        N = positions.shape[0]
        targets = np.zeros((N, 3))

        for i in range(N):
            pos = positions[i]
            
            # Attractive force towards the goal
            diff_goal = self.target - pos
            dist_goal = max(np.linalg.norm(diff_goal), 1e-6)
            
            # Conic/Quadratic potential hybrid: scale linearly when far, quadratically when close
            if dist_goal > self.d0:
                f_att = self.k_att * self.d0 * (diff_goal / dist_goal)
            else:
                f_att = self.k_att * diff_goal

            # Repulsive forces from other drones
            f_rep = np.zeros(3)
            for j in range(N):
                if i == j:
                    continue
                diff_obs = pos - positions[j]
                dist_obs = np.linalg.norm(diff_obs)

                if dist_obs < self.d0 and dist_obs > 1e-6:
                    # Magnitude: k_rep * (1/d - 1/d0) * (1/d^2)
                    mag = self.k_rep * (1.0 / dist_obs - 1.0 / self.d0) * (1.0 / (dist_obs ** 2))
                    f_rep += mag * (diff_obs / dist_obs)
            
            # Repulsion from the floor (z = 0)
            floor_dist = pos[2]
            if floor_dist < self.d0 and floor_dist > 1e-6:
                mag_floor = self.k_rep * (1.0 / floor_dist - 1.0 / self.d0) * (1.0 / (floor_dist ** 2))
                f_rep += mag_floor * np.array([0, 0, 1.0])

            # Total force acts as desired velocity
            f_total = f_att + f_rep

            # Clamp to max speed
            speed = np.linalg.norm(f_total)
            if speed > self.max_speed:
                f_total = (f_total / speed) * self.max_speed

            targets[i] = f_total

        return targets
