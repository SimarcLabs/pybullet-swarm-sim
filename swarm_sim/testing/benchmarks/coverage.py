"""Coverage Benchmark Scenario."""

from typing import Dict
import numpy as np

from swarm_sim.testing.benchmarks.base import BaseBenchmark
from swarm_sim.envs.base_swarm_env import BaseSwarmEnv


class CoverageBenchmark(BaseBenchmark):
    """Scenario for evaluating swarm exploration and coverage."""

    def __init__(self, num_drones: int, duration: float, ctrl_freq: int = 48, gui: bool = False):
        super().__init__(num_drones, duration, ctrl_freq, gui)
        
    def setup_environment(self) -> BaseSwarmEnv:
        """Create environment with drones tightly packed at origin."""
        # Initial cluster near origin
        rng = np.random.default_rng(42)
        init_xy = rng.uniform(-1.0, 1.0, size=(self.num_drones, 2))
        init_z = np.full((self.num_drones, 1), 1.0)
        initial_xyzs = np.hstack([init_xy, init_z])
        
        self.env = BaseSwarmEnv(
            num_drones=self.num_drones,
            initial_xyzs=initial_xyzs,
            gui=self.gui,
            ctrl_freq=self.ctrl_freq
        )
        return self.env
        
    def get_metric_weights(self) -> Dict[str, float]:
        """Coverage prioritizes exploration and collision avoidance."""
        return {
            "CoverageMetric": 0.6,
            "CollisionRateMetric": 0.3,
            "ConnectivityMetric": 0.1
        }
