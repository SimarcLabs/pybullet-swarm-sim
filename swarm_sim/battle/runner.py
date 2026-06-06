"""
Battle Runner — subprocess orchestrator for swarm-vs-swarm combat.

The key insight: existing algorithms are cooperative, not combative.
They produce swarming patterns (flock, converge, search) but don't know
about enemies. The runner solves this by:

1. Setting each algorithm's TARGET to the enemy centroid so the swarm
   naturally moves toward the opposition using its own movement pattern.
2. Adding the algorithm's swarming velocity ON TOP of the attack vector
   so you see the algorithm's characteristic pattern during the charge.

This means:
- Boids charge in formation (cohesive flock rushing at enemies)
- PSO converges on the enemy centroid (particle cloud collapse)
- Consensus rendezvous at enemy centroid (distributed convergence attack)
- APF is attracted to enemy centroid with inter-drone repulsion
- ABC sends scouts to find enemies, foragers swarm in
- Voronoi surrounds enemies from all angles

Usage
-----
python -m swarm_sim.battle.runner \
    --algo-alpha flocking --algo-bravo pso \
    --drones-alpha 10 --drones-bravo 10 \
    --duration 20 --job-id battle-abc123
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from swarm_sim.agents.pid_agent import PIDAgent
from swarm_sim.envs.battle_env import BattleSwarmEnv
from swarm_sim.battle.scoring import compute_battle_result
from swarm_sim.core.state import SwarmState

# Algorithms
from swarm_sim.algorithms.flocking import FlockingAlgorithm
from swarm_sim.algorithms.consensus import ConsensusAlgorithm
from swarm_sim.algorithms.pso import PSOAlgorithm
from swarm_sim.algorithms.aco import ACOPathPlanner
from swarm_sim.algorithms.apf import APFAlgorithm
from swarm_sim.algorithms.abc import ABCAlgorithm
from swarm_sim.algorithms.voronoi_coverage import VoronoiCoverageAlgorithm
from swarm_sim.algorithms.marl import MARLAlgorithm


ALGO_DISPLAY_NAMES = {
    "flocking": "Reynolds Boids",
    "pso": "PSO Search",
    "aco": "ACO Path Planning",
    "consensus": "Consensus",
    "apf": "Potential Fields",
    "abc": "Artificial Bee Colony",
    "voronoi": "Voronoi Coverage",
    "marl": "MARL (PPO)",
}


def make_algorithm(algo_name: str, num_drones: int):
    """Instantiate an algorithm by name."""
    if algo_name == "flocking":
        return FlockingAlgorithm(num_drones=num_drones)
    elif algo_name == "pso":
        return PSOAlgorithm(num_drones=num_drones)
    elif algo_name == "aco":
        return ACOPathPlanner(grid_size=10, num_drones=num_drones)
    elif algo_name == "consensus":
        return ConsensusAlgorithm(mode="rendezvous", gain=0.5)
    elif algo_name == "apf":
        return APFAlgorithm(num_drones=num_drones)
    elif algo_name == "abc":
        return ABCAlgorithm(num_drones=num_drones)
    elif algo_name == "voronoi":
        return VoronoiCoverageAlgorithm(num_drones=num_drones)
    elif algo_name == "marl":
        model_path = Path("models") / f"marl_ppo_{num_drones}d.zip"
        return MARLAlgorithm(
            num_drones=num_drones,
            model_path=str(model_path) if model_path.exists() else None,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algo_name}")


def safe_compute(algorithm, state, algo_name, num_alive):
    """Safely compute algorithm velocities, recreating on shape mismatch.

    Stateful algorithms (PSO, ABC) maintain internal arrays sized to the
    initial drone count. When drones are eliminated, the array shapes
    mismatch. This wrapper catches the error and creates a fresh algorithm
    instance with the correct size.

    Returns (velocity_array, possibly_new_algorithm).
    """
    try:
        vel = algorithm.compute(state)
        return vel, algorithm
    except (ValueError, IndexError):
        # Shape mismatch — recreate algorithm with current drone count
        new_algo = make_algorithm(algo_name, num_alive)
        # Copy target if applicable
        if hasattr(algorithm, "target") and hasattr(new_algo, "target"):
            new_algo.target = algorithm.target.copy()
        try:
            vel = new_algo.compute(state)
            return vel, new_algo
        except Exception:
            return np.zeros_like(state.positions), new_algo


def prepare_battle_state(
    own_positions: np.ndarray,
    own_velocities: np.ndarray,
    enemy_positions: np.ndarray,
    algo_name: str,
) -> SwarmState:
    """Build a SwarmState that directs an algorithm toward the enemy.

    Different algorithms use different fields:
    - FlockingAlgorithm: uses positions/velocities among teammates,
      but we need to inject the enemy centroid as a cohesion attractor
    - PSOAlgorithm: uses sensor_readings['fitness'] — we compute
      fitness as closeness to the nearest enemy
    - ConsensusAlgorithm: uses neighbor_graph — we build full connectivity
    - APFAlgorithm: uses self.target (set on the instance)
    - ABCAlgorithm: uses self.target (set on the instance)
    - VoronoiAlgorithm: uses positions for Voronoi tessellation
    """
    N = own_positions.shape[0]
    if N == 0:
        return None

    # Compute fitness for PSO: higher when closer to nearest enemy
    fitness = np.zeros(N)
    if len(enemy_positions) > 0:
        for i in range(N):
            dists = np.linalg.norm(enemy_positions - own_positions[i], axis=1)
            min_dist = np.min(dists)
            fitness[i] = 1.0 / (min_dist + 0.1)  # inverse distance = fitness

    # Full connectivity graph for consensus
    adj = np.ones((N, N))
    np.fill_diagonal(adj, 0)

    return SwarmState(
        positions=own_positions,
        velocities=own_velocities,
        orientations=np.zeros((N, 3)),
        angular_velocities=np.zeros((N, 3)),
        neighbor_graph=adj,
        targets=enemy_positions,
        active_drones_mask=np.ones(N, dtype=bool),
        battery_levels=np.ones(N),
        drone_status=["nominal"] * N,
        sensor_readings={"fitness": fitness},
    )


def compute_attack_vectors(
    own_positions: np.ndarray,
    enemy_positions: np.ndarray,
    attack_speed: float = 1.5,
) -> np.ndarray:
    """Compute velocity vectors that direct each drone toward nearest enemy.

    Each drone targets the closest enemy drone specifically, creating
    distributed targeting instead of everyone converging on the centroid.
    Speed is high at range to close distance, and stays strong up close
    to ensure elimination velocity threshold is met.
    """
    N = own_positions.shape[0]
    attack_vel = np.zeros((N, 3))

    if len(enemy_positions) == 0:
        return attack_vel

    for i in range(N):
        # Find nearest enemy
        dists = np.linalg.norm(enemy_positions - own_positions[i], axis=1)
        nearest_idx = np.argmin(dists)
        nearest_pos = enemy_positions[nearest_idx]

        # Vector toward nearest enemy
        diff = nearest_pos - own_positions[i]
        dist = np.linalg.norm(diff)

        if dist > 0.01:
            direction = diff / dist
            # Full speed at all ranges — drones charge aggressively
            # Slight boost when very close to ensure kill speed threshold
            speed = attack_speed * (1.0 + 0.5 / (dist + 0.3))
            speed = min(speed, attack_speed * 2.0)  # cap at 2x
            attack_vel[i] = direction * speed

    return attack_vel


def run_battle(
    algo_alpha: str,
    algo_bravo: str,
    drones_alpha: int,
    drones_bravo: int,
    duration: float,
    job_id: str,
):
    """Run a full swarm-vs-swarm battle and stream results."""
    ctrl_freq = 48
    steps = int(duration * ctrl_freq)
    dt = 1.0 / ctrl_freq

    out_dir = Path("results") / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print("PROGRESS:0%")
    print(f"Initializing battle: {algo_alpha.upper()} vs {algo_bravo.upper()}")
    print(f"  Alpha: {drones_alpha} drones | Bravo: {drones_bravo} drones")
    print(f"  Duration: {duration}s | Arena: 10x10m")

    # --- Create Environment ---
    env = BattleSwarmEnv(
        num_drones_alpha=drones_alpha,
        num_drones_bravo=drones_bravo,
        gui=True,
        ctrl_freq=ctrl_freq,
    )
    obs, info = env.reset()

    # --- Create Algorithms ---
    algorithm_alpha = make_algorithm(algo_alpha, drones_alpha)
    algorithm_bravo = make_algorithm(algo_bravo, drones_bravo)

    # Point target-based algorithms at the enemy spawn
    # Alpha spawns left (-x), Bravo spawns right (+x)
    # So Alpha's target is right side, Bravo's target is left side
    bravo_centroid = np.mean(env.pos[env.bravo_indices], axis=0)
    alpha_centroid = np.mean(env.pos[env.alpha_indices], axis=0)

    # Set initial targets for algorithms that have a .target attribute
    if hasattr(algorithm_alpha, "target"):
        algorithm_alpha.target = bravo_centroid.copy()
    if hasattr(algorithm_bravo, "target"):
        algorithm_bravo.target = alpha_centroid.copy()

    # --- Create PID Agents (one per drone) ---
    total_drones = drones_alpha + drones_bravo
    agents = [
        PIDAgent(
            drone_id=i, kf=env.KF, km=env.KM,
            mass=env.M, max_rpm=env.MAX_RPM,
        )
        for i in range(total_drones)
    ]

    # --- Battle Loop ---
    kill_log_dicts = []
    timeline = []
    start_time = time.time()
    last_print = 0
    last_battle_update = 0
    sim_time = 0.0

    print("Battle started!")

    for step in range(steps):
        sim_time = step * dt
        actions = np.zeros((total_drones, 4))

        # --- Get alive indices ---
        alive_alpha = env.get_alive_indices("alpha")
        alive_bravo = env.get_alive_indices("bravo")

        # --- Get current positions ---
        alpha_positions = env.pos[alive_alpha] if len(alive_alpha) > 0 else np.zeros((0, 3))
        alpha_velocities = env.vel[alive_alpha] if len(alive_alpha) > 0 else np.zeros((0, 3))
        bravo_positions = env.pos[alive_bravo] if len(alive_bravo) > 0 else np.zeros((0, 3))
        bravo_velocities = env.vel[alive_bravo] if len(alive_bravo) > 0 else np.zeros((0, 3))

        # --- Update algorithm targets to track living enemies ---
        if len(bravo_positions) > 0 and hasattr(algorithm_alpha, "target"):
            algorithm_alpha.target = np.mean(bravo_positions, axis=0)
        if len(alpha_positions) > 0 and hasattr(algorithm_bravo, "target"):
            algorithm_bravo.target = np.mean(alpha_positions, axis=0)

        # --- Compute Alpha team actions ---
        if len(alive_alpha) > 0 and len(alive_bravo) > 0:
            try:
                state_alpha = prepare_battle_state(
                    alpha_positions, alpha_velocities,
                    bravo_positions, algo_alpha
                )

                # Get algorithm's swarming velocity (safe against drone count changes)
                algo_vel, algorithm_alpha = safe_compute(
                    algorithm_alpha, state_alpha, algo_alpha, len(alive_alpha)
                )
                if algo_vel is None:
                    algo_vel = np.zeros_like(alpha_positions)

                # Get attack vector toward nearest enemy
                attack_vel = compute_attack_vectors(
                    alpha_positions, bravo_positions, attack_speed=1.5
                )

                # Blend: algorithm provides formation/pattern, attack provides direction
                # The algorithm's velocity is the "how they move"
                # The attack vector is the "where they move"
                combined_vel = algo_vel * 0.3 + attack_vel * 0.7

                for local_i, global_i in enumerate(alive_alpha):
                    if local_i < len(combined_vel):
                        target_pos = env.pos[global_i] + combined_vel[local_i] * dt * 15
                        target_pos[2] = np.clip(target_pos[2], 0.5, 2.5)
                        drone_state = env.get_drone_state(global_i)
                        actions[global_i] = agents[global_i].compute_action(
                            drone_state, target_pos, dt=dt
                        )
            except Exception as e:
                print(f"Alpha algorithm error: {e}")

        # --- Compute Bravo team actions ---
        if len(alive_bravo) > 0 and len(alive_alpha) > 0:
            try:
                state_bravo = prepare_battle_state(
                    bravo_positions, bravo_velocities,
                    alpha_positions, algo_bravo
                )

                algo_vel, algorithm_bravo = safe_compute(
                    algorithm_bravo, state_bravo, algo_bravo, len(alive_bravo)
                )
                if algo_vel is None:
                    algo_vel = np.zeros_like(bravo_positions)

                attack_vel = compute_attack_vectors(
                    bravo_positions, alpha_positions, attack_speed=1.5
                )

                combined_vel = algo_vel * 0.3 + attack_vel * 0.7

                for local_i, global_i in enumerate(alive_bravo):
                    if local_i < len(combined_vel):
                        target_pos = env.pos[global_i] + combined_vel[local_i] * dt * 15
                        target_pos[2] = np.clip(target_pos[2], 0.5, 2.5)
                        drone_state = env.get_drone_state(global_i)
                        actions[global_i] = agents[global_i].compute_action(
                            drone_state, target_pos, dt=dt
                        )
            except Exception as e:
                print(f"Bravo algorithm error: {e}")

        # --- Step physics ---
        obs, reward, terminated, truncated, info = env.step(actions)

        # --- Check eliminations ---
        new_kills = env.check_eliminations(sim_time)
        for kill in new_kills:
            kd = {
                "time": round(kill.timestamp, 2),
                "killer": int(kill.killer_id),
                "victim": int(kill.victim_id),
                "killer_team": kill.killer_team,
                "victim_team": kill.victim_team,
                "position": kill.position.tolist(),
            }
            kill_log_dicts.append(kd)
            print(f"KILL:{json.dumps(kd)}")

        # --- Sync to real-time ---
        elapsed = time.time() - start_time
        expected = (step + 1) * dt
        if expected > elapsed:
            time.sleep(expected - elapsed)

        # --- Stream battle status (every 200ms) ---
        now = time.time()
        if now - last_battle_update > 0.2:
            status = env.get_battle_status()
            status["time"] = round(sim_time, 2)

            # Collect positions for live replay
            all_pos = []
            for i in range(total_drones):
                if env.alive_mask[i]:
                    all_pos.append({
                        "id": i,
                        "team": env.team_labels[i],
                        "x": round(float(env.pos[i, 0]), 3),
                        "y": round(float(env.pos[i, 1]), 3),
                    })
            status["positions"] = all_pos

            print(f"BATTLE:{json.dumps(status)}")
            last_battle_update = now

            # Record timeline snapshot
            timeline.append({
                "time": round(sim_time, 2),
                "alpha_alive": status["alpha_alive"],
                "bravo_alive": status["bravo_alive"],
                "alpha_kills": status["alpha_kills"],
                "bravo_kills": status["bravo_kills"],
            })

        # --- Progress reporting ---
        if now - last_print > 0.1:
            pct = int((step / steps) * 100)
            print(f"PROGRESS:{pct}%")
            last_print = now

        # --- Check early termination ---
        if env.is_battle_over():
            print("Battle ended — one team eliminated!")
            break

    # --- Compute final results ---
    final_status = env.get_battle_status()

    env.close()

    result = compute_battle_result(
        algo_alpha=algo_alpha,
        algo_bravo=algo_bravo,
        alpha_initial=drones_alpha,
        bravo_initial=drones_bravo,
        alpha_survivors=final_status["alpha_alive"],
        bravo_survivors=final_status["bravo_alive"],
        duration=sim_time if step < steps - 1 else duration,
        kill_log=kill_log_dicts,
        timeline=timeline,
    )

    # --- Save results ---
    result_dict = result.to_dict()
    with open(out_dir / "battle_results.json", "w") as f:
        json.dump(result_dict, f, indent=2)

    # Save manifest for history compatibility
    with open(out_dir / "manifest.json", "w") as f:
        json.dump({
            "type": "battle",
            "algo_alpha": algo_alpha,
            "algo_bravo": algo_bravo,
            "drones_alpha": drones_alpha,
            "drones_bravo": drones_bravo,
            "duration": duration,
            "job_id": job_id,
        }, f, indent=2)

    print("PROGRESS:100%")
    print(f"Battle complete — Winner: {result.winner.upper()}")
    print(f"Results saved to {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Battle Runner")
    parser.add_argument("--algo-alpha", required=True)
    parser.add_argument("--algo-bravo", required=True)
    parser.add_argument("--drones-alpha", type=int, required=True)
    parser.add_argument("--drones-bravo", type=int, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()

    sys.stdout.reconfigure(line_buffering=True)

    run_battle(
        algo_alpha=args.algo_alpha,
        algo_bravo=args.algo_bravo,
        drones_alpha=args.drones_alpha,
        drones_bravo=args.drones_bravo,
        duration=args.duration,
        job_id=args.job_id,
    )
