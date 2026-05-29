"""
RL Hover Training — train a PPO agent to hover using Stable-Baselines3.

Requires the ``[rl]`` optional dependency group:

    pip install pybullet-swarm-sim[rl]

Usage
-----
    python -m swarm_sim.examples.rl_hover --train --timesteps 100000
    python -m swarm_sim.examples.rl_hover --play --model-path ppo_hover.zip --gui
"""

from __future__ import annotations

import argparse
from pathlib import Path


def train(timesteps: int = 100_000, save_path: str = "ppo_hover"):
    """Train a PPO agent on the RL hover environment.

    Parameters
    ----------
    timesteps : int
        Total training timesteps.
    save_path : str
        Where to save the trained model (without extension).
    """
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_util import make_vec_env
    except ImportError:
        raise ImportError(
            "stable-baselines3 is required.  Install with:\n"
            "  pip install pybullet-swarm-sim[rl]"
        )

    from swarm_sim.envs.rl_swarm_env import RLSwarmEnv

    print(f"[rl_hover] Training PPO for {timesteps:,} timesteps …")

    env = RLSwarmEnv(num_drones=1, gui=False, ctrl_freq=48, pyb_freq=240)

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        tensorboard_log="./tb_logs/",
    )
    model.learn(total_timesteps=timesteps)
    model.save(save_path)
    env.close()

    print(f"[rl_hover] Model saved to {save_path}.zip")


def play(model_path: str = "ppo_hover", gui: bool = True, episodes: int = 3):
    """Load a trained model and visualise its performance.

    Parameters
    ----------
    model_path : str
        Path to the saved SB3 model.
    gui : bool
        Open the PyBullet viewer.
    episodes : int
        Number of rollout episodes.
    """
    try:
        from stable_baselines3 import PPO
    except ImportError:
        raise ImportError(
            "stable-baselines3 is required.  Install with:\n"
            "  pip install pybullet-swarm-sim[rl]"
        )

    import numpy as np
    from swarm_sim.envs.rl_swarm_env import RLSwarmEnv
    from swarm_sim.utils.viz import sync
    import time

    env = RLSwarmEnv(num_drones=1, gui=gui, ctrl_freq=48, pyb_freq=240)
    model = PPO.load(model_path)

    for ep in range(episodes):
        obs, info = env.reset()
        total_reward = 0.0
        start = time.time()

        for step in range(1000):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward

            if gui:
                sync(step, start, 1 / 48)

            if terminated or truncated:
                break

        print(f"[rl_hover] Episode {ep + 1}: reward={total_reward:.2f}, "
              f"final_dist={info['distance']:.4f} m")

    env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RL Hover Demo")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--train", action="store_true", help="Train a PPO agent")
    group.add_argument("--play", action="store_true", help="Play a trained agent")
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--model-path", type=str, default="ppo_hover")
    parser.add_argument("--headless", action="store_true", help="Disable GUI during playback")
    parser.add_argument("--episodes", type=int, default=3)
    args = parser.parse_args()

    if args.train:
        train(timesteps=args.timesteps, save_path=args.model_path)
    else:
        play(model_path=args.model_path, gui=not args.headless, episodes=args.episodes)
