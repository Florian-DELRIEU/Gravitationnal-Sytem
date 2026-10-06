"""A single gravitating body."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


def _vec2(value) -> np.ndarray:
    arr = np.array(value, dtype=float).reshape(-1)
    if arr.shape != (2,):
        raise ValueError(f"expected a 2D vector, got {value!r}")
    return arr


@dataclass
class Body:
    """Body state and properties, in internal units (AU, Msun, yr).

    ``mass`` may be 0 (test particle: feels gravity, exerts none).
    ``radius`` is the physical radius, used only for collision detection and the
    overlap force law. A ``fixed`` body exerts gravity but is never accelerated;
    its velocity is ignored (treated as zero) by the simulation.
    """

    name: str
    mass: float
    position: np.ndarray = field(default_factory=lambda: np.zeros(2))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))
    radius: float = 0.0
    fixed: bool = False
    color: str | None = None

    def __post_init__(self):
        self.position = _vec2(self.position)
        self.velocity = _vec2(self.velocity)
        if self.mass < 0:
            raise ValueError(f"{self.name}: mass must be >= 0")
        if self.radius < 0:
            raise ValueError(f"{self.name}: radius must be >= 0")

    @property
    def speed(self) -> float:
        return float(np.hypot(*self.velocity))

    @property
    def direction_deg(self) -> float:
        """Direction of the velocity, in degrees counterclockwise from +x."""
        return math.degrees(math.atan2(self.velocity[1], self.velocity[0]))

    def set_velocity_polar(self, speed: float, direction_deg: float) -> None:
        angle = math.radians(direction_deg)
        self.velocity = np.array([speed * math.cos(angle), speed * math.sin(angle)])

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "mass": self.mass,
            "radius": self.radius,
            "position": self.position.tolist(),
            "velocity": self.velocity.tolist(),
            "fixed": self.fixed,
        }
        if self.color is not None:
            data["color"] = self.color
        return data
