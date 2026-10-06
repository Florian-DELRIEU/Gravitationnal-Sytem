"""Initial conditions: bodies, scheduled impulses, and helpers to set them up.

JSON format (version 1)::

    {
      "format": "gravsim-scenario", "version": 1,
      "name": "...", "description": "...",
      "bodies": [
        {"name": "Soleil", "mass": 1.0, "radius": {"value": 1, "unit": "Rsun"}},
        {"name": "Jupiter", "mass": {"value": 1, "unit": "Mjup"}, "radius": {"value": 1, "unit": "Rjup"},
         "orbit": {"around": "Soleil", "distance": 5.2, "angle_deg": 0, "e": 0.0,
                   "at": "periapsis", "clockwise": false}}
      ],
      "impulses": [{"body": "Jupiter", "dv": 0.1, "t": 2.0, "direction": "prograde"}],
      "zero_momentum": true
    }

A body gives either explicit ``position``/``velocity`` (velocity may also be
``{"speed": s, "direction_deg": a}``), or an ``orbit`` placing it relative to a
body listed before it. Quantities are numbers in internal units (Msun, AU,
AU/yr, yr) or ``{"value": v, "unit": u}`` (see ``units``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import kepler, units
from .body import Body
from .events import Impulse

FORMAT = "gravsim-scenario"
VERSION = 1


@dataclass
class Scenario:
    bodies: list[Body] = field(default_factory=list)
    impulses: list[Impulse] = field(default_factory=list)
    G: float = units.G
    t0: float = 0.0
    name: str = ""
    description: str = ""

    # --- access ------------------------------------------------------------
    def index(self, name: str) -> int:
        for k, b in enumerate(self.bodies):
            if b.name == name:
                return k
        raise KeyError(f"no body named {name!r}")

    def body(self, name: str) -> Body:
        return self.bodies[self.index(name)]

    def add(self, body: Body) -> Body:
        if any(b.name == body.name for b in self.bodies):
            raise ValueError(f"duplicate body name {body.name!r}")
        self.bodies.append(body)
        return body

    @property
    def names(self) -> list[str]:
        return [b.name for b in self.bodies]

    @property
    def masses(self) -> np.ndarray:
        return np.array([b.mass for b in self.bodies], dtype=float)

    @property
    def positions(self) -> np.ndarray:
        return np.array([b.position for b in self.bodies], dtype=float).reshape(-1, 2)

    @property
    def velocities(self) -> np.ndarray:
        return np.array([np.zeros(2) if b.fixed else b.velocity for b in self.bodies], dtype=float).reshape(-1, 2)

    @property
    def radii(self) -> np.ndarray:
        return np.array([b.radius for b in self.bodies], dtype=float)

    @property
    def fixed(self) -> np.ndarray:
        return np.array([b.fixed for b in self.bodies], dtype=bool)

    def default_reference(self, name: str) -> str:
        """Most massive body other than ``name``."""
        others = [b for b in self.bodies if b.name != name]
        if not others:
            raise ValueError("no other body to use as reference")
        return max(others, key=lambda b: b.mass).name

    # --- velocity helpers ----------------------------------------------------
    def _relative(self, name: str, around: str | None):
        body = self.body(name)
        if body.fixed:
            raise ValueError(f"{name} is fixed: its velocity cannot be set")
        ref = self.body(around or self.default_reference(name))
        mu = kepler.gravitational_parameter(self.G, body.mass, ref.mass, ref.fixed)
        ref_vel = np.zeros(2) if ref.fixed else ref.velocity
        return body, ref, mu, ref_vel

    def set_orbital_velocity(self, name: str, around: str | None = None, e: float = 0.0,
                             at: str = "periapsis", clockwise: bool = False) -> np.ndarray:
        """Give ``name`` the velocity of an orbit of eccentricity ``e`` around ``around``,
        its current position being the periapsis (or apoapsis). Two-body approximation."""
        body, ref, mu, ref_vel = self._relative(name, around)
        body.velocity = ref_vel + kepler.orbital_velocity(body.position - ref.position, mu, e, at, clockwise)
        return body.velocity

    def set_escape_velocity(self, name: str, around: str | None = None, clockwise: bool = False) -> np.ndarray:
        """Tangential escape velocity (parabolic orbit, e = 1)."""
        return self.set_orbital_velocity(name, around, e=1.0, at="periapsis", clockwise=clockwise)

    def circular_speed(self, name: str, around: str | None = None) -> float:
        """Reference circular speed, relative to ``around`` (displayed next to manual input)."""
        body, ref, mu, _ = self._relative(name, around)
        return kepler.circular_speed(mu, float(np.hypot(*(body.position - ref.position))))

    # --- barycentre ----------------------------------------------------------
    def total_mass(self) -> float:
        return float(self.masses.sum())

    def barycenter(self) -> tuple[np.ndarray, np.ndarray]:
        m = self.masses
        M = m.sum()
        if M == 0:
            raise ValueError("total mass is zero")
        return (m @ self.positions) / M, (m @ self.velocities) / M

    def zero_total_momentum(self) -> np.ndarray:
        """Subtract the barycentre velocity from every body (relative motions unchanged)."""
        if self.fixed.any():
            raise ValueError("total momentum is not conserved with a fixed body: cannot cancel it")
        _, v_cm = self.barycenter()
        for b in self.bodies:
            b.velocity = b.velocity - v_cm
        return v_cm

    def center_on_barycenter(self) -> np.ndarray:
        r_cm, _ = self.barycenter()
        for b in self.bodies:
            b.position = b.position - r_cm
        return r_cm

    # --- persistence ---------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "format": FORMAT,
            "version": VERSION,
            "name": self.name,
            "description": self.description,
            "G": self.G,
            "t0": self.t0,
            "bodies": [b.to_dict() for b in self.bodies],
            "impulses": [imp.to_dict() for imp in self.impulses],
        }

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        if data.get("format", FORMAT) != FORMAT:
            raise ValueError(f"not a gravsim scenario (format={data.get('format')!r})")
        if data.get("version", VERSION) > VERSION:
            raise ValueError(f"scenario version {data['version']} is newer than supported ({VERSION})")
        sc = cls(G=float(data.get("G", units.G)), t0=float(data.get("t0", 0.0)),
                 name=data.get("name", ""), description=data.get("description", ""))
        for spec in data.get("bodies", []):
            sc._add_from_spec(spec)
        sc.impulses = [Impulse(**imp) for imp in data.get("impulses", [])]
        if data.get("zero_momentum", False):
            sc.zero_total_momentum()
        if data.get("center", False):
            sc.center_on_barycenter()
        return sc

    @classmethod
    def load(cls, path) -> "Scenario":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def _add_from_spec(self, spec: dict) -> None:
        mass = _quantity(spec.get("mass", 0.0), units.MASS_UNITS)
        if "radius" in spec:
            radius = _quantity(spec["radius"], units.LENGTH_UNITS)
        elif "density" in spec and mass > 0:
            radius = units.radius_from_density(mass, float(spec["density"]))
        else:
            radius = 0.0
        body = Body(spec["name"], mass, radius=radius, fixed=bool(spec.get("fixed", False)), color=spec.get("color"))
        orbit = spec.get("orbit")
        if orbit is None:
            body.position = [_quantity(c, units.LENGTH_UNITS) for c in spec.get("position", [0.0, 0.0])]
            vel = spec.get("velocity", [0.0, 0.0])
            if isinstance(vel, dict):
                body.set_velocity_polar(float(vel["speed"]), float(vel["direction_deg"]))
            else:
                body.velocity = vel
            self.add(body)
            return
        ref = self.body(orbit["around"])
        dist = _quantity(orbit["distance"], units.LENGTH_UNITS)
        ang = math.radians(float(orbit.get("angle_deg", 0.0)))
        body.position = ref.position + dist * np.array([math.cos(ang), math.sin(ang)])
        self.add(body)
        self.set_orbital_velocity(body.name, ref.name, e=float(orbit.get("e", 0.0)),
                                  at=orbit.get("at", "periapsis"), clockwise=bool(orbit.get("clockwise", False)))


def _quantity(value, table) -> float:
    if isinstance(value, dict):
        return units.to_internal(float(value["value"]), value["unit"], table)
    return float(value)


def load_preset(name: str) -> Scenario:
    """Load a bundled preset by file stem (e.g. 'soleil_jupiter')."""
    path = Path(__file__).resolve().parent.parent / "presets" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"no preset {name!r}; available: {list_presets()}")
    return Scenario.load(path)


def list_presets() -> list[str]:
    folder = Path(__file__).resolve().parent.parent / "presets"
    return sorted(p.stem for p in folder.glob("*.json"))
