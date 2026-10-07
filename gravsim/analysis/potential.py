"""Gravitational potential, effective potential and Lagrange points of a pair of bodies (no Qt).

Potential per unit mass, with the same force law as ``core/forces.py`` (a point inside a homogeneous sphere of
radius R feels the inner law, so the potential has no singularity at the centre of a body with a radius):

    r >= R : Phi = -G m / r
    r <  R : Phi = -G m (3 R^2 - r^2) / (2 R^3)

In the frame rotating with a pair (angular velocity omega, centre c) the effective potential adds the centrifugal
term: Phi_eff = Phi - omega^2 |p - c|^2 / 2. The Lagrange points are the equilibria of that field.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import frames


@dataclass
class PairFrame:
    center: np.ndarray  # (2,) barycentre of the pair, inertial frame
    velocity: np.ndarray  # (2,) velocity of that barycentre
    angle: float  # direction a -> b (rad)
    omega: float  # (dr x dv) / |dr|^2, signed (rad/yr)
    separation: float  # |r_b - r_a|


def gravitational_potential(points, positions, masses, G: float, radii=None) -> np.ndarray:
    """Phi at ``points`` (..., 2) due to all bodies. Massless bodies contribute nothing."""
    points = np.asarray(points, dtype=float)
    positions = np.asarray(positions, dtype=float)
    masses = np.asarray(masses, dtype=float)
    radii = np.zeros(len(masses)) if radii is None else np.asarray(radii, dtype=float)
    phi = np.zeros(points.shape[:-1])
    for k in range(len(masses)):
        if masses[k] <= 0:
            continue
        d = points - positions[k]
        r2 = d[..., 0] ** 2 + d[..., 1] ** 2
        R = radii[k]
        with np.errstate(divide="ignore"):
            outer = -G * masses[k] / np.sqrt(r2)
        if R > 0:
            inner = -G * masses[k] * (3.0 * R * R - r2) / (2.0 * R**3)
            phi += np.where(r2 >= R * R, outer, inner)
        else:
            phi += outer
    return phi


def pair_frame(positions, velocities, masses, a: int, b: int) -> PairFrame:
    """State of the pair (a, b): barycentre, orientation and angular velocity of the line a -> b."""
    if a == b:
        raise ValueError("the two bodies of a pair must differ")
    ma, mb = float(masses[a]), float(masses[b])
    if ma + mb <= 0:
        raise ValueError("the pair has no mass")
    dr = np.asarray(positions[b], dtype=float) - np.asarray(positions[a], dtype=float)
    dv = np.asarray(velocities[b], dtype=float) - np.asarray(velocities[a], dtype=float)
    d2 = float(dr @ dr)
    if d2 <= 0:
        raise ValueError("the two bodies coincide")
    wa, wb = ma / (ma + mb), mb / (ma + mb)
    return PairFrame(center=wa * np.asarray(positions[a], float) + wb * np.asarray(positions[b], float),
                     velocity=wa * np.asarray(velocities[a], float) + wb * np.asarray(velocities[b], float),
                     angle=float(np.arctan2(dr[1], dr[0])), omega=float((dr[0] * dv[1] - dr[1] * dv[0]) / d2),
                     separation=float(np.sqrt(d2)))


def effective_potential(points, positions, masses, G: float, frame: PairFrame, radii=None) -> np.ndarray:
    """Phi(points) - omega^2 |points - center|^2 / 2 (potential felt in the frame rotating with the pair)."""
    points = np.asarray(points, dtype=float)
    d = points - frame.center
    return gravitational_potential(points, positions, masses, G, radii) - 0.5 * frame.omega**2 * (
        d[..., 0] ** 2 + d[..., 1] ** 2)


def lagrange_points_inertial(positions, velocities, masses, a: int, b: int) -> dict[str, np.ndarray]:
    """L1..L5 of the pair (a, b) in the inertial frame at this instant.

    Uses the two-body formula with the instantaneous separation: exact for a circular orbit of the pair.
    """
    if masses[a] <= 0 or masses[b] <= 0:
        raise ValueError("no Lagrange points when one body of the pair is massless")
    fr = pair_frame(positions, velocities, masses, a, b)
    c, s = np.cos(fr.angle), np.sin(fr.angle)
    rot = np.array([[c, -s], [s, c]])  # R(angle): rotating coordinates -> inertial
    pts = frames.lagrange_points(float(masses[a]), float(masses[b]), fr.separation)
    return {name: fr.center + rot @ p for name, p in pts.items()}


def critical_levels(positions, masses, G: float, frame: PairFrame, lagrange: dict, radii=None) -> dict[str, float]:
    """Phi_eff at L1, L2, L3: the zero-velocity curves through the collinear points (L1 = Roche lobe)."""
    return {name: float(effective_potential(lagrange[name], positions, masses, G, frame, radii))
            for name in ("L1", "L2", "L3")}


def zero_velocity_level(r, v, positions, masses, G: float, frame: PairFrame, radii=None) -> float:
    """Phi_eff(r) + |v'|^2 / 2, with v' the velocity in the rotating frame.

    For a test particle in the circular restricted problem this is conserved (it equals -C/2, C = Jacobi
    constant): the body can only reach the region where Phi_eff <= this level.
    """
    r, v = np.asarray(r, dtype=float), np.asarray(v, dtype=float)
    rel = r - frame.center
    v_rot = v - frame.velocity - frame.omega * np.array([-rel[1], rel[0]])
    return float(effective_potential(r, positions, masses, G, frame, radii)) + 0.5 * float(v_rot @ v_rot)
