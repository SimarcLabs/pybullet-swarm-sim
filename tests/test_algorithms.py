"""Tests for swarm algorithms."""

import numpy as np
import pytest

from swarm_sim.algorithms.flocking import FlockingAlgorithm
from swarm_sim.algorithms.formation import FormationPlanner
from swarm_sim.algorithms.consensus import ConsensusAlgorithm
from swarm_sim.algorithms.pso import PSOAlgorithm
from swarm_sim.algorithms.aco import ACOPathPlanner
from swarm_sim.core.state import SwarmState
from swarm_sim.utils.enums import FormationType


def make_state(positions, velocities=None, neighbor_graph=None, **kwargs):
    """Build a minimal :class:`SwarmState` for algorithm tests.

    Fields the algorithms under test do not read are filled with zeros, and
    the neighbour graph defaults to fully connected.

    Parameters
    ----------
    positions : array_like
        ``(N, 3)`` drone positions.
    velocities : array_like, optional
        ``(N, 3)`` drone velocities.  Defaults to zeros.
    neighbor_graph : array_like, optional
        ``(N, N)`` adjacency matrix.  Defaults to all-ones (fully connected).
    **kwargs
        Extra ``SwarmState`` fields, e.g. ``targets`` or ``sensor_readings``.

    Returns
    -------
    SwarmState
    """
    positions = np.asarray(positions, dtype=float)
    n = positions.shape[0]
    return SwarmState(
        positions=positions,
        velocities=(
            np.zeros((n, 3)) if velocities is None else np.asarray(velocities, dtype=float)
        ),
        orientations=np.zeros((n, 3)),
        angular_velocities=np.zeros((n, 3)),
        neighbor_graph=(
            np.ones((n, n), dtype=bool) if neighbor_graph is None else np.asarray(neighbor_graph)
        ),
        **kwargs,
    )


class TestFlocking:
    """Tests for the Reynolds boids algorithm."""

    def test_output_shape(self):
        flock = FlockingAlgorithm(num_drones=5)
        pos = np.random.randn(5, 3)
        vel = np.random.randn(5, 3)
        targets = flock.compute(make_state(pos, vel))
        assert targets.shape == (5, 3)

    def test_max_speed_clamped(self):
        flock = FlockingAlgorithm(num_drones=3, max_speed=1.0)
        pos = np.array([[0, 0, 0], [10, 10, 10], [-10, -10, -10]], dtype=float)
        vel = np.zeros((3, 3))
        targets = flock.compute(make_state(pos, vel))
        speeds = np.linalg.norm(targets, axis=1)
        assert np.all(speeds <= 1.0 + 1e-6)

    def test_single_drone(self):
        flock = FlockingAlgorithm(num_drones=1)
        pos = np.array([[0, 0, 1.0]])
        vel = np.array([[0, 0, 0.0]])
        targets = flock.compute(make_state(pos, vel))
        assert np.allclose(targets, 0), "Single drone should produce zero velocity"


class TestFormation:
    """Tests for the formation planner."""

    def test_output_shapes(self):
        planner = FormationPlanner()
        for fmt in FormationType:
            offsets = planner.compute_offsets(fmt, num_drones=6, spacing=0.5)
            assert offsets.shape == (6, 3), f"Failed for {fmt}"

    def test_mean_centred(self):
        planner = FormationPlanner()
        for fmt in FormationType:
            offsets = planner.compute_offsets(fmt, num_drones=8, spacing=1.0)
            mean = offsets.mean(axis=0)
            assert np.allclose(mean, 0, atol=1e-10), (
                f"{fmt}: mean offset should be zero, got {mean}"
            )

    def test_v_formation_has_leader(self):
        planner = FormationPlanner()
        offsets = planner.compute_offsets(FormationType.V, num_drones=5, spacing=1.0)
        # After mean-centring, the lead drone (index 0) should be at the front (max x)
        assert offsets[0, 0] >= offsets[1:, 0].max() - 1e-6


class TestConsensus:
    """Tests for the consensus algorithm."""

    def test_rendezvous_convergence_direction(self):
        alg = ConsensusAlgorithm(num_drones=3, gain=1.0, mode="rendezvous")
        pos = np.array([[0, 0, 1], [2, 0, 1], [1, 2, 1]], dtype=float)
        adj = np.ones((3, 3))
        vel = alg.compute(make_state(pos, neighbor_graph=adj))
        # All drones should move toward each other
        for i in range(3):
            assert np.linalg.norm(vel[i]) > 0, f"Drone {i} should have non-zero velocity"

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="mode must be"):
            ConsensusAlgorithm(mode="invalid")


class TestPSO:
    """Tests for Particle Swarm Optimization."""

    def test_output_shape(self):
        pso = PSOAlgorithm(num_drones=5)
        pos = np.random.randn(5, 3)
        vel = np.random.randn(5, 3)
        fitness = np.random.randn(5)
        targets = pso.compute(make_state(pos, vel, sensor_readings={"fitness": fitness}))
        assert targets.shape == (5, 3)

    def test_global_best_updated(self):
        pso = PSOAlgorithm(num_drones=3)
        pos = np.array([[0, 0, 1], [1, 1, 1], [2, 2, 1]], dtype=float)
        vel = np.zeros((3, 3))
        fitness = np.array([1.0, 5.0, 3.0])
        pso.compute(make_state(pos, vel, sensor_readings={"fitness": fitness}))
        assert pso.global_best_fitness == 5.0
        assert np.allclose(pso.global_best_position, [1, 1, 1])


class TestACO:
    """Tests for Ant Colony Optimization."""

    def test_output_shape(self):
        aco = ACOPathPlanner(grid_size=10, num_drones=4)
        pos = np.random.uniform(-2, 2, size=(4, 3))
        pos[:, 2] = 1.0
        goal = np.array([3, 3, 1.0])
        waypoints = aco.compute(make_state(pos, targets=goal.reshape(1, 3)))
        assert waypoints.shape == (4, 3)

    def test_pheromone_evaporation(self):
        aco = ACOPathPlanner(grid_size=5, rho=0.5)
        initial = aco.pheromone.copy()
        pos = np.array([[0, 0, 1.0]])
        aco.compute(make_state(pos, targets=np.array([[1.0, 1.0, 1.0]])))
        # After one step, most cells should have lower pheromone
        # (evaporation > deposit for most cells)
        assert aco.pheromone.mean() != initial.mean()

    def test_reset(self):
        aco = ACOPathPlanner(grid_size=5)
        aco.pheromone[:] = 999
        aco.reset()
        assert np.allclose(aco.pheromone, 0.1)
