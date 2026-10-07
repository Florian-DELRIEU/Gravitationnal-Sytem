"""The demonstration presets do what their description promises."""

import math

import numpy as np
import pytest

from gravsim.analysis import diagnostics, frames, orbits
from gravsim.core import units
from gravsim.core.scenario import load_preset
from gravsim.core.simulation import Simulation


def simulate(name, years, **kw):
    sim = Simulation(load_preset(name), kw.pop("integrator", "dop853"), **kw)
    sim.run(years)
    return sim


def test_figure_eight_is_periodic():
    period = 6.32591398 / (2 * math.pi)  # G = 1 period scaled to 1 Msun, 1 AU
    sim = simulate("figure_huit", period, output_dt=period / 600, rtol=1e-12, atol=1e-14)  # T/3 on the grid
    traj = sim.trajectory
    k = int(np.argmin(np.abs(traj.t - period)))
    assert np.max(np.abs(traj.pos[k] - traj.pos[0])) < 2e-3  # back to the start after one period
    # A choreography: body C at T/3 is where body A started (same curve, phase-shifted).
    j = int(np.argmin(np.abs(traj.t - period / 3)))
    assert min(np.hypot(*(traj.pos[j, i] - traj.pos[0, 0])) for i in range(3)) < 2e-3
    assert diagnostics.fidelity(traj).summary()["energy"] < 1e-9


def test_trojans_stay_near_l4_and_l5():
    sim = simulate("troyens", 60.0, integrator="yoshida4")
    rv = frames.rotating(sim.trajectory, "Soleil", "Jupiter")
    pts = frames.lagrange_points(1.0, units.M_JUP, 5.2)
    for name, key in (("Troyen L4", "L4"), ("Troyen L5", "L5")):
        k = sim.trajectory.index(name)
        assert np.max(np.hypot(*(rv.pos[:, k] - pts[key]).T)) < 0.3  # librates around its Lagrange point


def test_circumbinary_planet_orbits_both_stars():
    sim = simulate("circumbinaire", 6.0, integrator="yoshida4")
    traj = sim.trajectory
    m = traj.masses[:2]
    centre = np.einsum("n,tnk->tk", m, traj.pos[:, :2]) / m.sum()
    d = np.hypot(*(traj.pos[:, 2] - centre).T)
    assert 0.6 < d.min() and d.max() < 0.82  # stable, around the pair's barycentre
    turns = np.unwrap(np.arctan2(*(traj.pos[:, 2] - centre).T[::-1]))
    assert (turns[-1] - turns[0]) / (2 * math.pi) == pytest.approx(6.0 / (229 / 365.25), rel=0.05)


def test_head_on_collision_after_three_months():
    sim = Simulation(load_preset("collision_frontale"), "dop853", stop_on_collision=True)
    res = sim.run(1.0)
    assert res.status == "collision"
    ev = res.collisions[0]
    names = {sim.names[ev.i], sim.names[ev.j]}
    assert names == {"Planète A", "Planète B"}
    assert 0.2 < ev.t < 0.27
    assert units.au_per_yr_to_m_s(ev.relative_speed) / 1e3 == pytest.approx(59.6, rel=0.03)
    assert ev.impact_angle_deg < 5  # head-on


def test_moon_follows_the_earth_around_the_sun():
    sim = simulate("soleil_terre_lune", 1.0, output_dt=0.001)
    traj = sim.trajectory
    d = np.hypot(*(traj.pos[:, 2] - traj.pos[:, 1]).T)
    # The Sun perturbs the lunar orbit (evection, variation): starting circular, the distance wanders between
    # about 375 000 and 400 000 km in a year (the real Moon: 363 000 - 405 000 km).
    assert np.allclose(d, 384400e3 / units.AU_M, rtol=0.05)
    assert d.max() - d.min() > 0.03 * 384400e3 / units.AU_M  # the perturbation is really there
    period, _ = orbits.measure_period(traj, "Lune", "Terre")
    assert period / units.DAY_YR == pytest.approx(27.3, rel=0.02)  # sidereal month


def test_three_planets_periods():
    sim = Simulation(load_preset("trois_planetes"), "dop853")
    periods = [s.period for s in orbits.reflex_signatures(sim.trajectory, "Étoile")]
    assert periods == pytest.approx([0.1, 0.45, 1.6], rel=0.01)
