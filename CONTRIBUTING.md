# Contributing to PyBullet Swarm Sim

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/pybullet-swarm-sim/pybullet-swarm-sim.git
cd pybullet-swarm-sim

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install in editable mode with dev + RL dependencies
pip install -e ".[dev,rl]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

We use **Black** for formatting and **Ruff** for linting:

```bash
black swarm_sim/ tests/
ruff check swarm_sim/ tests/
```

## Pull Request Checklist

- [ ] Code passes `pytest tests/ -v`
- [ ] Code is formatted with `black`
- [ ] Docstrings follow NumPy-style
- [ ] New features include a test
- [ ] Examples still run: `python -m swarm_sim.examples.hover_swarm`

## Adding a New Swarm Algorithm

1. Create `swarm_sim/algorithms/your_algorithm.py`
2. Subclass `BaseAlgorithm` and implement `compute(state: SwarmState)`, returning `(N, 3)` velocity targets. Read what you need off the state, e.g. `state.positions`, `state.velocities`, `state.neighbor_graph`, `state.targets`, or `state.sensor_readings["..."]`
3. Add an example in `swarm_sim/examples/`
4. Add tests in `tests/test_algorithms.py`
5. Update `swarm_sim/__init__.py` to export the new class

## Adding a New Drone Model

1. Place the `.urdf` and `.dae` files in `swarm_sim/assets/`
2. Add an entry to `DroneModel` in `swarm_sim/utils/enums.py`
3. Verify with: `python -m swarm_sim.examples.hover_swarm --n-drones 1 --gui`

## Reporting Issues

Please include:
- Python version (`python --version`)
- OS and PyBullet version
- Minimal reproduction script
- Full error traceback
