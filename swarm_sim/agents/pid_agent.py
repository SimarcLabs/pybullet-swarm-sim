"""
PID Agent — cascaded position → attitude → motor-RPM controller.

This is the workhorse controller for non-RL swarm demos.  It implements a
two-stage PID cascade:

1. **Position PID** → desired thrust magnitude + desired orientation
2. **Attitude PID** → per-motor RPMs via a mixing matrix

Tuned for the Crazyflie 2.x (27 g) by default, but the gains can be
overridden in the constructor.

Example
-------
>>> from swarm_sim.agents.pid_agent import PIDAgent
>>> agent = PIDAgent()
>>> rpm = agent.compute_action(obs=state_vector, target=np.array([0, 0, 1]))
"""

from __future__ import annotations

import math

import numpy as np
import pybullet as p
from scipy.spatial.transform import Rotation

from swarm_sim.agents.base_agent import BaseAgent


class PIDAgent(BaseAgent):
    """Cascaded PID position + attitude controller.

    Parameters
    ----------
    drone_id : int
        Index of the drone this agent controls.
    kf : float
        Thrust coefficient (RPM² → Newtons).
    km : float
        Torque coefficient (RPM² → N·m).
    mass : float
        Drone mass in kg.
    gravity : float
        Gravitational acceleration (m/s²).
    p_pos : np.ndarray
        Position-loop proportional gains ``[kp_x, kp_y, kp_z]``.
    i_pos : np.ndarray
        Position-loop integral gains.
    d_pos : np.ndarray
        Position-loop derivative gains.
    p_att : np.ndarray
        Attitude-loop proportional gains ``[kp_roll, kp_pitch, kp_yaw]``.
    i_att : np.ndarray
        Attitude-loop integral gains.
    d_att : np.ndarray
        Attitude-loop derivative gains.
    max_rpm : float
        Upper saturation for motor commands.
    """

    def __init__(
        self,
        drone_id: int = 0,
        kf: float = 3.16e-10,
        km: float = 7.94e-12,
        mass: float = 0.027,
        gravity: float = 9.8,
        p_pos: np.ndarray | None = None,
        i_pos: np.ndarray | None = None,
        d_pos: np.ndarray | None = None,
        p_att: np.ndarray | None = None,
        i_att: np.ndarray | None = None,
        d_att: np.ndarray | None = None,
        max_rpm: float = 21_703.0,
    ):
        super().__init__(drone_id=drone_id)

        self.KF = kf
        self.KM = km
        self.MASS = mass
        self.GRAVITY = gravity * mass
        self.MAX_RPM = max_rpm

        # Position PID gains (force domain)
        self.P_POS = np.array(p_pos) if p_pos is not None else np.array([0.4, 0.4, 1.25])
        self.I_POS = np.array(i_pos) if i_pos is not None else np.array([0.05, 0.05, 0.05])
        self.D_POS = np.array(d_pos) if d_pos is not None else np.array([0.2, 0.2, 0.5])

        # Attitude PID gains (torque domain)
        self.P_ATT = np.array(p_att) if p_att is not None else np.array([70_000.0, 70_000.0, 60_000.0])
        self.I_ATT = np.array(i_att) if i_att is not None else np.array([0.0, 0.0, 500.0])
        self.D_ATT = np.array(d_att) if d_att is not None else np.array([20_000.0, 20_000.0, 12_000.0])

        # Crazyflie PWM ↔ RPM conversion
        self.PWM2RPM_SCALE = 0.2685
        self.PWM2RPM_CONST = 4070.3
        self.MIN_PWM = 20_000
        self.MAX_PWM = 65_535

        # Motor mixing matrix (X-configuration)
        self.MIXER = np.array([
            [-0.5, -0.5, -1],
            [-0.5,  0.5,  1],
            [ 0.5,  0.5, -1],
            [ 0.5, -0.5,  1],
        ])

        self.reset()

    def reset(self):
        """Zero all integrators and derivative buffers."""
        self._integral_pos = np.zeros(3)
        self._last_rpy = np.zeros(3)
        self._integral_rpy = np.zeros(3)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_action(
        self,
        obs: np.ndarray,
        target: np.ndarray,
        dt: float = 1 / 240,
    ) -> np.ndarray:
        """Compute RPMs to fly the drone toward ``target``.

        Parameters
        ----------
        obs : np.ndarray
            ``(20,)`` state vector — see :meth:`BaseSwarmEnv.get_drone_state`.
        target : np.ndarray
            ``(3,)`` desired XYZ.
        dt : float
            Control timestep (seconds).

        Returns
        -------
        np.ndarray
            ``(4,)`` RPM commands, clipped to ``[0, MAX_RPM]``.
        """
        cur_pos = obs[0:3]
        cur_quat = obs[3:7]
        cur_vel = obs[10:13]

        thrust_pwm, target_euler = self._position_control(
            dt, cur_pos, cur_quat, cur_vel, target
        )
        rpm = self._attitude_control(dt, thrust_pwm, cur_quat, target_euler)
        return np.clip(rpm, 0, self.MAX_RPM)

    # ------------------------------------------------------------------
    # Position PID
    # ------------------------------------------------------------------

    def _position_control(self, dt, cur_pos, cur_quat, cur_vel, target_pos):
        """Outer PID loop: position error → desired thrust + orientation."""
        rotation = np.array(p.getMatrixFromQuaternion(cur_quat)).reshape(3, 3)

        pos_e = target_pos - cur_pos
        vel_e = -cur_vel  # target velocity = 0

        self._integral_pos += pos_e * dt
        self._integral_pos = np.clip(self._integral_pos, -2.0, 2.0)
        self._integral_pos[2] = np.clip(self._integral_pos[2], -0.15, 0.15)

        # PID force = P·e + I·∫e + D·ė + gravity compensation
        gravity_comp = np.array([0, 0, self.GRAVITY])
        target_thrust = (
            self.P_POS * pos_e
            + self.I_POS * self._integral_pos
            + self.D_POS * vel_e
            + gravity_comp
        )

        # Scalar thrust projected onto body z-axis
        scalar_thrust = max(0.0, np.dot(target_thrust, rotation[:, 2]))
        thrust_pwm = (
            math.sqrt(scalar_thrust / (4 * self.KF)) - self.PWM2RPM_CONST
        ) / self.PWM2RPM_SCALE

        # Desired orientation from thrust vector
        norm = np.linalg.norm(target_thrust)
        target_z = target_thrust / norm if norm > 1e-6 else np.array([0, 0, 1])
        target_x_c = np.array([1.0, 0.0, 0.0])  # heading = 0 yaw
        cross = np.cross(target_z, target_x_c)
        cross_norm = np.linalg.norm(cross)
        target_y = cross / cross_norm if cross_norm > 1e-6 else np.array([0, 1, 0])
        target_x = np.cross(target_y, target_z)
        target_rot = np.column_stack([target_x, target_y, target_z])
        target_euler = Rotation.from_matrix(target_rot).as_euler("XYZ")

        return thrust_pwm, target_euler

    # ------------------------------------------------------------------
    # Attitude PID
    # ------------------------------------------------------------------

    def _attitude_control(self, dt, thrust_pwm, cur_quat, target_euler):
        """Inner PID loop: attitude error → per-motor RPMs."""
        cur_rot = np.array(p.getMatrixFromQuaternion(cur_quat)).reshape(3, 3)
        cur_rpy = np.array(p.getEulerFromQuaternion(cur_quat))

        target_rot = Rotation.from_euler("XYZ", target_euler).as_matrix()
        rot_err_mat = target_rot.T @ cur_rot - cur_rot.T @ target_rot
        rot_e = np.array([rot_err_mat[2, 1], rot_err_mat[0, 2], rot_err_mat[1, 0]])

        rpy_rates_e = -(cur_rpy - self._last_rpy) / dt
        self._last_rpy = cur_rpy.copy()

        self._integral_rpy -= rot_e * dt
        self._integral_rpy = np.clip(self._integral_rpy, -1500.0, 1500.0)
        self._integral_rpy[:2] = np.clip(self._integral_rpy[:2], -1.0, 1.0)

        target_torques = (
            -self.P_ATT * rot_e
            + self.D_ATT * rpy_rates_e
            + self.I_ATT * self._integral_rpy
        )
        target_torques = np.clip(target_torques, -3200, 3200)

        pwm = thrust_pwm + self.MIXER @ target_torques
        pwm = np.clip(pwm, self.MIN_PWM, self.MAX_PWM)
        return self.PWM2RPM_SCALE * pwm + self.PWM2RPM_CONST
