"""
Formation Environment — drones track a moving geometric formation.

Supports ``LINE``, ``V``, ``GRID``, ``RING``, and ``HELIX`` formations.  The
formation centre moves forward at a configurable speed so the swarm flies
as a coordinated group.

Example
-------
>>> from swarm_sim.envs.formation_env import FormationEnv
>>> from swarm_sim.utils.enums import FormationType
>>> env = FormationEnv(
...     num_drones=8, formation=FormationType.V, gui=True
... )
>>> obs, info = env.reset()
"""

from __future__ import annotations

import numpy as np

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.algorithms.formation import FormationPlanner
from swarm_sim.utils.enums import DroneModel, Physics, FormationType


class FormationEnv(BaseSwarmEnv):
    """Gymnasium env where the swarm must track a moving formation.

    Parameters
    ----------
    formation : FormationType
        Desired geometric pattern.
    spacing : float
        Metres between neighbouring drones in the formation.
    forward_speed : float
        Speed (m/s) of the formation centre along the x-axis.
    max_steps : int
        Episode length in control steps.
    **kwargs
        Forwarded to :class:`BaseSwarmEnv`.
    """

    def __init__(
        self,
        formation: FormationType = FormationType.V,
        spacing: float = 0.5,
        forward_speed: float = 0.3,
        max_steps: int = 2000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.formation = formation
        self.spacing = spacing
        self.forward_speed = forward_speed
        self.MAX_STEPS = max_steps
        self.planner = FormationPlanner()

        # Compute static formation offsets (relative to centre)
        self._offsets = self.planner.compute_offsets(
            formation=self.formation,
            num_drones=self.NUM_DRONES,
            spacing=self.spacing,
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_current_targets(self) -> np.ndarray:
        """Return the ``(num_drones, 3)`` target positions for this timestep."""
        t = self.step_counter * self.PYB_TIMESTEP
        centre = np.array([self.forward_speed * t, 0.0, 1.0])
        return self._offsets + centre

    # ------------------------------------------------------------------
    # Override reward / termination
    # ------------------------------------------------------------------

    def _compute_reward(self) -> float:
        targets = self.get_current_targets()
        distances = np.linalg.norm(self.pos - targets, axis=1)
        return -float(np.sum(distances))

    def _compute_terminated(self) -> bool:
        if self.step_counter < 100:
            return False
        return bool(np.any(self.pos[:, 2] < 0.02))

    def _compute_truncated(self) -> bool:
        return self.step_counter >= self.MAX_STEPS * self.PYB_STEPS_PER_CTRL

    def _compute_info(self) -> dict:
        targets = self.get_current_targets()
        distances = np.linalg.norm(self.pos - targets, axis=1)
        return {
            "per_drone_distance": distances,
            "formation_error": float(np.mean(distances)),
            "targets": targets,
        }
