"""Discrete events: impulses (velocity kicks) and collisions.

Collision detection is continuous: within each step the relative position of
every candidate pair is modelled by the cubic Hermite polynomial matching the
positions and velocities at both ends, so the squared distance is a degree-6
polynomial whose first entry into contact is found exactly (grazing contacts
between two steps are not missed). The contact time is then refined with
``brentq`` on the integrator's own interpolant.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import brentq

DIRECTIONS = ("prograde", "radial", "angle")
CONTACT_TOL = 1e-9  # relative tolerance on R_i + R_j when tracking ongoing contacts


@dataclass
class Impulse:
    """Instantaneous velocity change of a body.

    dv        signed magnitude (AU/yr): > 0 speeds up along ``direction``, < 0 the opposite way
    t         time of application (yr)
    direction 'prograde'  along the velocity relative to ``reference`` (negative dv = retrograde)
              'radial'    along the line from ``reference`` to the body (negative dv = inward)
              'angle'     along the absolute angle ``angle_deg`` (counterclockwise from +x)
    reference name of the reference body; default: the most massive other body
    """

    body: str
    dv: float
    t: float
    direction: str = "prograde"
    reference: str | None = None
    angle_deg: float = 0.0

    def __post_init__(self):
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}, got {self.direction!r}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImpulseEvent:
    t: float
    body: int
    position: np.ndarray
    velocity_before: np.ndarray
    dv: np.ndarray
    mass: float
    applied: bool = True  # False when the body is fixed
    kind: str = field(default="impulse", init=False)

    @property
    def delta_energy(self) -> float:
        v0, v1 = self.velocity_before, self.velocity_before + self.dv
        return 0.5 * self.mass * float(v1 @ v1 - v0 @ v0) if self.applied else 0.0

    def delta_momentum(self) -> np.ndarray:
        return self.mass * self.dv if self.applied else np.zeros(2)

    def delta_angular_momentum(self, origin=(0.0, 0.0)) -> float:
        if not self.applied:
            return 0.0
        r = self.position - np.asarray(origin, dtype=float)
        return self.mass * float(r[0] * self.dv[1] - r[1] * self.dv[0])


@dataclass
class CollisionEvent:
    t: float
    i: int
    j: int
    relative_speed: float
    impact_angle_deg: float  # 0 = head-on, 90 = grazing
    positions: np.ndarray
    velocities: np.ndarray
    kind: str = field(default="collision", init=False)


@dataclass
class SeparationEvent:
    """End of an overlap between two bodies (detected at the end of a step)."""

    t: float
    i: int
    j: int
    kind: str = field(default="separation", init=False)


def impulse_vector(impulse: Impulse, i: int, ref: int | None, pos: np.ndarray, vel: np.ndarray) -> np.ndarray:
    """Delta-v vector for ``impulse`` applied to body ``i`` (reference body index ``ref``)."""
    if impulse.direction == "angle":
        a = math.radians(impulse.angle_deg)
        u = np.array([math.cos(a), math.sin(a)])
    else:
        if impulse.direction == "prograde":
            w = vel[i] - (vel[ref] if ref is not None else 0.0)
        else:
            if ref is None:
                raise ValueError("a radial impulse needs a reference body")
            w = pos[i] - pos[ref]
        norm = float(np.hypot(*w))
        if norm == 0:
            raise ValueError(f"direction {impulse.direction!r} is undefined (zero relative vector)")
        u = w / norm
    return impulse.dv * u


# --- collision detection ------------------------------------------------------


class CollisionDetector:
    def __init__(self, radii, fixed):
        radii = np.asarray(radii, dtype=float)
        fixed = np.asarray(fixed, bool)
        iu, ju = np.triu_indices(len(radii), 1)
        keep = ((radii[iu] + radii[ju]) > 0) & ~(fixed[iu] & fixed[ju])
        self.iu, self.ju = iu[keep], ju[keep]
        self.rsum = (radii[iu] + radii[ju])[keep]
        self.active = len(self.iu) > 0
        self.in_contact: set[tuple[int, int]] = set()

    def initial_contacts(self, pos) -> list[tuple[int, int]]:
        """Pairs already overlapping at the start; they are put in contact."""
        if not self.active:
            return []
        d = np.hypot(*(pos[self.ju] - pos[self.iu]).T)
        pairs = [(int(i), int(j)) for i, j, dd, rs in zip(self.iu, self.ju, d, self.rsum) if dd <= rs]
        self.in_contact.update(pairs)
        return pairs

    def find(self, dt, x0, v0, x1, v1, state_at: Callable[[float], np.ndarray]) -> list[tuple[float, int, int]]:
        """Contacts starting during the step, as (tau, i, j) sorted by tau in [0, 1].

        ``state_at(tau)`` must return the positions (N, 2) at fraction ``tau`` of the step.
        Pairs already in contact are ignored.
        """
        if not self.active:
            return []
        # Cheap screening first (called at every step): a pair can only touch during the step if its end
        # distance minus twice the sum of the bodies' largest displacement is below contact.
        step = np.maximum(np.hypot(v0[:, 0], v0[:, 1]), np.hypot(v1[:, 0], v1[:, 1])) * dt
        d_end = x1[self.ju] - x1[self.iu]
        close = np.hypot(d_end[:, 0], d_end[:, 1]) - 2.0 * (step[self.iu] + step[self.ju]) <= self.rsum
        if not close.any():
            return []
        keep = np.nonzero(close)[0]
        iu, ju, rsum = self.iu[keep], self.ju[keep], self.rsum[keep]
        p0, p1 = x0[ju] - x0[iu], x1[ju] - x1[iu]
        m0, m1 = (v0[ju] - v0[iu]) * dt, (v1[ju] - v1[iu]) * dt
        d0, d1 = np.hypot(*p0.T), np.hypot(*p1.T)
        reach = np.maximum(np.hypot(*m0.T), np.hypot(*m1.T))
        candidates = np.nonzero(np.minimum(d0, d1) - reach <= rsum)[0]
        hits = []
        for k in candidates:
            pair = (int(iu[k]), int(ju[k]))
            if pair in self.in_contact:
                continue
            tau = self._first_contact(p0[k], m0[k], p1[k], m1[k], rsum[k], pair, state_at)
            if tau is not None:
                hits.append((tau, pair[0], pair[1]))
        hits.sort()
        return hits

    def touching(self, i: int, j: int, pos) -> bool:
        k = np.nonzero((self.iu == i) & (self.ju == j))[0]
        return bool(len(k)) and float(np.hypot(*(pos[j] - pos[i]))) <= self.rsum[k[0]] * (1 + CONTACT_TOL)

    @staticmethod
    def _first_contact(p0, m0, p1, m1, rsum, pair, state_at):
        # Hermite cubic p(tau) = A tau^3 + B tau^2 + C tau + D for each component.
        A = 2 * p0 + m0 - 2 * p1 + m1
        B = -3 * p0 - 2 * m0 + 3 * p1 - m1
        C, D = m0, p0
        coeffs = [np.array([A[c], B[c], C[c], D[c]]) for c in range(2)]
        g = np.polyadd(np.polymul(coeffs[0], coeffs[0]), np.polymul(coeffs[1], coeffs[1]))
        g[-1] -= rsum * rsum
        if np.polyval(g, 0.0) <= 0:
            return 0.0
        roots = np.roots(g)
        real = roots[np.abs(roots.imag) < 1e-7].real
        trial = sorted(t for t in real if 0.0 <= t <= 1.0)
        dg = np.polyder(g)
        mins = [t.real for t in np.roots(dg) if abs(t.imag) < 1e-7 and 0.0 <= t.real <= 1.0]
        trial += sorted(mins) + [1.0]

        i, j = pair

        def gap(tau):
            x = state_at(tau)
            d = x[j] - x[i]
            return float(d @ d) - rsum * rsum

        if not any(np.polyval(g, t) <= 1e-12 * rsum * rsum for t in trial):
            return None
        for t_hi in trial:
            if t_hi > 0 and gap(t_hi) <= 0:
                return brentq(gap, 0.0, t_hi, xtol=1e-14, rtol=4 * np.finfo(float).eps)
        return None

    def update_contacts(self, t, pos) -> list[SeparationEvent]:
        """Remove pairs no longer overlapping at the end of a step."""
        events = []
        for i, j in list(self.in_contact):
            rs = self.rsum[(self.iu == i) & (self.ju == j)]
            d = pos[j] - pos[i]
            if len(rs) and float(np.hypot(*d)) > rs[0] * (1 + CONTACT_TOL):
                self.in_contact.discard((i, j))
                events.append(SeparationEvent(t, i, j))
        return events


def make_collision_event(t, i, j, pos, vel) -> CollisionEvent:
    dr, dv = pos[j] - pos[i], vel[j] - vel[i]
    speed = float(np.hypot(*dv))
    dist = float(np.hypot(*dr))
    if speed > 0 and dist > 0:
        cos_a = abs(float(dr @ dv)) / (speed * dist)
        angle = math.degrees(math.acos(min(1.0, cos_a)))
    else:
        angle = float("nan")
    return CollisionEvent(t, i, j, speed, angle, pos.copy(), vel.copy())
