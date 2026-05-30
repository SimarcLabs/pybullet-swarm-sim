"""Coverage Metric."""

from typing import List
import numpy as np

from swarm_sim.evaluation.metrics.base import BaseMetric
from swarm_sim.telemetry.frame import FrameSnapshot


class CoverageMetric(BaseMetric):
    """Evaluates how much of a given space was explored by the swarm.
    
    A simple grid-based approach:
    Divide a bounded volume into voxels. Mark voxel as visited if a drone
    passes within it. The score is the percentage of visited voxels.
    """
    
    def __init__(self, bounds_lo: np.ndarray, bounds_hi: np.ndarray, resolution: float = 1.0):
        self.bounds_lo = bounds_lo
        self.bounds_hi = bounds_hi
        self.resolution = resolution
        
        # Dimensions
        self.grid_dims = np.ceil((self.bounds_hi - self.bounds_lo) / self.resolution).astype(int)
        self.grid_dims = np.maximum(self.grid_dims, 1)

    def compute(self, frames: List[FrameSnapshot]) -> float:
        if not frames:
            return 0.0
            
        visited = set()
        
        for frame in frames:
            for pos in frame.positions:
                idx = np.floor((pos - self.bounds_lo) / self.resolution).astype(int)
                # Check bounds
                if np.all(idx >= 0) and np.all(idx < self.grid_dims):
                    visited.add(tuple(idx))
                    
        total_voxels = np.prod(self.grid_dims)
        coverage_pct = len(visited) / float(total_voxels)
        return min(coverage_pct, 1.0)
