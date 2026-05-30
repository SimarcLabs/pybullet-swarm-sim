"""
Ant Colony Optimization (ACO) — heuristic path planner for drone swarms.

Implements ACO for cooperative waypoint planning.  Drones collectively build
a pheromone map over a discretised grid; each drone picks its next waypoint
probabilistically based on pheromone intensity and a heuristic (e.g. inverse
distance to goal).

References
----------
Dorigo, M., & Stützle, T. (2004). *Ant Colony Optimization*. MIT Press.

Example
-------
>>> from swarm_sim.algorithms.aco import ACOPathPlanner
>>> aco = ACOPathPlanner(grid_size=20, num_drones=6)
>>> next_waypoints = aco.compute(positions, goal=np.array([5, 5, 1]))
"""

from __future__ import annotations

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class ACOPathPlanner(BaseAlgorithm):
    """Ant Colony Optimization for cooperative drone path planning.

    The search space is discretised into a 3-D grid.  Each cell holds a
    pheromone value that evaporates over time and is reinforced by drones
    passing through.  Each drone picks its next cell using the standard
    ACO transition probability.

    Parameters
    ----------
    grid_size : int
        Number of cells per axis (total cells = grid_size³).
    bounds_lo : list[float]
        Lower corner of the search volume ``[x, y, z]``.
    bounds_hi : list[float]
        Upper corner of the search volume ``[x, y, z]``.
    num_drones : int
        Number of drones.
    alpha : float
        Pheromone importance exponent.
    beta : float
        Heuristic (inverse distance) importance exponent.
    rho : float
        Pheromone evaporation rate (0–1).  Higher = faster evaporation.
    q : float
        Pheromone deposit amount per visit.
    """

    def __init__(
        self,
        grid_size: int = 20,
        bounds_lo: list[float] | None = None,
        bounds_hi: list[float] | None = None,
        num_drones: int = 6,
        alpha: float = 1.0,
        beta: float = 2.0,
        rho: float = 0.1,
        q: float = 1.0,
    ):
        self.grid_size = grid_size
        self.bounds_lo = np.array(bounds_lo or [-5.0, -5.0, 0.5])
        self.bounds_hi = np.array(bounds_hi or [5.0, 5.0, 3.0])
        self.num_drones = num_drones
        self.alpha = alpha
        self.beta = beta
        self.beta = beta
        self.rho = rho
        self.q = q
        super().__init__(num_drones=num_drones)

        # Initialise uniform pheromone field
        self.pheromone = np.ones((grid_size, grid_size, grid_size)) * 0.1
        self._cell_size = (self.bounds_hi - self.bounds_lo) / self.grid_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        state: SwarmState,
    ) -> np.ndarray:
        """Run one ACO step: evaporate, deposit, choose next waypoint.

        Parameters
        ----------
        state : SwarmState
            The current state of the swarm. Goal is taken from state.targets[0].

        Returns
        -------
        np.ndarray
            ``(N, 3)`` next waypoint for each drone (world coordinates).
        """
        positions = state.positions
        if state.targets is not None and len(state.targets) > 0:
            goal = state.targets[0]
        else:
            goal = np.array([0.0, 0.0, 0.0])
            
        N = positions.shape[0]

        # --- Phase 1: Evaporate pheromone ---
        self.pheromone *= (1 - self.rho)
        self.pheromone = np.clip(self.pheromone, 0.01, 100.0)

        # --- Phase 2: Deposit pheromone at current cells ---
        for i in range(N):
            cell = self._pos_to_cell(positions[i])
            if cell is not None:
                self.pheromone[cell] += self.q

        # --- Phase 3: Pick next waypoint for each drone ---
        waypoints = np.zeros((N, 3))
        for i in range(N):
            waypoints[i] = self._choose_next(positions[i], goal)

        return waypoints

    def reset(self):
        """Reset pheromone field to uniform."""
        self.pheromone[:] = 0.1

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pos_to_cell(self, pos: np.ndarray) -> tuple | None:
        """Map world XYZ → grid index ``(ix, iy, iz)``."""
        idx = ((pos - self.bounds_lo) / self._cell_size).astype(int)
        idx = np.clip(idx, 0, self.grid_size - 1)
        return tuple(idx)

    def _cell_to_pos(self, cell: tuple) -> np.ndarray:
        """Map grid index → world XYZ (cell centre)."""
        return self.bounds_lo + (np.array(cell) + 0.5) * self._cell_size

    def _choose_next(self, pos: np.ndarray, goal: np.ndarray) -> np.ndarray:
        """ACO transition rule: pick the next cell probabilistically."""
        current = self._pos_to_cell(pos)
        neighbours = self._get_neighbours(current)

        if len(neighbours) == 0:
            return pos  # stay put if somehow stuck at boundary

        probs = np.zeros(len(neighbours))
        for k, nb in enumerate(neighbours):
            tau = self.pheromone[nb] ** self.alpha
            nb_pos = self._cell_to_pos(nb)
            dist_to_goal = np.linalg.norm(nb_pos - goal)
            eta = (1.0 / (dist_to_goal + 1e-6)) ** self.beta
            probs[k] = tau * eta

        total = probs.sum()
        if total < 1e-12:
            probs = np.ones(len(neighbours)) / len(neighbours)
        else:
            probs /= total

        chosen_idx = np.random.choice(len(neighbours), p=probs)
        return self._cell_to_pos(neighbours[chosen_idx])

    def _get_neighbours(self, cell: tuple) -> list[tuple]:
        """Return the 26-connected neighbourhood of a grid cell."""
        neighbours = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    nx = cell[0] + dx
                    ny = cell[1] + dy
                    nz = cell[2] + dz
                    if (
                        0 <= nx < self.grid_size
                        and 0 <= ny < self.grid_size
                        and 0 <= nz < self.grid_size
                    ):
                        neighbours.append((nx, ny, nz))
        return neighbours
