<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/physics-PyBullet-orange?style=for-the-badge" alt="PyBullet">
  <img src="https://img.shields.io/badge/gym-Gymnasium-purple?style=for-the-badge" alt="Gymnasium">
</p>

<h1 align="center">🐝 PyBullet Swarm Sim</h1>

<p align="center">
  <strong>Simulate drone swarms in PyBullet — ready to fly in 5 minutes.</strong>
</p>

<p align="center">
  A clean, modular Python library for multi-drone simulation with<br>
  classical PID control · heuristic swarm algorithms (PSO, ACO, Boids) · RL-ready environments
</p>

---

## ✨ Features

| Category | What you get |
|:---|:---|
| **🏗️ Environments** | Gymnasium-compatible envs for hover, formation flight, and RL training |
| **🤖 Agents** | Plug-and-play PID controller + RL agent wrapper (SB3) |
| **🧠 Algorithms** | Reynolds Boids · Formation Planner · PSO · ACO · Consensus |
| **📊 Visualization** | 3-D trajectory plots · real-time GUI · GIF export |
| **🔧 Physics** | Rigid body + ground effect + drag + downwash models |
| **🎓 Examples** | 4 runnable demos — copy-paste and go |

---

## 🚀 Quick Start

### Install

```bash
pip install pybullet-swarm-sim
```

Or install from source:

```bash
git clone https://github.com/pybullet-swarm-sim/pybullet-swarm-sim.git
cd pybullet-swarm-sim
pip install -e .
```

### Your First Swarm (8 lines)

```python
import swarm_sim
import numpy as np

env = swarm_sim.make("HoverSwarm-v0", num_drones=4, gui=True)
obs, info = env.reset()

for _ in range(1000):
    action = np.full((4, 4), env.HOVER_RPM)  # hover thrust
    obs, reward, terminated, truncated, info = env.step(action)

env.close()
```

---

## 📦 Runnable Examples

Every example works out of the box — no config files, no setup scripts.

### 🔹 Formation Flight (V-shape, 8 drones)

```bash
python -m swarm_sim.examples.formation_flight --n-drones 8 --formation v --gui
```

### 🔹 Boids Flocking (12 drones)

```bash
python -m swarm_sim.examples.flocking --n-drones 12 --gui
```

### 🔹 Hover Swarm (sanity check)

```bash
python -m swarm_sim.examples.hover_swarm --n-drones 4 --gui
```

### 🔹 RL Training (PPO hover)

```bash
pip install pybullet-swarm-sim[rl]
python -m swarm_sim.examples.rl_hover --train --timesteps 100000
python -m swarm_sim.examples.rl_hover --play --model-path ppo_hover --gui
```

---

## 🧠 Swarm Algorithms

### Reynolds Boids (Flocking)

```python
from swarm_sim.algorithms.flocking import FlockingAlgorithm

flock = FlockingAlgorithm(
    num_drones=10,
    r_separation=0.3,   # repel when closer than 30 cm
    r_alignment=1.0,     # match velocity within 1 m
    r_cohesion=1.5,      # flock together within 1.5 m
)
velocity_targets = flock.compute(positions, velocities)
```

### Particle Swarm Optimization (PSO)

```python
from swarm_sim.algorithms.pso import PSOAlgorithm

pso = PSOAlgorithm(num_drones=10, w=0.7, c1=1.5, c2=1.5)
velocity_targets = pso.compute(positions, velocities, fitness_values)
print(f"Best position found: {pso.global_best_position}")
```

### Ant Colony Optimization (ACO)

```python
from swarm_sim.algorithms.aco import ACOPathPlanner

aco = ACOPathPlanner(grid_size=20, num_drones=6)
next_waypoints = aco.compute(positions, goal=np.array([5, 5, 1]))
```

### Consensus (Rendezvous / Coverage)

```python
from swarm_sim.algorithms.consensus import ConsensusAlgorithm

consensus = ConsensusAlgorithm(mode="rendezvous", gain=0.5)
velocity_targets = consensus.compute(positions, adjacency_matrix)
```

### Formation Planner

```python
from swarm_sim.algorithms.formation import FormationPlanner
from swarm_sim.utils.enums import FormationType

planner = FormationPlanner()
offsets = planner.compute_offsets(FormationType.HELIX, num_drones=10, spacing=0.5)
```

---

## 🏗️ Architecture

```
pybullet-swarm-sim/
├── swarm_sim/
│   ├── envs/                    # Gymnasium environments
│   │   ├── base_swarm_env.py    # ← Core: PyBullet + multi-drone physics
│   │   ├── hover_swarm_env.py   # Hover at fixed positions
│   │   ├── formation_env.py     # Track a moving formation
│   │   └── rl_swarm_env.py      # Normalized obs/actions for SB3
│   ├── agents/                  # Per-drone controllers
│   │   ├── base_agent.py        # Abstract interface
│   │   ├── pid_agent.py         # Cascaded PID (position → attitude → RPM)
│   │   └── rl_agent.py          # Stable-Baselines3 policy wrapper
│   ├── algorithms/              # Swarm intelligence
│   │   ├── flocking.py          # Reynolds boids
│   │   ├── formation.py         # Geometric formation planner
│   │   ├── consensus.py         # Distributed consensus
│   │   ├── pso.py               # Particle Swarm Optimization
│   │   └── aco.py               # Ant Colony Optimization
│   ├── utils/                   # Logging, plotting, sync
│   ├── assets/                  # URDF drone models
│   └── examples/                # Runnable demos
├── tests/                       # Pytest suite
├── pyproject.toml               # Package config
└── README.md
```

---

## 🔧 Configuration

### Available Environments

| Environment | Description | Use Case |
|:---|:---|:---|
| `BaseSwarm-v0` | Raw multi-drone physics | Custom controllers |
| `HoverSwarm-v0` | Hover at target positions | PID testing, baseline |
| `Formation-v0` | Track a moving formation | Coordination demos |

### Drone Models

| Model | Weight | Config |
|:---|:---|:---|
| `CF2X` | 27 g | Crazyflie 2.x (X-config) |
| `CF2P` | 27 g | Crazyflie 2.x (+-config) |

### Physics Modes

| Mode | Description |
|:---|:---|
| `PYB` | Base rigid-body dynamics |
| `PYB_GND` | + ground effect |
| `PYB_DRAG` | + aerodynamic drag |
| `PYB_DW` | + rotor downwash |
| `PYB_GND_DRAG_DW` | All effects (most realistic) |

### Formation Shapes

`LINE` · `V` · `GRID` · `RING` · `HELIX`

---

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Code style (Black + Ruff)
- How to add new algorithms
- How to add new drone models

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <strong>⭐ If this project helps your research, give it a star!</strong><br>
  Built with 🐝 by the PyBullet Swarm Sim community
</p>
