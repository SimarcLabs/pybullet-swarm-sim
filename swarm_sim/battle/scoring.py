"""
Battle Scoring — metrics and result structures for swarm combat.

Computes post-battle statistics including K/D ratios, survival rates,
efficiency metrics, and generates structured result payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class BattleResult:
    """Complete battle result with all computed metrics."""

    # Configuration
    algo_alpha: str
    algo_bravo: str

    # Core counts
    alpha_initial: int
    bravo_initial: int
    alpha_survivors: int
    bravo_survivors: int
    alpha_kills: int
    bravo_kills: int

    # Timing
    duration: float
    first_blood_time: Optional[float]
    first_blood_team: Optional[str]

    # Winner
    winner: str  # "alpha", "bravo", or "draw"

    # Kill log
    kill_log: List[dict] = field(default_factory=list)

    # Snapshot timeline (for charts)
    timeline: List[dict] = field(default_factory=list)

    @property
    def alpha_losses(self) -> int:
        return self.alpha_initial - self.alpha_survivors

    @property
    def bravo_losses(self) -> int:
        return self.bravo_initial - self.bravo_survivors

    @property
    def alpha_kd_ratio(self) -> float:
        losses = self.alpha_losses
        return round(self.alpha_kills / max(losses, 1), 2)

    @property
    def bravo_kd_ratio(self) -> float:
        losses = self.bravo_losses
        return round(self.bravo_kills / max(losses, 1), 2)

    @property
    def alpha_survival_rate(self) -> float:
        return round(self.alpha_survivors / max(self.alpha_initial, 1) * 100, 1)

    @property
    def bravo_survival_rate(self) -> float:
        return round(self.bravo_survivors / max(self.bravo_initial, 1) * 100, 1)

    @property
    def alpha_efficiency(self) -> float:
        """Kills per initial drone — how effective was the swarm."""
        return round(self.alpha_kills / max(self.alpha_initial, 1) * 100, 1)

    @property
    def bravo_efficiency(self) -> float:
        return round(self.bravo_kills / max(self.bravo_initial, 1) * 100, 1)

    @property
    def battle_intensity(self) -> float:
        """Total kills per second — how intense was the fight."""
        total_kills = self.alpha_kills + self.bravo_kills
        return round(total_kills / max(self.duration, 0.1), 2)

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "winner": self.winner,
            "algo_alpha": self.algo_alpha,
            "algo_bravo": self.algo_bravo,
            "alpha": {
                "initial": self.alpha_initial,
                "survivors": self.alpha_survivors,
                "kills": self.alpha_kills,
                "losses": self.alpha_losses,
                "kd_ratio": self.alpha_kd_ratio,
                "survival_rate": self.alpha_survival_rate,
                "efficiency": self.alpha_efficiency,
            },
            "bravo": {
                "initial": self.bravo_initial,
                "survivors": self.bravo_survivors,
                "kills": self.bravo_kills,
                "losses": self.bravo_losses,
                "kd_ratio": self.bravo_kd_ratio,
                "survival_rate": self.bravo_survival_rate,
                "efficiency": self.bravo_efficiency,
            },
            "duration": round(self.duration, 2),
            "first_blood": {
                "team": self.first_blood_team,
                "time": round(self.first_blood_time, 2) if self.first_blood_time else None,
            },
            "battle_intensity": self.battle_intensity,
            "kill_log": self.kill_log,
            "timeline": self.timeline,
        }


def compute_battle_result(
    algo_alpha: str,
    algo_bravo: str,
    alpha_initial: int,
    bravo_initial: int,
    alpha_survivors: int,
    bravo_survivors: int,
    duration: float,
    kill_log: List[dict],
    timeline: List[dict],
) -> BattleResult:
    """Build a BattleResult from raw battle data."""

    alpha_kills = sum(1 for k in kill_log if k["killer_team"] == "alpha")
    bravo_kills = sum(1 for k in kill_log if k["killer_team"] == "bravo")

    # Determine winner
    if alpha_survivors > bravo_survivors:
        winner = "alpha"
    elif bravo_survivors > alpha_survivors:
        winner = "bravo"
    else:
        winner = "draw"

    # First blood
    first_blood_time = None
    first_blood_team = None
    if kill_log:
        first = kill_log[0]
        first_blood_time = first["time"]
        first_blood_team = first["killer_team"]

    return BattleResult(
        algo_alpha=algo_alpha,
        algo_bravo=algo_bravo,
        alpha_initial=alpha_initial,
        bravo_initial=bravo_initial,
        alpha_survivors=alpha_survivors,
        bravo_survivors=bravo_survivors,
        alpha_kills=alpha_kills,
        bravo_kills=bravo_kills,
        duration=duration,
        first_blood_time=first_blood_time,
        first_blood_team=first_blood_team,
        winner=winner,
        kill_log=kill_log,
        timeline=timeline,
    )
