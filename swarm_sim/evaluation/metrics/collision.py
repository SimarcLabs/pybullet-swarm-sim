"""Collision Rate Metric."""

from typing import List
import numpy as np

from swarm_sim.evaluation.metrics.base import BaseMetric
from swarm_sim.telemetry.frame import FrameSnapshot


class CollisionRateMetric(BaseMetric):
    """Evaluates the safety of the swarm by counting close-proximity events.
    
    Higher score means FEWER collisions (safer).
    """
    
    def __init__(self, safe_distance: float = 0.2):
        self.safe_distance = safe_distance

    def compute(self, frames: List[FrameSnapshot]) -> float:
        if not frames:
            return 1.0
            
        total_collisions = 0
        
        for frame in frames:
            pos = frame.positions
            N = len(pos)
            if N < 2:
                continue
                
            # Compute pairwise distances
            # (N, 1, 3) - (1, N, 3) -> (N, N, 3)
            diffs = pos[:, np.newaxis, :] - pos[np.newaxis, :, :]
            dists = np.linalg.norm(diffs, axis=2)
            
            # Mask out self-distances
            np.fill_diagonal(dists, np.inf)
            
            # Count pairs that are too close
            collisions = np.sum(dists < self.safe_distance) // 2
            total_collisions += collisions
            
        # Scale score: 0 collisions = 1.0, drops quickly
        # We normalize by total frames and total possible pairs
        N = len(frames[0].positions) if frames else 1
        max_possible_collisions_per_frame = (N * (N - 1)) / 2
        
        if max_possible_collisions_per_frame == 0:
            return 1.0
            
        mean_collisions = total_collisions / len(frames)
        
        # If mean collisions > 1.0 per frame, score approaches 0
        score = np.exp(-mean_collisions)
        return float(score)
