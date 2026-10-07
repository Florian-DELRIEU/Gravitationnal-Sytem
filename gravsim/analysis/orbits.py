"""Orbital analysis of a body relative to a reference body, and of a pair."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core import kepler
from ..core.trajectory import Trajectory


def default_reference(traj: Trajectory, body) -> int:
    """Index of the most massive body other than ``body``."""
    k = traj.index(body)
    masses = traj.masses.copy()
    masses[k] = -np.inf
    return int(np.argmax(masses))


def pair_mu(traj: Trajectory, body, reference) -> float:
    k, r = traj.index(body), traj.index(reference)
    return kepler.gravitational_parameter(traj.G, traj.masses[k], traj.masses[r], bool(traj.fixed[r]))


def relative_state(traj: Trajectory, body, reference) -> tuple[np.ndarray, np.ndarray]:
    k, r = traj.index(body), traj.index(reference)
    return traj.pos[:, k] - traj.pos[:, r], traj.vel[:, k] - traj.vel[:, r]


def osculating_elements(traj: Trajectory, body, reference=None) -> dict[str, np.ndarray]:
    """Instantaneous two-body elements of ``body`` around ``reference`` (default: most massive other body)."""
    ref = default_reference(traj, body) if reference is None else traj.index(reference)
    if traj.fixed[traj.index(body)]:
        raise ValueError("a fixed body has no orbit")
    rel, vrel = relative_state(traj, body, ref)
    el = kepler.elements_from_state(rel, vrel, pair_mu(traj, body, ref))
    return el


def measure_period(traj: Trajectory, body, reference=None) -> tuple[float, np.ndarray]:
    """Mean time for the relative polar angle to sweep 2 pi, and the crossing times.

    Model-free (does not assume a Kepler orbit). Returns nan if less than one turn.
    """
    ref = default_reference(traj, body) if reference is None else traj.index(reference)
    rel, _ = relative_state(traj, body, ref)
    theta = np.unwrap(np.arctan2(rel[:, 1], rel[:, 0]))
    sign = 1.0 if theta[-1] >= theta[0] else -1.0
    s = sign * (theta - theta[0]) / (2 * np.pi)
    turns = np.arange(1, int(np.floor(s.max())) + 1)
    if len(turns) == 0:
        return float("nan"), np.array([])
    idx = np.searchsorted(np.maximum.accumulate(s), turns)
    lo = idx - 1
    frac = (turns - s[lo]) / (s[idx] - s[lo])
    times = traj.t[lo] + frac * (traj.t[idx] - traj.t[lo])
    times = np.concatenate([[traj.t[0]], times])
    return float(np.mean(np.diff(times))), times


def hill_radius(a: float, e: float, m: float, M: float) -> float:
    """Hill sphere radius at periapsis."""
    return a * (1 - e) * (m / (3 * M)) ** (1 / 3)


@dataclass
class PairAnalysis:
    names: tuple[str, str]
    t: np.ndarray
    distance: np.ndarray
    relative_speed: np.ndarray
    reduced_mass: float
    relative_energy: np.ndarray  # energy of the relative motion (point masses)
    escape_speed: np.ndarray
    kind: np.ndarray  # 'elliptic' | 'parabolic' | 'hyperbolic'
    elements: dict

    @property
    def closest(self) -> tuple[float, float]:
        k = int(np.argmin(self.distance))
        return float(self.t[k]), float(self.distance[k])

    @property
    def farthest(self) -> tuple[float, float]:
        k = int(np.argmax(self.distance))
        return float(self.t[k]), float(self.distance[k])


def pair_analysis(traj: Trajectory, a, b) -> PairAnalysis:
    """Relative motion of ``b`` around ``a`` (two-body view, other bodies ignored)."""
    ia, ib = traj.index(a), traj.index(b)
    rel, vrel = relative_state(traj, ib, ia)
    mu = pair_mu(traj, ib, ia)
    ma, mb = traj.masses[ia], traj.masses[ib]
    red = ma * mb / (ma + mb) if ma + mb > 0 else 0.0
    if traj.fixed[ia]:
        red = mb
    d = np.hypot(*rel.T)
    v = np.hypot(*vrel.T)
    el = kepler.elements_from_state(rel, vrel, mu)
    energy = 0.5 * red * v**2 - traj.G * ma * mb / d
    return PairAnalysis((traj.names[ia], traj.names[ib]), traj.t, d, v, red, energy,
                        np.sqrt(2 * mu / d), el["kind"], el)


RADIAL_ECCENTRICITY = 1.0 - 1e-6  # above this, K = ... / sqrt(1 - e^2) is meaningless


@dataclass
class ReflexSignature:
    """Expected imprint of one companion on the star's motion (two-body formulas, initial elements)."""

    name: str
    period: float
    a: float
    e: float
    rv_semi_amplitude: float  # m/s, for the given observer
    astrometric_amplitude: float  # AU, semi-major axis of the star's reflex orbit
    direction: int  # +1 counterclockwise, -1 clockwise

    @property
    def frequency(self) -> float:
        return 1.0 / self.period


def reflex_signatures(traj: Trajectory, star, sin_i: float = 1.0) -> list[ReflexSignature]:
    """Ground truth for spectral studies: every bound companion of ``star``, sorted by period."""
    from ..core.units import au_per_yr_to_m_s

    s = traj.index(star)
    out = []
    for k, name in enumerate(traj.names):
        if k == s or traj.masses[k] == 0 or traj.fixed[k]:
            continue
        mu = pair_mu(traj, k, s)
        el = kepler.elements_from_state(traj.pos[0, k] - traj.pos[0, s], traj.vel[0, k] - traj.vel[0, s], mu)
        e, a, P = float(el["e"]), float(el["a"]), float(el["period"])
        if not np.isfinite(P) or e >= RADIAL_ECCENTRICITY:
            continue  # unbound, or a radial fall: not a planet with a Keplerian reflex signal
        m, M = traj.masses[k], traj.masses[s]
        K = (2 * np.pi * traj.G / P) ** (1 / 3) * m * sin_i / (M + m) ** (2 / 3) / np.sqrt(1 - e * e)
        out.append(ReflexSignature(name, P, a, e, float(au_per_yr_to_m_s(K)), a * m / (M + m),
                                   1 if el["h"] > 0 else -1))
    return sorted(out, key=lambda r: r.period)
