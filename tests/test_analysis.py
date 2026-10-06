"""Diagnostics, frames (T8), orbits, restricted three-body tools."""

import numpy as np
import pytest
from conftest import two_body

from gravsim.analysis import diagnostics, frames, orbits
from gravsim.core import kepler, units
from gravsim.core.body import Body
from gravsim.core.events import Impulse
from gravsim.core.scenario import Scenario, load_preset
from gravsim.core.simulation import Simulation


def run(sc, t_end, **kw):
    sim = Simulation(sc, **kw)
    sim.run(t_end)
    return sim.trajectory


# --- fidelity gauge -------------------------------------------------------------
def test_fidelity_ignores_impulses():
    sc = two_body(M=1.0, m=1e-3, r=1.0)
    sc.impulses += [Impulse("planet", 0.8, 0.3737), Impulse("star", 0.1, 0.9, direction="angle", angle_deg=45)]
    traj = run(sc, 2.0, integrator="dop853", rtol=1e-12, atol=1e-14)
    fid = diagnostics.fidelity(traj)
    worst = fid.summary()
    assert worst["energy"] < 1e-9 and worst["angular_momentum"] < 1e-9 and worst["momentum"] < 1e-12
    # Without the ledger the energy jump would be obvious.
    E = diagnostics.total_energy(traj)
    assert abs(E[-1] / E[0] - 1) > 1e-3


def test_fidelity_with_fixed_body():
    traj = run(load_preset("soleil_fixe_comete"), 1.0, integrator="dop853")
    fid = diagnostics.fidelity(traj)
    assert fid.momentum is None
    assert fid.summary()["energy"] < 1e-9 and fid.summary()["angular_momentum"] < 1e-9
    assert any("corps fixe" in note for note in fid.notes)


def test_barycentre_fixed_for_isolated_system():
    traj = run(load_preset("binaire"), 2.0, integrator="yoshida4")
    r, v = diagnostics.barycenter(traj)
    assert np.max(np.abs(r)) < 1e-12 and np.max(np.abs(v)) < 1e-12


# --- frames (T8) -----------------------------------------------------------------
def test_T8_rotating_frame_binary_is_static():
    traj = run(load_preset("binaire"), 3.0, integrator="dop853", rtol=1e-12, atol=1e-14)
    rv = frames.rotating(traj, "Étoile A", "Étoile B")
    assert np.max(np.abs(rv.pos - rv.pos[0])) < 1e-6
    assert np.max(np.abs(rv.vel)) < 1e-6
    # A on -x, B on +x, origin at the barycentre: x_B = m_A / M * d
    assert rv.pos[0, 1] == pytest.approx([1.0 / 1.8, 0.0], abs=1e-12)
    assert rv.omega == pytest.approx(2 * np.pi / kepler.period(1.0, units.G * 1.8), rel=1e-8)


def test_barycentric_and_centered_frames():
    traj = run(load_preset("soleil_jupiter"), 1.0, integrator="yoshida4")
    bc = frames.barycentric(traj)
    assert np.max(np.abs(np.einsum("n,tnk->tk", traj.masses, bc.pos))) < 1e-12
    sun = frames.view(traj, ("body", "Soleil"))
    assert np.all(sun.pos[:, 0] == 0) and np.all(sun.vel[:, 0] == 0)
    assert np.array_equal(frames.view(traj, "inertial").pos, traj.pos)


def test_rotating_velocity_transformation_consistent():
    """v' must equal the time derivative of r' (checked by finite differences)."""
    traj = run(load_preset("excentrique"), 0.2, integrator="dop853", output_dt=1e-4, rtol=1e-12, atol=1e-14)
    rv = frames.rotating(traj, "GJ 876", "Planète")
    k = 1
    fd = (rv.pos[2:, k] - rv.pos[:-2, k]) / (2e-4)
    assert np.max(np.abs(fd - rv.vel[1:-1, k])) < 1e-4 * np.max(np.abs(traj.vel[:, k]))


# --- restricted 3-body -------------------------------------------------------------
def test_lagrange_points():
    m1, m2 = 1.0, units.M_EARTH
    pts = frames.lagrange_points(m1, m2, separation=1.0)
    hill = (m2 / (3 * m1)) ** (1 / 3)
    x_earth = m1 / (m1 + m2)
    assert x_earth - pts["L1"][0] == pytest.approx(hill, rel=0.01)
    assert pts["L2"][0] - x_earth == pytest.approx(hill, rel=0.01)
    assert pts["L3"][0] == pytest.approx(-1.0, abs=1e-5)
    # L4 forms an equilateral triangle with both masses.
    l4 = pts["L4"]
    for xm in (-m2 / (m1 + m2), x_earth):
        assert np.hypot(l4[0] - xm, l4[1]) == pytest.approx(1.0, rel=1e-12)


def test_jacobi_constant_conserved():
    sc = load_preset("soleil_jupiter")
    sc.add(Body("Troyen", 0.0, sc.body("Soleil").position + 5.2 * np.array([0.5, np.sqrt(3) / 2])))
    # Co-rotating with the pair: velocity omega x r about the barycentre.
    r_cm, v_cm = sc.barycenter()
    omega = 2 * np.pi / kepler.period(5.2, units.G * (1 + units.M_JUP))
    rel = sc.body("Troyen").position - r_cm
    sc.body("Troyen").velocity = v_cm + omega * np.array([-rel[1], rel[0]])
    traj = run(sc, 30.0, integrator="dop853", rtol=1e-12, atol=1e-14)
    C = frames.jacobi_constant(traj, "Troyen", "Soleil", "Jupiter")
    assert np.max(np.abs(C / C[0] - 1)) < 1e-8
    # The Trojan stays near L4 (stable point).
    rv = frames.rotating(traj, "Soleil", "Jupiter")
    l4 = frames.lagrange_points(1.0, units.M_JUP, 5.2)["L4"]
    assert np.max(np.hypot(*(rv.pos[:, 2] - l4).T)) < 0.2


# --- orbits ----------------------------------------------------------------------
def test_measure_period_and_elements():
    sc = two_body(M=1.0, m=1e-3, r=0.5, e=0.5)
    traj = run(sc, 5.2, integrator="dop853", output_dt=1e-3)
    P, crossings = orbits.measure_period(traj, "planet")
    assert P == pytest.approx(kepler.period(1.0, units.G * 1.001), rel=1e-5)
    el = orbits.osculating_elements(traj, "planet")
    assert np.allclose(el["a"], 1.0, rtol=1e-7) and np.all(el["kind"] == "elliptic")


def test_pair_analysis():
    sc = two_body(M=1.0, m=1e-3, r=0.5, e=0.5)
    traj = run(sc, 1.0, integrator="dop853", output_dt=1e-4)
    pa = orbits.pair_analysis(traj, "star", "planet")
    assert pa.closest[1] == pytest.approx(0.5, rel=1e-6)
    assert pa.farthest[1] == pytest.approx(1.5, rel=1e-6)
    assert pa.reduced_mass == pytest.approx(1e-3 / 1.001)
    assert np.allclose(pa.relative_energy, pa.relative_energy[0], rtol=1e-8)


def test_hyperbolic_flyby_kind():
    sc = Scenario()
    sc.add(Body("star", 1.0))
    sc.add(Body("rogue", 1e-6, [-10.0, 1.0], [8.0, 0.0]))
    traj = run(sc, 2.0, integrator="dop853")
    pa = orbits.pair_analysis(traj, "star", "rogue")
    assert np.all(pa.kind == "hyperbolic")
    assert np.all(pa.relative_speed > pa.escape_speed)
