"""
PyBullet Swarm Sim — Simulate drone swarms in PyBullet.

A clean, modular Python library for multi-drone simulation with
classical control, heuristic swarm algorithms, and RL-ready environments.

Quick Start
-----------
>>> import swarm_sim
>>> env = swarm_sim.make("HoverSwarm-v0", num_drones=4, gui=True)
>>> obs, info = env.reset()
>>> for _ in range(1000):
...     actions = env.action_space.sample()
...     obs, reward, terminated, truncated, info = env.step(actions)
>>> env.close()
"""

__version__ = "0.1.0"
__author__ = "PyBullet Swarm Sim Contributors"

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.envs.hover_swarm_env import HoverSwarmEnv
from swarm_sim.envs.formation_env import FormationEnv

from swarm_sim.agents.pid_agent import PIDAgent
from swarm_sim.agents.base_agent import BaseAgent

from swarm_sim.algorithms.flocking import FlockingAlgorithm
from swarm_sim.algorithms.formation import FormationPlanner
from swarm_sim.algorithms.consensus import ConsensusAlgorithm
from swarm_sim.algorithms.pso import PSOAlgorithm
from swarm_sim.algorithms.aco import ACOPathPlanner

from swarm_sim.utils.enums import DroneModel, Physics, FormationType


def make(env_id: str, **kwargs):
    """Convenience factory to create swarm environments by name.

    Parameters
    ----------
    env_id : str
        One of ``"HoverSwarm-v0"``, ``"Formation-v0"``, ``"BaseSwarm-v0"``.
    **kwargs
        Forwarded to the environment constructor (``num_drones``, ``gui``, etc.).

    Returns
    -------
    BaseSwarmEnv
        An instantiated Gymnasium-compatible swarm environment.

    Examples
    --------
    >>> env = swarm_sim.make("HoverSwarm-v0", num_drones=8, gui=True)
    """
    registry = {
        "BaseSwarm-v0": BaseSwarmEnv,
        "HoverSwarm-v0": HoverSwarmEnv,
        "Formation-v0": FormationEnv,
    }
    if env_id not in registry:
        raise ValueError(
            f"Unknown env_id '{env_id}'. Available: {list(registry.keys())}"
        )
    return registry[env_id](**kwargs)
