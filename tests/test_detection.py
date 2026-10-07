"""Blind planet detection: Kepler model, T10-T12, false alarms, astrometry, scoring."""

import math

import numpy as np
import pytest

from gravsim.analysis import observer, orbits
from gravsim.analysis.detection import (DetectionSettings, detect, detect_observations, match_truth, planet_mass,
                                        solve_kepler)
from gravsim.core import units
from gravsim.core.body import Body
from gravsim.core.scenario import Scenario, load_preset
from gravsim.core.simulation import Simulation


def system(planets, star=1.0):
    """Star + planets given as (P yr, mass Mjup, e, angle deg), each starting at periapsis."""
    sc = Scenario()
    sc.add(Body("star", star, radius=units.R_SUN))
    for k, (P, m_mj, e, ang) in enumerate(planets):
        a = (units.G * (star + m_mj * units.M_JUP) * P**2 / (4 * np.pi**2)) ** (1 / 3)
        r = a * (1 - e)
        sc.add(Body(f"p{k}", m_mj * units.M_JUP, [r * np.cos(np.radians(ang)), r * np.sin(np.radians(ang))]))
        sc.set_orbital_velocity(f"p{k}", "star", e=e)
    sc.zero_total_momentum()
    return sc


def observe(sc, years, star="star", sigma=0.0, n_obs=None, season=0.0, seed=1, signal="rv"):
    truths = orbits.reflex_signatures(Simulation(sc, "dop853").trajectory, star)
    p_min = truths[0].period
    sim = Simulation(sc, "dop853", output_dt=p_min / 50, rtol=1e-11, atol=1e-13)
    sim.run(years)
    traj = sim.trajectory
    times = (observer.random_schedule(0, traj.t[-1], n_obs, rng=seed, season_fraction=season) if n_obs
             else observer.regular_schedule(0, traj.t[-1], p_min / 50))
    if signal == "rv":
        obs = observer.observe_rv(traj, star, times, sigma=sigma, rng=seed + 1)
    else:
        obs = observer.observe_astrometry(traj, star, times, sigma=sigma, rng=seed + 1)
    return obs, truths, sc.body(star).mass


def run(sc, years, **kw):
    obs, truths, m_star = observe(sc, years, **kw)
    res = detect_observations(obs, star_mass=m_star)
    return res, truths, match_truth(res.planets, truths, res.baseline)


PAIR_TEXT = "OU deux planètes circulaires"
MERGE_TEXT = "OU une seule planète excentrique"


def pair_vs_eccentric(res):
    return [a for a in res.ambiguities if PAIR_TEXT in a.text or MERGE_TEXT in a.text]


# --- Kepler model -----------------------------------------------------------------------------------------
def test_solve_kepler():
    rng = np.random.default_rng(0)
    M = rng.uniform(-20, 20, 2000)
    for e in (0.0, 0.1, 0.5, 0.9, 0.95):
        E = solve_kepler(M, e)
        wrapped = np.mod(M + np.pi, 2 * np.pi) - np.pi
        assert np.max(np.abs(E - e * np.sin(E) - wrapped)) < 1e-11


@pytest.mark.parametrize("data", ["rv", "astrometry"])
@pytest.mark.parametrize("e", [0.0, 0.3, 0.8])
def test_planet_mass_inverts_the_amplitude(data, e):
    m, M, P = 0.05, 0.8, 0.7  # a massive companion: the iteration on (M + m) matters
    if data == "rv":
        k = (2 * math.pi * units.G / P) ** (1 / 3) * m / (M + m) ** (2 / 3) / math.sqrt(1 - e * e)
        amp = units.au_per_yr_to_m_s(k)
    else:
        a = (units.G * (M + m) * P**2 / (4 * math.pi**2)) ** (1 / 3)
        amp = a * m / (M + m)
    assert planet_mass(P, amp, e if data == "rv" else 0.0, M, data) == pytest.approx(m, rel=1e-10)


# --- T10: one eccentric planet, harmonics absorbed by the eccentricity ---------------------------------------
@pytest.mark.parametrize("e", [0.5, 0.2])
def test_T10_eccentric_planet_counted_once(e):
    res, truths, match = run(system([(0.5, 2.0, e, 30)]), 3.0)
    assert res.count == 1 and match.exact_count and not res.ambiguous
    p, tr = res.planets[0], truths[0]
    assert p.period == pytest.approx(tr.period, rel=1e-4)
    assert p.amplitude == pytest.approx(tr.rv_semi_amplitude, rel=1e-3)
    assert p.e == pytest.approx(e, abs=2e-3)
    assert p.mass_mjup == pytest.approx(2.0, rel=2e-3)  # m sin i with i = 90 deg: the true mass
    assert p.a == pytest.approx((units.G * (1 + 2 * units.M_JUP) * 0.25 / (4 * np.pi**2)) ** (1 / 3), rel=1e-3)


def test_T10_preset_eccentric():
    res, truths, match = run(load_preset("excentrique"), 1.0, star="GJ 876")
    assert res.count == 1 and match.exact_count
    assert res.planets[0].e == pytest.approx(0.4, abs=2e-3)
    assert res.planets[0].mass_mjup == pytest.approx(2.276, rel=3e-3)


# --- T11: three well separated planets ------------------------------------------------------------------------
THREE = [(0.1, 1.0, 0.05, 0), (0.45, 1.5, 0.1, 100), (1.6, 3.0, 0.08, 220)]


@pytest.mark.parametrize("noise", [dict(), dict(sigma=2.0, n_obs=200, season=0.3)])
def test_T11_three_planets(noise):
    res, truths, match = run(system(THREE), 6.0, **noise)
    assert res.count == 3 and match.exact_count and not res.ambiguous
    for i, j in match.matches:
        p, tr = res.planets[i], truths[j]
        assert p.period == pytest.approx(tr.period, rel=5e-3)
        assert p.amplitude == pytest.approx(tr.rv_semi_amplitude, rel=0.03)
        assert p.e == pytest.approx(tr.e, abs=0.02)


# --- T12: 2:1 pair versus one eccentric planet ----------------------------------------------------------------
ECCENTRIC = [(0.4, 2.0, 0.2, 0)]
LIGHT_PAIR = [(0.4, 2.0, 0.0, 0), (0.2, 0.3, 0.0, 70)]  # inner signal ~ 0.2 x outer: first order like e = 0.2


def test_T12_noise_free_data_tell_them_apart():
    """Second-order terms (3f, ...) break the degeneracy when the data are good enough."""
    ecc, _, m1 = run(system(ECCENTRIC), 3.0)
    pair, _, m2 = run(system(LIGHT_PAIR), 3.0)
    assert ecc.count == 1 and m1.exact_count and not pair_vs_eccentric(ecc)
    assert pair.count == 2 and m2.exact_count and not pair_vs_eccentric(pair)


@pytest.mark.parametrize("planets,true_count,sigma,n_obs", [(ECCENTRIC, 1, 15.0, 80), (LIGHT_PAIR, 2, 12.0, 50)],
                         ids=["excentrique", "couple 2:1"])
def test_T12_noisy_data_flag_the_ambiguity_in_both_cases(planets, true_count, sigma, n_obs):
    """2f clearly significant, second-order terms (3f) buried in the noise: over five noise realisations the true
    answer is always among the reported possibilities, and the ambiguity is flagged in most of them."""
    flagged = 0
    for seed in range(1, 6):
        res, _, _ = run(system(planets), 3.0, sigma=sigma, n_obs=n_obs, season=0.3, seed=seed)
        assert true_count in res.possible_counts
        if res.ambiguous:
            assert res.possible_counts == [1, 2] and "AMBIGU" in res.count_text()
            flagged += 1
    assert flagged >= 3


def test_resonant_pair_gj876_counts_two_planets():
    """Strongly interacting pair: the extra signals are classified as non-planetary, not counted."""
    res, truths, match = run(load_preset("resonance_2_1"), 3.0, star="GJ 876", sigma=5.0, n_obs=150, season=0.3)
    assert res.count == 2 and match.exact_count
    assert res.others  # interaction terms were found and set aside
    assert all("non planétaire" in o.reason for o in res.others)


# --- false alarms, astrometry, settings ---------------------------------------------------------------------------
def test_pure_noise_gives_no_planet():
    rng = np.random.default_rng(4)
    false = 0
    for _ in range(10):
        t = np.sort(rng.uniform(0, 5, 100))
        y = 3.0 * rng.standard_normal(100)
        false += detect(t, y, np.full(100, 3.0)).count
    assert false == 0


def test_astrometry_single_planet_true_mass_and_sense():
    sc = load_preset("soleil_jupiter")
    res, truths, match = run(sc, 60.0, star="Soleil", sigma=2e-4, n_obs=80, season=0.2, signal="astrometry")
    assert res.count == 1 and match.exact_count
    p = res.planets[0]
    assert p.sense == 1  # counterclockwise orbit
    assert p.amplitude == pytest.approx(truths[0].astrometric_amplitude, rel=0.05)
    assert p.mass_mjup == pytest.approx(1.0, rel=0.06)  # face-on astrometry: the true mass


def test_max_planets_setting_and_errors():
    obs, truths, m = observe(system(THREE), 6.0)
    res = detect_observations(obs, m, DetectionSettings(max_planets=2))
    assert res.count == 2 and "maximal de planètes" in res.stop_reason
    with pytest.raises(ValueError):
        detect(obs.t[:5], obs.value[:5])
    with pytest.raises(ValueError):
        detect(obs.t, obs.value, data="autre")
    no_mass = detect_observations(obs)
    assert no_mass.planets[0].mass is None and no_mass.planets[0].a is None


def test_model_reproduces_the_data():
    obs, _, m = observe(system(THREE), 6.0, sigma=2.0, n_obs=200, season=0.3)
    res = detect_observations(obs, m)
    resid = obs.value - res.model(obs.t)
    assert np.std(resid) == pytest.approx(2.0, rel=0.2)  # what is left is the noise
    assert res.rms_residual == pytest.approx(np.sqrt(np.mean(resid**2)), rel=1e-9)
    assert np.std(obs.value - res.planet_model(obs.t)) < 1.5 * np.std(resid) + abs(np.mean(obs.value))


def test_steps_record_the_cascade():
    res, _, _ = run(system(THREE), 6.0, sigma=2.0, n_obs=200, season=0.3)
    kept = [s for s in res.steps if s.decision.startswith("retenu")]
    assert len(kept) == 3 and res.steps[-1].decision.startswith("arrêt")
    assert all(len(s.freq) == len(s.spectrum) > 10 for s in res.steps)
    assert all(s.delta_bic > 10 for s in kept)


def test_match_truth():
    class P:
        def __init__(self, f):
            self.frequency = f

    truths = [P(1.0), P(2.5), P(7.0)]
    found = [P(2.52), P(1.001), P(4.0)]
    m = match_truth(found, truths, baseline=10.0)
    assert m.matches == [(1, 0), (0, 1)] and m.missed == [2] and m.spurious == [2] and not m.exact_count
