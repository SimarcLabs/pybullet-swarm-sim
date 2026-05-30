"""Formation Benchmark Scenario."""

from typing import Dict
import numpy as np

from swarm_sim.testing.benchmarks.base import BaseBenchmark
from swarm_sim.envs.formation_env import FormationEnv
from swarm_sim.utils.enums import FormationType


class FormationBenchmark(BaseBenchmark):
    """Scenario for evaluating swarm formation keeping and stability."""

    def __init__(
        self, 
        num_drones: int, 
        duration: float, 
        ctrl_freq: int = 48, 
        gui: bool = False,
        formation_type: str = "v"
    ):
        super().__init__(num_drones, duration, ctrl_freq, gui)
        self.formation_type = formation_type
        
    def setup_environment(self) -> FormationEnv:
        """Create moving formation environment."""
        fmt = {f.value: f for f in FormationType}.get(self.formation_type, FormationType.V)
        
        self.env = FormationEnv(
            num_drones=self.num_drones,
            formation=fmt,
            gui=self.gui,
            ctrl_freq=self.ctrl_freq
        )
        return self.env
        
    def get_metric_weights(self) -> Dict[str, float]:
        """Formation keeping prioritizes cohesion and lack of collisions."""
        return {
            "CohesionMetric": 0.5,
            "ConnectivityMetric": 0.3,
            "CollisionRateMetric": 0.2
        }
