"""Analysis and spectrum pages (headless). Every state is also rendered with ``grab()``: painting is where Qt
crashes show up (a legend asked to draw a vertical line once took the interpreter down)."""

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from gravsim.analysis import orbits  # noqa: E402
from gravsim.core import kepler, units  # noqa: E402
from gravsim.core.events import Impulse  # noqa: E402
from gravsim.core.scenario import load_preset  # noqa: E402
from gravsim.gui.main_window import MainWindow  # noqa: E402
from gravsim.gui.plots import Curve, SeriesPlot, decimate_minmax  # noqa: E402

P_JUP = kepler.period(5.2, units.G * (1 + units.M_JUP))


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = MainWindow(load_preset("soleil_jupiter"))
    w.timer.stop()
    w.ctrl.budget = 60.0
    w.resize(1500, 900)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def settle(qapp):
    for _ in range(3):
        qapp.processEvents()


def run_to(window, years):
    window.ctrl.advance_to(years, budget=120.0)
    window.ctrl.go_live()


def render(window, qapp):
    settle(qapp)
    assert not window.grab().isNull()


# --- plots -----------------------------------------------------------------------------------------
def test_decimate_keeps_spikes_and_shared_axis():
    t = np.linspace(0, 100, 200_000)
    y = np.ones_like(t)
    y[123_457] = 50.0  # a one-sample periapsis spike that plain striding would miss
    z = np.sin(t)
    ts, (ys, zs) = decimate_minmax(t, [y, z], max_points=2000)
    assert len(ts) <= 2400 and ys.max() == 50.0 and len(ys) == len(zs) == len(ts)
    assert np.all(np.diff(ts) > 0) and ts[0] == t[0] and ts[-1] == t[-1]
    small_t, (small,) = decimate_minmax(t[:100], [y[:100]], max_points=2000)
    assert len(small_t) == 100 and small is not None  # short series are untouched
    nan = np.full_like(t, np.nan)
    ts2, _ = decimate_minmax(t, [nan], max_points=2000)  # all-NaN series must not crash
    assert len(ts2) > 2


def test_series_plot_markers_legend_and_paint(qapp):
    plot = SeriesPlot("distance (UA)")
    plot.resize(600, 400)
    plot.show()
    t = np.linspace(0, 10, 500)
    plot.set_curves(t, [Curve("A", np.sin(t), "#ffffff"), Curve("B", np.cos(t), "#ff0000", "dash")],
                    collisions=[2.0, 4.0], impulses=[6.0])
    settle(qapp)
    assert not plot.grab().isNull()  # painting the legend with marker entries used to crash
    assert len(plot._markers) == 3
    names = [s[1].text for s in plot.getPlotItem().legend.items]
    assert names == ["A", "B", "collision", "poussée"]


def test_flat_curve_is_not_zoomed_into_rounding_noise(qapp):
    plot = SeriesPlot("distance (UA)")
    plot.resize(500, 300)
    plot.show()
    t = np.linspace(0, 10, 300)
    noise = 5.2 + 1e-9 * np.random.default_rng(0).standard_normal(300)  # a circular orbit's distance
    plot.set_curves(t, [Curve("d", noise, "#ffffff")])
    settle(qapp)
    lo, hi = plot.getPlotItem().viewRange()[1]
    assert hi - lo >= 0.5 * SeriesPlot.MIN_RELATIVE_SPAN * 5.2  # shown as a flat line
    plot.set_curves(t, [Curve("d", 5.2 + np.sin(t), "#ffffff")])  # a real variation is not clipped
    settle(qapp)
    lo, hi = plot.getPlotItem().viewRange()[1]
    assert lo < 4.3 and hi > 6.1


# --- analysis page ------------------------------------------------------------------------------------
def test_every_analysis_tab_renders_with_events(window, qapp):
    ctrl = window.ctrl
    ctrl.scenario.impulses.append(Impulse("Jupiter", 0.4, 8.0))
    ctrl.rebuild()
    run_to(window, 30.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    for i in range(page.tabs.count()):
        page.tabs.setCurrentIndex(i)
        page.refresh(force=True)
        assert "Erreur" not in page.header.text(), page.header.text()
        render(window, qapp)


def test_distance_tab_values_and_markers(window, qapp):
    run_to(window, 25.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    page.tabs.setCurrentIndex(0)
    page.refresh(force=True)
    tab = page.pages[0][1]
    assert tab.table.rowCount() == 1 and "Soleil – Jupiter" in tab.table.item(0, 0).text()
    assert float(tab.table.item(0, 3).text()) == pytest.approx(5.2, rel=1e-3)
    window.ctrl.apply_impulse(Impulse("Jupiter", 0.3, 0.0), now=True)
    page.refresh(force=True)
    assert len(tab.plot._markers) == 1  # the impulse is marked on the graph


def test_velocity_modes_follow_the_frame(window, qapp):
    run_to(window, 25.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    page.tabs.setCurrentIndex(1)
    tab = page.pages[1][1]
    page.refresh(force=True)
    items = tab.plot.getPlotItem().listDataItems()
    v_sun_inertial = items[0].getData()[1].max()
    window.view.frame, window.view.frame_body = "body", 0  # centred on the Sun: its velocity is exactly zero
    window.view.notify()
    page.refresh(force=True)
    assert tab.plot.getPlotItem().listDataItems()[0].getData()[1].max() == pytest.approx(0.0, abs=1e-12)
    assert v_sun_inertial > 0
    tab.mode.setCurrentIndex(3)  # velocity relative to a reference body
    tab.ref.setCurrentText("Soleil")
    page.refresh(force=True)
    labels = [i.name() for i in tab.plot.getPlotItem().listDataItems()]
    assert "Jupiter / Soleil" in labels and not any(lab.startswith("Soleil /") for lab in labels)
    render(window, qapp)


def test_position_tab_xy_mode_aspect(window, qapp):
    run_to(window, 20.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    page.tabs.setCurrentIndex(2)
    tab = page.pages[2][1]
    tab.mode.setCurrentIndex(3)
    page.refresh(force=True)
    assert tab.plot.getPlotItem().getViewBox().state["aspectLocked"]
    tab.mode.setCurrentIndex(0)
    page.refresh(force=True)
    assert not tab.plot.getPlotItem().getViewBox().state["aspectLocked"]
    render(window, qapp)


def test_energy_tab_gauge_ignores_impulses(window, qapp):
    ctrl = window.ctrl
    ctrl.scenario.impulses.append(Impulse("Jupiter", 0.5, 5.0))
    ctrl.rebuild()
    run_to(window, 20.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    page.tabs.setCurrentIndex(3)
    page.refresh(force=True)
    tab = page.pages[3][1]
    text = tab.notes.text()
    assert "énergie" in text and "poussée(s) retirée(s)" in text and "energy" not in text
    drift = [i.getData()[1] for i in tab.drift.getPlotItem().listDataItems() if i.name() == "énergie"][0]
    assert 10 ** drift.max() < 1e-6  # log mode: the kick itself is not counted as an error
    render(window, qapp)


def test_orbit_tab_summary_in_french_with_kinds(window, qapp):
    ctrl = window.ctrl
    ctrl.scenario.impulses.append(Impulse("Jupiter", 1.0, 10.0))  # +4.7 km/s: 17.8 km/s, still below the 18.5 km/s escape speed
    ctrl.rebuild()
    run_to(window, 40.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    page.tabs.setCurrentIndex(4)
    page.refresh(force=True)
    summary = page.pages[4][1].summary.text()
    assert "Jupiter" in summary and "elliptic " not in summary and "elliptique (liée)" in summary
    assert "hyperbolique" not in summary
    assert "période moyenne mesurée sur la fenêtre" in summary or "période képlérienne" in summary
    render(window, qapp)


def test_orbit_tab_unbound_and_degenerate_selections(window, qapp):
    ctrl = window.ctrl
    ctrl.scenario.impulses.append(Impulse("Jupiter", 6.0, 3.0))  # 28 km/s extra: unbound
    ctrl.rebuild()
    run_to(window, 20.0)
    window.pages.setCurrentIndex(1)
    page = window.analysis
    page.tabs.setCurrentIndex(4)
    tab = page.pages[4][1]
    page.refresh(force=True)
    assert "hyperbolique" in tab.summary.text() and "non liée" in tab.summary.text()
    tab.ref.setCurrentText("Jupiter")  # a body orbiting itself
    page.refresh(force=True)
    assert "différents" in tab.summary.text()
    render(window, qapp)


def test_auto_refresh_is_throttled_and_follows_the_page(window, qapp):
    page = window.analysis
    window.pages.setCurrentIndex(0)
    calls = []
    original = page.refresh
    page.refresh = lambda force=False: calls.append(force)  # type: ignore[method-assign]
    for _ in range(50):
        window.ctrl.changed.emit()  # playback emits this at every tick
    assert calls == []  # the page is hidden: nothing is computed
    window.pages.setCurrentIndex(1)
    page._timer.stop()
    for _ in range(50):
        window.ctrl.changed.emit()
    assert page._timer.isActive()  # one pending refresh, not fifty
    page.refresh = original  # type: ignore[method-assign]


def test_docks_hidden_on_analysis_pages_and_restored(window, qapp):
    window.right_dock.hide()  # the user's own choice must come back
    window.pages.setCurrentIndex(1)
    assert window.left_dock.isHidden() and window.bottom_dock.isHidden() and window.right_dock.isHidden()
    window.pages.setCurrentIndex(0)
    assert not window.left_dock.isHidden() and window.right_dock.isHidden()
    window.right_dock.show()
    window.pages.setCurrentIndex(1)
    assert not window.right_dock.isHidden()  # the Vue panel (frames) stays on the "Analyse" page
    window.pages.setCurrentIndex(2)
    assert window.right_dock.isHidden() and window.left_dock.isHidden()
    window.pages.setCurrentIndex(0)
    assert not window.right_dock.isHidden() and not window.left_dock.isHidden()


def test_export_analysis_action(window, qapp, monkeypatch, tmp_path):
    ctrl = window.ctrl
    ctrl.scenario.impulses.append(Impulse("Jupiter", 0.2, 3.0))
    ctrl.rebuild()
    run_to(window, 8.0)
    target = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    window.view.frame = "barycentric"
    window.view.notify()
    window.export_analysis()
    assert target.exists() and "referentiel=barycentric" in target.read_text(encoding="utf-8").splitlines()[0]
    assert (tmp_path / "out_evenements.csv").exists()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    window.export_analysis()  # cancelled: nothing breaks


# --- spectrum page --------------------------------------------------------------------------------------
def test_spectrum_compute_single_planet(window, qapp):
    run_to(window, 6 * P_JUP)
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    sp.apply_suggestions(full=True)
    res = sp.compute()
    assert res is not None and res.labels[0] == "Jupiter"
    assert abs(res.peaks[0].frequency - 1 / P_JUP) < 1 / res.obs.baseline
    assert sp.peaks_table.rowCount() == len(res.peaks) and sp.truth_table.rowCount() == 1
    assert sp.peaks_table.item(0, 5).text() == "Jupiter"
    render(window, qapp)
    for freq_axis in (True, False):  # both axes, with and without the real-planet markers
        for truth in (True, False):
            sp.freq_axis.setChecked(freq_axis)
            sp.show_truth.setChecked(truth)
            render(window, qapp)


def test_spectrum_astrometry_irregular_with_spectrogram(window, qapp):
    run_to(window, 6 * P_JUP)
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    sp.signal.setCurrentIndex(1)
    sp.sampling.setCurrentIndex(1)
    sp.n_obs.setValue(200)
    sp.sigma.setValue(20.0)  # 2e-5 AU
    sp.season.setValue(0.25)
    sp.use_spectrogram.setChecked(True)
    sp.spectro_window.setValue(2 * P_JUP)
    res = sp.compute()
    assert res is not None and res.spectrogram is not None
    assert res.settings.sigma == pytest.approx(2e-5)  # the field is in 1e-6 AU
    assert res.peaks[0].frequency > 0 and not sp.los.isEnabled()
    for tab in range(3):
        sp.tabs.setCurrentIndex(tab)
        render(window, qapp)
    sp.freq_axis.setChecked(True)
    render(window, qapp)


def test_spectrum_errors_are_reported_not_raised(window, qapp):
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    assert sp.compute() is None and "trop courte" in sp.status.text()  # nothing simulated yet
    window.ctrl.set_scenario(load_preset("soleil_fixe_comete"))
    run_to(window, 0.5)
    sp.body.setCurrentText("Soleil")
    assert sp.compute() is None and "fixe" in sp.status.text()
    window.ctrl.scenario.bodies.clear()
    window.ctrl.edit()
    assert sp.compute() is None


def test_spectrum_impulse_inside_interval(window, qapp):
    ctrl = window.ctrl
    ctrl.scenario.impulses.append(Impulse("Jupiter", 0.3, 15.0))
    ctrl.rebuild()
    run_to(window, 6 * P_JUP)
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    sp._update_info()  # what the page does when shown or refreshed during playback
    first_after = sp.t_start.value()
    assert 15.0 < first_after <= 15.0 + 2 * window.ctrl.sim.output_dt  # follows the kick: starts at the next sample
    assert sp.compute() is not None
    sp.t_start.setText("0")  # the user insists on a start before the kick
    sp.t_start.editingFinished.emit()
    sp._update_info()
    assert sp.t_start.value() == 0.0  # a typed value is respected from then on
    assert sp.compute() is None and "poussée" in sp.status.text()
    sp.suggest_btn.click()  # "Valeurs conseillées" gives the automatic behaviour back
    assert sp.t_start.value() == pytest.approx(first_after)


def test_spectrum_complete_simulation_reaches_six_periods(window, qapp):
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    window.ctrl.advance_to(5.0, budget=10)
    sp._update_info()
    assert "Conseillé" in sp.info.text()
    assert sp.complete_simulation()
    assert window.ctrl.sim.t >= 6 * P_JUP - 1e-6
    assert "6 × P max" not in sp.info.text().split("Conseillé")[-1] or "Conseillé" not in sp.info.text()
    assert sp.complete_simulation()  # already done: a no-op, still successful
    assert sp.compute() is not None


def test_spectrum_resonance_flags_ambiguity_in_the_table(window, qapp):
    window.ctrl.set_scenario(load_preset("resonance_2_1"))
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    assert sp.complete_simulation()
    res = sp.compute()
    assert any("AMBIGU" in sp.peaks_table.item(r, 5).text() for r in range(sp.peaks_table.rowCount()))
    assert [t.name for t in res.truths] == ["GJ 876 c", "GJ 876 b"]
    render(window, qapp)


def test_spectrum_reset_clears_status_and_recomputes_defaults(window, qapp):
    run_to(window, 6 * P_JUP)
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    sp.compute()
    assert sp.status.text()
    window.ctrl.set_scenario(load_preset("jupiter_chaud"))
    assert sp.status.text() == ""
    p_min = orbits.reflex_signatures(window.ctrl.traj, "51 Peg")[0].period
    assert sp.dt.value() == pytest.approx(p_min / 50, rel=1e-3)  # the step follows the new system, not the old one
    assert sp.t_start.value() == 0.0
    names = [sp.body.itemText(i) for i in range(sp.body.count())]
    assert names == ["51 Peg", "51 Peg b"] and sp.body.currentText() == "51 Peg"


# --- detection sub-tab ------------------------------------------------------------------------------------
def test_detection_tab_counts_and_renders(window, qapp):
    run_to(window, 6 * P_JUP)
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    sp.sampling.setCurrentIndex(1)
    sp.n_obs.setValue(80)
    sp.sigma.setValue(3.0)
    sp.season.setValue(0.3)
    sp.tabs.setCurrentIndex(3)
    res = sp.detection.run()  # computes the observations itself when needed
    assert res is not None and res.count == 1
    assert sp.detection.planets_table.rowCount() == 1
    assert sp.detection.planets_table.item(0, 9).text() == "Jupiter"
    assert "M_Jup" in sp.detection.planets_table.item(0, 5).text()
    assert "1 planète détectée" in sp.detection.summary.text()
    assert sp.detection.steps_table.rowCount() == len(res.steps) >= 2
    render(window, qapp)


def test_detection_tab_resonance_and_errors(window, qapp):
    window.pages.setCurrentIndex(2)
    sp = window.spectrum
    window.ctrl.scenario.bodies.clear()
    window.ctrl.edit()
    assert sp.detection.run() is None and "spectre" in sp.detection.summary.text()
    window.ctrl.set_scenario(load_preset("resonance_2_1"))
    assert sp.complete_simulation()
    sp.sampling.setCurrentIndex(1)
    sp.n_obs.setValue(150)
    sp.sigma.setValue(5.0)
    sp.season.setValue(0.3)
    sp.compute()
    res = sp.detection.run()
    assert res.count == 2
    names = {sp.detection.planets_table.item(r, 9).text() for r in range(2)}
    assert names == {"GJ 876 b", "GJ 876 c"}
    assert sp.detection.others_table.rowCount() == len(res.others) > 0
    sp.tabs.setCurrentIndex(3)
    render(window, qapp)
