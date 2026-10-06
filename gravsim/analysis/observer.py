"""Synthetic observations of a star's reflex motion: radial velocity and astrometry.

Geometry: the simulation plane is the orbital plane. The observer looks along
the in-plane direction ``line_of_sight_deg`` and sits at ``inclination_deg``
from the plane's normal (90 deg = edge-on). Radial velocity is the barycentric
velocity projected on the line of sight, times sin(i); positive = receding.
Astrometry is the barycentric position as a complex number z = x + i y (face-on view).

Observation times are independent of the simulation step: states are
interpolated with cubic Hermite polynomials (positions from positions and
velocities, velocities from velocities and accelerations), accurate to O(h^4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..core import units
from ..core.trajectory import Trajectory
from .diagnostics import model_of


@dataclass
class Observer:
    line_of_sight_deg: float = 0.0
    inclination_deg: float = 90.0

    @property
    def direction(self) -> np.ndarray:
        a = math.radians(self.line_of_sight_deg)
        return np.array([math.cos(a), math.sin(a)])

    @property
    def sin_i(self) -> float:
        return math.sin(math.radians(self.inclination_deg))


@dataclass
class Observations:
    t: np.ndarray
    value: np.ndarray  # RV in m/s (real) or astrometry in AU (complex)
    error: np.ndarray  # 1-sigma per point (white noise level)
    kind: str  # 'rv' | 'astrometry'
    body: str
    observer: Observer | None = None

    @property
    def baseline(self) -> float:
        return float(self.t[-1] - self.t[0])


# --- signals at the trajectory samples ------------------------------------------


def barycentric_state(traj: Trajectory, body) -> tuple[np.ndarray, np.ndarray]:
    k = traj.index(body)
    m = traj.masses
    M = m.sum()
    r_cm = np.einsum("n,tnk->tk", m, traj.pos) / M
    v_cm = np.einsum("n,tnk->tk", m, traj.vel) / M
    return traj.pos[:, k] - r_cm, traj.vel[:, k] - v_cm


def radial_velocity(traj: Trajectory, body, observer: Observer | None = None, unit: str = "m/s") -> np.ndarray:
    observer = observer or Observer()
    _, v = barycentric_state(traj, body)
    vr = observer.sin_i * (v @ observer.direction)
    return units.au_per_yr_to_m_s(vr) if unit == "m/s" else vr


def astrometric_signal(traj: Trajectory, body) -> np.ndarray:
    r, _ = barycentric_state(traj, body)
    return r[:, 0] + 1j * r[:, 1]


# --- interpolation at arbitrary times ---------------------------------------------


def interpolate_state(traj: Trajectory, body, times) -> tuple[np.ndarray, np.ndarray]:
    """Barycentric position and velocity of ``body`` at arbitrary ``times`` (within the trajectory).

    Not valid across an impulse (velocity discontinuity): such intervals raise an error.
    """
    times = np.asarray(times, dtype=float)
    t = traj.t
    if times.min() < t[0] - 1e-12 or times.max() > t[-1] + 1e-12:
        raise ValueError("observation times outside the simulated interval")
    k = traj.index(body)
    hi = np.clip(np.searchsorted(t, times, side="right"), 1, len(t) - 1)
    lo = hi - 1
    for ev in traj.impulses:
        if np.any((t[lo] < ev.t) & (ev.t < t[hi]) & (times != t[lo]) & (times != t[hi])):
            raise ValueError(f"cannot interpolate across the impulse at t={ev.t}")

    rows = np.unique(np.concatenate([lo, hi]))
    acc = model_of(traj).acceleration_batch(traj.pos[rows])
    m = traj.masses
    a_cm = np.einsum("n,tnk->tk", m, acc) / m.sum()
    a_body = np.empty((len(t), 2))
    a_body[rows] = acc[:, k] - a_cm
    r, v = barycentric_state(traj, body)

    h = (t[hi] - t[lo])[:, None]
    s = ((times - t[lo]) / (t[hi] - t[lo]))[:, None]
    h00, h10, h01, h11 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s, -2 * s**3 + 3 * s**2, s**3 - s**2
    pos = h00 * r[lo] + h10 * h * v[lo] + h01 * r[hi] + h11 * h * v[hi]
    vel = h00 * v[lo] + h10 * h * a_body[lo] + h01 * v[hi] + h11 * h * a_body[hi]
    return pos, vel


# --- schedules and noise ------------------------------------------------------------


def regular_schedule(t_start: float, t_end: float, dt: float) -> np.ndarray:
    n = int(np.floor((t_end - t_start) / dt + 1e-9))
    return t_start + dt * np.arange(n + 1)


def random_schedule(t_start: float, t_end: float, n: int, rng=None, season_fraction: float = 0.0,
                    season_phase: float = 0.0) -> np.ndarray:
    """``n`` random observation times, avoiding a yearly unobservable season.

    ``season_fraction`` is the fraction of each year when the star cannot be observed
    (e.g. 0.33 for four months behind the Sun), starting at ``season_phase`` (yr).
    """
    if not 0.0 <= season_fraction < 1.0:
        raise ValueError("season_fraction must be in [0, 1)")
    rng = np.random.default_rng(rng)
    out = np.empty(0)
    for _ in range(1000):
        cand = rng.uniform(t_start, t_end, 2 * n)
        phase = (cand - season_phase) % 1.0
        out = np.concatenate([out, cand[phase >= season_fraction]])
        if len(out) >= n:
            return np.sort(out[:n])
    raise ValueError("the whole observing interval falls in the unobservable season; "
                     "shift season_phase or reduce season_fraction")


def red_noise(times, sigma: float, tau: float, rng=None) -> np.ndarray:
    """Exponentially correlated (Ornstein-Uhlenbeck) noise of std ``sigma`` and timescale ``tau``."""
    rng = np.random.default_rng(rng)
    times = np.asarray(times, dtype=float)
    out = np.empty(len(times))
    out[0] = sigma * rng.standard_normal()
    for k in range(1, len(times)):
        rho = math.exp(-(times[k] - times[k - 1]) / tau)
        out[k] = rho * out[k - 1] + sigma * math.sqrt(1 - rho * rho) * rng.standard_normal()
    return out


def observe_rv(traj: Trajectory, body, times, observer: Observer | None = None, sigma: float = 0.0,
               red_sigma: float = 0.0, red_tau: float | None = None, rng=None) -> Observations:
    """Radial velocities (m/s) at ``times`` with white noise ``sigma`` and optional red noise."""
    observer = observer or Observer()
    rng = np.random.default_rng(rng)
    times = np.asarray(times, dtype=float)
    _, vel = interpolate_state(traj, body, times)
    vr = units.au_per_yr_to_m_s(observer.sin_i * (vel @ observer.direction))
    if sigma > 0:
        vr = vr + sigma * rng.standard_normal(len(times))
    if red_sigma > 0:
        if not red_tau:
            raise ValueError("red noise needs a correlation time red_tau")
        vr = vr + red_noise(times, red_sigma, red_tau, rng)
    return Observations(times, vr, np.full(len(times), sigma), "rv", traj.names[traj.index(body)], observer)


def observe_astrometry(traj: Trajectory, body, times, sigma: float = 0.0, rng=None) -> Observations:
    """Barycentric positions (complex, AU) at ``times`` with white noise ``sigma`` on each axis."""
    rng = np.random.default_rng(rng)
    times = np.asarray(times, dtype=float)
    pos, _ = interpolate_state(traj, body, times)
    z = pos[:, 0] + 1j * pos[:, 1]
    if sigma > 0:
        z = z + sigma * (rng.standard_normal(len(times)) + 1j * rng.standard_normal(len(times)))
    return Observations(times, z, np.full(len(times), sigma), "astrometry", traj.names[traj.index(body)])


# --- expected signals (two-body formulas, for comparison with what is measured) ------


def expected_rv_semi_amplitude(period: float, m_planet: float, m_star: float, e: float = 0.0,
                               sin_i: float = 1.0, G: float = units.G) -> float:
    """K in m/s: (2 pi G / P)^(1/3) m sin i / (M + m)^(2/3) / sqrt(1 - e^2)."""
    k = (2 * math.pi * G / period) ** (1 / 3) * m_planet * sin_i / (m_star + m_planet) ** (2 / 3) / math.sqrt(1 - e * e)
    return units.au_per_yr_to_m_s(k)


def expected_astrometric_amplitude(a: float, m_planet: float, m_star: float) -> float:
    """Semi-major axis (AU) of the star's reflex orbit."""
    return a * m_planet / (m_star + m_planet)
