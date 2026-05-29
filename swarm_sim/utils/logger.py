"""
Trajectory Logger — records per-drone state every control step.

Logs position, velocity, orientation, angular velocity, and motor RPMs.
Can save to ``.npz`` and ``.csv``, and produces summary plots.

Example
-------
>>> from swarm_sim.utils.logger import SwarmLogger
>>> logger = SwarmLogger(num_drones=4, logging_freq_hz=240, duration_sec=10)
>>> logger.log(drone=0, timestamp=0.004, state=state_20d)
>>> logger.save()
>>> logger.plot()
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt


class SwarmLogger:
    """Per-drone flight data recorder with save and plotting utilities.

    Parameters
    ----------
    num_drones : int
        Number of drones to log.
    logging_freq_hz : int
        How many log entries per second.
    duration_sec : int
        Expected duration (used to pre-allocate arrays).  0 = dynamic growth.
    output_folder : str
        Directory where files are saved.
    """

    def __init__(
        self,
        num_drones: int = 1,
        logging_freq_hz: int = 240,
        duration_sec: int = 0,
        output_folder: str = "results",
    ):
        self.NUM_DRONES = num_drones
        self.LOGGING_FREQ_HZ = logging_freq_hz
        self.OUTPUT_FOLDER = output_folder
        os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)

        total = duration_sec * logging_freq_hz if duration_sec > 0 else 1
        self.counters = np.zeros(num_drones, dtype=int)
        self.timestamps = np.zeros((num_drones, total))
        # 16 channels: pos(3) + vel(3) + rpy(3) + ang_vel(3) + rpm(4)
        self.states = np.zeros((num_drones, 16, total))

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def log(self, drone: int, timestamp: float, state: np.ndarray):
        """Log one step for a single drone.

        Parameters
        ----------
        drone : int
            Drone index.
        timestamp : float
            Simulation time (seconds).
        state : np.ndarray
            ``(20,)`` state vector from :meth:`BaseSwarmEnv.get_drone_state`.
        """
        idx = self.counters[drone]

        # Grow arrays if needed
        if idx >= self.timestamps.shape[1]:
            self.timestamps = np.concatenate(
                [self.timestamps, np.zeros((self.NUM_DRONES, 1))], axis=1
            )
            self.states = np.concatenate(
                [self.states, np.zeros((self.NUM_DRONES, 16, 1))], axis=2
            )

        self.timestamps[drone, idx] = timestamp
        # Re-order: pos(0:3), vel(10:13), rpy(7:10), ang_vel(13:16), rpm(16:20)
        self.states[drone, :, idx] = np.hstack(
            [state[0:3], state[10:13], state[7:10], state[13:16], state[16:20]]
        )
        self.counters[drone] = idx + 1

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save(self, tag: str = ""):
        """Save logs to ``.npz`` file.

        Parameters
        ----------
        tag : str
            Optional tag appended to the filename.
        """
        stamp = datetime.now().strftime("%m.%d.%Y_%H.%M.%S")
        fname = os.path.join(self.OUTPUT_FOLDER, f"flight-{tag}-{stamp}.npz")
        np.savez(fname, timestamps=self.timestamps, states=self.states)
        print(f"[SwarmLogger] Saved to {fname}")

    def save_csv(self, tag: str = ""):
        """Save per-drone position CSV files."""
        stamp = datetime.now().strftime("%m.%d.%Y_%H.%M.%S")
        csv_dir = os.path.join(self.OUTPUT_FOLDER, f"csv-{tag}-{stamp}")
        os.makedirs(csv_dir, exist_ok=True)
        for d in range(self.NUM_DRONES):
            n = self.counters[d]
            t = self.timestamps[d, :n]
            data = np.column_stack([t, self.states[d, 0:3, :n].T])
            np.savetxt(
                os.path.join(csv_dir, f"drone_{d}.csv"),
                data,
                delimiter=",",
                header="t,x,y,z",
                comments="",
            )
        print(f"[SwarmLogger] CSVs saved to {csv_dir}")

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def plot(self, show: bool = True, save_path: str | None = None):
        """Plot position, velocity, and RPM for all drones.

        Parameters
        ----------
        show : bool
            Whether to call ``plt.show()``.
        save_path : str | None
            If set, save the figure as PNG.
        """
        fig, axes = plt.subplots(3, 3, figsize=(14, 10), constrained_layout=True)
        fig.suptitle("Swarm Flight Telemetry", fontsize=14, fontweight="bold")

        labels_pos = ["x (m)", "y (m)", "z (m)"]
        labels_vel = ["vx (m/s)", "vy (m/s)", "vz (m/s)"]
        labels_rpy = ["roll (rad)", "pitch (rad)", "yaw (rad)"]

        for d in range(self.NUM_DRONES):
            n = self.counters[d]
            t = np.arange(n) / self.LOGGING_FREQ_HZ

            for k in range(3):
                axes[0, k].plot(t, self.states[d, k, :n], label=f"drone_{d}")
                axes[0, k].set_ylabel(labels_pos[k])
                axes[0, k].grid(True, alpha=0.3)

                axes[1, k].plot(t, self.states[d, 3 + k, :n], label=f"drone_{d}")
                axes[1, k].set_ylabel(labels_vel[k])
                axes[1, k].grid(True, alpha=0.3)

                axes[2, k].plot(t, self.states[d, 6 + k, :n], label=f"drone_{d}")
                axes[2, k].set_ylabel(labels_rpy[k])
                axes[2, k].set_xlabel("time (s)")
                axes[2, k].grid(True, alpha=0.3)

        axes[0, 0].legend(fontsize=7)

        if save_path:
            fig.savefig(save_path, dpi=150)
            print(f"[SwarmLogger] Figure saved to {save_path}")
        if show:
            plt.show()

    def plot_3d(self, show: bool = True, save_path: str | None = None):
        """3-D trajectory plot of all drones.

        Parameters
        ----------
        show : bool
            Whether to call ``plt.show()``.
        save_path : str | None
            If set, save the figure as PNG.
        """
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")
        ax.set_title("Swarm 3-D Trajectories", fontweight="bold")

        colours = plt.cm.viridis(np.linspace(0, 1, self.NUM_DRONES))
        for d in range(self.NUM_DRONES):
            n = self.counters[d]
            ax.plot(
                self.states[d, 0, :n],
                self.states[d, 1, :n],
                self.states[d, 2, :n],
                color=colours[d],
                linewidth=1.2,
                label=f"drone_{d}",
            )
            # Start and end markers
            ax.scatter(*self.states[d, 0:3, 0], color=colours[d], marker="o", s=40)
            ax.scatter(
                *self.states[d, 0:3, n - 1], color=colours[d], marker="^", s=60
            )

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.legend(fontsize=7, loc="upper left")

        if save_path:
            fig.savefig(save_path, dpi=150)
            print(f"[SwarmLogger] 3-D plot saved to {save_path}")
        if show:
            plt.show()
