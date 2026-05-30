"""
Base multi-drone Gymnasium environment powered by PyBullet.

This is the **heart of the library**.  It manages the PyBullet physics client,
loads N drone URDFs, steps the simulation, and exposes a standard Gymnasium
``Env`` interface (``reset`` / ``step`` / ``render`` / ``close``).

All higher-level environments (hover, formation, RL) inherit from this class
and override ``_computeReward``, ``_computeTerminated``, etc.

Example
-------
>>> from swarm_sim.envs.base_swarm_env import BaseSwarmEnv
>>> env = BaseSwarmEnv(num_drones=4, gui=False)
>>> obs, info = env.reset()
>>> action = env.action_space.sample()
>>> obs, reward, terminated, truncated, info = env.step(action)
>>> env.close()
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as etxml
from datetime import datetime
from pathlib import Path

import numpy as np
import pybullet as p
import pybullet_data
import gymnasium as gym
from gymnasium import spaces
from PIL import Image

from swarm_sim.utils.enums import DroneModel, Physics

# ---------------------------------------------------------------------------
# Resolve the path to bundled URDF assets shipped with the package.
# ---------------------------------------------------------------------------
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class BaseSwarmEnv(gym.Env):
    """Gymnasium environment for multi-drone swarm simulation in PyBullet.

    Parameters
    ----------
    drone_model : DroneModel
        Which URDF to load for every drone.
    num_drones : int
        Number of drones in the swarm.
    neighbourhood_radius : float
        Distance (m) used to build the adjacency matrix for neighbour queries.
    initial_xyzs : np.ndarray | None
        ``(num_drones, 3)`` starting positions.  ``None`` → auto-grid.
    initial_rpys : np.ndarray | None
        ``(num_drones, 3)`` starting orientations (rad).  ``None`` → zeros.
    physics : Physics
        Which physics pipeline to use (base, +ground, +drag, +downwash, or all).
    pyb_freq : int
        PyBullet internal step frequency (Hz).
    ctrl_freq : int
        Control / environment step frequency (Hz).  Must divide ``pyb_freq``.
    gui : bool
        If ``True`` opens the PyBullet OpenGL viewer.
    record : bool
        If ``True`` saves rendered frames for video export.
    obstacles : bool
        If ``True`` adds sample obstacles to the scene.
    output_folder : str
        Directory for logs, recordings, etc.
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        drone_model: DroneModel = DroneModel.CF2X,
        num_drones: int = 1,
        neighbourhood_radius: float = np.inf,
        initial_xyzs: np.ndarray | None = None,
        initial_rpys: np.ndarray | None = None,
        physics: Physics = Physics.PYB,
        pyb_freq: int = 240,
        ctrl_freq: int = 240,
        gui: bool = False,
        record: bool = False,
        obstacles: bool = False,
        output_folder: str = "results",
    ):
        super().__init__()

        # ---- constants ------------------------------------------------
        self.G = 9.8
        self.RAD2DEG = 180.0 / np.pi
        self.DEG2RAD = np.pi / 180.0

        # ---- timing ---------------------------------------------------
        self.PYB_FREQ = pyb_freq
        self.CTRL_FREQ = ctrl_freq
        if self.PYB_FREQ % self.CTRL_FREQ != 0:
            raise ValueError(
                f"pyb_freq ({pyb_freq}) must be divisible by ctrl_freq ({ctrl_freq})."
            )
        self.PYB_STEPS_PER_CTRL = int(self.PYB_FREQ / self.CTRL_FREQ)
        self.CTRL_TIMESTEP = 1.0 / self.CTRL_FREQ
        self.PYB_TIMESTEP = 1.0 / self.PYB_FREQ

        # ---- swarm params ---------------------------------------------
        self.NUM_DRONES = num_drones
        self.NEIGHBOURHOOD_RADIUS = neighbourhood_radius

        # ---- options --------------------------------------------------
        self.DRONE_MODEL = drone_model
        self.GUI = gui
        self.RECORD = record
        self.PHYSICS = physics
        self.OBSTACLES = obstacles
        self.URDF = self.DRONE_MODEL.value + ".urdf"
        self.OUTPUT_FOLDER = output_folder

        # ---- load drone physical properties from URDF -----------------
        (
            self.M,
            self.L,
            self.THRUST2WEIGHT_RATIO,
            self.J,
            self.J_INV,
            self.KF,
            self.KM,
            self.COLLISION_H,
            self.COLLISION_R,
            self.COLLISION_Z_OFFSET,
            self.MAX_SPEED_KMH,
            self.GND_EFF_COEFF,
            self.PROP_RADIUS,
            self.DRAG_COEFF,
            self.DW_COEFF_1,
            self.DW_COEFF_2,
            self.DW_COEFF_3,
        ) = self._parse_urdf_parameters()

        # ---- derived constants ----------------------------------------
        self.GRAVITY = self.G * self.M
        self.HOVER_RPM = np.sqrt(self.GRAVITY / (4 * self.KF))
        self.MAX_RPM = np.sqrt(
            (self.THRUST2WEIGHT_RATIO * self.GRAVITY) / (4 * self.KF)
        )
        self.MAX_THRUST = 4 * self.KF * self.MAX_RPM**2
        if self.DRONE_MODEL == DroneModel.CF2X:
            self.MAX_XY_TORQUE = (2 * self.L * self.KF * self.MAX_RPM**2) / np.sqrt(2)
        elif self.DRONE_MODEL == DroneModel.CF2P:
            self.MAX_XY_TORQUE = self.L * self.KF * self.MAX_RPM**2
        else:
            self.MAX_XY_TORQUE = (2 * self.L * self.KF * self.MAX_RPM**2) / np.sqrt(2)
        self.MAX_Z_TORQUE = 2 * self.KM * self.MAX_RPM**2
        self.GND_EFF_H_CLIP = 0.25 * self.PROP_RADIUS * np.sqrt(
            (15 * self.MAX_RPM**2 * self.KF * self.GND_EFF_COEFF) / self.MAX_THRUST
        )

        # ---- initial poses --------------------------------------------
        if initial_xyzs is None:
            self.INIT_XYZS = self._default_initial_positions()
        else:
            self.INIT_XYZS = np.array(initial_xyzs).reshape(self.NUM_DRONES, 3)

        if initial_rpys is None:
            self.INIT_RPYS = np.zeros((self.NUM_DRONES, 3))
        else:
            self.INIT_RPYS = np.array(initial_rpys).reshape(self.NUM_DRONES, 3)

        # ---- recording setup -----------------------------------------
        if self.RECORD:
            self._recording_dir = os.path.join(
                self.OUTPUT_FOLDER,
                "recording_" + datetime.now().strftime("%m.%d.%Y_%H.%M.%S"),
            )
            os.makedirs(self._recording_dir, exist_ok=True)

        # ---- connect to PyBullet -------------------------------------
        if self.GUI:
            self.CLIENT = p.connect(p.GUI)
            for flag in [
                p.COV_ENABLE_RGB_BUFFER_PREVIEW,
                p.COV_ENABLE_DEPTH_BUFFER_PREVIEW,
                p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW,
                p.COV_ENABLE_GUI,
            ]:
                p.configureDebugVisualizer(flag, 0, physicsClientId=self.CLIENT)
            p.resetDebugVisualizerCamera(
                cameraDistance=3,
                cameraYaw=-30,
                cameraPitch=-30,
                cameraTargetPosition=[0, 0, 0],
                physicsClientId=self.CLIENT,
            )
        else:
            self.CLIENT = p.connect(p.DIRECT)

        if self.RECORD and not self.GUI:
            self.VID_WIDTH = 640
            self.VID_HEIGHT = 480
            self.FRAME_PER_SEC = 24
            self.CAPTURE_FREQ = int(self.PYB_FREQ / self.FRAME_PER_SEC)
            self.CAM_VIEW = p.computeViewMatrixFromYawPitchRoll(
                distance=3,
                yaw=-30,
                pitch=-30,
                roll=0,
                cameraTargetPosition=[0, 0, 0],
                upAxisIndex=2,
                physicsClientId=self.CLIENT,
            )
            self.CAM_PRO = p.computeProjectionMatrixFOV(
                fov=60.0,
                aspect=self.VID_WIDTH / self.VID_HEIGHT,
                nearVal=0.1,
                farVal=1000.0,
            )

        # ---- Gymnasium spaces ----------------------------------------
        self.action_space = self._action_space()
        self.observation_space = self._observation_space()

        # ---- first reset ---------------------------------------------
        self._housekeeping()
        self._update_kinematic_info()
        self._start_video_recording()

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        """Reset all drones to their initial poses.

        Returns
        -------
        obs : np.ndarray
            ``(num_drones, 20)`` observation matrix.
        info : dict
            Auxiliary information.
        """
        super().reset(seed=seed)
        p.resetSimulation(physicsClientId=self.CLIENT)
        self._housekeeping()
        self._update_kinematic_info()
        self._start_video_recording()
        return self._compute_obs(), self._compute_info()

    def step(self, action: np.ndarray):
        """Advance the simulation by one control step.

        Parameters
        ----------
        action : np.ndarray
            ``(num_drones, 4)`` array of RPM commands for each motor.

        Returns
        -------
        obs, reward, terminated, truncated, info
        """
        # ---- record frames -------------------------------------------
        if (
            self.RECORD
            and not self.GUI
            and self.step_counter % self.CAPTURE_FREQ == 0
        ):
            self._save_frame()

        # ---- clip action to valid RPMs --------------------------------
        clipped = np.reshape(self._preprocess_action(action), (self.NUM_DRONES, 4))

        # ---- sub-step physics ----------------------------------------
        for _ in range(self.PYB_STEPS_PER_CTRL):
            if self.PYB_STEPS_PER_CTRL > 1 and self.PHYSICS in (
                Physics.PYB_GND,
                Physics.PYB_DRAG,
                Physics.PYB_DW,
                Physics.PYB_GND_DRAG_DW,
            ):
                self._update_kinematic_info()

            for i in range(self.NUM_DRONES):
                if self.PHYSICS == Physics.PYB:
                    self._apply_physics(clipped[i], i)
                elif self.PHYSICS == Physics.PYB_GND:
                    self._apply_physics(clipped[i], i)
                    self._ground_effect(clipped[i], i)
                elif self.PHYSICS == Physics.PYB_DRAG:
                    self._apply_physics(clipped[i], i)
                    self._drag(self.last_clipped_action[i], i)
                elif self.PHYSICS == Physics.PYB_DW:
                    self._apply_physics(clipped[i], i)
                    self._downwash(i)
                elif self.PHYSICS == Physics.PYB_GND_DRAG_DW:
                    self._apply_physics(clipped[i], i)
                    self._ground_effect(clipped[i], i)
                    self._drag(self.last_clipped_action[i], i)
                    self._downwash(i)

            p.stepSimulation(physicsClientId=self.CLIENT)
            self.last_clipped_action = clipped

        self._update_kinematic_info()
        self.step_counter += self.PYB_STEPS_PER_CTRL

        obs = self._compute_obs()
        reward = self._compute_reward()
        terminated = self._compute_terminated()
        truncated = self._compute_truncated()
        info = self._compute_info()
        return obs, reward, terminated, truncated, info

    def render(self, mode: str = "human"):
        """Print a textual summary of all drone states."""
        elapsed = time.time() - self.RESET_TIME
        sim_time = self.step_counter * self.PYB_TIMESTEP
        ratio = sim_time / elapsed if elapsed > 0 else 0
        print(
            f"\n[SwarmSim] step={self.step_counter:05d}  "
            f"wall={elapsed:.1f}s  sim={sim_time:.1f}s@{self.PYB_FREQ}Hz  "
            f"({ratio:.2f}x real-time)"
        )
        for i in range(self.NUM_DRONES):
            print(
                f"  drone {i}: "
                f"pos=[{self.pos[i,0]:+.2f}, {self.pos[i,1]:+.2f}, {self.pos[i,2]:+.2f}]  "
                f"vel=[{self.vel[i,0]:+.2f}, {self.vel[i,1]:+.2f}, {self.vel[i,2]:+.2f}]  "
                f"rpy=[{self.rpy[i,0]*self.RAD2DEG:+.1f}°, "
                f"{self.rpy[i,1]*self.RAD2DEG:+.1f}°, "
                f"{self.rpy[i,2]*self.RAD2DEG:+.1f}°]"
            )

    def close(self):
        """Disconnect the PyBullet client and release resources."""
        if self.RECORD and self.GUI:
            p.stopStateLogging(self.VIDEO_ID, physicsClientId=self.CLIENT)
        p.disconnect(physicsClientId=self.CLIENT)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_drone_state(self, nth_drone: int) -> np.ndarray:
        """Return a 20-D state vector for a single drone.

        Layout: ``[x, y, z, qx, qy, qz, qw, r, p, y, vx, vy, vz,
        wx, wy, wz, rpm0, rpm1, rpm2, rpm3]``.
        """
        return np.hstack(
            [
                self.pos[nth_drone],
                self.quat[nth_drone],
                self.rpy[nth_drone],
                self.vel[nth_drone],
                self.ang_v[nth_drone],
                self.last_clipped_action[nth_drone],
            ]
        ).reshape(20)

    def get_adjacency_matrix(self) -> np.ndarray:
        """Compute the (symmetric) adjacency matrix based on ``neighbourhood_radius``."""
        adj = np.eye(self.NUM_DRONES)
        for i in range(self.NUM_DRONES - 1):
            for j in range(i + 1, self.NUM_DRONES):
                if (
                    np.linalg.norm(self.pos[i] - self.pos[j])
                    < self.NEIGHBOURHOOD_RADIUS
                ):
                    adj[i, j] = adj[j, i] = 1
        return adj

    # ------------------------------------------------------------------
    # Spaces  (override in subclasses for custom obs / actions)
    # ------------------------------------------------------------------

    def _action_space(self) -> spaces.Box:
        lo = np.zeros((self.NUM_DRONES, 4), dtype=np.float32)
        hi = np.full((self.NUM_DRONES, 4), self.MAX_RPM, dtype=np.float32)
        return spaces.Box(low=lo, high=hi, dtype=np.float32)

    def _observation_space(self) -> spaces.Box:
        lo = np.array(
            [
                [
                    -np.inf, -np.inf, 0.0,
                    -1, -1, -1, -1,
                    -np.pi, -np.pi, -np.pi,
                    -np.inf, -np.inf, -np.inf,
                    -np.inf, -np.inf, -np.inf,
                    0, 0, 0, 0,
                ]
            ]
            * self.NUM_DRONES,
            dtype=np.float32,
        )
        hi = np.array(
            [
                [
                    np.inf, np.inf, np.inf,
                    1, 1, 1, 1,
                    np.pi, np.pi, np.pi,
                    np.inf, np.inf, np.inf,
                    np.inf, np.inf, np.inf,
                    self.MAX_RPM, self.MAX_RPM, self.MAX_RPM, self.MAX_RPM,
                ]
            ]
            * self.NUM_DRONES,
            dtype=np.float32,
        )
        return spaces.Box(low=lo, high=hi, dtype=np.float32)

    # ------------------------------------------------------------------
    # Compute methods  (override in subclasses)
    # ------------------------------------------------------------------

    def _compute_obs(self) -> np.ndarray:
        return np.array(
            [self.get_drone_state(i) for i in range(self.NUM_DRONES)]
        )

    def _compute_reward(self) -> float:
        return 0.0

    def _compute_terminated(self) -> bool:
        return False

    def _compute_truncated(self) -> bool:
        return False

    def _compute_info(self) -> dict:
        return {}

    def _preprocess_action(self, action: np.ndarray) -> np.ndarray:
        return np.clip(action, 0, self.MAX_RPM)

    # ------------------------------------------------------------------
    # Internal: housekeeping
    # ------------------------------------------------------------------

    def _housekeeping(self):
        """Allocate arrays, set gravity, load ground plane and drones."""
        self.RESET_TIME = time.time()
        self.step_counter = 0
        self.last_clipped_action = np.zeros((self.NUM_DRONES, 4))

        # kinematic arrays
        self.pos = np.zeros((self.NUM_DRONES, 3))
        self.quat = np.zeros((self.NUM_DRONES, 4))
        self.rpy = np.zeros((self.NUM_DRONES, 3))
        self.vel = np.zeros((self.NUM_DRONES, 3))
        self.ang_v = np.zeros((self.NUM_DRONES, 3))

        # PyBullet setup
        p.setGravity(0, 0, -self.G, physicsClientId=self.CLIENT)
        p.setRealTimeSimulation(0, physicsClientId=self.CLIENT)
        p.setTimeStep(self.PYB_TIMESTEP, physicsClientId=self.CLIENT)
        p.setAdditionalSearchPath(
            pybullet_data.getDataPath(), physicsClientId=self.CLIENT
        )

        # ground plane
        self.PLANE_ID = p.loadURDF("plane.urdf", physicsClientId=self.CLIENT)

        # drones
        urdf_path = str(_ASSETS_DIR / self.URDF)
        self.DRONE_IDS = np.array(
            [
                p.loadURDF(
                    urdf_path,
                    self.INIT_XYZS[i],
                    p.getQuaternionFromEuler(self.INIT_RPYS[i]),
                    flags=p.URDF_USE_INERTIA_FROM_FILE,
                    physicsClientId=self.CLIENT,
                )
                for i in range(self.NUM_DRONES)
            ]
        )

        if self.OBSTACLES:
            self._add_obstacles()

    def _update_kinematic_info(self):
        """Read current drone poses and velocities from PyBullet."""
        for i in range(self.NUM_DRONES):
            self.pos[i], self.quat[i] = p.getBasePositionAndOrientation(
                self.DRONE_IDS[i], physicsClientId=self.CLIENT
            )
            self.rpy[i] = p.getEulerFromQuaternion(self.quat[i])
            self.vel[i], self.ang_v[i] = p.getBaseVelocity(
                self.DRONE_IDS[i], physicsClientId=self.CLIENT
            )

    def _start_video_recording(self):
        if self.RECORD and self.GUI:
            self.VIDEO_ID = p.startStateLogging(
                loggingType=p.STATE_LOGGING_VIDEO_MP4,
                fileName=os.path.join(
                    self.OUTPUT_FOLDER,
                    "video-" + datetime.now().strftime("%m.%d.%Y_%H.%M.%S") + ".mp4",
                ),
                physicsClientId=self.CLIENT,
            )
        if self.RECORD and not self.GUI:
            self.FRAME_NUM = 0
            self.IMG_PATH = os.path.join(self._recording_dir, "")
            os.makedirs(self.IMG_PATH, exist_ok=True)

    def _save_frame(self):
        w, h, rgb, _dep, _seg = p.getCameraImage(
            width=self.VID_WIDTH,
            height=self.VID_HEIGHT,
            shadow=1,
            viewMatrix=self.CAM_VIEW,
            projectionMatrix=self.CAM_PRO,
            renderer=p.ER_TINY_RENDERER,
            flags=p.ER_SEGMENTATION_MASK_OBJECT_AND_LINKINDEX,
            physicsClientId=self.CLIENT,
        )
        img = Image.fromarray(np.reshape(rgb, (h, w, 4)), "RGBA")
        img.save(os.path.join(self.IMG_PATH, f"frame_{self.FRAME_NUM:05d}.png"))
        self.FRAME_NUM += 1

    def _default_initial_positions(self) -> np.ndarray:
        """Place drones on a grid 4×arm-length apart, slightly above ground."""
        cols = int(np.ceil(np.sqrt(self.NUM_DRONES)))
        positions = []
        for i in range(self.NUM_DRONES):
            x = (i % cols) * 4 * self.L
            y = (i // cols) * 4 * self.L
            z = self.COLLISION_H / 2 - self.COLLISION_Z_OFFSET + 0.1
            positions.append([x, y, z])
        return np.array(positions)

    def _add_obstacles(self):
        """Override to place custom obstacles in the scene."""
        pass

    # ------------------------------------------------------------------
    # Internal: physics models
    # ------------------------------------------------------------------

    def _apply_physics(self, rpm: np.ndarray, nth_drone: int):
        """Apply motor forces and yaw torque (base rigid-body model)."""
        forces = rpm**2 * self.KF
        torques = rpm**2 * self.KM
        z_torque = -torques[0] + torques[1] - torques[2] + torques[3]
        for i in range(4):
            p.applyExternalForce(
                self.DRONE_IDS[nth_drone],
                i,
                forceObj=[0, 0, forces[i]],
                posObj=[0, 0, 0],
                flags=p.LINK_FRAME,
                physicsClientId=self.CLIENT,
            )
        p.applyExternalTorque(
            self.DRONE_IDS[nth_drone],
            4,
            torqueObj=[0, 0, z_torque],
            flags=p.LINK_FRAME,
            physicsClientId=self.CLIENT,
        )

    def _ground_effect(self, rpm: np.ndarray, nth_drone: int):
        """Analytical ground-effect model (Shi et al., 2019)."""
        link_states = p.getLinkStates(
            self.DRONE_IDS[nth_drone],
            linkIndices=[0, 1, 2, 3, 4],
            computeLinkVelocity=1,
            computeForwardKinematics=1,
            physicsClientId=self.CLIENT,
        )
        prop_heights = np.array([ls[0][2] for ls in link_states[:4]])
        prop_heights = np.clip(prop_heights, self.GND_EFF_H_CLIP, np.inf)
        gnd = (
            rpm**2
            * self.KF
            * self.GND_EFF_COEFF
            * (self.PROP_RADIUS / (4 * prop_heights)) ** 2
        )
        if (
            abs(self.rpy[nth_drone, 0]) < np.pi / 2
            and abs(self.rpy[nth_drone, 1]) < np.pi / 2
        ):
            for i in range(4):
                p.applyExternalForce(
                    self.DRONE_IDS[nth_drone],
                    i,
                    forceObj=[0, 0, gnd[i]],
                    posObj=[0, 0, 0],
                    flags=p.LINK_FRAME,
                    physicsClientId=self.CLIENT,
                )

    def _drag(self, rpm: np.ndarray, nth_drone: int):
        """First-order aerodynamic drag (Forster, 2015)."""
        base_rot = np.array(
            p.getMatrixFromQuaternion(self.quat[nth_drone])
        ).reshape(3, 3)
        drag_factor = -1 * self.DRAG_COEFF * np.sum(2 * np.pi * rpm / 60)
        drag = base_rot.T @ (drag_factor * self.vel[nth_drone])
        p.applyExternalForce(
            self.DRONE_IDS[nth_drone],
            4,
            forceObj=drag,
            posObj=[0, 0, 0],
            flags=p.LINK_FRAME,
            physicsClientId=self.CLIENT,
        )

    def _downwash(self, nth_drone: int):
        """Rotor-to-rotor downwash interaction model."""
        for i in range(self.NUM_DRONES):
            if i == nth_drone:
                continue
            delta_z = self.pos[i, 2] - self.pos[nth_drone, 2]
            delta_xy = np.linalg.norm(self.pos[i, :2] - self.pos[nth_drone, :2])
            if delta_z > 0 and delta_xy / delta_z < 2:
                alpha = (
                    self.DW_COEFF_1
                    * (delta_z / (self.PROP_RADIUS * 4)) ** 2
                    + self.DW_COEFF_2
                ) * (delta_xy / (self.PROP_RADIUS * 4)) + self.DW_COEFF_3
                dw_force = [0, 0, -alpha * self.GRAVITY]
                p.applyExternalForce(
                    self.DRONE_IDS[nth_drone],
                    4,
                    forceObj=dw_force,
                    posObj=[0, 0, 0],
                    flags=p.LINK_FRAME,
                    physicsClientId=self.CLIENT,
                )

    # ------------------------------------------------------------------
    # Internal: URDF parser
    # ------------------------------------------------------------------

    def _parse_urdf_parameters(self):
        """Read physical constants from the drone's ``.urdf`` file.

        Returns
        -------
        tuple
            (M, L, T2W, J, J_inv, KF, KM, col_h, col_r, col_z_off,
             max_speed_kmh, gnd_eff_coeff, prop_radius, drag_coeff,
             dw1, dw2, dw3)
        """
        urdf_path = str(_ASSETS_DIR / self.URDF)
        tree = etxml.parse(urdf_path).getroot()

        # mass
        m = float(tree[1][0][1].attrib["value"])
        # inertia
        ixx = float(tree[1][0][2].attrib["ixx"])
        iyy = float(tree[1][0][2].attrib["iyy"])
        izz = float(tree[1][0][2].attrib["izz"])
        J = np.diag([ixx, iyy, izz])
        J_inv = np.linalg.inv(J)
        # arm length (from properties element)
        props = tree[0].attrib
        l = float(props["arm"])
        t2w = float(props["thrust2weight"])
        kf = float(props["kf"])
        km = float(props["km"])
        max_speed_kmh = float(props["max_speed_kmh"])
        gnd_eff_coeff = float(props["gnd_eff_coeff"])
        prop_radius = float(props["prop_radius"])
        drag_xy = float(props["drag_coeff_xy"])
        drag_z = float(props["drag_coeff_z"])
        drag_coeff = np.array([drag_xy, drag_xy, drag_z])
        dw1 = float(props["dw_coeff_1"])
        dw2 = float(props["dw_coeff_2"])
        dw3 = float(props["dw_coeff_3"])
        # collision geometry
        col_el = tree[1][2][1][0]  # cylinder element
        col_h = float(col_el.attrib["length"])
        col_r = float(col_el.attrib["radius"])
        offsets = [float(s) for s in tree[1][2][0].attrib["xyz"].split()]
        col_z_off = offsets[2]

        return (
            m, l, t2w, J, J_inv, kf, km,
            col_h, col_r, col_z_off,
            max_speed_kmh, gnd_eff_coeff, prop_radius, drag_coeff,
            dw1, dw2, dw3,
        )
