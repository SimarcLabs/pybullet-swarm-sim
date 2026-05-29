"""
Visualization utilities — wall-clock sync and trajectory animation.

Provides real-time sync for GUI simulations and a helper to stitch
recorded frames into a GIF or MP4.

Example
-------
>>> from swarm_sim.utils.viz import sync, frames_to_gif
>>> sync(step=100, start_time=t0, timestep=1/240)
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np


def sync(step: int, start_time: float, timestep: float):
    """Pause the loop to keep the simulation at wall-clock speed.

    Call this inside a control loop when ``gui=True`` to prevent the
    simulation from running faster than real-time.

    Parameters
    ----------
    step : int
        Current iteration counter.
    start_time : float
        ``time.time()`` at the start of the simulation.
    timestep : float
        Desired wall-clock step duration (seconds).
    """
    if timestep > 0.04 or step % max(1, int(1 / (24 * timestep))) == 0:
        elapsed = time.time() - start_time
        expected = step * timestep
        if elapsed < expected:
            time.sleep(expected - elapsed)


def frames_to_gif(
    frame_dir: str,
    output_path: str = "swarm_demo.gif",
    fps: int = 24,
    resize: tuple[int, int] | None = None,
):
    """Stitch PNG frames into an animated GIF.

    Parameters
    ----------
    frame_dir : str
        Directory containing ``frame_00000.png``, ``frame_00001.png``, …
    output_path : str
        Output GIF file path.
    fps : int
        Frames per second.
    resize : tuple[int, int] | None
        ``(width, height)`` to resize frames. ``None`` = keep original.
    """
    from PIL import Image  # lazy import

    frame_files = sorted(Path(frame_dir).glob("frame_*.png"))
    if not frame_files:
        print(f"[viz] No frames found in {frame_dir}")
        return

    frames = []
    for f in frame_files:
        img = Image.open(f).convert("RGB")
        if resize:
            img = img.resize(resize, Image.LANCZOS)
        frames.append(img)

    duration_ms = int(1000 / fps)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print(f"[viz] GIF saved to {output_path} ({len(frames)} frames)")


def draw_trajectory_lines(
    physics_client: int,
    positions_history: np.ndarray,
    colours: list[list[float]] | None = None,
    line_width: float = 1.5,
):
    """Draw 3-D trajectory lines in the PyBullet GUI.

    Parameters
    ----------
    physics_client : int
        PyBullet client ID.
    positions_history : np.ndarray
        ``(num_drones, num_steps, 3)`` position history.
    colours : list | None
        ``(num_drones,)`` list of ``[r, g, b]`` per drone. ``None`` = auto.
    line_width : float
        Width of the debug lines.
    """
    import pybullet as p  # lazy import

    N, T, _ = positions_history.shape
    if colours is None:
        cmap = np.linspace(0, 1, N)
        colours = [[c, 0.3, 1 - c] for c in cmap]

    for d in range(N):
        for t in range(1, T):
            p.addUserDebugLine(
                lineFromXYZ=positions_history[d, t - 1].tolist(),
                lineToXYZ=positions_history[d, t].tolist(),
                lineColorRGB=colours[d],
                lineWidth=line_width,
                physicsClientId=physics_client,
            )
