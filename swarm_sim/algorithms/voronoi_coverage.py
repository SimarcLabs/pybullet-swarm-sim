"""
Voronoi Coverage Algorithm (Lloyd's Algorithm).

Drones use Lloyd's method to converge to centroidal Voronoi configurations,
naturally dispersing to maximise spatial coverage without central coordination.

Unlike rigid formation control, this approach is fully decentralised — each
drone only needs to know its own position and its neighbours' positions to
compute its Voronoi cell centroid and steer toward it.

References
----------
Lloyd, S. P. (1982). Least squares quantization in PCM. *IEEE Transactions on
Information Theory*, 28(2), 129–137.

Cortés, J., Martínez, S., Karatas, T., & Bullo, F. (2004). Coverage control
for mobile sensing networks. *IEEE Transactions on Robotics and Automation*,
20(2), 243–255.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import Voronoi  # type: ignore

from swarm_sim.core.state import SwarmState
from swarm_sim.algorithms.base_algorithm import BaseAlgorithm


class VoronoiCoverageAlgorithm(BaseAlgorithm):
    """Centroidal Voronoi Tessellation for decentralised area coverage.

    Each drone computes the centroid of its 2D Voronoi cell (clipped to the
    arena bounds) and steers toward it, at a fixed hover altitude.  Over time
    the swarm converges to a configuration that maximises uniform spatial
    coverage — the Lloyd optimum.

    Parameters
    ----------
    num_drones : int
        Number of drones in the swarm.
    arena_bounds : tuple[float, float]
        (min_xy, max_xy) defining the square arena boundary in the XY plane.
    hover_altitude : float
        Target Z height all drones maintain (metres).
    gain : float
        Proportional gain — how aggressively drones chase their cell centroid.
    max_speed : float
        Maximum output speed (m/s).
    min_separation : float
        Minimum separation distance before repulsion kicks in (metres).
    rep_gain : float
        Repulsion gain applied when two drones come too close.
    """

    def __init__(
        self,
        num_drones: int = 10,
        arena_bounds: tuple[float, float] = (-6.0, 6.0),
        hover_altitude: float = 1.2,
        gain: float = 0.6,
        max_speed: float = 0.8,
        min_separation: float = 0.5,
        rep_gain: float = 1.2,
    ):
        self.arena_lo = arena_bounds[0]
        self.arena_hi = arena_bounds[1]
        self.hover_z = hover_altitude
        self.gain = gain
        self.max_speed = max_speed
        self.min_sep = min_separation
        self.rep_gain = rep_gain
        super().__init__(num_drones=num_drones)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clip_to_arena(self, pt: np.ndarray) -> np.ndarray:
        """Clip a 2-D point to the arena square."""
        return np.clip(pt, self.arena_lo, self.arena_hi)

    def _voronoi_centroid(
        self, idx: int, pts_2d: np.ndarray
    ) -> np.ndarray:
        """Estimate the centroid of drone `idx`'s Voronoi cell.

        Strategy
        --------
        We add 8 mirror-ghost points well outside the arena so that
        scipy.spatial.Voronoi always produces finite regions for every
        real drone.  Then we clip all vertices of drone i's polygon to
        the arena and compute the area-weighted centroid.

        Falls back to the drone's own position if the cell cannot be
        determined (e.g. collinear points).
        """
        lo, hi = self.arena_lo, self.arena_hi
        margin = abs(hi - lo) * 2.0

        # 8 far ghost points that bound the arena
        ghosts = np.array([
            [lo - margin, lo - margin],
            [lo - margin, 0.0],
            [lo - margin, hi + margin],
            [0.0,         hi + margin],
            [hi + margin, hi + margin],
            [hi + margin, 0.0],
            [hi + margin, lo - margin],
            [0.0,         lo - margin],
        ])
        all_pts = np.vstack([pts_2d, ghosts])

        try:
            vor = Voronoi(all_pts)
        except Exception:
            return pts_2d[idx]

        # Find the region belonging to drone `idx`
        region_idx = vor.point_region[idx]
        region = vor.regions[region_idx]

        # Region must be finite (no -1 indices)
        if -1 in region or len(region) == 0:
            return pts_2d[idx]

        vertices = np.array([vor.vertices[v] for v in region])

        # Clip vertices to arena
        vertices = np.clip(vertices, lo, hi)

        # Compute polygon centroid via the shoelace / surveyor formula
        centroid = self._polygon_centroid(vertices)
        return self._clip_to_arena(centroid)

    @staticmethod
    def _polygon_centroid(verts: np.ndarray) -> np.ndarray:
        """Area-weighted centroid of a 2-D polygon (vertices in order)."""
        n = len(verts)
        if n == 0:
            return np.zeros(2)
        if n == 1:
            return verts[0]
        if n == 2:
            return verts.mean(axis=0)

        cx = cy = area = 0.0
        for k in range(n):
            x0, y0 = verts[k]
            x1, y1 = verts[(k + 1) % n]
            cross = x0 * y1 - x1 * y0
            area += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross

        area *= 0.5
        if abs(area) < 1e-9:
            return verts.mean(axis=0)  # degenerate polygon

        cx /= (6.0 * area)
        cy /= (6.0 * area)
        return np.array([cx, cy])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, state: SwarmState) -> np.ndarray:
        """Compute Lloyd step velocities for every drone.

        Parameters
        ----------
        state : SwarmState
            Current swarm state.

        Returns
        -------
        np.ndarray
            ``(N, 3)`` target velocity vectors.
        """
        positions = state.positions
        N = positions.shape[0]
        velocities = np.zeros((N, 3))

        # Work in 2-D (XY) for the Voronoi tessellation
        pts_2d = positions[:, :2].copy()

        for i in range(N):
            pos = positions[i]

            # ── 1. Voronoi centroid attraction (XY plane) ─────────────
            if N >= 2:
                centroid_2d = self._voronoi_centroid(i, pts_2d)
                delta_xy = centroid_2d - pos[:2]
            else:
                # Single drone — hold position
                delta_xy = np.zeros(2)

            # ── 2. Altitude hold (Z axis) ─────────────────────────────
            delta_z = self.hover_z - pos[2]

            vel = np.array([
                self.gain * delta_xy[0],
                self.gain * delta_xy[1],
                2.0 * delta_z,          # faster Z correction
            ])

            # ── 3. Peer repulsion (safety buffer) ─────────────────────
            for j in range(N):
                if i == j:
                    continue
                diff = pos - positions[j]
                dist = np.linalg.norm(diff)
                if dist < self.min_sep and dist > 1e-6:
                    vel += self.rep_gain * (diff / dist) * (self.min_sep - dist)

            # ── 4. Arena boundary repulsion ───────────────────────────
            margin = 0.5
            for axis in range(2):          # only X, Y
                if pos[axis] < self.arena_lo + margin:
                    vel[axis] += self.rep_gain * (self.arena_lo + margin - pos[axis])
                elif pos[axis] > self.arena_hi - margin:
                    vel[axis] -= self.rep_gain * (pos[axis] - (self.arena_hi - margin))

            # ── 5. Speed clamp ────────────────────────────────────────
            speed = np.linalg.norm(vel)
            if speed > self.max_speed:
                vel = vel / speed * self.max_speed

            velocities[i] = vel

        return velocities
