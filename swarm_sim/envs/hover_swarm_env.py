"""
Hover Swarm Environment — each drone must hover at its assigned 3-D waypoint.

The reward is the **negative sum of Euclidean distances** between each drone
and its target hover position, encouraging the swarm to converge quickly.

Example
-------
>>> from swarm_sim.envs.hover_swarm_env import HoverSwarmEnv
>>> env = HoverSwarmEnv(num_drones=4, gui=True)
>>> obs, info = env.reset()
"""

from __future__ import annotations

import numpy as np

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.utils.enums import DroneModel, Physics


class HoverSwarmEnv(BaseSwarmEnv):
    """Gymnasium env where each drone must hover at a fixed target position.

    Parameters
    ----------
    target_positions : np.ndarray | None
        ``(num_drones, 3)`` target XYZ per drone.  ``None`` → 1 m above start.
    max_steps : int
        Episode length in control steps.  Episode truncates after this.
    **kwargs
        Forwarded to :class:`BaseSwarmEnv`.
    """

    def __init__(
        self,
        target_positions: np.ndarray | None = None,
        max_steps: int = 1000,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.MAX_STEPS = max_steps

        if target_positions is not None:
            self.TARGET_POS = np.array(target_positions).reshape(self.NUM_DRONES, 3)
        else:
            # Default: hover 1 m directly above starting position
            self.TARGET_POS = self.INIT_XYZS.copy()
            self.TARGET_POS[:, 2] = 1.0

    # ------------------------------------------------------------------
    # Override reward / termination
    # ------------------------------------------------------------------

    def _compute_reward(self) -> float:
        """Negative total distance of all drones from their target positions."""
        distances = np.linalg.norm(self.pos - self.TARGET_POS, axis=1)
        return -float(np.sum(distances))

    def _compute_terminated(self) -> bool:
        """Terminate if any drone crashes (z < 0.02 m) after warm-up."""
        if self.step_counter < 100:
            return False
        return bool(np.any(self.pos[:, 2] < 0.02))

    def _compute_truncated(self) -> bool:
        """Truncate after MAX_STEPS."""
        return self.step_counter >= self.MAX_STEPS * self.PYB_STEPS_PER_CTRL

    def _compute_info(self) -> dict:
        distances = np.linalg.norm(self.pos - self.TARGET_POS, axis=1)
        return {
            "per_drone_distance": distances,
            "mean_distance": float(np.mean(distances)),
            "max_distance": float(np.max(distances)),
        }
