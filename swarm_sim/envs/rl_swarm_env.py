"""
RL-ready Swarm Environment — normalized obs / actions for Stable-Baselines3.

Wraps the hover task with **normalised observation and action spaces** so it
plugs directly into ``stable_baselines3.PPO`` without any external wrapper.

Example
-------
>>> from swarm_sim.envs.rl_swarm_env import RLSwarmEnv
>>> env = RLSwarmEnv(num_drones=1, gui=False)
>>> obs, info = env.reset()
>>> print(env.observation_space.shape, env.action_space.shape)
"""

from __future__ import annotations

import numpy as np
from gymnasium import spaces

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.utils.enums import DroneModel, Physics


class RLSwarmEnv(BaseSwarmEnv):
    """Single-agent RL env for learning to hover (designed for SB3).

    The env presents a **flat** observation vector and action vector for a
    *single* drone (multi-agent support can be layered on top with PettingZoo).

    Observation (12-D):
        ``[x, y, z, vx, vy, vz, roll, pitch, yaw, wx, wy, wz]``

    Action (4-D):
        ``[-1, 1]`` mapped to ``[0, MAX_RPM]`` for each motor.

    Parameters
    ----------
    target_pos : np.ndarray
        ``(3,)`` XYZ hover target.  Default ``[0, 0, 1]``.
    max_steps : int
        Episode length.
    **kwargs
        Forwarded to :class:`BaseSwarmEnv`.
    """

    def __init__(
        self,
        target_pos: np.ndarray | None = None,
        max_steps: int = 1000,
        **kwargs,
    ):
        kwargs.setdefault("num_drones", 1)
        super().__init__(**kwargs)
        self.MAX_STEPS = max_steps
        self.target_pos = (
            np.array(target_pos, dtype=np.float32)
            if target_pos is not None
            else np.array([0.0, 0.0, 1.0], dtype=np.float32)
        )

    # ------------------------------------------------------------------
    # Spaces
    # ------------------------------------------------------------------

    def _action_space(self) -> spaces.Box:
        return spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)

    def _observation_space(self) -> spaces.Box:
        return spaces.Box(
            low=-np.inf, high=np.inf, shape=(12,), dtype=np.float32
        )

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------

    def _preprocess_action(self, action: np.ndarray) -> np.ndarray:
        """Map ``[-1, 1]`` → ``[0, MAX_RPM]``."""
        rpm = (np.array(action).flatten()[:4] + 1.0) / 2.0 * self.MAX_RPM
        return rpm.reshape(1, 4)

    def _compute_obs(self) -> np.ndarray:
        state = self.get_drone_state(0)
        # [pos(3), vel(3), rpy(3), ang_vel(3)]
        obs = np.concatenate([state[0:3], state[10:13], state[7:10], state[13:16]])
        return obs.astype(np.float32)

    def _compute_reward(self) -> float:
        pos = self.pos[0]
        dist = np.linalg.norm(pos - self.target_pos)
        vel_penalty = 0.01 * np.linalg.norm(self.vel[0])
        ang_penalty = 0.01 * np.linalg.norm(self.ang_v[0])
        # Shaped reward: bonus for being close, penalties for instability
        return -(dist + vel_penalty + ang_penalty)

    def _compute_terminated(self) -> bool:
        if self.step_counter < 50:
            return False
        return bool(self.pos[0, 2] < 0.02 or self.pos[0, 2] > 3.0)

    def _compute_truncated(self) -> bool:
        return self.step_counter >= self.MAX_STEPS * self.PYB_STEPS_PER_CTRL

    def _compute_info(self) -> dict:
        return {"distance": float(np.linalg.norm(self.pos[0] - self.target_pos))}
