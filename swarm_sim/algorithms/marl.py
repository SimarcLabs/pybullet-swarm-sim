"""
MARL Algorithm — wraps a trained SB3 PPO model as a BaseAlgorithm.

In **inference mode**, the algorithm loads a pre-trained model and uses it to
produce velocity targets for all drones.  In the absence of a model, it falls
back to a simple heuristic (cooperative goal-seeking with separation).

This allows MARL to plug seamlessly into the runner/dashboard pipeline just
like Flocking, APF, etc.

Usage
-----
    # With a trained model
    algo = MARLAlgorithm(num_drones=5, model_path="models/marl_ppo.zip")

    # Without a model (heuristic fallback)
    algo = MARLAlgorithm(num_drones=5)
"""

from __future__ import annotations

import numpy as np
from pathlib import Path

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class MARLAlgorithm(BaseAlgorithm):
    """Multi-Agent RL algorithm with trained-model inference or heuristic fallback.

    Parameters
    ----------
    num_drones : int
        Number of drones.
    model_path : str | None
        Path to a trained SB3 PPO model (.zip).
        If None, uses a cooperative heuristic fallback.
    goal : tuple[float, float, float]
        Shared goal coordinate.
    max_speed : float
        Maximum velocity output (m/s).
    k_neighbours : int
        Number of nearest neighbours used in ego observations.
    """

    def __init__(
        self,
        num_drones: int = 5,
        model_path: str | None = None,
        goal: tuple[float, float, float] = (0.0, 0.0, 1.0),
        max_speed: float = 1.0,
        k_neighbours: int = 3,
    ):
        self.goal = np.array(goal, dtype=np.float32)
        self.max_speed = max_speed
        self.K = k_neighbours
        self.model = None

        if model_path and Path(model_path).exists():
            try:
                from stable_baselines3 import PPO
                self.model = PPO.load(model_path)
                print(f"[MARL] Loaded trained model from {model_path}")
            except ImportError:
                print("[MARL] stable-baselines3 not installed — using heuristic fallback")
            except Exception as e:
                print(f"[MARL] Could not load model ({e}) — using heuristic fallback")
        else:
            if model_path:
                print(f"[MARL] Model not found at {model_path} — using heuristic fallback")
            else:
                print("[MARL] No model path provided — using cooperative heuristic")

        super().__init__(num_drones=num_drones)

    def _ego_obs(self, i: int, positions: np.ndarray, velocities: np.ndarray,
                 orientations: np.ndarray) -> np.ndarray:
        """Build the same ego-centric observation the training env produces."""
        pos = positions[i]
        vel = velocities[i]
        rpy = orientations[i]
        goal_off = self.goal - pos

        N = positions.shape[0]
        dists = np.linalg.norm(positions - pos, axis=1)
        dists[i] = np.inf
        nearest = np.argsort(dists)[:self.K]

        neighbour_offsets = []
        for j in nearest:
            if j < N:
                neighbour_offsets.append(positions[j] - pos)
        while len(neighbour_offsets) < self.K:
            neighbour_offsets.append(np.zeros(3))

        return np.concatenate([goal_off, vel, rpy, *neighbour_offsets]).astype(np.float32)

    def _heuristic_velocity(self, i: int, positions: np.ndarray) -> np.ndarray:
        """Simple cooperative heuristic: goal attraction + separation."""
        pos = positions[i]
        N = positions.shape[0]

        # Attraction to goal
        diff_goal = self.goal - pos
        dist_goal = max(np.linalg.norm(diff_goal), 1e-6)
        f_att = 0.4 * diff_goal / max(dist_goal, 0.5)

        # Separation from peers
        f_sep = np.zeros(3)
        for j in range(N):
            if i == j:
                continue
            diff = pos - positions[j]
            dist = np.linalg.norm(diff)
            if dist < 0.8 and dist > 1e-6:
                f_sep += (diff / dist) * (0.8 - dist)

        vel = f_att + 1.5 * f_sep

        # Altitude hold
        if pos[2] < 0.3:
            vel[2] += 0.5

        speed = np.linalg.norm(vel)
        if speed > self.max_speed:
            vel = vel / speed * self.max_speed

        return vel

    def compute(self, state: SwarmState) -> np.ndarray:
        """Compute velocity targets for all drones.

        Uses the trained model if available, otherwise the heuristic fallback.

        Parameters
        ----------
        state : SwarmState
            Current swarm state.

        Returns
        -------
        np.ndarray
            ``(N, 3)`` velocity vectors.
        """
        positions = state.positions
        N = positions.shape[0]
        velocities = np.zeros((N, 3))

        if self.model is not None:
            # Build flat observation (same format as MARLSwarmEnv)
            obs = np.concatenate([
                self._ego_obs(i, positions, state.velocities, state.orientations)
                for i in range(N)
            ]).astype(np.float32)

            action, _ = self.model.predict(obs, deterministic=True)
            # The model outputs motor RPMs — convert to approximate velocity
            # direction from the action vector (4 values per drone)
            for i in range(N):
                motors = action[i * 4:(i + 1) * 4]
                # Higher thrust on right vs left → roll → lateral velocity
                # This is an approximation; the PID controller handles the rest
                avg_thrust = np.mean(motors)
                lat_x = (motors[2] + motors[3] - motors[0] - motors[1]) * 0.3
                lat_y = (motors[0] + motors[3] - motors[1] - motors[2]) * 0.3
                vert = (avg_thrust - 0.5) * 2.0  # centred around hover

                vel = np.array([lat_x, lat_y, vert])
                speed = np.linalg.norm(vel)
                if speed > self.max_speed:
                    vel = vel / speed * self.max_speed
                velocities[i] = vel
        else:
            # Heuristic fallback
            for i in range(N):
                velocities[i] = self._heuristic_velocity(i, positions)

        return velocities
