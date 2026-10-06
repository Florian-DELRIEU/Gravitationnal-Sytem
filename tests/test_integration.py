"""T1-T5: accuracy and conservation laws of the integrators."""

import numpy as np
import pytest
from conftest import crossing_times, relative_state, two_body

from gravsim.core import kepler, units
from gravsim.core.body import Body
from gravsim.core.scenario import Scenario
from gravsim.core.simulation import Simulation

ALL = ["dop853", "yoshida4", "leapfrog"]


def energy(traj, model):
    kin = 0.5 * np.einsum("n,tnk,tnk->t", traj.masses, traj.vel, traj.vel)
    return kin + model.potential_energy(traj.pos)


# --- T1 -----------------------------------------------------------------------
@pytest.mark.parametrize("integrator", ["dop853", "yoshida4"])
def test_T1_circular_period(integrator):
    sc = two_body(M=1.0, m=1e-3, r=1.0)
    P = kepler.period(1.0, units.G * 1.001)
    sim = Simulation(sc, integrator, dt=P / 1000, output_dt=P / 1000)
    sim.run(10.5 * P)
    rel, _ = relative_state(sim.trajectory)
    crossings = crossing_times(sim.trajectory.t, rel)
    measured = np.mean(np.diff(crossings))
    assert len(crossings) == 10
    assert measured == pytest.approx(P, rel=1e-6)


# --- T2 -----------------------------------------------------------------------
def test_T2_energy_dop853_eccentric():
    sc = two_body(M=1.0, m=1e-3, r=0.5, e=0.5)  # a = 1
    P = kepler.period(1.0, units.G * 1.001)
    sim = Simulation(sc, "dop853", output_dt=P / 50, rtol=1e-12, atol=1e-14)
    sim.run(100 * P)
    E = energy(sim.trajectory, sim.model)
    assert np.max(np.abs(E / E[0] - 1)) < 1e-9


# Bounds calibrated at the recommended step (P/355 at e = 0.5): oscillating error ~ (dt * omega_peri)^order.
@pytest.mark.parametrize("integrator,bound", [("yoshida4", 5e-6), ("leapfrog", 1e-3)])
def test_T2_energy_symplectic_bounded(integrator, bound):
    sc = two_body(M=1.0, m=1e-3, r=0.5, e=0.5)
    P = kepler.period(1.0, units.G * 1.001)
    sim = Simulation(sc, integrator, output_dt=P / 50)
    sim.run(200 * P)
    err = np.abs(energy(sim.trajectory, sim.model) / energy(sim.trajectory, sim.model)[0] - 1)
    half = len(err) // 2
    assert err.max() < bound
    # No secular drift: the error in the second half is not growing.
    assert err[half:].max() < 2.0 * err[:half].max() + 1e-14


# --- T3 -----------------------------------------------------------------------
@pytest.mark.parametrize("integrator", ALL)
def test_T3_momentum_conservation(integrator):
    sc = Scenario()
    sc.add(Body("A", 1.0, [0.0, 0.0], [0.0, -0.3]))
    sc.add(Body("B", 0.5, [1.0, 0.2], [0.4, 4.0]))
    sc.add(Body("C", 0.3, [-0.6, 0.9], [-3.0, -1.0]))
    sim = Simulation(sc, integrator)
    sim.run(3.0)
    p = np.einsum("n,tnk->tk", sim.masses, sim.trajectory.vel)
    p_ref = np.sum(sim.masses * np.hypot(*sim.trajectory.vel[0].T))
    assert np.max(np.hypot(*(p - p[0]).T)) / p_ref < 1e-12


# --- T4 -----------------------------------------------------------------------
@pytest.mark.parametrize("integrator", ALL)
def test_T4_fixed_body(integrator):
    sc = Scenario()
    sc.add(Body("sun", 1.0, [0.3, -0.2], [5.0, 5.0], fixed=True))  # velocity must be ignored
    sc.add(Body("planet", 1e-3, [1.3, -0.2]))
    sc.add(Body("comet", 0.0, [0.3, 0.6]))
    sc.set_orbital_velocity("planet", "sun")
    sc.set_orbital_velocity("comet", "sun", e=0.6, at="apoapsis")
    sim = Simulation(sc, integrator)
    sim.run(3.0)
    traj = sim.trajectory
    assert np.array_equal(traj.pos[:, 0], np.tile([0.3, -0.2], (len(traj), 1)))
    assert np.all(traj.vel[:, 0] == 0.0)
    E = energy(traj, sim.model)
    assert np.max(np.abs(E / E[0] - 1)) < (1e-9 if integrator == "dop853" else 1e-4)
    # Angular momentum about the fixed body is conserved.
    r = traj.pos - traj.pos[:, :1]
    L = np.einsum("n,tn->t", traj.masses, r[..., 0] * traj.vel[..., 1] - r[..., 1] * traj.vel[..., 0])
    assert np.max(np.abs(L / L[0] - 1)) < 1e-9


# --- T5 -----------------------------------------------------------------------
@pytest.mark.parametrize("integrator,bound", [("dop853", 1e-6), ("yoshida4", 5e-6)])
def test_T5_auto_circular_velocity(integrator, bound):
    sc = two_body(M=1.0, m=0.01, r=2.0)
    sim = Simulation(sc, integrator)
    sim.run(5.0)
    rel, vrel = relative_state(sim.trajectory)
    el = kepler.elements_from_state(rel, vrel, units.G * 1.01)
    assert el["e"][0] < 1e-12  # the setup itself is exact
    assert el["e"].max() < bound  # bounded integration error


@pytest.mark.parametrize("e,at", [(0.3, "periapsis"), (0.3, "apoapsis"), (0.7, "periapsis")])
def test_T5_auto_eccentric_velocity(e, at):
    sc = two_body(M=1.0, m=0.01, r=1.5, e=e, at=at)
    sim = Simulation(sc, "dop853")
    sim.run(3.0)
    rel, vrel = relative_state(sim.trajectory)
    el = kepler.elements_from_state(rel, vrel, units.G * 1.01)
    assert np.max(np.abs(el["e"] - e)) < 1e-6
    apsis = el["periapsis"] if at == "periapsis" else el["apoapsis"]
    assert np.max(np.abs(apsis / 1.5 - 1)) < 1e-6


def test_T5_fixed_reference_uses_mu_of_reference_only():
    sc = two_body(M=1.0, m=0.05, r=1.0, star_fixed=True)  # heavy planet: mu = G M, not G (M+m)
    sim = Simulation(sc, "dop853")
    sim.run(3.0)
    rel, vrel = relative_state(sim.trajectory)
    assert kepler.elements_from_state(rel, vrel, units.G * 1.0)["e"].max() < 1e-6


def test_T5_escape_velocity():
    sc = two_body(M=1.0, m=1e-3, r=1.0, zero_momentum=False)
    sc.set_escape_velocity("planet", "star")
    sc.zero_total_momentum()
    rel = sc.bodies[1].position - sc.bodies[0].position
    vrel = sc.bodies[1].velocity - sc.bodies[0].velocity
    assert kepler.elements_from_state(rel, vrel, units.G * 1.001)["e"] == pytest.approx(1.0, abs=1e-12)


def test_zero_momentum_refused_with_fixed_body():
    sc = two_body(star_fixed=True)
    with pytest.raises(ValueError):
        sc.zero_total_momentum()


def test_samples_on_regular_grid():
    sc = two_body()
    for integrator in ("dop853", "yoshida4"):
        sim = Simulation(sc, integrator, output_dt=0.01)
        sim.run(0.5)
        sim.run(1.0)  # resumed in chunks
        assert np.allclose(np.diff(sim.trajectory.t), 0.01, rtol=0, atol=1e-12)
