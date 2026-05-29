"""Tests for per-drone agents."""

import numpy as np
import pytest

from swarm_sim.agents.pid_agent import PIDAgent
from swarm_sim.envs.base_swarm_env import BaseSwarmEnv


class TestPIDAgent:
    """Tests for the PID controller agent."""

    def test_compute_action_shape(self):
        agent = PIDAgent()
        obs = np.zeros(20)
        obs[2] = 0.1  # z position
        target = np.array([0.0, 0.0, 1.0])
        rpm = agent.compute_action(obs, target)
        assert rpm.shape == (4,), f"Expected (4,), got {rpm.shape}"

    def test_rpm_positive(self):
        agent = PIDAgent()
        obs = np.zeros(20)
        obs[2] = 0.1
        # Set quaternion to identity [0, 0, 0, 1]
        obs[6] = 1.0
        target = np.array([0.0, 0.0, 1.0])
        rpm = agent.compute_action(obs, target)
        assert np.all(rpm >= 0), "RPMs must be non-negative"

    def test_hover_convergence(self):
        """Simulate 5 seconds of PID hover and check final error < 0.15 m."""
        env = BaseSwarmEnv(num_drones=1, gui=False, ctrl_freq=48, pyb_freq=240)
        env.reset()
        agent = PIDAgent(
            kf=env.KF, km=env.KM, mass=env.M, max_rpm=env.MAX_RPM
        )
        target = np.array([0.0, 0.0, 1.0])
        dt = 1 / 48

        for _ in range(5 * 48):  # 5 seconds at 48 Hz
            state = env.get_drone_state(0)
            rpm = agent.compute_action(state, target, dt=dt)
            env.step(rpm.reshape(1, 4))

        final_pos = env.pos[0]
        error = np.linalg.norm(final_pos - target)
        env.close()
        assert error < 0.15, f"Final hover error {error:.4f} m exceeds 0.15 m"

    def test_reset_clears_integrators(self):
        agent = PIDAgent()
        agent._integral_pos = np.array([1.0, 2.0, 3.0])
        agent.reset()
        assert np.allclose(agent._integral_pos, 0)
