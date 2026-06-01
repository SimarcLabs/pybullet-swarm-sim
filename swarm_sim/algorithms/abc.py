"""
Artificial Bee Colony (ABC) Algorithm.

Simulates the foraging behavior of honey bees. Drones are divided into
Employed, Onlooker, and Scout bees to dynamically search an environment.

References
----------
Karaboga, D. (2005). An idea based on honey bee swarm for numerical optimization tasks.
"""

from __future__ import annotations

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class ABCAlgorithm(BaseAlgorithm):
    """Artificial Bee Colony for spatial search and optimization.

    Parameters
    ----------
    num_drones : int
        Number of drones in the swarm.
    target : tuple[float, float, float]
        The 3D global target coordinate that represents the 'food source'.
    max_speed : float
        Maximum output velocity (m/s).
    """

    def __init__(
        self,
        num_drones: int = 10,
        target: tuple[float, float, float] = (3.0, 3.0, 1.0),
        max_speed: float = 1.0,
    ):
        self.num_drones = num_drones
        self.target = np.array(target)
        self.max_speed = max_speed
        
        # State tracking for the algorithm
        self.roles = np.zeros(num_drones, dtype=int)  # 0: Employed, 1: Onlooker, 2: Scout
        self._assign_roles()
        
        self.personal_best_pos = None
        self.personal_best_fitness = np.full(num_drones, -np.inf)
        self.global_best_pos = np.zeros(3)
        self.global_best_fitness = -np.inf
        
        self.scout_targets = np.zeros((num_drones, 3))
        
        super().__init__(num_drones=num_drones)

    def _assign_roles(self):
        """Evenly divide drones into Employed, Onlooker, and Scout roles."""
        n_employed = max(1, self.num_drones // 3)
        n_onlooker = max(1, self.num_drones // 3)
        # The rest are scouts
        
        self.roles[:n_employed] = 0
        self.roles[n_employed:n_employed+n_onlooker] = 1
        self.roles[n_employed+n_onlooker:] = 2

    def _fitness(self, pos: np.ndarray) -> float:
        """Fitness function: Closer to target is better."""
        dist = np.linalg.norm(pos - self.target)
        # Avoid division by zero, return inverse distance
        return 1.0 / (dist + 1e-6)

    def compute(
        self,
        state: SwarmState,
    ) -> np.ndarray:
        """Compute the desired velocity for every drone based on its ABC role.

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
        
        if self.personal_best_pos is None:
            self.personal_best_pos = positions.copy()
            for i in range(N):
                # Pick a random scout target initially for scouts
                if self.roles[i] == 2:
                    self.scout_targets[i] = positions[i] + (np.random.rand(3) - 0.5) * 5.0
                    self.scout_targets[i][2] = max(0.5, self.scout_targets[i][2]) # Keep above ground

        # Update fitness and bests
        for i in range(N):
            fit = self._fitness(positions[i])
            if fit > self.personal_best_fitness[i]:
                self.personal_best_fitness[i] = fit
                self.personal_best_pos[i] = positions[i].copy()
                
            if fit > self.global_best_fitness:
                self.global_best_fitness = fit
                self.global_best_pos = positions[i].copy()

        # Compute velocities based on roles
        for i in range(N):
            role = self.roles[i]
            pos = positions[i]
            vel = np.zeros(3)
            
            if role == 0:
                # Employed Bee: Explores around a known food source (personal best)
                # Picks a random neighbor to interact with
                neighbor_idx = np.random.randint(0, N)
                while neighbor_idx == i and N > 1:
                    neighbor_idx = np.random.randint(0, N)
                    
                phi = (np.random.rand(3) - 0.5) * 2.0
                target_pos = self.personal_best_pos[i] + phi * (self.personal_best_pos[i] - positions[neighbor_idx])
                
                direction = target_pos - pos
                
            elif role == 1:
                # Onlooker Bee: Moves towards the global best food source
                phi = np.random.rand(3) * 1.5 # Attraction strength
                direction = phi * (self.global_best_pos - pos)
                
            else:
                # Scout Bee: Random walk to find new food sources
                dist_to_scout = np.linalg.norm(self.scout_targets[i] - pos)
                if dist_to_scout < 0.5:
                    # Reached waypoint, pick a new random spot
                    self.scout_targets[i] = pos + (np.random.rand(3) - 0.5) * 8.0
                    self.scout_targets[i][2] = max(0.5, self.scout_targets[i][2])
                
                direction = self.scout_targets[i] - pos
            
            # Simple obstacle/ground avoidance for all roles
            if pos[2] < 0.3:
                direction[2] += 1.0 # Push up
                
            # Normalize and scale to max speed
            mag = np.linalg.norm(direction)
            if mag > 1e-6:
                vel = (direction / mag) * self.max_speed
                
            # Add a tiny bit of separation to prevent crashes
            for j in range(N):
                if i != j:
                    diff = pos - positions[j]
                    dist = np.linalg.norm(diff)
                    if dist < 0.5 and dist > 1e-6:
                        vel += (diff / dist) * (0.5 / dist)
                        
            # Re-clamp after separation
            final_speed = np.linalg.norm(vel)
            if final_speed > self.max_speed:
                vel = (vel / final_speed) * self.max_speed
                
            targets[i] = vel

        return targets
