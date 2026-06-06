"""
Battle Swarm Environment — Two-team drone combat in PyBullet.

Manages two teams of drones in a shared physics world with kinetic
elimination mechanics. Drones are eliminated when an enemy gets
within `r_kill` distance at a closing speed above `v_min_kill`.

Example
-------
>>> from swarm_sim.envs.battle_env import BattleSwarmEnv
>>> env = BattleSwarmEnv(num_drones_alpha=5, num_drones_bravo=5, gui=True)
>>> obs, info = env.reset()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pybullet as p

from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
from swarm_sim.core.state import SwarmState
from swarm_sim.utils.enums import DroneModel, Physics


@dataclass
class KillEvent:
    """Record of a single drone elimination."""
    timestamp: float
    killer_id: int
    victim_id: int
    killer_team: str
    victim_team: str
    position: np.ndarray  # where the kill happened


class BattleSwarmEnv(BaseSwarmEnv):
    """Two-team battle environment with kinetic elimination mechanics.

    Parameters
    ----------
    num_drones_alpha : int
        Number of drones on Team Alpha (red).
    num_drones_bravo : int
        Number of drones on Team Bravo (blue).
    r_kill : float
        Elimination radius in meters. An enemy within this distance
        is eligible for elimination.
    v_min_kill : float
        Minimum closing speed (m/s) required for a kill to register.
    arena_size : float
        Half-width of the square arena in meters.
    spawn_altitude : float
        Starting altitude for all drones.
    """

    def __init__(
        self,
        num_drones_alpha: int = 5,
        num_drones_bravo: int = 5,
        r_kill: float = 0.4,
        v_min_kill: float = 0.15,
        arena_size: float = 5.0,
        spawn_altitude: float = 1.0,
        drone_model: DroneModel = DroneModel.CF2X,
        physics: Physics = Physics.PYB,
        pyb_freq: int = 240,
        ctrl_freq: int = 48,
        gui: bool = False,
        **kwargs,
    ):
        self.num_alpha = num_drones_alpha
        self.num_bravo = num_drones_bravo
        self.r_kill = r_kill
        self.v_min_kill = v_min_kill
        self.arena_size = arena_size
        self.spawn_altitude = spawn_altitude

        total = num_drones_alpha + num_drones_bravo

        # Generate spawn positions — teams on opposite sides
        initial_xyzs = self._generate_spawn_positions(
            num_drones_alpha, num_drones_bravo, arena_size, spawn_altitude
        )

        super().__init__(
            drone_model=drone_model,
            num_drones=total,
            initial_xyzs=initial_xyzs,
            physics=physics,
            pyb_freq=pyb_freq,
            ctrl_freq=ctrl_freq,
            gui=gui,
            **kwargs,
        )

        # Team index ranges
        self.alpha_indices = np.arange(0, num_drones_alpha)
        self.bravo_indices = np.arange(num_drones_alpha, total)

        # Battle state
        self.alive_mask = np.ones(total, dtype=bool)
        self.kill_log: List[KillEvent] = []
        self.team_labels = (
            ["alpha"] * num_drones_alpha + ["bravo"] * num_drones_bravo
        )
        self.battle_start_time = 0.0

    @staticmethod
    def _generate_spawn_positions(
        n_alpha: int, n_bravo: int, arena_size: float, altitude: float
    ) -> np.ndarray:
        """Place teams on opposite sides of the arena."""
        positions = []

        # Alpha spawns on the left side (negative x)
        cols_a = max(1, int(np.ceil(np.sqrt(n_alpha))))
        for i in range(n_alpha):
            row = i // cols_a
            col = i % cols_a
            x = -arena_size * 0.6 + col * 0.4
            y = -((cols_a - 1) * 0.4) / 2 + row * 0.4
            positions.append([x, y, altitude])

        # Bravo spawns on the right side (positive x)
        cols_b = max(1, int(np.ceil(np.sqrt(n_bravo))))
        for i in range(n_bravo):
            row = i // cols_b
            col = i % cols_b
            x = arena_size * 0.6 - col * 0.4
            y = -((cols_b - 1) * 0.4) / 2 + row * 0.4
            positions.append([x, y, altitude])

        return np.array(positions)

    def reset(self, *, seed=None, options=None):
        """Reset the battle — all drones alive, clear kill log."""
        obs, info = super().reset(seed=seed, options=options)
        total = self.num_alpha + self.num_bravo
        self.alive_mask = np.ones(total, dtype=bool)
        self.kill_log = []
        self.battle_start_time = time.time()
        return obs, info

    # ------------------------------------------------------------------
    # Elimination Logic
    # ------------------------------------------------------------------

    def check_eliminations(self, sim_time: float) -> List[KillEvent]:
        """Check for kinetic eliminations between opposing teams.

        Returns a list of new KillEvents that occurred this step.
        """
        new_kills = []
        total = self.NUM_DRONES

        for i in range(total):
            if not self.alive_mask[i]:
                continue
            for j in range(total):
                if i == j or not self.alive_mask[j]:
                    continue
                # Only check cross-team encounters
                if self.team_labels[i] == self.team_labels[j]:
                    continue

                dist = np.linalg.norm(self.pos[i] - self.pos[j])
                if dist > self.r_kill:
                    continue

                # Compute closing speed (relative velocity along the line
                # connecting the two drones)
                direction = self.pos[j] - self.pos[i]
                if dist > 1e-6:
                    direction /= dist
                rel_vel = self.vel[i] - self.vel[j]
                closing_speed = np.dot(rel_vel, direction)

                if closing_speed < self.v_min_kill:
                    continue

                # The faster drone eliminates the slower one
                speed_i = np.linalg.norm(self.vel[i])
                speed_j = np.linalg.norm(self.vel[j])

                if speed_i > speed_j * 1.1:
                    # i kills j
                    kill = KillEvent(
                        timestamp=sim_time,
                        killer_id=i,
                        victim_id=j,
                        killer_team=self.team_labels[i],
                        victim_team=self.team_labels[j],
                        position=self.pos[j].copy(),
                    )
                    new_kills.append(kill)
                    self._eliminate_drone(j)
                elif speed_j > speed_i * 1.1:
                    # j kills i
                    kill = KillEvent(
                        timestamp=sim_time,
                        killer_id=j,
                        victim_id=i,
                        killer_team=self.team_labels[j],
                        victim_team=self.team_labels[i],
                        position=self.pos[i].copy(),
                    )
                    new_kills.append(kill)
                    self._eliminate_drone(i)
                    break  # i is dead, stop checking its interactions
                else:
                    # Mutual kill — speeds within 10%
                    kill_a = KillEvent(
                        timestamp=sim_time,
                        killer_id=i,
                        victim_id=j,
                        killer_team=self.team_labels[i],
                        victim_team=self.team_labels[j],
                        position=self.pos[j].copy(),
                    )
                    kill_b = KillEvent(
                        timestamp=sim_time,
                        killer_id=j,
                        victim_id=i,
                        killer_team=self.team_labels[j],
                        victim_team=self.team_labels[i],
                        position=self.pos[i].copy(),
                    )
                    new_kills.extend([kill_a, kill_b])
                    self._eliminate_drone(i)
                    self._eliminate_drone(j)
                    break  # i is dead

        self.kill_log.extend(new_kills)
        return new_kills

    def _eliminate_drone(self, drone_id: int):
        """Remove a drone from the battle by moving it underground."""
        if not self.alive_mask[drone_id]:
            return
        self.alive_mask[drone_id] = False
        # Move the drone body far underground so it doesn't interfere
        p.resetBasePositionAndOrientation(
            self.DRONE_IDS[drone_id],
            [0, 0, -100],
            [0, 0, 0, 1],
            physicsClientId=self.CLIENT,
        )
        p.resetBaseVelocity(
            self.DRONE_IDS[drone_id],
            [0, 0, 0],
            [0, 0, 0],
            physicsClientId=self.CLIENT,
        )

    # ------------------------------------------------------------------
    # Team State Extraction
    # ------------------------------------------------------------------

    def get_team_state(self, team: str) -> SwarmState:
        """Get SwarmState for one team, with enemy positions as targets."""
        if team == "alpha":
            own_idx = self.alpha_indices
            enemy_idx = self.bravo_indices
        else:
            own_idx = self.bravo_indices
            enemy_idx = self.alpha_indices

        own_alive = own_idx[self.alive_mask[own_idx]]
        enemy_alive = enemy_idx[self.alive_mask[enemy_idx]]

        own_positions = self.pos[own_alive] if len(own_alive) > 0 else np.zeros((0, 3))
        own_velocities = self.vel[own_alive] if len(own_alive) > 0 else np.zeros((0, 3))
        own_orientations = self.rpy[own_alive] if len(own_alive) > 0 else np.zeros((0, 3))
        own_ang_vel = self.ang_v[own_alive] if len(own_alive) > 0 else np.zeros((0, 3))

        enemy_positions = (
            self.pos[enemy_alive] if len(enemy_alive) > 0 else np.zeros((0, 3))
        )

        n_own = len(own_alive)
        return SwarmState(
            positions=own_positions,
            velocities=own_velocities,
            orientations=own_orientations,
            angular_velocities=own_ang_vel,
            neighbor_graph=np.zeros((n_own, n_own)) if n_own > 0 else np.array([]),
            targets=enemy_positions,
            active_drones_mask=np.ones(n_own, dtype=bool),
            battery_levels=np.ones(n_own),
            drone_status=["nominal"] * n_own,
        )

    # ------------------------------------------------------------------
    # Battle Status
    # ------------------------------------------------------------------

    def get_battle_status(self) -> dict:
        """Return current battle statistics."""
        alpha_alive = int(np.sum(self.alive_mask[self.alpha_indices]))
        bravo_alive = int(np.sum(self.alive_mask[self.bravo_indices]))

        alpha_kills = sum(
            1 for k in self.kill_log if k.killer_team == "alpha"
        )
        bravo_kills = sum(
            1 for k in self.kill_log if k.killer_team == "bravo"
        )

        return {
            "alpha_alive": alpha_alive,
            "bravo_alive": bravo_alive,
            "alpha_initial": self.num_alpha,
            "bravo_initial": self.num_bravo,
            "alpha_kills": alpha_kills,
            "bravo_kills": bravo_kills,
            "total_kills": len(self.kill_log),
        }

    def is_battle_over(self) -> bool:
        """Check if the battle has ended (one team fully eliminated)."""
        alpha_alive = np.sum(self.alive_mask[self.alpha_indices])
        bravo_alive = np.sum(self.alive_mask[self.bravo_indices])
        return alpha_alive == 0 or bravo_alive == 0

    def get_winner(self) -> str:
        """Determine the winner. Returns 'alpha', 'bravo', or 'draw'."""
        alpha_alive = int(np.sum(self.alive_mask[self.alpha_indices]))
        bravo_alive = int(np.sum(self.alive_mask[self.bravo_indices]))

        if alpha_alive > bravo_alive:
            return "alpha"
        elif bravo_alive > alpha_alive:
            return "bravo"
        return "draw"

    def get_alive_indices(self, team: str) -> np.ndarray:
        """Return indices of alive drones for a team."""
        if team == "alpha":
            return self.alpha_indices[self.alive_mask[self.alpha_indices]]
        return self.bravo_indices[self.alive_mask[self.bravo_indices]]
