"""Two-body (Kepler) formulas, in the plane.

``mu`` is the gravitational parameter of the relative motion: G (m_i + m_j) for
two free bodies, G m_j when the attracting body j is fixed (it does not recoil,
so the reduced two-body problem does not apply).
"""

from __future__ import annotations

import math

import numpy as np

PARABOLIC_TOL = 1e-9


def gravitational_parameter(G: float, m_body: float, m_ref: float, ref_fixed: bool = False) -> float:
    return G * m_ref if ref_fixed else G * (m_body + m_ref)


def circular_speed(mu: float, r: float) -> float:
    return math.sqrt(mu / r)


def escape_speed(mu: float, r: float) -> float:
    return math.sqrt(2.0 * mu / r)


def apsis_speed(mu: float, r: float, e: float, at: str = "periapsis") -> float:
    """Speed at an apsis located at distance ``r`` of an orbit of eccentricity ``e``."""
    if e < 0:
        raise ValueError("eccentricity must be >= 0")
    if at == "periapsis":
        return math.sqrt(mu * (1.0 + e) / r)
    if at == "apoapsis":
        if e >= 1:
            raise ValueError("an unbound orbit has no apoapsis")
        return math.sqrt(mu * (1.0 - e) / r)
    raise ValueError("at must be 'periapsis' or 'apoapsis'")


def orbital_velocity(r_rel, mu: float, e: float = 0.0, at: str = "periapsis", clockwise: bool = False) -> np.ndarray:
    """Relative velocity putting a body at relative position ``r_rel`` on an apsis.

    The velocity is perpendicular to ``r_rel``; counterclockwise by default.
    """
    r_rel = np.asarray(r_rel, dtype=float)
    r = float(np.hypot(*r_rel))
    if r == 0:
        raise ValueError("bodies are at the same position")
    speed = apsis_speed(mu, r, e, at)
    tangent = np.array([-r_rel[1], r_rel[0]]) / r
    return speed * (-tangent if clockwise else tangent)


def period(a: float, mu: float) -> float:
    return 2.0 * math.pi * math.sqrt(a**3 / mu)


def elements_from_state(r_rel, v_rel, mu: float) -> dict:
    """Osculating elements of the relative orbit. Works on single vectors (2,) or arrays (..., 2).

    Returns a dict of arrays: a (negative if hyperbolic, inf if parabolic), e,
    omega (argument of periapsis, rad), h (specific angular momentum, >0 if
    counterclockwise), energy (specific orbital energy), period (nan if unbound),
    periapsis, apoapsis (inf if unbound), true_anomaly (rad), kind ('elliptic' | 'parabolic' | 'hyperbolic',
    from the sign of the energy).
    """
    r_rel = np.asarray(r_rel, dtype=float)
    v_rel = np.asarray(v_rel, dtype=float)
    x, y = r_rel[..., 0], r_rel[..., 1]
    vx, vy = v_rel[..., 0], v_rel[..., 1]
    r = np.hypot(x, y)
    v2 = vx * vx + vy * vy
    h = x * vy - y * vx
    rv = x * vx + y * vy
    energy = 0.5 * v2 - mu / r
    ex = ((v2 - mu / r) * x - rv * vx) / mu
    ey = ((v2 - mu / r) * y - rv * vy) / mu
    e = np.hypot(ex, ey)
    omega = np.arctan2(ey, ex)
    # Classification uses the energy, not e alone: a radial fall from rest has e = 1 yet is bound.
    scale = 0.5 * v2 + mu / r
    rel_energy = energy / scale
    kind = np.where(rel_energy < -PARABOLIC_TOL, "elliptic", np.where(rel_energy > PARABOLIC_TOL, "hyperbolic", "parabolic"))
    bound = kind == "elliptic"
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.where(np.abs(energy) > 0, -mu / (2.0 * energy), np.inf)
        periapsis = h * h / mu / (1.0 + e)  # p / (1 + e), accurate also when h -> 0
        apoapsis = np.where(bound, a * (1.0 + e), np.inf)
        per = np.where(bound, 2.0 * np.pi * np.sqrt(np.abs(a) ** 3 / mu), np.nan)
    nu = np.arctan2(y, x) - omega
    if np.ndim(h):
        nu = np.where(h < 0, -nu, nu)
    elif h < 0:
        nu = -nu
    nu = (nu + np.pi) % (2.0 * np.pi) - np.pi
    return {
        "a": a,
        "e": e,
        "omega": omega,
        "h": h,
        "energy": energy,
        "period": per,
        "periapsis": periapsis,
        "apoapsis": apoapsis,
        "true_anomaly": nu,
        "kind": kind,
    }


def orbit_kind(e) -> np.ndarray:
    """'elliptic', 'parabolic' or 'hyperbolic' from the eccentricity alone.

    Wrong for radial orbits (e = 1 but bound): prefer ``elements_from_state(...)["kind"]``.
    """
    e = np.asarray(e)
    return np.where(e < 1 - PARABOLIC_TOL, "elliptic", np.where(e > 1 + PARABOLIC_TOL, "hyperbolic", "parabolic"))


def recommended_dt(positions, velocities, masses, G: float, fixed=None, radii=None,
                   steps_per_period: float = 200.0, steps_per_periapsis: float = 20.0) -> float:
    """Advised fixed time step: resolves the shortest period and the fastest periapsis passage.

    Each moving body is paired with its dominant attractor (largest G m / r^2);
    the step is the smallest of P / steps_per_period and sqrt(r_p^3 / mu) / steps_per_periapsis.
    A (near-)radial orbit has r_p -> 0: r_p is floored at the contact distance R_i + R_j,
    or 1e-3 of the current distance for point masses.
    """
    pos = np.asarray(positions, dtype=float)
    vel = np.asarray(velocities, dtype=float)
    masses = np.asarray(masses, dtype=float)
    n = len(masses)
    fixed = np.zeros(n, bool) if fixed is None else np.asarray(fixed, bool)
    radii = np.zeros(n) if radii is None else np.asarray(radii, dtype=float)
    best = math.inf
    for i in range(n):
        if fixed[i]:
            continue
        others = [j for j in range(n) if j != i and masses[j] > 0]
        if not others:
            continue
        d = pos[others] - pos[i]
        r2 = np.einsum("ij,ij->i", d, d)
        j = others[int(np.argmax(masses[others] / r2))]
        mu = gravitational_parameter(G, masses[i], masses[j], fixed[j])
        vj = np.zeros(2) if fixed[j] else vel[j]
        el = elements_from_state(pos[i] - pos[j], vel[i] - vj, mu)
        r_now = float(np.hypot(*(pos[i] - pos[j])))
        floor = radii[i] + radii[j] if radii[i] + radii[j] > 0 else 1e-3 * r_now
        rp = max(float(el["periapsis"]), min(floor, r_now))
        candidates = [math.sqrt(rp**3 / mu) / steps_per_periapsis]
        if np.isfinite(el["period"]):
            candidates.append(float(el["period"]) / steps_per_period)
        best = min(best, *candidates)
    if not math.isfinite(best):
        return 1e-3
    return best
