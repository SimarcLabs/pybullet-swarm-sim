"""
Formation Flight — ⭐ primary demo for README.

Flies N drones in a V-formation (or any other shape) using PID control,
with the formation centre advancing along the x-axis.

Usage
-----
    python -m swarm_sim.examples.formation_flight
    python -m swarm_sim.examples.formation_flight --n-drones 8 --formation v --gui
    python -m swarm_sim.examples.formation_flight --formation helix --n-drones 10
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from swarm_sim.envs.formation_env import FormationEnv
from swarm_sim.agents.pid_agent import PIDAgent
from swarm_sim.utils.enums import FormationType
from swarm_sim.utils.logger import SwarmLogger
from swarm_sim.utils.viz import sync


_FORMATION_MAP = {f.value: f for f in FormationType}


def run(
    num_drones: int = 8,
    formation: str = "v",
    duration_sec: float = 15.0,
    gui: bool = True,
    spacing: float = 0.5,
    speed: float = 0.3,
):
    """Run the formation-flight demo.

    Parameters
    ----------
    num_drones : int
        Number of drones.
    formation : str
        One of ``"line"``, ``"v"``, ``"grid"``, ``"ring"``, ``"helix"``.
    duration_sec : float
        Simulation length in seconds.
    gui : bool
        Open the PyBullet viewer.
    spacing : float
        Inter-drone spacing (m).
    speed : float
        Forward speed of the formation centre (m/s).
    """
    fmt = _FORMATION_MAP.get(formation.lower())
    if fmt is None:
        raise ValueError(f"Unknown formation '{formation}'. Choose from {list(_FORMATION_MAP)}")

    ctrl_freq = 48
    env = FormationEnv(
        num_drones=num_drones,
        formation=fmt,
        spacing=spacing,
        forward_speed=speed,
        gui=gui,
        ctrl_freq=ctrl_freq,
        pyb_freq=240,
    )
    obs, info = env.reset()

    agents = [
        PIDAgent(drone_id=i, kf=env.KF, km=env.KM, mass=env.M, max_rpm=env.MAX_RPM)
        for i in range(num_drones)
    ]

    logger = SwarmLogger(
        num_drones=num_drones,
        logging_freq_hz=ctrl_freq,
        duration_sec=int(duration_sec),
    )

    total_steps = int(duration_sec * ctrl_freq)
    start = time.time()

    print(
        f"[formation_flight] {num_drones} drones · {formation.upper()} formation · "
        f"{duration_sec}s · speed={speed} m/s"
    )

    for step in range(total_steps):
        targets = env.get_current_targets()
        actions = np.zeros((num_drones, 4))

        for i in range(num_drones):
            state = env.get_drone_state(i)
            actions[i] = agents[i].compute_action(state, targets[i], dt=1 / ctrl_freq)
            logger.log(drone=i, timestamp=step / ctrl_freq, state=state)

        obs, reward, terminated, truncated, info = env.step(actions)

        if gui:
            sync(step, start, 1 / ctrl_freq)

        if terminated or truncated:
            break

    env.close()

    print(f"\n[formation_flight] Done in {time.time() - start:.1f}s")
    print(f"  Final formation error: {info.get('formation_error', 'N/A'):.4f} m")

    logger.plot_3d(show=gui)
    return logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Formation Flight Demo")
    parser.add_argument("--n-drones", type=int, default=8)
    parser.add_argument("--formation", type=str, default="v",
                        choices=list(_FORMATION_MAP.keys()))
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--headless", action="store_true", help="Disable GUI")
    parser.add_argument("--spacing", type=float, default=0.5)
    parser.add_argument("--speed", type=float, default=0.3)
    args = parser.parse_args()
    run(
        num_drones=args.n_drones,
        formation=args.formation,
        duration_sec=args.duration,
        gui=not args.headless,
        spacing=args.spacing,
        speed=args.speed,
    )
