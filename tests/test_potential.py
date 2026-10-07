"""Gravitational / effective potential and Lagrange points (analysis/potential.py)."""

import numpy as np
import pytest
from conftest import two_body

from gravsim.analysis import frames, potential
from gravsim.core import units
from gravsim.core.body import Body
from gravsim.core.forces import GravityModel
from gravsim.core.scenario import load_preset
from gravsim.core.simulation import Simulation

G = units.G


def run(sc, t_end, **kw):
    sim = Simulation(sc, **kw)
    sim.run(t_end)
    return sim.trajectory


def gradient(f, p, h):
    p = np.asarray(p, float)
    g = np.zeros(2)
    for k in range(2):
        e = np.zeros(2)
        e[k] = h
        g[k] = (f(p + e) - f(p - e)) / (2 * h)
    return g


def hessian(f, p, h):
    p = np.asarray(p, float)
    H = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            ei, ej = np.zeros(2), np.zeros(2)
            ei[i], ej[j] = h, h
            H[i, j] = (f(p + ei + ej) - f(p + ei - ej) - f(p - ei + ej) + f(p - ei - ej)) / (4 * h * h)
    return H


def two_masses(m1, m2, d):
    """Circular pair about its barycentre, a on the left, b on the right (rotating counterclockwise)."""
    mu = m2 / (m1 + m2)
    pos = np.array([[-mu * d, 0.0], [(1 - mu) * d, 0.0]])
    omega = np.sqrt(G * (m1 + m2) / d**3)
    vel = omega * np.array([[0.0, -mu * d], [0.0, (1 - mu) * d]])
    return pos, vel, np.array([m1, m2])


def pair_setup(name):
    if name == "sun_jupiter":
        m1, m2, d = 1.0, units.M_JUP, 5.2
    else:
        m1, m2, d = 1.0, 0.8, 1.0
    pos, vel, masses = two_masses(m1, m2, d)
    fr = potential.pair_frame(pos, vel, masses, 0, 1)
    return pos, vel, masses, fr, d


# 1 -----------------------------------------------------------------------------------
def test_gradient_matches_gravity_model():
    rng = np.random.default_rng(1)
    pos = rng.uniform(-2, 2, (4, 2))
    masses = np.array([1.0, 1e-3, 0.3, 0.0])
    radii = np.array([0.0, 0.0, 0.0, 0.0])
    for p in ([3.0, 1.0], [-1.2, 2.5], [0.4, -0.7]):
        model = GravityModel(np.append(masses, 0.0), G, np.append(radii, 0.0))
        acc = model.acceleration(np.vstack([pos, p]))[-1]
        grad = gradient(lambda q: potential.gravitational_potential(q, pos, masses, G, radii), p, 1e-5)
        assert -grad == pytest.approx(acc, rel=1e-6, abs=1e-8)


def test_gradient_inside_a_body():
    pos = np.array([[0.0, 0.0], [3.0, 0.0]])
    masses = np.array([1.0, 1e-3])
    radii = np.array([0.5, 0.0])
    p = np.array([0.2, 0.1])  # inside the first body
    model = GravityModel(np.append(masses, 0.0), G, np.append(radii, 0.0))
    acc = model.acceleration(np.vstack([pos, p]))[-1]
    grad = gradient(lambda q: potential.gravitational_potential(q, pos, masses, G, radii), p, 1e-5)
    assert -grad == pytest.approx(acc, rel=1e-6)
    # continuous at the surface, finite at the centre
    on = np.array([[0.5 - 1e-9, 0.0], [0.5 + 1e-9, 0.0]])
    phi = potential.gravitational_potential(on, pos, masses, G, radii)
    assert phi[0] == pytest.approx(phi[1], rel=1e-6)
    assert np.isfinite(potential.gravitational_potential(np.array([0.0, 0.0]), pos, masses, G, radii))


# 2, 3, 4 ----------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["sun_jupiter", "binary"])
def test_lagrange_points_are_equilibria_and_stable_as_expected(name):
    pos, vel, masses, fr, d = pair_setup(name)
    pts = potential.lagrange_points_inertial(pos, vel, masses, 0, 1)
    f = lambda q: potential.effective_potential(q, pos, masses, G, fr)  # noqa: E731
    scale = G * masses.sum() / d**2
    for key, p in pts.items():
        assert np.hypot(*gradient(f, p, 1e-6 * d)) < 1e-6 * scale, key
        eig = np.linalg.eigvalsh(hessian(f, p, 1e-4 * d))
        if key in ("L1", "L2", "L3"):
            assert eig[0] < 0 < eig[1], key  # saddle
        else:
            assert eig[1] < 0, key  # maximum


def test_critical_levels_values():
    pos, vel, masses, fr, d = pair_setup("sun_jupiter")
    pts = potential.lagrange_points_inertial(pos, vel, masses, 0, 1)
    lv = potential.critical_levels(pos, masses, G, fr, pts)
    assert lv["L1"] == pytest.approx(-11.54616, abs=1e-4)
    assert lv["L2"] == pytest.approx(-11.54132, abs=1e-4)
    assert lv["L3"] == pytest.approx(-11.40250, abs=1e-4)
    l4 = potential.effective_potential(pts["L4"], pos, masses, G, fr)
    l5 = potential.effective_potential(pts["L5"], pos, masses, G, fr)
    assert l4 == pytest.approx(-11.39526, abs=1e-4) and l5 == pytest.approx(l4, abs=1e-9)
    assert lv["L1"] < lv["L2"] < lv["L3"] < l4

    pos, vel, masses, fr, d = pair_setup("binary")
    pts = potential.lagrange_points_inertial(pos, vel, masses, 0, 1)
    lv = potential.critical_levels(pos, masses, G, fr, pts)
    assert lv["L1"] == pytest.approx(-141.915, abs=1e-2)
    assert lv["L2"] == pytest.approx(-124.134, abs=1e-2)
    assert lv["L3"] == pytest.approx(-121.342, abs=1e-2)
    assert potential.effective_potential(pts["L4"], pos, masses, G, fr) == pytest.approx(-97.819, abs=1e-2)


# 5 -----------------------------------------------------------------------------------
def test_trojans_sit_on_l4_l5():
    sc = load_preset("troyens")
    pts = potential.lagrange_points_inertial(sc.positions, sc.velocities, sc.masses, 0, 1)
    assert np.hypot(*(pts["L4"] - sc.body("Troyen L4").position)) < 1e-6
    assert np.hypot(*(pts["L5"] - sc.body("Troyen L5").position)) < 1e-6


# 6 -----------------------------------------------------------------------------------
def test_lagrange_points_fixed_in_rotating_frame():
    sc = load_preset("binaire")
    traj = run(sc, 3.0, integrator="dop853", rtol=1e-12, atol=1e-14)
    rv = frames.rotating(traj, 0, 1)
    ref = None
    for k in range(0, len(traj), max(1, len(traj) // 25)):
        pts = potential.lagrange_points_inertial(traj.pos[k], traj.vel[k], traj.masses, 0, 1)
        c, s = np.cos(rv.angle[k]), np.sin(rv.angle[k])
        rot = {n: np.array([c * (p - rv.origin[k])[0] + s * (p - rv.origin[k])[1],
                            -s * (p - rv.origin[k])[0] + c * (p - rv.origin[k])[1]]) for n, p in pts.items()}
        if ref is None:
            ref = rot
        for n in rot:
            assert np.hypot(*(rot[n] - ref[n])) < 1e-6, n


# 7 -----------------------------------------------------------------------------------
def test_zero_velocity_level_conserved():
    sc = load_preset("soleil_jupiter")
    sc.add(Body("Test", 0.0, sc.body("Soleil").position + 5.2 * np.array([0.55, np.sqrt(3) / 2 - 0.05])))
    r_cm, v_cm = sc.barycenter()
    omega = np.sqrt(units.G * (1 + units.M_JUP) / 5.2**3)
    rel = sc.body("Test").position - r_cm
    sc.body("Test").velocity = v_cm + omega * np.array([-rel[1], rel[0]]) + np.array([0.05, -0.03])
    traj = run(sc, 20.0, integrator="dop853", rtol=1e-12, atol=1e-14)
    k = traj.index("Test")
    levels = []
    for i in range(0, len(traj), max(1, len(traj) // 40)):
        fr = potential.pair_frame(traj.pos[i], traj.vel[i], traj.masses, 0, 1)
        levels.append(potential.zero_velocity_level(traj.pos[i, k], traj.vel[i, k], traj.pos[i], traj.masses, G, fr))
    levels = np.array(levels)
    assert np.max(np.abs(levels - levels[0])) < 1e-8


# 8 -----------------------------------------------------------------------------------
def test_errors():
    pos, vel, masses = two_masses(1.0, 1e-3, 1.0)
    with pytest.raises(ValueError):
        potential.pair_frame(pos, vel, masses, 0, 0)
    with pytest.raises(ValueError):
        potential.pair_frame(np.zeros((2, 2)), vel, masses, 0, 1)  # coincident bodies
    with pytest.raises(ValueError):
        potential.pair_frame(pos, vel, np.zeros(2), 0, 1)
    with pytest.raises(ValueError):
        potential.lagrange_points_inertial(pos, vel, np.array([1.0, 0.0]), 0, 1)


def test_two_body_fixture_still_available():
    # sanity: the shared helper builds a valid pair for the potential module too
    sc = two_body(M=1.0, m=1e-3, r=1.0)
    fr = potential.pair_frame(sc.positions, sc.velocities, sc.masses, 0, 1)
    assert fr.separation == pytest.approx(1.0) and fr.omega > 0
