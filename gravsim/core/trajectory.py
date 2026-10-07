"""Recorded simulation output: regularly sampled states plus an event log."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields

import numpy as np

from .events import CollisionEvent, ImpulseEvent, SeparationEvent


@dataclass
class Trajectory:
    """Sampled states of N bodies.

    t (T,), pos (T, N, 2), vel (T, N, 2) are views on a growable buffer.
    Metadata (names, masses, radii, fixed, G) describes the bodies.
    """

    names: list[str]
    masses: np.ndarray
    radii: np.ndarray
    fixed: np.ndarray
    G: float
    colors: list[str | None] = field(default_factory=list)
    events: list = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def __post_init__(self):
        self.masses = np.asarray(self.masses, dtype=float)
        self.radii = np.asarray(self.radii, dtype=float)
        self.fixed = np.asarray(self.fixed, bool)
        n = len(self.names)
        self._cap = 1024
        self._len = 0
        self._t = np.empty(self._cap)
        self._pos = np.empty((self._cap, n, 2))
        self._vel = np.empty((self._cap, n, 2))

    # --- buffer ------------------------------------------------------------
    def append(self, t: float, pos: np.ndarray, vel: np.ndarray) -> None:
        if self._len == self._cap:
            self._grow()
        k = self._len
        self._t[k] = t
        self._pos[k] = pos
        self._vel[k] = vel
        self._len += 1

    def _grow(self):
        self._cap *= 2
        for name in ("_t", "_pos", "_vel"):
            old = getattr(self, name)
            new = np.empty((self._cap,) + old.shape[1:])
            new[: self._len] = old[: self._len]
            setattr(self, name, new)

    def __len__(self) -> int:
        return self._len

    @property
    def n_bodies(self) -> int:
        return len(self.names)

    @property
    def t(self) -> np.ndarray:
        return self._t[: self._len]

    @property
    def pos(self) -> np.ndarray:
        return self._pos[: self._len]

    @property
    def vel(self) -> np.ndarray:
        return self._vel[: self._len]

    def window(self, start: int, stop: int, events: bool = True) -> "Trajectory":
        """Read-only view on samples ``start:stop`` (no copy of the arrays)."""
        start, stop = max(0, start), min(self._len, stop)
        if stop <= start:
            raise ValueError("empty window")
        w = Trajectory(self.names, self.masses, self.radii, self.fixed, self.G, colors=self.colors, info=self.info)
        w._cap = w._len = stop - start
        w._t, w._pos, w._vel = self._t[start:stop], self._pos[start:stop], self._vel[start:stop]
        if events:
            t0, t1 = self._t[start], self._t[stop - 1]
            w.events = [e for e in self.events if t0 <= e.t <= t1]
        return w

    def index(self, body: str | int) -> int:
        if isinstance(body, (int, np.integer)):
            return int(body)
        try:
            return self.names.index(body)
        except ValueError:
            raise KeyError(f"no body named {body!r}; bodies: {self.names}") from None

    # --- events ------------------------------------------------------------
    def events_of(self, kind: str) -> list:
        return [e for e in self.events if e.kind == kind]

    @property
    def impulses(self) -> list[ImpulseEvent]:
        return self.events_of("impulse")

    @property
    def collisions(self) -> list[CollisionEvent]:
        return self.events_of("collision")

    # --- persistence -------------------------------------------------------
    def save_npz(self, path) -> None:
        events = [_event_to_dict(e) for e in self.events]
        np.savez_compressed(
            path,
            t=self.t, pos=self.pos, vel=self.vel,
            masses=self.masses, radii=self.radii, fixed=self.fixed, G=self.G,
            meta=json.dumps({"names": self.names, "colors": self.colors, "info": self.info, "events": events}),
        )

    @classmethod
    def load_npz(cls, path) -> "Trajectory":
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            traj = cls(meta["names"], data["masses"], data["radii"], data["fixed"], float(data["G"]),
                       colors=meta["colors"], info=meta["info"])
            t, pos, vel = data["t"], data["pos"], data["vel"]
        traj._cap = max(1, len(t))
        traj._t, traj._pos, traj._vel = t.copy(), pos.copy(), vel.copy()
        traj._len = len(t)
        traj.events = [_event_from_dict(e) for e in meta["events"]]
        return traj


def _event_to_dict(e) -> dict:
    values = {f.name: getattr(e, f.name) for f in fields(e)}
    return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in values.items()}


def _event_from_dict(d: dict):
    d = dict(d)
    kind = d.pop("kind")  # set by the event class itself (init=False)
    cls = {"impulse": ImpulseEvent, "collision": CollisionEvent, "separation": SeparationEvent}[kind]
    for key in ("position", "velocity_before", "dv", "positions", "velocities"):
        if key in d:
            d[key] = np.asarray(d[key], dtype=float)
    return cls(**d)
