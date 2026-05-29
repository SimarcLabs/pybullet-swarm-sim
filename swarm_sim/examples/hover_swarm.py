"""
Hover Swarm — minimal sanity-check example.

Spawns N drones and flies them to fixed hover points using PID control.
This is the simplest possible demo — run it to verify your installation.

Usage
-----
    python -m swarm_sim.examples.hover_swarm
    python -m swarm_sim.examples.hover_swarm --n-drones 8 --gui
    python -m swarm_sim.examples.hover_swarm --n-drones 4 --duration 5
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from swarm_sim.envs.hover_swarm_env import HoverSwarmEnv
from swarm_sim.agents.pid_agent import PIDAgent
from swarm_sim.utils.logger import SwarmLogger
from swarm_sim.utils.viz import sync


def run(
    num_drones: int = 4,
    duration_sec: float = 10.0,
    gui: bool = True,
):
    """Run the hover-swarm demo.

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
    env = HoverSwarmEnv(
        num_drones=num_drones,
        gui=gui,
        ctrl_freq=ctrl_freq,
        pyb_freq=240,
    )
    obs, info = env.reset()

    # Create one PID agent per drone
    agents = [
        PIDAgent(drone_id=i, kf=env.KF, km=env.KM, mass=env.M, max_rpm=env.MAX_RPM)
        for i in range(num_drones)
    ]

    # Logger
    logger = SwarmLogger(
        num_drones=num_drones,
        logging_freq_hz=ctrl_freq,
        duration_sec=int(duration_sec),
    )

    total_steps = int(duration_sec * ctrl_freq)
    start = time.time()

    print(f"[hover_swarm] Starting {num_drones}-drone hover for {duration_sec}s …")

    for step in range(total_steps):
        actions = np.zeros((num_drones, 4))
        for i in range(num_drones):
            state = env.get_drone_state(i)
            target = env.TARGET_POS[i]
            actions[i] = agents[i].compute_action(state, target, dt=1 / ctrl_freq)
            logger.log(drone=i, timestamp=step / ctrl_freq, state=state)

        obs, reward, terminated, truncated, info = env.step(actions)

        if gui:
            sync(step, start, 1 / ctrl_freq)

        if terminated or truncated:
            break

    env.close()

    # Report final errors
    print(f"\n[hover_swarm] Done in {time.time() - start:.1f}s")
    print(f"  Mean distance to target: {info.get('mean_distance', 'N/A'):.4f} m")
    print(f"  Max  distance to target: {info.get('max_distance', 'N/A'):.4f} m")

    logger.plot(show=gui)
    return logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hover Swarm Demo")
    parser.add_argument("--n-drones", type=int, default=4, help="Number of drones")
    parser.add_argument("--duration", type=float, default=10.0, help="Sim duration (s)")
    parser.add_argument("--headless", action="store_true", help="Disable PyBullet GUI")
    args = parser.parse_args()
    run(num_drones=args.n_drones, duration_sec=args.duration, gui=not args.headless)
