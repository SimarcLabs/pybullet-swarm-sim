"""
Formation Planner — compute target positions for geometric swarm patterns.

Supports ``LINE``, ``V``, ``GRID``, ``RING``, and ``HELIX`` formations.
Returns an ``(N, 3)`` offset matrix relative to the formation centre so that
the caller can animate the centre independently.

Example
-------
>>> from swarm_sim.algorithms.formation import FormationPlanner
>>> from swarm_sim.utils.enums import FormationType
>>> planner = FormationPlanner()
>>> offsets = planner.compute_offsets(FormationType.V, num_drones=8, spacing=0.5)
"""

from __future__ import annotations

import numpy as np

from swarm_sim.utils.enums import FormationType


class FormationPlanner:
    """Generate drone-slot offsets for common formation shapes.

    All returned offsets are centred so the mean offset is ``[0, 0, 0]``.
    """

    def compute_offsets(
        self,
        formation: FormationType,
        num_drones: int,
        spacing: float = 0.5,
    ) -> np.ndarray:
        """Compute ``(num_drones, 3)`` position offsets for a given formation.

        Parameters
        ----------
        formation : FormationType
            The desired geometric pattern.
        num_drones : int
            Number of drones.
        spacing : float
            Minimum distance (m) between adjacent drones.

        Returns
        -------
        np.ndarray
            ``(num_drones, 3)`` offset matrix (mean-centred).
        """
        dispatch = {
            FormationType.LINE: self._line,
            FormationType.V: self._v_shape,
            FormationType.GRID: self._grid,
            FormationType.RING: self._ring,
            FormationType.HELIX: self._helix,
        }
        fn = dispatch.get(formation)
        if fn is None:
            raise ValueError(f"Unknown formation type: {formation}")
        offsets = fn(num_drones, spacing)
        # Mean-centre so the formation is centred at origin
        offsets -= offsets.mean(axis=0)
        return offsets

    # ------------------------------------------------------------------
    # Formation generators
    # ------------------------------------------------------------------

    @staticmethod
    def _line(n: int, s: float) -> np.ndarray:
        """Straight line along the y-axis."""
        return np.column_stack([
            np.zeros(n),
            np.arange(n) * s,
            np.zeros(n),
        ])

    @staticmethod
    def _v_shape(n: int, s: float) -> np.ndarray:
        """V-formation (like migrating birds)."""
        offsets = []
        for i in range(n):
            side = 1 if i % 2 == 0 else -1
            rank = (i + 1) // 2  # distance from the lead drone
            x = -rank * s * 0.7  # trail behind
            y = side * rank * s
            offsets.append([x, y, 0.0])
        return np.array(offsets)

    @staticmethod
    def _grid(n: int, s: float) -> np.ndarray:
        """Rectangular grid (as square as possible)."""
        cols = int(np.ceil(np.sqrt(n)))
        offsets = []
        for i in range(n):
            x = (i % cols) * s
            y = (i // cols) * s
            offsets.append([x, y, 0.0])
        return np.array(offsets)

    @staticmethod
    def _ring(n: int, s: float) -> np.ndarray:
        """Circular ring in the XY plane."""
        if n <= 1:
            return np.zeros((n, 3))
        radius = (n * s) / (2 * np.pi)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        return np.column_stack([
            radius * np.cos(angles),
            radius * np.sin(angles),
            np.zeros(n),
        ])

    @staticmethod
    def _helix(n: int, s: float) -> np.ndarray:
        """3-D helical spiral with z-offsets symmetric around the centre.

        The helix rises from ``-total_height/2`` to ``+total_height/2`` so that
        after mean-centering no drone ends up with a large negative z-offset
        that would push its target underground.
        """
        radius = s * 2
        height_step = s * 0.4
        total_height = (n - 1) * height_step
        angles = np.linspace(0, 4 * np.pi, n, endpoint=False)
        z_vals = np.linspace(-total_height / 2, total_height / 2, n)
        return np.column_stack([
            radius * np.cos(angles),
            radius * np.sin(angles),
            z_vals,
        ])
