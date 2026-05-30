"""Telemetry logger and exporter."""

import json
from typing import List, Dict, Any
from pathlib import Path

import numpy as np

from swarm_sim.core.state import SwarmState
from swarm_sim.telemetry.frame import FrameSnapshot


class TelemetryLogger:
    """Records FrameSnapshots and serializes them to standard formats."""

    def __init__(self):
        self.frames: List[FrameSnapshot] = []
        self.manifest: Dict[str, Any] = {}

    def log_frame(self, timestamp: float, state: SwarmState, live_metrics: dict = None):
        """Extracts data from a SwarmState and saves it as a FrameSnapshot."""
        frame = FrameSnapshot(
            timestamp=timestamp,
            positions=state.positions.copy(),
            velocities=state.velocities.copy(),
            orientations=state.orientations.copy(),
            angular_velocities=state.angular_velocities.copy(),
            neighbor_graph=state.neighbor_graph.copy() if state.neighbor_graph is not None else np.array([]),
            communication_graph=state.communication_graph.copy() if state.communication_graph is not None else np.array([]),
            targets=state.targets.copy() if state.targets is not None else np.array([]),
            obstacles=state.obstacles.copy() if state.obstacles is not None else np.array([]),
            active_mask=state.active_drones_mask.copy(),
            battery_levels=state.battery_levels.copy(),
            drone_status=list(state.drone_status),
            live_metrics=live_metrics or {}
        )
        self.frames.append(frame)

    def set_manifest(self, config: Dict[str, Any]):
        self.manifest = config

    def save(self, output_dir: str):
        """Save telemetry.npz and manifest.json to the output directory."""
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save Manifest
        with open(path / "manifest.json", "w") as f:
            json.dump(self.manifest, f, indent=4)
            
        # Serialize Frames to NPZ
        if not self.frames:
            return

        data = {
            "timestamps": np.array([f.timestamp for f in self.frames]),
            "positions": np.array([f.positions for f in self.frames]),
            "velocities": np.array([f.velocities for f in self.frames]),
            "orientations": np.array([f.orientations for f in self.frames]),
            "angular_velocities": np.array([f.angular_velocities for f in self.frames]),
            "neighbor_graph": np.array([f.neighbor_graph for f in self.frames]),
            "communication_graph": np.array([f.communication_graph for f in self.frames]),
            "active_mask": np.array([f.active_mask for f in self.frames]),
            "battery_levels": np.array([f.battery_levels for f in self.frames]),
        }
        
        np.savez_compressed(path / "telemetry.npz", **data)
