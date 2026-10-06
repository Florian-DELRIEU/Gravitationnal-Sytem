"""Observer, spectral calibration, and T9 (single planet recovered from the star's motion)."""

import numpy as np
import pytest

from gravsim.analysis import observer, spectral
from gravsim.core import kepler, units
from gravsim.core.scenario import load_preset
from gravsim.core.simulation import Simulation


@pytest.fixture(scope="module")
def jupiter_traj():
    sim = Simulation(load_preset("soleil_jupiter"), "yoshida4", output_dt=0.02)
    sim.run(120.0)
    return sim.trajectory


P_JUP = kepler.period(5.2, units.G * (1 + units.M_JUP))
K_JUP = observer.expected_rv_semi_amplitude(P_JUP, units.M_JUP, 1.0)


# --- calibration on synthetic signals -----------------------------------------------
def test_gls_recovers_sinusoid_irregular():
    rng = np.random.default_rng(0)
    t = np.sort(rng.uniform(0, 50, 300))
    y = 3.0 * np.sin(2 * np.pi * 0.37 * t + 1.0) + 5.0
    peak = spectral.gls(t, y, f_max=2.0).peaks(1)[0]
    assert peak.frequency == pytest.approx(0.37, abs=1 / 50 / 10)
    assert peak.amplitude == pytest.approx(3.0, rel=1e-3)
    assert peak.power == pytest.approx(1.0, abs=1e-6)


def test_fft_amplitude_calibrated_real_and_complex():
    t = np.arange(4000) * 0.01
    y = 2.0 * np.cos(2 * np.pi * 3.3 * t)
    peak = spectral.fft_spectrum(t, y).peaks(1)[0]
    assert peak.frequency == pytest.approx(3.3, abs=0.01) and peak.amplitude == pytest.approx(2.0, rel=0.01)
    z = 0.5 * np.exp(-2j * np.pi * 1.7 * t)  # clockwise
    peak = spectral.fft_spectrum(t, z).peaks(1)[0]
    assert peak.frequency == pytest.approx(-1.7, abs=0.01) and peak.amplitude == pytest.approx(0.5, rel=0.01)


def test_complex_periodogram_matches_direction():
    rng = np.random.default_rng(1)
    t = np.sort(rng.uniform(0, 30, 400))
    z = 0.8 * np.exp(2j * np.pi * 0.5 * t) + 0.2 * np.exp(-2j * np.pi * 1.25 * t)
    peaks = spectral.complex_periodogram(t, z, f_max=3.0).peaks(2)
    assert peaks[0].frequency == pytest.approx(0.5, abs=0.005) and peaks[0].amplitude == pytest.approx(0.8, rel=0.02)
    assert peaks[1].frequency == pytest.approx(-1.25, abs=0.005) and peaks[1].amplitude == pytest.approx(0.2, rel=0.1)


def test_false_alarm_probability_monotonic():
    faps = [spectral.false_alarm_probability(p, 200, 10.0, 20.0) for p in (0.05, 0.1, 0.3)]
    assert faps[0] > faps[1] > faps[2] and faps[2] < 1e-6


# --- observer ----------------------------------------------------------------------------
def test_rv_amplitude_and_geometry(jupiter_traj):
    vr = observer.radial_velocity(jupiter_traj, "Soleil")
    assert np.max(np.abs(vr)) == pytest.approx(K_JUP, rel=1e-4)
    assert K_JUP == pytest.approx(12.5, rel=0.01)  # textbook value
    face_on = observer.radial_velocity(jupiter_traj, "Soleil", observer.Observer(inclination_deg=0.0))
    assert np.max(np.abs(face_on)) < 1e-12
    inclined = observer.radial_velocity(jupiter_traj, "Soleil", observer.Observer(30.0, 30.0))
    assert np.max(np.abs(inclined)) == pytest.approx(0.5 * K_JUP, rel=1e-3)


def test_interpolation_matches_direct_samples(jupiter_traj):
    sim = Simulation(load_preset("soleil_jupiter"), "yoshida4", output_dt=0.005)
    sim.run(3.0)
    fine = sim.trajectory
    times = fine.t[1:-1:7]
    coarse = jupiter_traj
    pos, vel = observer.interpolate_state(coarse, "Soleil", times)
    ref_pos, ref_vel = observer.barycentric_state(fine, "Soleil")
    k = np.searchsorted(fine.t, times)
    assert np.max(np.abs(pos - ref_pos[k])) < 1e-6 * np.max(np.abs(ref_pos))
    assert np.max(np.abs(vel - ref_vel[k])) < 1e-6 * np.max(np.abs(ref_vel))


def test_noise_level(jupiter_traj):
    times = observer.random_schedule(0, 100, 2000, rng=3, season_fraction=0.3)
    phase = times % 1.0
    assert phase.min() >= 0.3
    clean = observer.observe_rv(jupiter_traj, "Soleil", times)
    noisy = observer.observe_rv(jupiter_traj, "Soleil", times, sigma=2.0, rng=4)
    assert np.std(noisy.value - clean.value) == pytest.approx(2.0, rel=0.05)
    red = observer.red_noise(np.linspace(0, 100, 5000), 1.5, 0.5, rng=5)
    assert np.std(red) == pytest.approx(1.5, rel=0.15)


# --- T9 ------------------------------------------------------------------------------------
def test_T9_single_planet_from_rv(jupiter_traj):
    t = jupiter_traj.t
    vr = observer.radial_velocity(jupiter_traj, "Soleil")
    T = t[-1] - t[0]
    for spec in (spectral.gls(t[::5], vr[::5], f_max=1.0), spectral.fft_spectrum(t, vr)):
        peak = spec.peaks(1)[0]
        assert abs(peak.frequency - 1 / P_JUP) < 1 / T
        assert peak.amplitude == pytest.approx(K_JUP, rel=0.02)


def test_T9_single_planet_from_noisy_irregular_rv(jupiter_traj):
    times = observer.random_schedule(0, 120, 150, rng=7, season_fraction=0.3)
    obs = observer.observe_rv(jupiter_traj, "Soleil", times, sigma=3.0, rng=8)
    spec = spectral.gls(obs.t, obs.value, dy=obs.error, f_max=2.0)
    peak = spec.peaks(1)[0]
    assert abs(peak.frequency - 1 / P_JUP) < 1 / obs.baseline
    assert peak.amplitude == pytest.approx(K_JUP, rel=0.1)
    assert spectral.false_alarm_probability(peak.power, len(obs.t), 2.0, obs.baseline) < 1e-6


def test_T9_single_planet_from_astrometry(jupiter_traj):
    z = observer.astrometric_signal(jupiter_traj, "Soleil")
    peak = spectral.fft_spectrum(jupiter_traj.t, z).peaks(1)[0]
    assert peak.frequency > 0  # counterclockwise orbit
    assert abs(peak.frequency - 1 / P_JUP) < 1 / 120
    expected = observer.expected_astrometric_amplitude(5.2, units.M_JUP, 1.0)
    assert peak.amplitude == pytest.approx(expected, rel=0.02)


# --- ground truth and study script -----------------------------------------------------------
def test_reflex_signatures_match_textbook_values():
    from gravsim.analysis import orbits

    sim = Simulation(load_preset("systeme_solaire"), "dop853")
    truths = {tr.name: tr for tr in orbits.reflex_signatures(sim.trajectory, "Soleil")}
    assert list(truths) == ["Mercure", "Vénus", "Terre", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune"]
    assert truths["Jupiter"].rv_semi_amplitude == pytest.approx(12.5, rel=0.01)
    assert truths["Terre"].rv_semi_amplitude == pytest.approx(0.09, rel=0.02)
    assert truths["Terre"].period == pytest.approx(1.0, rel=0.002)
    assert all(tr.direction == 1 for tr in truths.values())


def test_study_script_runs(tmp_path):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "scripts" / "etude_spectre.py"
    spec = importlib.util.spec_from_file_location("etude_spectre", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    png = mod.study("jupiter_chaud", None, None, "yoshida4", None, 2.0, 80, 0.0, 0.0, 90.0, tmp_path, 1)
    assert png.exists() and png.stat().st_size > 10_000


def test_random_schedule_inside_unobservable_season():
    """A 25-day campaign falling entirely in the gap must fail loudly, not loop forever."""
    with pytest.raises(ValueError):
        observer.random_schedule(0.0, 0.07, 50, rng=1, season_fraction=0.3)
    times = observer.random_schedule(0.0, 0.07, 50, rng=1, season_fraction=0.3, season_phase=0.5)
    assert len(times) == 50
