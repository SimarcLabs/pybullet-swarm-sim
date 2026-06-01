"""
Multi-Agent RL Environment — Parameter-Sharing PPO.

Each drone is treated as an independent agent that shares the same policy
network. Observations are **ego-centric** (relative positions of neighbours)
so the policy generalises across any drone index.

Compatible with Stable-Baselines3 via a flattened vectorised interface.

References
----------
Yu, C., et al. (2022). The surprising effectiveness of PPO in cooperative
multi-agent games. *NeurIPS 2022*.
"""

from __future__ import annotations

import numpy as np
from gymnasium import spaces

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.utils.enums import DroneModel, Physics


class MARLSwarmEnv(BaseSwarmEnv):
    """Multi-agent swarm env with parameter-sharing (single-policy) design.

    All N drones share one policy.  At each control step, the env collects
    N ego-centric observations, the external caller runs the policy N times,
    and returns N actions that are concatenated and stepped together.

    This allows training with vanilla SB3 PPO by treating each drone's
    experience as an independent sample from the same MDP.

    Observation per drone (18-D):
        ``[dx_goal, dy_goal, dz_goal,   # relative goal offset
          vx, vy, vz,                    # own velocity
          roll, pitch, yaw,              # own orientation
          n1_dx, n1_dy, n1_dz,           # nearest neighbour 1 offset
          n2_dx, n2_dy, n2_dz,           # nearest neighbour 2 offset
          n3_dx, n3_dy, n3_dz]``         # nearest neighbour 3 offset

    Action per drone (4-D):
        ``[-1, 1]^4`` mapped to ``[0, MAX_RPM]`` for each motor.

    Parameters
    ----------
    goal : np.ndarray
        Shared goal position ``(3,)`` all drones should approach.
    max_steps : int
        Max steps per episode.
    k_neighbours : int
        Number of nearest neighbours included in each observation.
    **kwargs
        Forwarded to BaseSwarmEnv.
    """

    def __init__(
        self,
        goal: np.ndarray | None = None,
        max_steps: int = 500,
        k_neighbours: int = 3,
        **kwargs,
    ):
        kwargs.setdefault("num_drones", 5)
        super().__init__(**kwargs)
        self.MAX_STEPS = max_steps
        self.K = k_neighbours
        self.goal = (
            np.array(goal, dtype=np.float32) if goal is not None
            else np.array([0.0, 0.0, 1.0], dtype=np.float32)
        )

    # ------------------------------------------------------------------
    # Spaces — flattened across all drones for SB3 compatibility
    # ------------------------------------------------------------------
    def _obs_dim_per_drone(self) -> int:
        return 3 + 3 + 3 + self.K * 3   # goal_off + vel + rpy + K neighbours

    def _action_space(self) -> spaces.Box:
        # Flat action for ALL drones
        return spaces.Box(
            low=-1.0, high=1.0,
            shape=(self.NUM_DRONES * 4,),
            dtype=np.float32,
        )

    def _observation_space(self) -> spaces.Box:
        dim = self.NUM_DRONES * self._obs_dim_per_drone()
        return spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(dim,),
            dtype=np.float32,
        )

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------
    def _ego_obs(self, i: int) -> np.ndarray:
        """Build ego-centric observation for drone i."""
        pos = self.pos[i]
        vel = self.vel[i]
        rpy = self.rpy[i]

        # Goal offset (ego-relative)
        goal_off = self.goal - pos

        # Nearest K neighbours
        dists = np.linalg.norm(self.pos - pos, axis=1)
        dists[i] = np.inf  # exclude self
        nearest = np.argsort(dists)[:self.K]

        neighbour_offsets = []
        for j in nearest:
            neighbour_offsets.append(self.pos[j] - pos)
        # Pad if fewer than K neighbours
        while len(neighbour_offsets) < self.K:
            neighbour_offsets.append(np.zeros(3))

        return np.concatenate([
            goal_off, vel, rpy, *neighbour_offsets
        ]).astype(np.float32)

    def _compute_obs(self) -> np.ndarray:
        """Flat observation: concat of all ego observations."""
        obs = np.concatenate([self._ego_obs(i) for i in range(self.NUM_DRONES)])
        return obs.astype(np.float32)

    # ------------------------------------------------------------------
    # Action preprocessing
    # ------------------------------------------------------------------
    def _preprocess_action(self, action: np.ndarray) -> np.ndarray:
        """Map [-1,1]^(N*4) → [0, MAX_RPM]^(N,4)."""
        flat = np.array(action).flatten()[: self.NUM_DRONES * 4]
        rpm = (flat + 1.0) / 2.0 * self.MAX_RPM
        return rpm.reshape(self.NUM_DRONES, 4)

    # ------------------------------------------------------------------
    # Reward
    # ------------------------------------------------------------------
    def _compute_reward(self) -> float:
        """Team reward: all drones near goal + separation bonus."""
        reward = 0.0
        for i in range(self.NUM_DRONES):
            dist = np.linalg.norm(self.pos[i] - self.goal)
            reward -= dist  # distance penalty

            vel_penalty = 0.005 * np.linalg.norm(self.vel[i])
            reward -= vel_penalty

        # Separation bonus: reward for maintaining healthy spacing
        for i in range(self.NUM_DRONES):
            for j in range(i + 1, self.NUM_DRONES):
                d = np.linalg.norm(self.pos[i] - self.pos[j])
                if d < 0.3:
                    reward -= 2.0  # collision penalty
                elif d < 1.0:
                    reward += 0.1  # healthy spacing

        return reward / self.NUM_DRONES  # normalise

    # ------------------------------------------------------------------
    # Termination
    # ------------------------------------------------------------------
    def _compute_terminated(self) -> bool:
        if self.step_counter < 50:
            return False
        # Terminate if any drone crashes
        for i in range(self.NUM_DRONES):
            if self.pos[i, 2] < 0.02 or self.pos[i, 2] > 4.0:
                return True
        return False

    def _compute_truncated(self) -> bool:
        return self.step_counter >= self.MAX_STEPS * self.PYB_STEPS_PER_CTRL

    def _compute_info(self) -> dict:
        dists = [float(np.linalg.norm(self.pos[i] - self.goal))
                 for i in range(self.NUM_DRONES)]
        return {
            "mean_distance": float(np.mean(dists)),
            "min_distance": float(np.min(dists)),
            "max_distance": float(np.max(dists)),
        }
