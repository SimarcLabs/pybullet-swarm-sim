"""Cohesion Metric."""

from typing import List
import numpy as np

from swarm_sim.evaluation.metrics.base import BaseMetric
from swarm_sim.telemetry.frame import FrameSnapshot


class CohesionMetric(BaseMetric):
    """Evaluates how tightly the swarm stays together.
    
    Computed as the inverse of the mean distance to the swarm centroid 
    across all frames. Scaled so that closer = closer to 1.0.
    """

    def compute(self, frames: List[FrameSnapshot]) -> float:
        if not frames:
            return 0.0
            
        total_dispersion = 0.0
        
        for frame in frames:
            pos = frame.positions
            if len(pos) == 0:
                continue
            centroid = np.mean(pos, axis=0)
            dispersion = np.mean(np.linalg.norm(pos - centroid, axis=1))
            total_dispersion += dispersion
            
        mean_dispersion = total_dispersion / len(frames)
        
        # Scale to [0, 1] using a decay function. 
        # A dispersion of 0 gives 1.0. A dispersion of 5.0 gives ~0.1
        score = np.exp(-mean_dispersion / 2.0)
        return float(score)
