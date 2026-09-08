"""
Particle Swarm Optimization (PSO) — heuristic swarm search.

Implements the canonical PSO algorithm adapted for multi-drone swarm path
planning and target search.  Each drone acts as a *particle* that
maintains a personal best and tracks a global best, producing velocity
targets that the PID agent can track.

References
----------
Kennedy, J., & Eberhart, R. (1995). Particle swarm optimization.
*ICNN '95*, 4, 1942–1948.

Example
-------
>>> from swarm_sim.algorithms.pso import PSOAlgorithm
>>> pso = PSOAlgorithm(num_drones=10, bounds_lo=[-5,-5,0.5], bounds_hi=[5,5,3])
>>> state.sensor_readings["fitness"] = fitness_values
>>> vel_targets = pso.compute(state)
"""

from __future__ import annotations

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class PSOAlgorithm(BaseAlgorithm):
    """Particle Swarm Optimization for drone swarm search / exploration.

    Parameters
    ----------
    num_drones : int
        Number of particles (drones).
    bounds_lo : list[float]
        Lower bounds ``[x_min, y_min, z_min]`` for the search space.
    bounds_hi : list[float]
        Upper bounds ``[x_max, y_max, z_max]`` for the search space.
    w : float
        Inertia weight — controls how much of the previous velocity is kept.
    c1 : float
        Cognitive coefficient — attraction toward personal best.
    c2 : float
        Social coefficient — attraction toward global best.
    max_speed : float
        Maximum velocity magnitude (m/s).
    """

    def __init__(
        self,
        num_drones: int = 10,
        bounds_lo: list[float] | None = None,
        bounds_hi: list[float] | None = None,
        w: float = 0.7,
        c1: float = 1.5,
        c2: float = 1.5,
        max_speed: float = 1.0,
    ):
        self.num_drones = num_drones
        self.bounds_lo = np.array(bounds_lo or [-5, -5, 0.5])
        self.bounds_hi = np.array(bounds_hi or [5, 5, 3.0])
        self.w = w
        self.c1 = c1
        self.c2 = c2
        self.max_speed = max_speed
        super().__init__(num_drones=num_drones)

        # PSO state
        self._pbest_pos = None  # (N, 3)  personal best positions
        self._pbest_val = None  # (N,)    personal best fitness
        self._gbest_pos = None  # (3,)    global best position
        self._gbest_val = -np.inf
        self._prev_vel = None   # (N, 3)  velocity from last step

    def reset(self, positions: np.ndarray):
        """Initialize PSO state from current drone positions.

        Parameters
        ----------
        positions : np.ndarray
            ``(N, 3)`` initial drone positions.
        """
        N = positions.shape[0]
        self._pbest_pos = positions.copy()
        self._pbest_val = np.full(N, -np.inf)
        self._gbest_pos = positions[0].copy()
        self._gbest_val = -np.inf
        self._prev_vel = np.zeros((N, 3))

    def compute(
        self,
        state: SwarmState,
    ) -> np.ndarray:
        """Run one PSO update step and return velocity targets.

        Parameters
        ----------
        state : SwarmState
            The current state of the swarm. Expects 'fitness' in state.sensor_readings.

        Returns
        -------
        np.ndarray
            ``(N, 3)`` velocity targets for the next control step.
        """
        positions = state.positions
        velocities = state.velocities
        fitness = state.sensor_readings.get('fitness', np.zeros(positions.shape[0]))

        if self._pbest_pos is None:
            self.reset(positions)

        N = positions.shape[0]

        # Update personal and global bests
        for i in range(N):
            if fitness[i] > self._pbest_val[i]:
                self._pbest_val[i] = fitness[i]
                self._pbest_pos[i] = positions[i].copy()
            if fitness[i] > self._gbest_val:
                self._gbest_val = fitness[i]
                self._gbest_pos = positions[i].copy()

        # PSO velocity update
        r1 = np.random.random((N, 3))
        r2 = np.random.random((N, 3))

        cognitive = self.c1 * r1 * (self._pbest_pos - positions)
        social = self.c2 * r2 * (self._gbest_pos - positions)
        new_vel = self.w * self._prev_vel + cognitive + social

        # Clamp speed
        speeds = np.linalg.norm(new_vel, axis=1, keepdims=True)
        safe_speeds = np.maximum(speeds, 1e-10)  # avoid divide-by-zero
        mask = speeds > self.max_speed
        if np.any(mask):
            new_vel = np.where(mask, new_vel / safe_speeds * self.max_speed, new_vel)

        self._prev_vel = new_vel
        return new_vel

    @property
    def global_best_position(self) -> np.ndarray:
        """The best position found so far across the entire swarm."""
        return self._gbest_pos.copy()

    @property
    def global_best_fitness(self) -> float:
        """The best fitness value found so far."""
        return float(self._gbest_val)
