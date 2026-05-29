"""
RL Agent — thin wrapper around a trained Stable-Baselines3 policy.

Loads a saved SB3 model and exposes the same ``compute_action`` interface as
:class:`PIDAgent`, so RL and classical agents are fully interchangeable.

Example
-------
>>> from swarm_sim.agents.rl_agent import RLAgent
>>> agent = RLAgent(model_path="ppo_hover.zip")
>>> rpm = agent.compute_action(obs, target=np.array([0, 0, 1]))
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from swarm_sim.agents.base_agent import BaseAgent


class RLAgent(BaseAgent):
    """Wraps a trained Stable-Baselines3 model as a swarm agent.

    Parameters
    ----------
    model_path : str | Path
        Path to a saved ``.zip`` SB3 model file.
    drone_id : int
        Drone index.
    """

    def __init__(self, model_path: str | Path, drone_id: int = 0):
        super().__init__(drone_id=drone_id)
        self.model_path = Path(model_path)
        self._model = None

    def _load_model(self):
        """Lazy-load the SB3 model (avoids hard torch dependency at import time)."""
        try:
            from stable_baselines3 import PPO
        except ImportError as e:
            raise ImportError(
                "stable-baselines3 is required for RLAgent.  "
                "Install with:  pip install pybullet-swarm-sim[rl]"
            ) from e
        self._model = PPO.load(str(self.model_path))

    def compute_action(
        self,
        obs: np.ndarray,
        target: np.ndarray,
        dt: float = 1 / 240,
    ) -> np.ndarray:
        """Run the RL policy to produce motor RPMs.

        Parameters
        ----------
        obs : np.ndarray
            ``(20,)`` drone state vector.
        target : np.ndarray
            Ignored by the RL policy (target is baked into the trained reward).
        dt : float
            Unused; kept for interface consistency.

        Returns
        -------
        np.ndarray
            ``(4,)`` RPM commands.
        """
        if self._model is None:
            self._load_model()

        # Build the 12-D normalized obs the RL env uses
        rl_obs = np.concatenate([obs[0:3], obs[10:13], obs[7:10], obs[13:16]])
        action, _ = self._model.predict(rl_obs.astype(np.float32), deterministic=True)
        # Map [-1, 1] → RPM  (same mapping as RLSwarmEnv)
        rpm = (action.flatten()[:4] + 1.0) / 2.0 * 21_703.0
        return rpm

    def reset(self):
        pass
