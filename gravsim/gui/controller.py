"""Playback controller: owns the scenario and the running simulation, independent of any widget layout.

Playback model: a view time ``view_time`` moves at ``speed`` (simulated years per real second). When it
reaches the end of the computed trajectory the simulation is advanced, within a CPU budget per tick so the
interface stays responsive (the achieved speed then drops below the requested one). Scrubbing back replays
recorded samples.

The simulation is advanced from the GUI thread, in short budgeted slices: for the 2 to ~10 bodies targeted
here this is as smooth as a worker thread, with no locking around immediate impulses or edits.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..core import kepler
from ..core.body import Body
from ..core.events import Impulse
from ..core.scenario import Scenario
from ..core.simulation import Simulation
from ..core import units
from .widgets import default_color, format_time

_EPS = 1e-12


@dataclass
class IntegrationSettings:
    integrator: str = "dop853"
    auto_dt: bool = True
    dt: float = 1e-3  # yr, fixed-step integrators when not auto
    rtol: float = 1e-10
    atol: float = 1e-12


def locate(times: np.ndarray, t: float) -> tuple[int, int, float]:
    """Samples (i, j) bracketing ``t`` and the interpolation weight w in [0, 1] of sample j."""
    n = len(times)
    i = int(np.clip(np.searchsorted(times, t, side="right") - 1, 0, n - 1))
    if i >= n - 1:
        return n - 1, n - 1, 0.0
    j = i + 1
    return i, j, float(np.clip((t - times[i]) / (times[j] - times[i]), 0.0, 1.0))


class SimulationController(QObject):
    MAX_SAMPLES = 2_000_000
    DEFAULT_BUDGET = 0.012  # seconds of CPU per playback tick

    reset = Signal()  # simulation rebuilt from the initial conditions
    changed = Signal()  # view time or state changed: redraw
    scenarioEdited = Signal()  # initial conditions edited in place
    scenarioReplaced = Signal()  # a whole new scenario was loaded
    appearanceChanged = Signal()  # colours, sizes: redraw without reset
    selectionChanged = Signal(int)
    playingChanged = Signal(bool)
    eventLogged = Signal(str, str)  # text, level ('info' | 'warning' | 'collision' | 'error')
    collisionOccurred = Signal(object)
    impulsesChanged = Signal()

    def __init__(self, scenario: Scenario, parent=None):
        super().__init__(parent)
        self.scenario = scenario
        self.settings = IntegrationSettings()
        self.sim: Simulation | None = None
        self.error: str | None = None
        self.playing = False
        self.pause_on_collision = False
        self.budget = self.DEFAULT_BUDGET
        self.speed = 1.0
        self.view_time = scenario.t0
        self.selected = 0 if scenario.bodies else -1
        self.achieved_rate = 0.0
        self._events_seen = 0
        self._injected_energy = 0.0
        self._e0 = 0.0
        self.rebuild()
        self.speed = self.auto_speed()

    # --- convenience -------------------------------------------------------------
    @property
    def traj(self):
        return self.sim.trajectory if self.sim else None

    @property
    def live(self) -> bool:
        return self.sim is not None and self.view_time >= self.sim.t - _EPS * max(1.0, abs(self.sim.t))

    @property
    def output_dt(self) -> float | None:
        return self.sim.output_dt if self.sim else None

    def log(self, text: str, level: str = "info") -> None:
        self.eventLogged.emit(text, level)

    # --- building ---------------------------------------------------------------
    def rebuild(self) -> None:
        """(Re)create the simulation from the initial conditions."""
        was_playing = self.playing
        self.playing = False
        self.sim, self.error = None, None
        self._events_seen, self._injected_energy = 0, 0.0
        self.view_time = self.scenario.t0
        problems = self.scenario.problems()
        if not problems:
            try:
                self.sim = self._make_simulation()
                self._e0 = self.sim.energy
            except Exception as exc:  # invalid combination of settings: report, don't crash
                problems = [str(exc)]
        if problems:
            self.error = "; ".join(problems)
            self.log(f"Simulation impossible : {self.error}", "error")
        else:
            self._flush_events()
        if was_playing:
            self.playingChanged.emit(False)
        self.reset.emit()
        self.changed.emit()

    def _make_simulation(self) -> Simulation:
        sc, st = self.scenario, self.settings
        rec = kepler.recommended_dt(sc.positions, sc.velocities, sc.masses, sc.G, sc.fixed, sc.radii)
        fixed_step = st.integrator != "dop853"
        dt = None if (st.auto_dt or not fixed_step) else st.dt
        output_dt = rec if dt is None else max(rec, dt)
        return Simulation(sc, st.integrator, dt=dt, output_dt=output_dt, rtol=st.rtol, atol=st.atol,
                          stop_on_collision=self.pause_on_collision)

    def auto_speed(self) -> float:
        """A readable default speed: one orbit of the geometric-mean period in about 8 s."""
        sc = self.scenario
        periods = []
        if len(sc.bodies) >= 2:
            m = sc.masses
            for k, b in enumerate(sc.bodies):
                if b.fixed:
                    continue
                others = [j for j in range(len(m)) if j != k and m[j] > 0]
                if not others:
                    continue
                j = max(others, key=lambda q: m[q] / max(np.sum((sc.positions[q] - b.position) ** 2), 1e-30))
                ref = sc.bodies[j]
                mu = kepler.gravitational_parameter(sc.G, b.mass, ref.mass, ref.fixed)
                vj = np.zeros(2) if ref.fixed else ref.velocity
                el = kepler.elements_from_state(b.position - ref.position, b.velocity - vj, mu)
                if np.isfinite(el["period"]) and el["period"] > 0:
                    periods.append(float(el["period"]))
        if not periods:
            return 1.0
        return math.exp(np.mean(np.log(periods))) / 8.0

    # --- scenario editing ---------------------------------------------------------
    def edit(self, reset: bool = True) -> None:
        """Call after modifying the scenario in place."""
        if reset:
            self.rebuild()
            self.scenarioEdited.emit()
        else:
            self.appearanceChanged.emit()
            self.changed.emit()

    def set_scenario(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.selected = 0 if scenario.bodies else -1
        self.rebuild()
        self.speed = self.auto_speed()
        self.scenarioReplaced.emit()
        self.selectionChanged.emit(self.selected)

    def select(self, index: int) -> None:
        if index != self.selected and -1 <= index < len(self.scenario.bodies):
            self.selected = index
            self.selectionChanged.emit(index)
            self.changed.emit()

    def unique_name(self, base: str) -> str:
        names = set(self.scenario.names)
        if base not in names:
            return base
        k = 2
        while f"{base} {k}" in names:
            k += 1
        return f"{base} {k}"

    def add_body(self) -> int:
        """New body on a circular orbit around the most massive one (or a Sun-like star if the system is empty)."""
        sc = self.scenario
        if not sc.bodies:
            sc.add(Body(self.unique_name("Étoile"), 1.0, radius=units.R_SUN, color=default_color(0)))
        else:
            far = max(float(np.hypot(*b.position)) for b in sc.bodies)
            body = Body(self.unique_name("Planète"), units.M_JUP, radius=units.R_JUP,
                        position=[1.5 * far if far > 0 else 1.0, 0.0], color=default_color(len(sc.bodies)))
            sc.add(body)
            try:
                sc.set_orbital_velocity(body.name)
            except ValueError:
                pass
        self.selected = len(sc.bodies) - 1
        self.edit()
        self.selectionChanged.emit(self.selected)
        return self.selected

    def duplicate_body(self, index: int) -> int:
        sc = self.scenario
        src = sc.bodies[index]
        dup = Body(self.unique_name(src.name), src.mass, src.position + np.array([0.0, 0.2 * max(src.radius, 0.05)]),
                   src.velocity.copy(), src.radius, src.fixed, src.color, src.display_px)
        sc.bodies.insert(index + 1, dup)
        self.selected = index + 1
        self.edit()
        self.selectionChanged.emit(self.selected)
        return self.selected

    def remove_body(self, index: int) -> None:
        sc = self.scenario
        name = sc.bodies[index].name
        del sc.bodies[index]
        sc.impulses = [i for i in sc.impulses if i.body != name]
        for imp in sc.impulses:
            if imp.reference == name:
                imp.reference = None
        self.selected = min(index, len(sc.bodies) - 1)
        self.edit()
        self.selectionChanged.emit(self.selected)

    def rename_body(self, index: int, new_name: str) -> bool:
        sc = self.scenario
        new_name = new_name.strip()
        old = sc.bodies[index].name
        if not new_name or new_name == old:
            return False
        if new_name in sc.names:
            self.log(f"Le nom « {new_name} » est déjà utilisé", "warning")
            return False
        sc.bodies[index].name = new_name
        for imp in sc.impulses:
            if imp.body == old:
                imp.body = new_name
            if imp.reference == old:
                imp.reference = new_name
        self.edit()
        return True

    def zero_momentum(self) -> bool:
        try:
            v = self.scenario.zero_total_momentum()
        except ValueError as exc:
            self.log(str(exc), "warning")
            return False
        self.log(f"Quantité de mouvement annulée (vitesse du barycentre retirée : {np.hypot(*v):.3g} UA/an)")
        self.edit()
        return True

    def center_on_barycenter(self) -> bool:
        try:
            self.scenario.center_on_barycenter()
        except ValueError as exc:
            self.log(str(exc), "warning")
            return False
        self.edit()
        return True

    # --- playback ---------------------------------------------------------------
    def play(self) -> None:
        if self.sim is None or self.playing:
            return
        self.playing = True
        self.playingChanged.emit(True)

    def pause(self) -> None:
        if self.playing:
            self.playing = False
            self.playingChanged.emit(False)

    def toggle(self) -> None:
        self.pause() if self.playing else self.play()

    def set_pause_on_collision(self, flag: bool) -> None:
        self.pause_on_collision = flag
        if self.sim is not None:
            self.sim.stop_on_collision = flag

    def set_speed(self, yr_per_s: float) -> None:
        self.speed = float(yr_per_s)

    def tick(self, wall_dt: float) -> None:
        """Advance playback by ``wall_dt`` real seconds."""
        if not self.playing or self.sim is None or wall_dt <= 0:
            return
        before = self.view_time
        self.advance_to(before + self.speed * wall_dt, self.budget)
        rate = (self.view_time - before) / wall_dt
        self.achieved_rate = rate if self.achieved_rate == 0 else 0.8 * self.achieved_rate + 0.2 * rate
        self.changed.emit()

    def step(self) -> None:
        """Advance by one output sample (paused stepping)."""
        if self.sim is None:
            return
        self.pause()
        self.advance_to(self.view_time + self.sim.output_dt, budget=2.0)
        self.changed.emit()

    def advance_to(self, target: float, budget: float | None = None) -> None:
        """Move the view to ``target``, simulating further if needed (CPU time capped by ``budget`` seconds)."""
        sim = self.sim
        if sim is None:
            return
        budget = self.budget if budget is None else budget
        status = "done"
        started = time.perf_counter()
        try:
            while sim.t < target - _EPS and status == "done":
                if len(sim.trajectory) >= self.MAX_SAMPLES:
                    self.pause()
                    self.log("Trajectoire trop longue : réinitialisez la simulation pour continuer.", "warning")
                    break
                res = sim.run(min(target, sim.t + 25.0 * sim.output_dt))
                status = res.status
                if not (np.all(np.isfinite(sim.x)) and np.all(np.isfinite(sim.v))):
                    raise FloatingPointError("valeurs non finies : rencontre trop proche ou pas trop grand")
                if time.perf_counter() - started > budget:
                    break
        except Exception as exc:
            self.pause()
            self.log(f"Erreur de simulation à t = {format_time(sim.t)} : {exc}", "error")
            self.view_time = min(self.view_time, sim.t)
            self._flush_events()
            return
        self._flush_events()
        self.view_time = min(target, sim.t)
        if status == "collision" and self.pause_on_collision:
            self.pause()

    def scrub(self, t: float) -> None:
        """Show the recorded state at time ``t`` (pauses playback)."""
        if self.sim is None:
            return
        self.pause()
        self.view_time = float(np.clip(t, self.scenario.t0, self.sim.t))
        self.changed.emit()

    def go_live(self) -> None:
        if self.sim is not None:
            self.view_time = self.sim.t
            self.changed.emit()

    # --- impulses -----------------------------------------------------------------
    def apply_impulse(self, impulse: Impulse, now: bool) -> str:
        """Apply immediately (at the live time) or schedule at ``impulse.t``. Returns a status message."""
        sim, sc = self.sim, self.scenario
        if sim is None:
            return "Aucune simulation en cours."
        if impulse.body not in sc.names:
            return f"Corps inconnu : {impulse.body}"
        if now:
            impulse.t = sim.t
            self.go_live()
            sc.impulses.append(impulse)
            sim.add_impulse(impulse)
            try:
                sim.apply_due_impulses()
            except ValueError as exc:
                sc.impulses.remove(impulse)
                return f"Poussée impossible : {exc}"
            self._flush_events()
            self.impulsesChanged.emit()
            self.changed.emit()
            return f"Poussée appliquée à t = {format_time(sim.t)} (visible dès le prochain pas)."
        sc.impulses.append(impulse)
        if impulse.t >= sim.t - _EPS:
            sim.add_impulse(impulse)
            self.impulsesChanged.emit()
            return f"Poussée programmée à t = {format_time(impulse.t)}."
        self.rebuild()
        self.impulsesChanged.emit()
        return (f"Instant passé (t = {format_time(impulse.t)}) : poussée ajoutée et simulation réinitialisée "
                f"pour la rejouer.")

    def remove_impulse(self, impulse: Impulse) -> None:
        self.scenario.impulses = [i for i in self.scenario.impulses if i is not impulse]
        if self.sim is not None and not self.sim.cancel_impulse(impulse):
            self.log("Poussée déjà appliquée : simulation réinitialisée.", "warning")
            self.rebuild()
        self.impulsesChanged.emit()

    # --- events and readouts ------------------------------------------------------
    def _flush_events(self) -> None:
        traj = self.traj
        if traj is None:
            return
        names = traj.names
        for ev in traj.events[self._events_seen:]:
            if ev.kind == "impulse":
                self._injected_energy += ev.delta_energy
                if ev.applied:
                    sign = "+" if np.dot(ev.dv, ev.velocity_before) >= 0 else "−"
                    self.log(f"t = {format_time(ev.t)} : poussée sur {names[ev.body]}, |Δv| = {np.hypot(*ev.dv):.4g} "
                             f"UA/an ({sign})")
                else:
                    self.log(f"t = {format_time(ev.t)} : poussée ignorée, {names[ev.body]} est fixe", "warning")
            elif ev.kind == "collision":
                text = (f"t = {format_time(ev.t)} : COLLISION {names[ev.i]} – {names[ev.j]}, vitesse relative "
                        f"{units.au_per_yr_to_m_s(ev.relative_speed) / 1e3:.4g} km/s, angle d'impact "
                        f"{ev.impact_angle_deg:.0f}°")
                self.log(text, "collision")
                self.collisionOccurred.emit(ev)
            elif ev.kind == "separation":
                self.log(f"t = {format_time(ev.t)} : {names[ev.i]} et {names[ev.j]} se séparent")
        self._events_seen = len(traj.events)

    def energy_drift(self) -> float | None:
        """Relative energy drift, corrected for the energy injected by impulses."""
        if self.sim is None or self._e0 == 0:
            return None
        return (self.sim.energy - self._e0 - self._injected_energy) / abs(self._e0)

    def state_at_view(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Inertial positions and velocities (N, 2) at the view time."""
        sim = self.sim
        if sim is None:
            return None
        if self.live:
            return sim.x.copy(), sim.v.copy()
        traj = sim.trajectory
        i, j, w = locate(traj.t, self.view_time)
        return (1 - w) * traj.pos[i] + w * traj.pos[j], (1 - w) * traj.vel[i] + w * traj.vel[j]
