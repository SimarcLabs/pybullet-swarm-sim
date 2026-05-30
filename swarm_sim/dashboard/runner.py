"""
Simulation Runner for SwarmSim Dashboard.

Runs a simulation based on the requested algorithm and benchmark scenario,
logs the telemetry, and generates the standardized evaluation report.
"""

import argparse
import os
import sys
import time
import importlib.util
from pathlib import Path

import numpy as np

from swarm_sim.agents.pid_agent import PIDAgent

# New Architecture Components
from swarm_sim.telemetry.telemetry import TelemetryLogger
from swarm_sim.events.base import EventLogger
from swarm_sim.evaluation.report import BenchmarkReporter
from swarm_sim.testing.benchmarks.coverage import CoverageBenchmark
from swarm_sim.testing.benchmarks.formation import FormationBenchmark

# Algorithms
from swarm_sim.algorithms.flocking import FlockingAlgorithm
from swarm_sim.algorithms.consensus import ConsensusAlgorithm
from swarm_sim.algorithms.pso import PSOAlgorithm
from swarm_sim.algorithms.aco import ACOPathPlanner


def load_custom_algorithm(filepath: str):
    """Dynamically load a custom algorithm class from a .py file."""
    path = Path(filepath)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    for name, obj in module.__dict__.items():
        if isinstance(obj, type) and hasattr(obj, "compute") and name != "BaseAlgorithm":
            return obj
    raise ValueError("No valid algorithm class found in custom file.")


def run_simulation(
    algo: str,
    num_drones: int,
    duration: float,
    job_id: str,
    formation_type: str = "v",
    custom_algo_path: str = "",
):
    ctrl_freq = 48
    steps = int(duration * ctrl_freq)
    
    out_dir = Path("results") / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"PROGRESS:0%")
    print(f"Initializing {algo} benchmark with {num_drones} drones...")

    # --- Benchmark Setup ---
    if algo == "formation" or algo == "hover":
        benchmark = FormationBenchmark(
            num_drones=num_drones, 
            duration=duration, 
            ctrl_freq=ctrl_freq, 
            gui=True, 
            formation_type=formation_type if algo == "formation" else "grid"
        )
        algorithm = None
    else:
        benchmark = CoverageBenchmark(
            num_drones=num_drones, 
            duration=duration, 
            ctrl_freq=ctrl_freq, 
            gui=True
        )
        
        if algo == "flocking":
            algorithm = FlockingAlgorithm(num_drones=num_drones)
        elif algo == "pso":
            algorithm = PSOAlgorithm(num_drones=num_drones)
        elif algo == "aco":
            algorithm = ACOPathPlanner(grid_size=10, num_drones=num_drones)
        elif algo == "consensus":
            algorithm = ConsensusAlgorithm(mode="rendezvous", gain=0.5)
        elif algo == "custom" and custom_algo_path:
            CustomAlgoClass = load_custom_algorithm(custom_algo_path)
            try:
                algorithm = CustomAlgoClass(num_drones=num_drones)
            except TypeError:
                algorithm = CustomAlgoClass()
        else:
            raise ValueError(f"Unknown algorithm: {algo}")

    env = benchmark.setup_environment()
    obs, info = env.reset()
    
    agents = [
        PIDAgent(drone_id=i, kf=env.KF, km=env.KM, mass=env.M, max_rpm=env.MAX_RPM)
        for i in range(num_drones)
    ]
    
    # --- Framework Systems ---
    telemetry = TelemetryLogger()
    telemetry.set_manifest({
        "algo": algo,
        "num_drones": num_drones,
        "duration": duration,
        "formation_type": formation_type,
        "job_id": job_id
    })
    
    events = EventLogger()
    events.log(0.0, "SimulationStarted", {"algo": algo, "drones": num_drones})
    
    start_time = time.time()
    last_print = 0
    
    print("Simulation started.")
    
    for step in range(steps):
        state = benchmark.get_state()
        dt = 1 / ctrl_freq
        actions = np.zeros((num_drones, 4))
        
        # Determine targets
        if algo == "formation" or algo == "hover":
            targets = env.get_current_targets()
        else:
            if algorithm is not None:
                vel_targets = algorithm.compute(state)
            else:
                vel_targets = np.zeros_like(state.positions)
                
            if vel_targets is not None:
                targets = state.positions + vel_targets * dt * 5
                targets[:, 2] = np.clip(targets[:, 2], 0.5, 3.0)
            else:
                # E.g. ACO might return waypoints instead of velocities, but let's assume it returns velocity targets for now.
                # Oh wait, ACO returned targets previously.
                targets = np.zeros_like(state.positions)
                
        # Control
        for i in range(num_drones):
            drone_state = env.get_drone_state(i)
            actions[i] = agents[i].compute_action(drone_state, targets[i], dt=dt)
            
        obs, reward, terminated, truncated, info = env.step(actions)
        
        # Update state after step for accurate telemetry
        new_state = benchmark.get_state()
        telemetry.log_frame(step * dt, new_state)
        
        # Sync to real-time since gui=True
        elapsed = time.time() - start_time
        expected = (step + 1) * dt
        if expected > elapsed:
            time.sleep(expected - elapsed)
            
        # Progress reporting
        if time.time() - last_print > 0.1:
            pct = int((step / steps) * 100)
            print(f"PROGRESS:{pct}%")
            last_print = time.time()
            
    env.close()
    
    events.log(duration, "SimulationEnded", {"wall_time": time.time() - start_time})
    
    print("PROGRESS:100%")
    print("Simulation complete. Evaluating and saving results...")
    
    # --- Generate Artifacts ---
    telemetry.save(str(out_dir))
    events.save(str(out_dir))
    
    reporter = BenchmarkReporter(str(out_dir))
    reporter.generate(telemetry, benchmark.get_metric_weights())
        
    print(f"Results saved to {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", required=True)
    parser.add_argument("--drones", type=int, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--formation-type", type=str, default="v")
    parser.add_argument("--custom-algo", type=str, default="")
    args = parser.parse_args()
    
    sys.stdout.reconfigure(line_buffering=True)
    
    run_simulation(
        algo=args.algo,
        num_drones=args.drones,
        duration=args.duration,
        job_id=args.job_id,
        formation_type=args.formation_type,
        custom_algo_path=args.custom_algo
    )
