"""Tests for swarm environments."""

import numpy as np
import pytest

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.envs.hover_swarm_env import HoverSwarmEnv
from swarm_sim.envs.formation_env import FormationEnv
from swarm_sim.utils.enums import FormationType


class TestBaseSwarmEnv:
    """Tests for the base multi-drone environment."""

    def test_create_and_close(self):
        env = BaseSwarmEnv(num_drones=2, gui=False)
        obs, info = env.reset()
        env.close()

    def test_reset_shape(self):
        env = BaseSwarmEnv(num_drones=3, gui=False)
        obs, info = env.reset()
        assert obs.shape == (3, 20), f"Expected (3, 20), got {obs.shape}"
        env.close()

    def test_step_runs(self):
        env = BaseSwarmEnv(num_drones=2, gui=False)
        obs, _ = env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs.shape == (2, 20)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        env.close()

    def test_num_drones_configurable(self):
        for n in [1, 4, 8]:
            env = BaseSwarmEnv(num_drones=n, gui=False)
            obs, _ = env.reset()
            assert obs.shape[0] == n
            env.close()

    def test_get_drone_state(self):
        env = BaseSwarmEnv(num_drones=2, gui=False)
        env.reset()
        state = env.get_drone_state(0)
        assert state.shape == (20,)
        env.close()

    def test_adjacency_matrix(self):
        env = BaseSwarmEnv(num_drones=3, gui=False, neighbourhood_radius=10.0)
        env.reset()
        adj = env.get_adjacency_matrix()
        assert adj.shape == (3, 3)
        assert np.allclose(adj, adj.T), "Adjacency matrix should be symmetric"
        env.close()


class TestHoverSwarmEnv:
    """Tests for the hover environment."""

    def test_reward_negative(self):
        env = HoverSwarmEnv(num_drones=2, gui=False)
        env.reset()
        action = np.zeros((2, 4))
        _, reward, _, _, _ = env.step(action)
        assert reward <= 0, "Hover reward should be non-positive"
        env.close()

    def test_info_contains_distances(self):
        env = HoverSwarmEnv(num_drones=2, gui=False)
        env.reset()
        action = env.action_space.sample()
        _, _, _, _, info = env.step(action)
        assert "mean_distance" in info
        assert "per_drone_distance" in info
        env.close()


class TestFormationEnv:
    """Tests for the formation environment."""

    def test_targets_correct_count(self):
        env = FormationEnv(
            num_drones=5, formation=FormationType.V, gui=False
        )
        env.reset()
        targets = env.get_current_targets()
        assert targets.shape == (5, 3)
        env.close()

    def test_different_formations(self):
        for fmt in FormationType:
            env = FormationEnv(num_drones=4, formation=fmt, gui=False)
            env.reset()
            targets = env.get_current_targets()
            assert targets.shape == (4, 3), f"Failed for {fmt}"
            env.close()
