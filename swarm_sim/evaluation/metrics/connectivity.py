"""Connectivity Metric."""

from typing import List
import numpy as np

from swarm_sim.evaluation.metrics.base import BaseMetric
from swarm_sim.telemetry.frame import FrameSnapshot


class ConnectivityMetric(BaseMetric):
    """Evaluates the algebraic connectivity (Fiedler value) of the swarm graph.
    
    A higher Fiedler value indicates a better connected communication graph.
    If the value is 0, the graph is disconnected (multiple components).
    """

    def compute(self, frames: List[FrameSnapshot]) -> float:
        if not frames:
            return 0.0
            
        total_fiedler = 0.0
        
        for frame in frames:
            adj = frame.neighbor_graph
            if len(adj) <= 1:
                total_fiedler += 1.0 # Trivally connected
                continue
                
            degree = np.diag(np.sum(adj, axis=1))
            laplacian = degree - adj
            
            # Compute eigenvalues
            try:
                eigenvalues = np.linalg.eigvalsh(laplacian)
                # The second smallest eigenvalue is the algebraic connectivity
                fiedler = eigenvalues[1]
                # Clip to 0 for numerical stability on disconnected graphs
                total_fiedler += max(0.0, float(fiedler))
            except np.linalg.LinAlgError:
                pass
                
        mean_fiedler = total_fiedler / len(frames)
        
        # Scale for scoring (assuming max typical degree ~ N, we just use a loose upper bound)
        N = len(frames[0].positions) if frames else 1
        score = min(mean_fiedler / (N / 2.0), 1.0)
        return float(score)
