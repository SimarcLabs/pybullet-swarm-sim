"""
Flocking Demo — Reynolds boids with PID-controlled drones.

Spawns N drones and applies the flocking algorithm (separation, alignment,
cohesion) each step.  The boid velocity target is converted to a position
waypoint that the PID agent tracks.

Usage
-----
    python -m swarm_sim.examples.flocking
    python -m swarm_sim.examples.flocking --n-drones 12 --gui
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.agents.pid_agent import PIDAgent
from swarm_sim.algorithms.flocking import FlockingAlgorithm
from swarm_sim.core.state import SwarmState
from swarm_sim.utils.logger import SwarmLogger
from swarm_sim.utils.viz import sync


def run(
    num_drones: int = 12,
    duration_sec: float = 15.0,
    gui: bool = True,
):
    """Run the boids flocking demo.

    Parameters
    ----------
    num_drones : int
        Number of drones.
    duration_sec : float
        Simulation length in seconds.
    gui : bool
        Open the PyBullet viewer.
    """
    ctrl_freq = 48

    # Start drones in a random cluster
    rng = np.random.default_rng(42)
    init_xy = rng.uniform(-1.0, 1.0, size=(num_drones, 2))
    init_z = np.full((num_drones, 1), 1.0)
    initial_xyzs = np.hstack([init_xy, init_z])

    env = BaseSwarmEnv(
        num_drones=num_drones,
        initial_xyzs=initial_xyzs,
        gui=gui,
        ctrl_freq=ctrl_freq,
        pyb_freq=240,
    )
    obs, info = env.reset()

    agents = [
        PIDAgent(drone_id=i, kf=env.KF, km=env.KM, mass=env.M, max_rpm=env.MAX_RPM)
        for i in range(num_drones)
    ]

    flock = FlockingAlgorithm(
        num_drones=num_drones,
        r_separation=0.25,
        r_alignment=0.8,
        r_cohesion=1.5,
        w_separation=2.5,
        w_alignment=1.0,
        w_cohesion=1.2,
        max_speed=0.6,
    )

    logger = SwarmLogger(
        num_drones=num_drones,
        logging_freq_hz=ctrl_freq,
        duration_sec=int(duration_sec),
    )

    total_steps = int(duration_sec * ctrl_freq)
    start = time.time()

    print(f"[flocking] {num_drones} drones · boids flocking · {duration_sec}s")

    for step in range(total_steps):
        # Get current positions and velocities
        positions = env.pos.copy()
        velocities = env.vel.copy()

        # Compute boid velocity targets
        vel_targets = flock.compute(
            SwarmState(
                positions=positions,
                velocities=velocities,
                orientations=env.rpy.copy(),
                angular_velocities=env.ang_v.copy(),
                neighbor_graph=env.get_adjacency_matrix(),
            )
        )

        # Convert velocity targets to position waypoints
        dt = 1 / ctrl_freq
        waypoints = positions + vel_targets * dt * 5  # lookahead
        waypoints[:, 2] = np.clip(waypoints[:, 2], 0.5, 2.5)  # keep altitude

        actions = np.zeros((num_drones, 4))
        for i in range(num_drones):
            state = env.get_drone_state(i)
            actions[i] = agents[i].compute_action(state, waypoints[i], dt=dt)
            logger.log(drone=i, timestamp=step * dt, state=state)

        obs, reward, terminated, truncated, info = env.step(actions)

        if gui:
            sync(step, start, dt)

    env.close()

    print(f"\n[flocking] Done in {time.time() - start:.1f}s")
    logger.plot_3d(show=gui)
    return logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Boids Flocking Demo")
    parser.add_argument("--n-drones", type=int, default=12)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--headless", action="store_true", help="Disable GUI")
    args = parser.parse_args()
    run(num_drones=args.n_drones, duration_sec=args.duration, gui=not args.headless)
