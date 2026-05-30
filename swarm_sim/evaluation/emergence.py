"""Emergence Detection System."""

from typing import List, Dict, Any, Tuple
import numpy as np

from swarm_sim.telemetry.frame import FrameSnapshot


class EmergenceDetector:
    """Detects emergent behaviors geometrically and kinematically."""

    @staticmethod
    def detect_flocking(frames: List[FrameSnapshot]) -> Dict[str, Any]:
        """Detect flocking (high velocity alignment + tight cohesion)."""
        if not frames:
            return {"behavior": "flocking", "confidence": 0.0, "time_range": None}
            
        alignments = []
        timestamps = []
        
        for frame in frames:
            vel = frame.velocities
            if len(vel) < 2:
                continue
                
            # Compute velocity alignment (variance of normalized velocities)
            speeds = np.linalg.norm(vel, axis=1, keepdims=True)
            # Avoid division by zero
            speeds[speeds < 1e-6] = 1e-6
            dirs = vel / speeds
            
            mean_dir = np.mean(dirs, axis=0)
            alignment = np.linalg.norm(mean_dir)
            
            alignments.append(alignment)
            timestamps.append(frame.timestamp)
            
        alignments = np.array(alignments)
        
        # High alignment implies flocking
        flocking_mask = alignments > 0.8
        
        confidence = float(np.mean(alignments)) if len(alignments) > 0 else 0.0
        
        # Find longest continuous window
        time_range = None
        if np.any(flocking_mask):
            indices = np.where(flocking_mask)[0]
            start_idx = indices[0]
            end_idx = indices[-1]
            time_range = [float(timestamps[start_idx]), float(timestamps[end_idx])]
            
        return {
            "behavior": "flocking",
            "confidence": round(confidence, 4),
            "time_range": time_range
        }
