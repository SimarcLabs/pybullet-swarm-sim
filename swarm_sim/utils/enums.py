"""Enumeration types for the swarm simulation library."""

from enum import Enum


class DroneModel(Enum):
    """Available drone URDF models.

    Each value corresponds to a ``.urdf`` filename in ``swarm_sim/assets/``.

    Attributes
    ----------
    CF2X : str
        Bitcraze Crazyflie 2.x in X-configuration (27 g).
    CF2P : str
        Bitcraze Crazyflie 2.x in +-configuration (27 g).
    """

    CF2X = "cf2x"
    CF2P = "cf2p"


class Physics(Enum):
    """Physics engine variants.

    Attributes
    ----------
    PYB : str
        Base PyBullet rigid-body dynamics.
    PYB_GND : str
        PyBullet + analytical ground-effect model.
    PYB_DRAG : str
        PyBullet + first-order aerodynamic drag.
    PYB_DW : str
        PyBullet + rotor downwash interaction.
    PYB_GND_DRAG_DW : str
        PyBullet + ground effect + drag + downwash (most realistic).
    """

    PYB = "pyb"
    PYB_GND = "pyb_gnd"
    PYB_DRAG = "pyb_drag"
    PYB_DW = "pyb_dw"
    PYB_GND_DRAG_DW = "pyb_gnd_drag_dw"


class FormationType(Enum):
    """Pre-defined swarm formation shapes.

    Attributes
    ----------
    LINE : str
        Drones arranged in a straight line.
    V : str
        V-shaped formation (like migrating birds).
    GRID : str
        Rectangular grid pattern.
    RING : str
        Circular ring around a center point.
    HELIX : str
        3-D helical spiral.
    """

    LINE = "line"
    V = "v"
    GRID = "grid"
    RING = "ring"
    HELIX = "helix"


class ActionType(Enum):
    """How the agent's output is interpreted.

    Attributes
    ----------
    RPM : str
        Direct per-motor RPM commands.
    VEL : str
        3-D velocity targets tracked by an internal PID.
    """

    RPM = "rpm"
    VEL = "vel"
