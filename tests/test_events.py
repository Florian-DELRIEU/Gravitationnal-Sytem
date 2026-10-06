"""T6 (impulses) and T7 (collisions)."""

import math

import numpy as np
import pytest
from conftest import relative_state, two_body

from gravsim.core import kepler, units
from gravsim.core.body import Body
from gravsim.core.events import Impulse
from gravsim.core.scenario import Scenario
from gravsim.core.simulation import Simulation

MU = units.G * 1.001


# --- T6 -----------------------------------------------------------------------
@pytest.mark.parametrize("integrator", ["dop853", "yoshida4"])
def test_T6_prograde_impulse_raises_apoapsis(integrator):
    sc = two_body(M=1.0, m=1e-3, r=1.0)
    t_imp, dv = 0.3737, 0.8
    sc.impulses.append(Impulse("planet", dv, t_imp))  # not on the sampling grid
    sim = Simulation(sc, integrator, output_dt=0.01)
    sim.run(2.0)
    ev = sim.trajectory.impulses[0]
    assert ev.t == pytest.approx(t_imp, abs=1e-14)

    # Expected orbit from vis-viva. Only the planet is kicked, so the relative speed
    # changes by exactly dv (the impulse is along the relative velocity).
    rel, vrel = relative_state(sim.trajectory)
    after = sim.trajectory.t > t_imp + 1e-9
    el = kepler.elements_from_state(rel[after], vrel[after], MU)
    r = 1.0
    v_rel_new = kepler.circular_speed(MU, r) + dv
    a_new = 1.0 / (2.0 / r - v_rel_new**2 / MU)
    assert np.max(np.abs(el["apoapsis"] / (2 * a_new - r) - 1)) < 1e-6
    assert np.max(np.abs(el["periapsis"] / r - 1)) < 1e-6
    # The impulse point becomes the periapsis: omega = polar angle of the planet relative to
    # the star at t_imp (star position taken at the previous sample; it moves < 1e-4 AU).
    k = np.searchsorted(sim.trajectory.t, t_imp)
    rel_imp = ev.position - sim.trajectory.pos[k - 1, 0]
    assert el["omega"][0] == pytest.approx(math.atan2(rel_imp[1], rel_imp[0]), abs=1e-3)


def test_T6_relative_dv_and_star_recoil():
    """Check the exact impulse vector: along the relative velocity."""
    sc = two_body(M=1.0, m=1e-3, r=1.0)
    sc.impulses.append(Impulse("planet", 0.5, 0.0))
    sim = Simulation(sc, "dop853")
    sim.run(0.01)
    ev = sim.trajectory.impulses[0]
    vrel = sc.bodies[1].velocity - sc.bodies[0].velocity
    assert ev.dv == pytest.approx(0.5 * vrel / np.hypot(*vrel), rel=1e-14)


@pytest.mark.parametrize("integrator", ["dop853", "yoshida4"])
def test_T6_energy_ledger(integrator):
    sc = two_body(M=1.0, m=1e-3, r=1.0)
    sc.impulses += [Impulse("planet", 0.8, 0.37), Impulse("planet", -1.1, 1.21, direction="radial"),
                    Impulse("star", 0.05, 1.5, direction="angle", angle_deg=30)]
    sim = Simulation(sc, integrator, rtol=1e-12, atol=1e-14)
    E0 = sim.energy
    sim.run(2.0)
    injected = sum(ev.delta_energy for ev in sim.trajectory.impulses)
    assert abs(injected) > 1e-4
    tol = 1e-9 if integrator == "dop853" else 1e-6
    assert abs(sim.energy - E0 - injected) / abs(E0) < tol


def test_T6_directions_and_signs():
    sc = Scenario()
    sc.add(Body("star", 1.0))
    sc.add(Body("p", 1e-3, [1.0, 0.0]))
    sc.set_orbital_velocity("p", "star")
    sc.impulses += [Impulse("p", -0.2, 0.0, direction="radial"),
                    Impulse("p", 0.3, 0.0, direction="angle", angle_deg=90.0),
                    Impulse("star", 1.0, 0.0)]
    sc.bodies[0].fixed = True
    sim = Simulation(sc, "dop853")
    sim.run(0.01)
    radial, angle, on_fixed = sim.trajectory.impulses
    assert radial.dv == pytest.approx([-0.2, 0.0], abs=1e-15)  # inward
    assert angle.dv == pytest.approx([0.0, 0.3], abs=1e-15)
    assert not on_fixed.applied and on_fixed.delta_energy == 0.0
    assert np.all(sim.trajectory.vel[:, 0] == 0)


def test_impulse_cannot_be_in_the_past():
    sim = Simulation(two_body(), "dop853")
    sim.run(0.1)
    with pytest.raises(ValueError):
        sim.add_impulse(Impulse("planet", 0.1, 0.05))
    sim.add_impulse(Impulse("planet", 0.1, sim.t))  # immediate
    sim.run(0.2)
    assert sim.trajectory.impulses[0].t == pytest.approx(0.1)


# --- T7 -----------------------------------------------------------------------
def radial_infall_time(r0, r, mu):
    x = r / r0
    return math.sqrt(r0**3 / (2 * mu)) * (math.sqrt(x * (1 - x)) + math.acos(math.sqrt(x)))


def infall_scenario():
    sc = Scenario()
    sc.add(Body("A", 1.0, [0.0, 0.0], radius=0.01))
    sc.add(Body("B", 1e-3, [1.0, 0.0], radius=0.005))
    return sc


@pytest.mark.parametrize("integrator,kwargs", [("dop853", {"rtol": 1e-12, "atol": 1e-14}),
                                               ("yoshida4", {"dt": 1e-5, "output_dt": 1e-3})])
def test_T7_radial_infall_contact_time(integrator, kwargs):
    sim = Simulation(infall_scenario(), integrator, stop_on_collision=True, **kwargs)
    res = sim.run(1.0)
    expected = radial_infall_time(1.0, 0.015, units.G * 1.001)
    assert res.status == "collision"
    assert len(res.collisions) == 1
    ev = res.collisions[0]
    assert ev.t == pytest.approx(expected, abs=1e-6)
    assert sim.t == ev.t
    assert np.hypot(*(sim.x[1] - sim.x[0])) == pytest.approx(0.015, rel=1e-9)
    assert ev.impact_angle_deg == pytest.approx(0.0, abs=1e-6)  # head-on


def test_T7_resume_after_collision_conserves_energy():
    """Bodies pass through each other with the homogeneous-sphere law; energy stays conserved."""
    sim = Simulation(infall_scenario(), "dop853", stop_on_collision=True, rtol=1e-12, atol=1e-14)
    E0 = sim.energy
    sim.run(1.0)
    res = sim.run(sim.t + 0.05)
    assert res.status == "done"  # no second stop for the same contact
    assert abs(sim.energy / E0 - 1) < 1e-8
    assert any(e.kind == "separation" for e in sim.trajectory.events)


@pytest.mark.parametrize("integrator", ["dop853", "yoshida4", "leapfrog"])
def test_T7_grazing_contact_between_steps(integrator):
    """Straight-line flyby whose contact chord (0.087 AU) is far shorter than one step (10 AU)."""
    sc = Scenario()
    sc.add(Body("A", 0.0, [0.0, 0.0], radius=0.05))
    sc.add(Body("B", 0.0, [-5.0, 0.09], [10.0, 0.0], radius=0.05))
    sim = Simulation(sc, integrator, dt=1.0, output_dt=1.0, stop_on_collision=True)
    res = sim.run(2.0)
    t_entry = (5.0 - math.sqrt(0.1**2 - 0.09**2)) / 10.0
    assert res.status == "collision"
    assert res.collisions[0].t == pytest.approx(t_entry, abs=1e-9)
    assert res.collisions[0].impact_angle_deg > 60  # grazing


def test_T7_collision_reported_without_stopping():
    sc = Scenario()
    sc.add(Body("A", 0.0, [0.0, 0.0], radius=0.05))
    sc.add(Body("B", 0.0, [-5.0, 0.0], [10.0, 0.0], radius=0.05))
    sim = Simulation(sc, "yoshida4", dt=0.01, output_dt=0.1)
    res = sim.run(1.0)
    assert res.status == "done" and len(res.collisions) == 1
    assert res.collisions[0].t == pytest.approx(0.49, abs=1e-9)


def test_initial_overlap_reported():
    sc = Scenario()
    sc.add(Body("A", 1.0, [0.0, 0.0], radius=0.1))
    sc.add(Body("B", 1e-3, [0.05, 0.0], radius=0.1))
    sim = Simulation(sc, "dop853")
    assert len(sim.trajectory.collisions) == 1 and sim.trajectory.collisions[0].t == 0.0
