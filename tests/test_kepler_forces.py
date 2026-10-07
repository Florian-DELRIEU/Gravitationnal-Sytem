"""Unit tests: units, Kepler formulas, gravity model."""

import math

import numpy as np
import pytest

from gravsim.core import kepler, units
from gravsim.core.forces import GravityModel


def test_kepler_third_law_units():
    # Earth around the Sun (m -> 0): 1 AU <-> 1 yr with G = 4 pi^2.
    assert kepler.period(1.0, units.G * 1.0) == pytest.approx(1.0, rel=1e-15)


def test_radius_from_density_sun():
    assert units.radius_from_density(1.0, 1.408) == pytest.approx(units.R_SUN, rel=5e-3)


def test_velocity_conversion():
    assert units.au_per_yr_to_m_s(1.0) == pytest.approx(4740.47, rel=1e-6)


@pytest.mark.parametrize("e,at", [(0.0, "periapsis"), (0.3, "periapsis"), (0.3, "apoapsis"), (0.9, "periapsis")])
def test_orbital_velocity_gives_requested_elements(e, at):
    mu = 2.5
    r = np.array([0.7, -0.4])
    v = kepler.orbital_velocity(r, mu, e, at)
    el = kepler.elements_from_state(r, v, mu)
    assert el["e"] == pytest.approx(e, abs=1e-12)
    dist = np.hypot(*r)
    expected = el["periapsis"] if at == "periapsis" else el["apoapsis"]
    assert dist == pytest.approx(float(expected), rel=1e-12)
    assert el["h"] > 0  # counterclockwise by default


def test_escape_velocity_is_parabolic():
    v = kepler.orbital_velocity([1.0, 0.0], 1.0, e=1.0)
    assert np.hypot(*v) == pytest.approx(kepler.escape_speed(1.0, 1.0))
    el = kepler.elements_from_state([1.0, 0.0], v, 1.0)
    assert el["e"] == pytest.approx(1.0, abs=1e-12)
    assert kepler.orbit_kind(el["e"]) == "parabolic"


def test_hyperbolic_elements():
    el = kepler.elements_from_state([1.0, 0.0], [0.0, 2.0], 1.0)
    assert el["e"] > 1 and el["a"] < 0 and np.isnan(el["period"]) and np.isinf(el["apoapsis"])


def test_radial_fall_is_bound_not_parabolic():
    """Radial fall from rest: e = 1 but the energy is negative, so the orbit is a degenerate ellipse."""
    el = kepler.elements_from_state([1.0, 0.0], [0.0, 0.0], 4.0)
    assert el["e"] == pytest.approx(1.0) and el["kind"] == "elliptic"
    assert el["a"] == pytest.approx(0.5) and el["period"] == pytest.approx(kepler.period(0.5, 4.0))
    assert el["periapsis"] == pytest.approx(0.0, abs=1e-15) and el["apoapsis"] == pytest.approx(1.0)
    # Same at a nonzero speed along the radius.
    el = kepler.elements_from_state([1.0, 0.0], [0.5, 0.0], 4.0)
    assert el["kind"] == "elliptic" and np.isfinite(el["period"])


def test_kind_vector_and_hyperbolic():
    r = np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    v = np.array([[0.0, 1.0], [0.0, math.sqrt(2.0)], [0.0, 2.0]])  # mu = 1: ellipse, parabola, hyperbola
    assert list(kepler.elements_from_state(r, v, 1.0)["kind"]) == ["elliptic", "parabolic", "hyperbolic"]


def test_clockwise_orbit():
    v = kepler.orbital_velocity([1.0, 0.0], 1.0, clockwise=True)
    assert kepler.elements_from_state([1.0, 0.0], v, 1.0)["h"] < 0


def test_two_body_force_and_newton_third_law():
    model = GravityModel([2.0, 3.0], G=1.5)
    pos = np.array([[0.0, 0.0], [2.0, 0.0]])
    a = model.acceleration(pos)
    assert a[0] == pytest.approx([1.5 * 3.0 / 4.0, 0.0])
    assert a[1] == pytest.approx([-1.5 * 2.0 / 4.0, 0.0])
    assert 2.0 * a[0] + 3.0 * a[1] == pytest.approx([0.0, 0.0], abs=1e-15)


def test_fixed_body_and_test_particle():
    model = GravityModel([1.0, 0.0, 1e-3], G=1.0, fixed=[True, False, False])
    pos = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    a = model.acceleration(pos)
    assert np.all(a[0] == 0.0)  # fixed
    # The test particle (index 1) exerts nothing: body 2 feels only bodies 0 (and 1 with m=0).
    expected = GravityModel([1.0, 1e-3], G=1.0, fixed=[True, False]).acceleration(pos[[0, 2]])[1]
    assert a[2] == pytest.approx(expected, rel=1e-14)


def test_batch_matches_single():
    rng = np.random.default_rng(1)
    model = GravityModel(rng.uniform(0.1, 1, 5), G=4.0, radii=rng.uniform(0, 0.05, 5))
    pos = rng.normal(size=(7, 5, 2))
    batch = model.acceleration_batch(pos)
    for k in range(7):
        assert batch[k] == pytest.approx(model.acceleration(pos[k]), rel=1e-13)


def test_overlap_force_continuous_symmetric_and_conservative():
    model = GravityModel([1.0, 0.5], G=1.0, radii=[0.2, 0.1])  # s = 0.2
    def acc(r):
        return model.acceleration(np.array([[0.0, 0.0], [r, 0.0]]))
    # Continuity at r = s
    assert acc(0.2 - 1e-12)[0] == pytest.approx(acc(0.2 + 1e-12)[0], rel=1e-9)
    # Inside: linear in r (homogeneous sphere)
    assert acc(0.05)[0][0] == pytest.approx(0.5 * 0.05 / 0.2**3, rel=1e-12)
    # Momentum conserved inside
    a = acc(0.07)
    assert 1.0 * a[0] + 0.5 * a[1] == pytest.approx([0.0, 0.0], abs=1e-14)
    # Force = -dU/dr inside and outside (finite differences)
    for r in (0.05, 0.15, 0.5):
        h = 1e-6
        u = lambda rr: model.potential_energy(np.array([[0.0, 0.0], [rr, 0.0]]))
        force_on_1 = -(u(r + h) - u(r - h)) / (2 * h)
        assert 0.5 * acc(r)[1][0] == pytest.approx(force_on_1, rel=1e-7)


def test_potential_of_point_masses():
    model = GravityModel([1.0, 2.0, 3.0], G=2.0)
    pos = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    expected = -2.0 * (1 * 2 / 1.0 + 1 * 3 / 2.0 + 2 * 3 / math.sqrt(5))
    assert model.potential_energy(pos) == pytest.approx(expected, rel=1e-14)
    assert model.potential_energy(pos[None])[0] == pytest.approx(expected, rel=1e-14)


def test_recommended_dt_resolves_period_and_periapsis():
    mu = units.G * 1.001
    for e in (0.0, 0.5, 0.9):
        v = kepler.orbital_velocity([1.0, 0.0], mu, e)
        dt = kepler.recommended_dt([[0, 0], [1, 0]], [[0, 0], v], [1.0, 1e-3], units.G)
        P = kepler.period(1.0 / (1 - e), mu)
        assert dt <= P / 200 * (1 + 1e-12)
    # Radial infall from rest: finite step.
    assert kepler.recommended_dt([[0, 0], [1, 0]], [[0, 0], [0, 0]], [1.0, 1e-3], units.G) > 0
