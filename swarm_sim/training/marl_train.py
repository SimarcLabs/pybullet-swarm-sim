"""
MARL Training Script — trains a shared-parameter PPO policy for swarm coordination.

Can be invoked from the command line or by the dashboard server.

Usage
-----
    python -m swarm_sim.training.marl_train --drones 5 --timesteps 50000
    python -m swarm_sim.training.marl_train --drones 5 --timesteps 50000 --job-id abc123

Output
------
    models/marl_ppo_<drones>d.zip   — the trained model
    PROGRESS:<pct>%                 — progress updates for the dashboard
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def train_marl(
    num_drones: int = 5,
    timesteps: int = 50_000,
    job_id: str = "",
    save_dir: str = "models",
):
    """Train a PPO agent on the MARL swarm environment."""

    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError:
        print("ERROR: stable-baselines3 is required. Install with:")
        print("  pip install pybullet-swarm-sim[rl]")
        sys.exit(1)

    from swarm_sim.envs.marl_env import MARLSwarmEnv

    # Progress callback for dashboard integration
    class ProgressCallback(BaseCallback):
        def __init__(self, total_timesteps: int):
            super().__init__()
            self.total = total_timesteps
            self.last_pct = -1

        def _on_step(self) -> bool:
            pct = int((self.num_timesteps / self.total) * 100)
            if pct != self.last_pct and pct % 5 == 0:
                print(f"PROGRESS:{pct}%")
                self.last_pct = pct
            return True

    print(f"[MARL] Initialising training: {num_drones} drones, {timesteps:,} timesteps")
    print("PROGRESS:0%")

    env = MARLSwarmEnv(
        num_drones=num_drones,
        gui=False,
        ctrl_freq=48,
        pyb_freq=240,
        max_steps=500,
    )

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        tensorboard_log="./tb_logs/marl/",
    )

    callback = ProgressCallback(timesteps)
    start = time.time()
    model.learn(total_timesteps=timesteps, callback=callback)
    elapsed = time.time() - start

    # Save model
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)
    model_file = save_path / f"marl_ppo_{num_drones}d"
    model.save(str(model_file))

    env.close()

    print("PROGRESS:100%")
    print(f"[MARL] Training complete in {elapsed:.1f}s")
    print(f"[MARL] Model saved to {model_file}.zip")

    # If launched from dashboard, write a manifest
    if job_id:
        import json
        result_dir = Path("results") / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "type": "marl_training",
            "num_drones": num_drones,
            "timesteps": timesteps,
            "elapsed_seconds": round(elapsed, 1),
            "model_path": str(model_file) + ".zip",
        }
        with open(result_dir / "marl_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MARL Swarm Training")
    parser.add_argument("--drones", type=int, default=5)
    parser.add_argument("--timesteps", type=int, default=50_000)
    parser.add_argument("--job-id", type=str, default="")
    parser.add_argument("--save-dir", type=str, default="models")
    args = parser.parse_args()

    sys.stdout.reconfigure(line_buffering=True)

    train_marl(
        num_drones=args.drones,
        timesteps=args.timesteps,
        job_id=args.job_id,
        save_dir=args.save_dir,
    )
