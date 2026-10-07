"""Observation pipeline and CSV export (headless)."""

import numpy as np
import pytest

from gravsim.analysis import export, orbits, pipeline
from gravsim.analysis.pipeline import ObservationSettings, run_observation
from gravsim.core import kepler, units
from gravsim.core.events import Impulse
from gravsim.core.scenario import load_preset
from gravsim.core.simulation import Simulation

P_JUP = kepler.period(5.2, units.G * (1 + units.M_JUP))


def simulate(preset, years, **kw):
    sim = Simulation(load_preset(preset), kw.pop("integrator", "yoshida4"), **kw)
    sim.run(years)
    return sim.trajectory


@pytest.fixture(scope="module")
def jupiter():
    return simulate("soleil_jupiter", 6 * P_JUP, output_dt=0.05)


def test_suggest(jupiter):
    sug = pipeline.suggest(jupiter, "Soleil")
    assert sug["p_min"] == pytest.approx(P_JUP, rel=1e-3) == pytest.approx(sug["p_max"], rel=1e-3)
    assert sug["duration"] == pytest.approx(6 * P_JUP, rel=1e-3)
    assert sug["dt"] >= sug["spacing"]
    assert pipeline.suggest(jupiter, "Jupiter")["truths"][0].name == "Soleil"  # companions of any body


@pytest.mark.parametrize("sampling", ["regular", "irregular"])
@pytest.mark.parametrize("signal", ["rv", "astrometry"])
def test_single_planet_recovered(jupiter, sampling, signal):
    sigma = 0.0 if sampling == "regular" else (2.0 if signal == "rv" else 2e-5)
    res = run_observation(jupiter, ObservationSettings("Soleil", signal, sampling=sampling, n_obs=160,
                                                       season_fraction=0.25, sigma=sigma))
    top = res.peaks[0]
    assert abs(abs(top.frequency) - 1 / P_JUP) < 1 / res.obs.baseline
    assert res.labels[0] == "Jupiter"
    expected = res.truths[0].rv_semi_amplitude if signal == "rv" else res.truths[0].astrometric_amplitude
    assert top.amplitude == pytest.approx(expected, rel=0.15)
    if signal == "astrometry":
        assert top.frequency > 0  # counterclockwise orbit
    assert (res.fap[0] is not None) == (res.spectrum.method == "gls")


def test_geometry_changes_rv_not_astrometry(jupiter):
    edge = run_observation(jupiter, ObservationSettings("Soleil", "rv"))
    tilted = run_observation(jupiter, ObservationSettings("Soleil", "rv", inclination_deg=30.0, line_of_sight_deg=70.0))
    assert tilted.peaks[0].amplitude == pytest.approx(0.5 * edge.peaks[0].amplitude, rel=0.03)
    face = run_observation(jupiter, ObservationSettings("Soleil", "rv", inclination_deg=0.0))
    assert any("Inclinaison nulle" in n for n in face.notes)


def test_resonant_pair_flags_ambiguity():
    traj = simulate("resonance_2_1", 1.0, output_dt=0.0005)
    res = run_observation(traj, ObservationSettings("GJ 876", "rv"))
    assert any("AMBIGU" in lab for lab in res.labels)  # c's fundamental coincides with b's 2f harmonic
    assert [t.name for t in res.truths] == ["GJ 876 c", "GJ 876 b"]


def test_eccentric_planet_harmonics_labelled():
    traj = simulate("excentrique", 1.0, output_dt=0.0005)
    res = run_observation(traj, ObservationSettings("GJ 876", "rv", peak_threshold=0.03))
    labels = " | ".join(res.labels)
    assert "harmonique 2f" in labels and "harmonique 3f" in labels
    assert res.labels[0] == "Planète"


def test_notes_and_errors(jupiter):
    short = run_observation(jupiter, ObservationSettings("Soleil", "rv", t_end=2 * P_JUP))
    assert any("Durée courte" in n for n in short.notes)
    coarse = run_observation(jupiter, ObservationSettings("Soleil", "rv", dt=P_JUP / 4))
    assert any("Pas d'observation grossier" in n for n in coarse.notes)
    with pytest.raises(ValueError, match="trop courte"):
        run_observation(simulate("soleil_jupiter", 0.5, output_dt=0.1), ObservationSettings("Soleil"))
    with pytest.raises(ValueError, match="observations"):
        run_observation(jupiter, ObservationSettings("Soleil", t_end=jupiter.t[0] + 0.3, dt=0.2))
    fixed = simulate("soleil_fixe_comete", 0.5, output_dt=0.005)
    with pytest.raises(ValueError, match="fixe"):
        run_observation(fixed, ObservationSettings("Soleil"))
    with pytest.raises(KeyError):
        run_observation(jupiter, ObservationSettings("Inconnu"))
    with pytest.raises(ValueError, match="échantillonnage"):
        run_observation(jupiter, ObservationSettings("Soleil", sampling="autre"))


def test_impulse_inside_interval_is_refused_with_advice():
    sc = load_preset("soleil_jupiter")
    sc.impulses.append(Impulse("Jupiter", 0.3, 20.0))
    sim = Simulation(sc, "yoshida4", output_dt=0.05)
    sim.run(60.0)
    traj = sim.trajectory
    # The sample at t = 20 holds the state before the kick: the valid start is the next sample.
    assert pipeline.default_start(traj) == pytest.approx(20.05)
    assert pipeline.default_start(simulate("binaire", 0.5)) == 0.0  # no impulse: the very beginning
    with pytest.raises(ValueError, match="poussée"):
        run_observation(traj, ObservationSettings("Soleil", "rv"))
    res = run_observation(traj, ObservationSettings("Soleil", "rv", t_start=pipeline.default_start(traj)))
    assert res.obs.t[0] == pytest.approx(20.05)  # the very first valid instant works, no margin needed
    assert any("poussées" in n for n in res.notes)


def test_spectrogram_shapes(jupiter):
    res = run_observation(jupiter, ObservationSettings("Soleil", "rv", spectrogram_window=2 * P_JUP))
    centres, freq, amp = res.spectrogram
    assert amp.shape == (len(centres), len(freq)) and len(centres) >= 3
    peak_freq = freq[np.argmax(amp.mean(axis=0))]
    assert abs(peak_freq - 1 / P_JUP) < 0.35 / P_JUP  # coarse window: resolution ~ 1 / window
    astro = run_observation(jupiter, ObservationSettings("Soleil", "astrometry", spectrogram_window=2 * P_JUP))
    assert astro.spectrogram[1].min() < 0 < astro.spectrogram[1].max()  # two-sided


# --- export ---------------------------------------------------------------------------------
def test_export_table_columns_and_values(jupiter):
    header, data = export.analysis_table(jupiter, "barycentric")
    assert data.shape == (len(jupiter), len(header)) and header[0] == "t"
    col = {h: k for k, h in enumerate(header)}
    assert {"x_Soleil", "vy_Jupiter", "E_totale", "d_Soleil_Jupiter", "derive_energie"} <= set(header)
    assert np.allclose(data[:, col["d_Soleil_Jupiter"]], 5.2, rtol=1e-3)
    m = jupiter.masses
    assert abs(m[0] * data[0, col["x_Soleil"]] + m[1] * data[0, col["x_Jupiter"]]) < 1e-12  # barycentric frame
    assert np.nanmax(np.abs(data[:, col["derive_energie"]])) < 1e-6
    step_header, step_data = export.analysis_table(jupiter, "inertial", step=4)
    assert len(step_data) == -(-len(jupiter) // 4)


def test_export_csv_files_and_events(tmp_path):
    sc = load_preset("soleil_jupiter")
    sc.impulses.append(Impulse("Jupiter", 0.1, 1.0))
    sim = Simulation(sc, "yoshida4", output_dt=0.05)
    sim.run(3.0)
    path, events = export.export_csv(sim.trajectory, tmp_path / "analyse.csv", frame=("body", "Soleil"))
    text = path.read_text(encoding="utf-8").splitlines()
    assert text[0].startswith("# positions en UA") and "referentiel=body:Soleil" in text[0]
    assert text[1].startswith("# t,x_Soleil") and len(text) == 2 + len(sim.trajectory)
    values = np.loadtxt(path, delimiter=",")
    assert values.shape[0] == len(sim.trajectory)
    assert events is not None and "poussee" in events.read_text(encoding="utf-8")
    quiet = Simulation(load_preset("binaire"), "yoshida4")
    quiet.run(0.2)
    _, none = export.export_csv(quiet.trajectory, tmp_path / "b.csv")
    assert none is None  # no event file when there is nothing to report


def test_window_step_view():
    traj = simulate("binaire", 0.5)
    w = traj.window(2, 40, step=3)
    assert np.array_equal(w.t, traj.t[2:40:3]) and w.pos.base is not None  # a view, not a copy
    with pytest.raises(ValueError):
        traj.window(5, 5)


def test_radial_fall_is_not_reported_as_a_planet():
    from gravsim.core.body import Body
    from gravsim.core.scenario import Scenario

    sc = Scenario()
    sc.add(Body("A", 1.0, [0.0, 0.0], radius=0.01))
    sc.add(Body("B", 1e-3, [1.0, 0.0], radius=0.005))  # released from rest: a radial orbit, e = 1
    sim = Simulation(sc, "dop853")
    sim.run(0.01)
    assert orbits.reflex_signatures(sim.trajectory, "A") == []
