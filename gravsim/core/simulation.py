"""Time integration of a scenario, with impulses and collisions as exact-time events.

Output samples are recorded on a regular grid t0 + k * output_dt, independent of
the integration step:
- fixed-step integrators use dt_eff = output_dt / ceil(output_dt / dt), so that
  samples fall exactly on step boundaries (no interpolation);
- DOP853 evaluates its dense output (order 7) at the sample times.

Event ordering: a sample at time t records the state *before* any impulse
scheduled at that same time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import DOP853

from .events import CollisionDetector, ImpulseEvent, impulse_vector, make_collision_event
from .forces import GravityModel
from .integrators import FIXED_STEP_INTEGRATORS, INTEGRATORS
from .kepler import recommended_dt
from .scenario import Scenario
from .trajectory import Trajectory

_EPS = 1e-12


@dataclass
class RunResult:
    status: str  # 'done' | 'collision'
    t: float
    collisions: list


class Simulation:
    """Integrates a :class:`Scenario` and records a :class:`Trajectory`.

    Parameters
    ----------
    integrator        'dop853' (adaptive, default), 'yoshida4' or 'leapfrog' (fixed step)
    dt                fixed step (yr); default: ``kepler.recommended_dt``
    output_dt         sampling interval of the trajectory (yr); default: 2 * recommended dt
    rtol, atol        DOP853 tolerances
    stop_on_collision stop exactly at the first contact between two bodies
    """

    def __init__(self, scenario: Scenario, integrator: str = "dop853", dt: float | None = None,
                 output_dt: float | None = None, rtol: float = 1e-10, atol: float = 1e-12,
                 stop_on_collision: bool = False):
        if integrator not in INTEGRATORS:
            raise ValueError(f"integrator must be one of {INTEGRATORS}")
        self.scenario = scenario
        self.integrator = integrator
        self.names = scenario.names
        self.n = len(self.names)
        self.masses = scenario.masses
        self.fixed = scenario.fixed
        self.G = scenario.G
        self.model = GravityModel(self.masses, self.G, scenario.radii, self.fixed)
        self.rtol, self.atol = rtol, atol
        self.stop_on_collision = stop_on_collision

        self.t = float(scenario.t0)
        self.x = scenario.positions.copy()
        self.v = scenario.velocities.copy()  # fixed bodies: zero
        self.a = self.model.acceleration(self.x)

        self.recommended_dt = recommended_dt(self.x, self.v, self.masses, self.G, self.fixed, scenario.radii)
        self.output_dt = float(output_dt) if output_dt else 2.0 * self.recommended_dt
        if integrator in FIXED_STEP_INTEGRATORS:
            raw = float(dt) if dt else self.recommended_dt
            self.stride = max(1, math.ceil(self.output_dt / raw - 1e-9))
            self.dt = self.output_dt / self.stride
            self._stepper = FIXED_STEP_INTEGRATORS[integrator]()
        else:
            self.stride = 1
            self.dt = None
            self._stepper = None
        self._t_origin = self.t
        self._k = 0  # fixed-step grid index
        self._n_out = 0  # index of the last emitted sample
        self._h = None  # last DOP853 step size

        self._pending = sorted(scenario.impulses, key=lambda imp: imp.t)
        if self._pending and self._pending[0].t < self.t - _EPS:
            raise ValueError("an impulse is scheduled before the start time")

        self.trajectory = Trajectory(
            self.names, self.masses, scenario.radii, self.fixed, self.G,
            colors=[b.color for b in scenario.bodies],
            info={"integrator": integrator, "dt": self.dt, "output_dt": self.output_dt,
                  "rtol": rtol, "atol": atol, "scenario": scenario.name},
        )
        self.trajectory.append(self.t, self.x, self.v)
        self.detector = CollisionDetector(scenario.radii, self.fixed)
        for i, j in self.detector.initial_contacts(self.x):
            self.trajectory.events.append(make_collision_event(self.t, i, j, self.x, self.v))

    # --- public API ----------------------------------------------------------
    def run(self, t_end: float) -> RunResult:
        """Advance up to ``t_end`` (fixed step: to the first grid point >= t_end).

        Returns early with status 'collision' if ``stop_on_collision`` is set;
        calling ``run`` again resumes from the contact.
        """
        n_before = len(self.trajectory.collisions)
        if self._stepper is not None:
            status = self._run_fixed(t_end)
        else:
            status = self._run_adaptive(t_end)
        return RunResult(status, self.t, self.trajectory.collisions[n_before:])

    def add_impulse(self, impulse) -> None:
        """Schedule an impulse (``impulse.t`` >= current time; use ``t = sim.t`` for an immediate one)."""
        if impulse.t < self.t - _EPS:
            raise ValueError("cannot schedule an impulse in the past")
        self._pending.append(impulse)
        self._pending.sort(key=lambda imp: imp.t)

    @property
    def energy(self) -> float:
        kinetic = 0.5 * float(np.sum(self.masses[:, None] * self.v**2))
        return kinetic + float(self.model.potential_energy(self.x))

    # --- impulses ------------------------------------------------------------
    def _next_impulse_time(self) -> float:
        return self._pending[0].t if self._pending else math.inf

    def _apply_due_impulses(self) -> None:
        while self._pending and self._pending[0].t <= self.t + _EPS * max(1.0, abs(self.t)):
            imp = self._pending.pop(0)
            i = self.names.index(imp.body)
            ref_name = imp.reference or (self.scenario.default_reference(imp.body) if self.n > 1 else None)
            ref = self.names.index(ref_name) if ref_name else None
            dv = impulse_vector(imp, i, ref, self.x, self.v)
            applied = not self.fixed[i]
            self.trajectory.events.append(
                ImpulseEvent(self.t, i, self.x[i].copy(), self.v[i].copy(), dv, float(self.masses[i]), applied))
            if applied:
                self.v[i] = self.v[i] + dv

    # --- fixed step ----------------------------------------------------------
    def _grid_time(self, k: int) -> float:
        return self._t_origin + k * self.dt

    def _run_fixed(self, t_end: float) -> str:
        k_end = math.ceil((t_end - self._t_origin) / self.dt - 1e-9)
        while True:
            self._apply_due_impulses()
            if self._k >= k_end:
                return "done"
            t_grid = self._grid_time(self._k + 1)
            t_imp = self._next_impulse_time()
            on_grid = not (t_imp < t_grid - _EPS * max(1.0, abs(t_grid)))
            target = t_grid if on_grid else t_imp
            if self._substep(target - self.t, target):
                return "collision"
            if on_grid:
                self._k += 1
                if self._k % self.stride == 0:
                    self._n_out += 1
                    self.trajectory.append(self.t, self.x, self.v)

    def _substep(self, h: float, t_target: float) -> bool:
        """One step of size h ending at t_target. Returns True if stopped on a collision."""
        x0, v0, a0, t0 = self.x, self.v, self.a, self.t
        x1, v1, a1 = self._stepper.step(x0, v0, a0, h, self.model.acceleration)

        def state_at(tau):
            return self._stepper.step(x0, v0, a0, tau * h, self.model.acceleration)[0]

        hits = self.detector.find(h, x0, v0, x1, v1, state_at)
        if hits and self.stop_on_collision:
            tau, i, j = hits[0]
            self.x, self.v, self.a = self._stepper.step(x0, v0, a0, tau * h, self.model.acceleration)
            self.t = t0 + tau * h
            self._record_collision(i, j, self.x, self.v, stop=True)
            return True
        for tau, i, j in hits:
            xs, vs, _ = self._stepper.step(x0, v0, a0, tau * h, self.model.acceleration)
            self._record_collision(i, j, xs, vs, t=t0 + tau * h, end_pos=x1)
        self.x, self.v, self.a, self.t = x1, v1, a1, t_target
        self.trajectory.events.extend(self.detector.update_contacts(self.t, self.x))
        return False

    def _record_collision(self, i, j, pos, vel, t=None, stop=False, end_pos=None):
        self.trajectory.events.append(make_collision_event(self.t if t is None else t, i, j, pos, vel))
        if stop:
            self.detector.in_contact.add((i, j))
        elif end_pos is not None and self.detector.touching(i, j, end_pos):
            self.detector.in_contact.add((i, j))

    # --- adaptive (DOP853) -----------------------------------------------------
    def _rhs(self, t, y):
        n2 = 2 * self.n
        x = y[:n2].reshape(self.n, 2)
        return np.concatenate([y[n2:], self.model.acceleration(x).ravel()])

    def _pack(self):
        return np.concatenate([self.x.ravel(), self.v.ravel()])

    def _unpack(self, y):
        n2 = 2 * self.n
        return y[:n2].reshape(self.n, 2).copy(), y[n2:].reshape(self.n, 2).copy()

    def _run_adaptive(self, t_end: float) -> str:
        while True:
            self._apply_due_impulses()
            if self.t >= t_end - _EPS * max(1.0, abs(t_end)):
                return "done"
            t_bound = min(t_end, self._next_impulse_time())
            solver = DOP853(self._rhs, self.t, self._pack(), t_bound, rtol=self.rtol, atol=self.atol,
                            first_step=min(self._h, t_bound - self.t) if self._h else None)
            while solver.status == "running":
                t_old, y_old = solver.t, solver.y.copy()
                solver.step()
                if solver.status == "failed":
                    raise RuntimeError(f"DOP853 failed at t={t_old}")
                self._h = solver.step_size
                dense = solver.dense_output()
                h = solver.t - t_old
                x0, v0 = self._unpack(y_old)
                x1, v1 = self._unpack(solver.y)

                def state_at(tau, dense=dense, t_old=t_old, h=h):
                    return dense(t_old + tau * h)[: 2 * self.n].reshape(self.n, 2)

                hits = self.detector.find(h, x0, v0, x1, v1, state_at)
                if hits and self.stop_on_collision:
                    tau, i, j = hits[0]
                    t_c = t_old + tau * h
                    self._emit_dense(dense, t_c)
                    self.x, self.v = self._unpack(dense(t_c))
                    self.t = t_c
                    self.a = self.model.acceleration(self.x)
                    self._record_collision(i, j, self.x, self.v, stop=True)
                    return "collision"
                for tau, i, j in hits:
                    xs, vs = self._unpack(dense(t_old + tau * h))
                    self._record_collision(i, j, xs, vs, t=t_old + tau * h, end_pos=x1)
                self._emit_dense(dense, solver.t)
                self.x, self.v, self.t = x1, v1, solver.t
                self.trajectory.events.extend(self.detector.update_contacts(self.t, self.x))
            self.t = t_bound  # exact, so that due impulses are applied
            self.a = self.model.acceleration(self.x)

    def _emit_dense(self, dense, t_until: float) -> None:
        while True:
            t_next = self._t_origin + (self._n_out + 1) * self.output_dt
            if t_next > t_until + _EPS * max(1.0, abs(t_until)):
                return
            x, v = self._unpack(dense(t_next))
            self._n_out += 1
            self.trajectory.append(t_next, x, v)
