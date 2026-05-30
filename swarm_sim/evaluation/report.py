"""Benchmark Report Generator."""

import json
from pathlib import Path
from typing import Dict, Any, List

from swarm_sim.telemetry.telemetry import TelemetryLogger
from swarm_sim.evaluation.metrics.coverage import CoverageMetric
from swarm_sim.evaluation.metrics.cohesion import CohesionMetric
from swarm_sim.evaluation.metrics.connectivity import ConnectivityMetric
from swarm_sim.evaluation.metrics.collision import CollisionRateMetric
from swarm_sim.evaluation.emergence import EmergenceDetector


class BenchmarkReporter:
    """Generates the standardized run artifact structure and health score."""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        
    def generate(self, telemetry: TelemetryLogger, metric_weights: Dict[str, float]):
        """Evaluates metrics and writes all artifacts."""
        frames = telemetry.frames
        
        # 1. Compute Metrics
        metrics_dict = {}
        metric_classes = {
            "CoverageMetric": CoverageMetric(bounds_lo=-5, bounds_hi=5, resolution=1.0),
            "CohesionMetric": CohesionMetric(),
            "ConnectivityMetric": ConnectivityMetric(),
            "CollisionRateMetric": CollisionRateMetric()
        }
        
        total_weight = sum(metric_weights.values()) if metric_weights else 1.0
        health_score = 0.0
        
        for name, instance in metric_classes.items():
            if name in metric_weights:
                # Compute full metric
                val = instance.compute(frames)
                metrics_dict[name] = val
                
                # Weight contribution
                weight = metric_weights[name] / total_weight
                health_score += val * weight
                
        # 2. Detect Emergence
        emergence_results = [
            EmergenceDetector.detect_flocking(frames)
        ]
        
        # 3. Write metrics.json
        with open(self.output_dir / "metrics.json", "w") as f:
            json.dump({
                "health_score": round(health_score, 4),
                "metrics": metrics_dict,
                "emergence": emergence_results
            }, f, indent=4)
            
        # 4. Write report.md
        manifest = telemetry.manifest
        md_content = f"""# Swarm Benchmark Report

## Overview
- **Algorithm:** {manifest.get('algo', 'Unknown')}
- **Swarm Size:** {manifest.get('num_drones', 0)} drones
- **Duration:** {manifest.get('duration', 0.0)} seconds
- **Health Score:** {health_score:.4f} / 1.0

## Evaluated Metrics
"""
        for m, v in metrics_dict.items():
            weight = metric_weights.get(m, 0.0)
            md_content += f"- **{m}:** {v:.4f} (Weight: {weight})\n"
            
        md_content += "\n## Emergence Detection\n"
        for em in emergence_results:
            md_content += f"- **{em['behavior']}**: Confidence {em['confidence']} (Time: {em['time_range']})\n"
            
        with open(self.output_dir / "report.md", "w") as f:
            f.write(md_content)
