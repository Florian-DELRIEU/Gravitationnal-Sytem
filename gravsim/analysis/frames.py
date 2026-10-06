"""Reference frames, applied to a recorded trajectory (the physics is always inertial).

Every frame returns a :class:`FrameView` with positions and velocities *as seen
in that frame*. In a rotating frame, v' = R(-theta) (v - V_origin) - omega x r'.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from ..core.trajectory import Trajectory
from .diagnostics import barycenter


@dataclass
class FrameView:
    t: np.ndarray
    pos: np.ndarray  # (T, N, 2)
    vel: np.ndarray  # (T, N, 2)
    label: str
    origin: np.ndarray  # (T, 2) origin position in the inertial frame
    angle: np.ndarray  # (T,) rotation angle of the frame axes (0 if not rotating)
    omega: np.ndarray  # (T,) angular velocity of the frame (0 if not rotating)


def _translated(traj, origin, v_origin, label):
    zeros = np.zeros(len(traj))
    return FrameView(traj.t, traj.pos - origin[:, None, :], traj.vel - v_origin[:, None, :], label, origin, zeros, zeros)


def inertial(traj: Trajectory) -> FrameView:
    zeros2 = np.zeros((len(traj), 2))
    return _translated(traj, zeros2, zeros2, "inertiel")


def barycentric(traj: Trajectory) -> FrameView:
    r, v = barycenter(traj)
    return _translated(traj, r, v, "barycentrique")


def centered(traj: Trajectory, body) -> FrameView:
    k = traj.index(body)
    return _translated(traj, traj.pos[:, k], traj.vel[:, k], f"centré sur {traj.names[k]}")


def rotating(traj: Trajectory, a, b) -> FrameView:
    """Frame rotating with the pair (a, b): origin at their barycentre, +x axis from a to b."""
    ia, ib = traj.index(a), traj.index(b)
    ma, mb = traj.masses[ia], traj.masses[ib]
    wa, wb = (0.5, 0.5) if ma + mb == 0 else (ma / (ma + mb), mb / (ma + mb))
    origin = wa * traj.pos[:, ia] + wb * traj.pos[:, ib]
    v_origin = wa * traj.vel[:, ia] + wb * traj.vel[:, ib]
    dr = traj.pos[:, ib] - traj.pos[:, ia]
    dv = traj.vel[:, ib] - traj.vel[:, ia]
    theta = np.unwrap(np.arctan2(dr[:, 1], dr[:, 0]))
    omega = (dr[:, 0] * dv[:, 1] - dr[:, 1] * dv[:, 0]) / np.einsum("tk,tk->t", dr, dr)
    c, s = np.cos(theta)[:, None], np.sin(theta)[:, None]

    def rot(vec):  # apply R(-theta) to (T, N, 2)
        x, y = vec[..., 0], vec[..., 1]
        return np.stack([c * x + s * y, -s * x + c * y], axis=-1)

    pos = rot(traj.pos - origin[:, None, :])
    vel = rot(traj.vel - v_origin[:, None, :])
    vel = vel - omega[:, None, None] * np.stack([-pos[..., 1], pos[..., 0]], axis=-1)
    label = f"tournant {traj.names[ia]}–{traj.names[ib]}"
    return FrameView(traj.t, pos, vel, label, origin, theta, omega)


def view(traj: Trajectory, spec) -> FrameView:
    """Frame from a spec: 'inertial', 'barycentric', ('body', name) or ('rotating', a, b)."""
    if spec in ("inertial", "inertiel"):
        return inertial(traj)
    if spec in ("barycentric", "barycentrique"):
        return barycentric(traj)
    if isinstance(spec, (tuple, list)) and spec[0] == "body":
        return centered(traj, spec[1])
    if isinstance(spec, (tuple, list)) and spec[0] == "rotating":
        return rotating(traj, spec[1], spec[2])
    raise ValueError(f"unknown frame spec {spec!r}")


# --- restricted three-body tools ----------------------------------------------


def lagrange_points(m1: float, m2: float, separation: float = 1.0) -> dict[str, np.ndarray]:
    """L1..L5 in the frame rotating with (m1, m2): origin at the barycentre, m1 on -x, m2 on +x.

    Exact for a circular orbit of the pair.
    """
    if m1 <= 0 or m2 <= 0:
        raise ValueError("both masses must be positive")
    mu = m2 / (m1 + m2)
    x1, x2 = -mu, 1.0 - mu

    def f(x):  # x-component of the effective acceleration on the axis (normalised units)
        return x - (1 - mu) * (x - x1) / abs(x - x1) ** 3 - mu * (x - x2) / abs(x - x2) ** 3

    eps = 1e-12
    l1 = brentq(f, x1 + eps, x2 - eps)
    l2 = brentq(f, x2 + eps, x2 + 2.0)
    l3 = brentq(f, x1 - 2.0, x1 - eps)
    h = np.sqrt(3.0) / 2.0
    pts = {"L1": (l1, 0.0), "L2": (l2, 0.0), "L3": (l3, 0.0), "L4": (0.5 - mu, h), "L5": (0.5 - mu, -h)}
    return {k: separation * np.array(v) for k, v in pts.items()}


def jacobi_constant(traj: Trajectory, body, a, b) -> np.ndarray:
    """Jacobi constant of ``body`` (ideally a test particle) in the frame rotating with (a, b).

    C = omega^2 |r'|^2 + 2 G m_a / r_a + 2 G m_b / r_b - |v'|^2, conserved in the
    circular restricted three-body problem.
    """
    rv = rotating(traj, a, b)
    k, ia, ib = traj.index(body), traj.index(a), traj.index(b)
    r = rv.pos[:, k]
    ra = np.hypot(*(traj.pos[:, k] - traj.pos[:, ia]).T)
    rb = np.hypot(*(traj.pos[:, k] - traj.pos[:, ib]).T)
    G = traj.G
    return (rv.omega**2 * np.einsum("tk,tk->t", r, r) + 2 * G * traj.masses[ia] / ra
            + 2 * G * traj.masses[ib] / rb - np.einsum("tk,tk->t", rv.vel[:, k], rv.vel[:, k]))
