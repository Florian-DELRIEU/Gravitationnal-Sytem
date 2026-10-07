"""GUI tests, run headless (QT_QPA_PLATFORM=offscreen): controller logic, viewer drawing, panels."""

import math

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gravsim.core import units  # noqa: E402
from gravsim.core.body import Body  # noqa: E402
from gravsim.core.events import Impulse  # noqa: E402
from gravsim.core.scenario import Scenario, load_preset  # noqa: E402
from gravsim.gui.controller import SimulationController, locate  # noqa: E402
from gravsim.gui.main_window import MainWindow  # noqa: E402
from gravsim.gui.widgets import NumberEdit, QuantityEdit, SPEED_CHOICES, format_speed, format_time  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = MainWindow(load_preset("soleil_jupiter"))
    w.timer.stop()  # ticks are driven by the tests
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def collision_scenario():
    sc = Scenario(name="chute")
    sc.add(Body("A", 1.0, [0.0, 0.0], radius=0.01))
    sc.add(Body("B", 1e-3, [1.0, 0.0], radius=0.005))
    return sc


# --- widgets and formatting ------------------------------------------------------------
def test_number_edit_parsing(qapp):
    e = NumberEdit(1.0, minimum=0.0, maximum=10.0)
    got = []
    e.valueChanged.connect(got.append)
    for text, expected in (("2,5", 2.5), ("1e-3", 1e-3), ("99", 10.0), ("-4", 0.0)):
        e.setText(text)
        e.editingFinished.emit()
        assert e.value() == pytest.approx(expected)
    e.setText("abc")
    e.editingFinished.emit()
    assert e.value() == 0.0 and e.text() == "0"  # reverted to the last valid value
    e.setValue(7.0)  # programmatic changes are silent
    assert got[-1] == 0.0 and e.value() == 7.0


def test_quantity_edit_units(qapp):
    q = QuantityEdit(SPEED_CHOICES, default=0)
    q.setInternal(1.0)  # 1 AU/yr
    q.unit.setCurrentIndex(1)  # km/s
    assert q.edit.value() == pytest.approx(4.74047, rel=1e-5)
    q.edit.setText("10")
    q.edit.editingFinished.emit()
    assert q.internal() == pytest.approx(10.0 * 1e3 / units.AU_PER_YR_IN_M_S)


def test_time_formatting():
    assert format_time(2.0) == "2 ans" and format_time(2.5 * units.DAY_YR) == "2.5 j"
    assert format_time(0.5 * units.DAY_YR) == "12 h" and format_time(0.0) == "0"
    assert format_speed(2.0) == "2 ans/s" and format_speed(units.DAY_YR).endswith("j/s")


def test_locate():
    t = np.array([0.0, 1.0, 2.0, 4.0])
    assert locate(t, 1.5) == (1, 2, 0.5)
    assert locate(t, 3.0) == (2, 3, 0.5)
    assert locate(t, 4.0) == (3, 3, 0.0) and locate(t, 99.0) == (3, 3, 0.0) and locate(t, -1.0) == (0, 1, 0.0)


# --- controller ----------------------------------------------------------------------------
def test_playback_advances_and_scrubs(qapp):
    ctrl = SimulationController(load_preset("soleil_jupiter"))
    ctrl.budget = 60.0  # deterministic: never limited by CPU time
    assert ctrl.speed == pytest.approx(ctrl.auto_speed()) and ctrl.speed > 0
    ctrl.set_speed(1.0)
    ctrl.play()
    for _ in range(20):
        ctrl.tick(0.1)
    assert ctrl.playing and ctrl.view_time == pytest.approx(2.0, abs=ctrl.output_dt * 1.01)
    assert ctrl.view_time <= ctrl.sim.t + 1e-12
    assert abs(ctrl.energy_drift()) < 1e-10

    t_live = ctrl.sim.t
    ctrl.scrub(0.5)  # replay: pauses, no new simulation
    assert not ctrl.playing and ctrl.view_time == pytest.approx(0.5) and ctrl.sim.t == t_live
    assert not ctrl.live
    ctrl.play()
    ctrl.tick(0.1)  # still replaying recorded samples
    assert ctrl.view_time == pytest.approx(0.6) and ctrl.sim.t == t_live
    ctrl.scrub(1e9)  # clamped to what is computed
    assert ctrl.view_time == pytest.approx(t_live)
    ctrl.step()
    assert ctrl.sim.t > t_live


def test_cpu_budget_limits_speed(qapp):
    ctrl = SimulationController(load_preset("systeme_solaire"))
    ctrl.budget = 0.005
    ctrl.set_speed(1e4)  # unreachable: the view must lag behind the request, not freeze the UI
    ctrl.play()
    ctrl.tick(0.05)
    assert 0 < ctrl.view_time < 1e4 * 0.05
    assert ctrl.sim.t == pytest.approx(ctrl.view_time)  # nothing computed beyond what is shown


def test_pause_on_collision(qapp):
    ctrl = SimulationController(collision_scenario())
    ctrl.budget = 60.0
    caught = []
    ctrl.collisionOccurred.connect(caught.append)
    ctrl.set_pause_on_collision(True)
    ctrl.set_speed(0.2)  # contact at t = 0.1764 yr: reached after 18 ticks of 0.05 s
    ctrl.play()
    for _ in range(40):
        ctrl.tick(0.05)
        if not ctrl.playing:
            break
    assert not ctrl.playing and len(caught) == 1
    assert ctrl.view_time == pytest.approx(ctrl.sim.t)
    assert ctrl.sim.t == pytest.approx(caught[0].t)
    ctrl.play()  # resumes through the contact without stopping again
    for _ in range(10):
        ctrl.tick(0.05)
    assert len(caught) == 1 and ctrl.sim.t > caught[0].t


def test_collision_does_not_pause_by_default(qapp):
    ctrl = SimulationController(collision_scenario())
    ctrl.budget = 60.0
    caught = []
    ctrl.collisionOccurred.connect(caught.append)
    ctrl.set_speed(0.5)
    ctrl.play()
    for _ in range(8):  # 0.2 yr: just past the first contact (0.1765 yr)
        ctrl.tick(0.05)
    assert ctrl.playing and len(caught) == 1 and ctrl.sim.t > caught[0].t
    for _ in range(52):  # no merging: the bodies oscillate through each other and touch again at every pass
        ctrl.tick(0.05)
    assert ctrl.playing and len(caught) >= 3
    times = [c.t for c in caught]
    assert times == sorted(times) and len(set(times)) == len(times)


def test_immediate_and_scheduled_impulses(qapp):
    ctrl = SimulationController(load_preset("soleil_jupiter"))
    ctrl.budget = 60.0
    ctrl.set_speed(1.0)
    ctrl.play()
    for _ in range(10):
        ctrl.tick(0.1)
    ctrl.pause()
    k = ctrl.scenario.index("Jupiter")
    v_before = np.hypot(*ctrl.sim.v[k])
    msg = ctrl.apply_impulse(Impulse("Jupiter", 0.5, 0.0), now=True)
    assert "appliquée" in msg
    assert np.hypot(*ctrl.sim.v[k]) == pytest.approx(v_before + 0.5, rel=1e-9)
    assert len(ctrl.traj.impulses) == 1 and len(ctrl.scenario.impulses) == 1
    assert abs(ctrl.energy_drift()) < 1e-9  # the injected energy is not counted as an error

    future = Impulse("Jupiter", -0.2, ctrl.sim.t + 1.0)
    assert "programmée" in ctrl.apply_impulse(future, now=False)
    ctrl.play()
    for _ in range(20):
        ctrl.tick(0.1)
    assert len(ctrl.traj.impulses) == 2
    assert abs(ctrl.energy_drift()) < 1e-9

    # Deleting an applied impulse forces a replay from the start.
    ctrl.remove_impulse(ctrl.scenario.impulses[0])
    assert ctrl.view_time == ctrl.scenario.t0 and len(ctrl.scenario.impulses) == 1

    # An instant in the past is replayed from the start.
    ctrl.play()
    ctrl.tick(0.5)
    now_t = ctrl.sim.t
    msg = ctrl.apply_impulse(Impulse("Jupiter", 0.1, now_t / 2), now=False)
    assert "réinitialisée" in msg and ctrl.sim.t == pytest.approx(ctrl.scenario.t0)


def test_remove_future_impulse_without_reset(qapp):
    ctrl = SimulationController(load_preset("soleil_jupiter"))
    imp = Impulse("Jupiter", 0.3, 5.0)
    ctrl.apply_impulse(imp, now=False)
    ctrl.advance_to(1.0, budget=1.0)
    t = ctrl.sim.t
    ctrl.remove_impulse(imp)
    assert ctrl.sim.t == t and not ctrl.scenario.impulses
    ctrl.advance_to(8.0, budget=5.0)
    assert not ctrl.traj.impulses


def test_edits_reset_and_invalid_scenarios_do_not_crash(qapp):
    ctrl = SimulationController(load_preset("soleil_jupiter"))
    ctrl.advance_to(2.0, budget=1.0)
    resets = []
    ctrl.reset.connect(lambda: resets.append(1))
    ctrl.scenario.bodies[1].mass *= 2
    ctrl.edit()
    assert resets and ctrl.view_time == ctrl.scenario.t0 and not ctrl.playing

    ctrl.scenario.bodies[1].position = ctrl.scenario.bodies[0].position.copy()  # coincident bodies
    ctrl.edit()
    assert ctrl.sim is None and "même position" in ctrl.error
    ctrl.play()
    ctrl.tick(0.1)
    ctrl.step()
    ctrl.scrub(1.0)
    assert not ctrl.playing
    assert ctrl.apply_impulse(Impulse("Jupiter", 1.0, 0.0), True) == "Aucune simulation en cours."

    ctrl.scenario.bodies.clear()
    ctrl.edit()
    assert ctrl.sim is None and "aucun corps" in ctrl.error


def test_add_duplicate_rename_remove(qapp):
    ctrl = SimulationController(load_preset("soleil_jupiter"))
    n = ctrl.add_body()
    assert n == 2 and ctrl.scenario.names == ["Soleil", "Jupiter", "Planète"]
    new = ctrl.scenario.bodies[2]
    rel = new.position - ctrl.scenario.bodies[0].position
    assert np.hypot(*rel) > 5.2 and new.speed > 0  # placed outside, on a circular orbit
    assert ctrl.duplicate_body(2) == 3 and ctrl.scenario.names[3] == "Planète 2"
    ctrl.scenario.impulses.append(Impulse("Planète", 0.1, 3.0, reference="Jupiter"))
    assert ctrl.rename_body(2, "Saturne") and ctrl.scenario.impulses[0].body == "Saturne"
    assert not ctrl.rename_body(2, "Jupiter")  # duplicate names refused
    ctrl.remove_body(1)  # removing the reference body cleans the impulse reference
    assert ctrl.scenario.impulses[0].reference is None and "Jupiter" not in ctrl.scenario.names
    while ctrl.scenario.bodies:
        ctrl.remove_body(0)
    assert ctrl.selected == -1
    assert ctrl.add_body() == 0 and ctrl.scenario.bodies[0].mass == 1.0  # empty system gets a star


def test_zero_momentum_and_fixed_body(qapp):
    ctrl = SimulationController(load_preset("soleil_fixe_comete"))
    assert not ctrl.zero_momentum()  # refused with a fixed body, reported, no crash
    ctrl = SimulationController(load_preset("systeme_solaire"))
    ctrl.scenario.bodies[0].velocity = [0.001, 0.0]
    assert ctrl.zero_momentum()
    assert np.hypot(*ctrl.scenario.barycenter()[1]) < 1e-15


def test_integrator_choices_run(qapp):
    for name in ("dop853", "yoshida4", "leapfrog"):
        ctrl = SimulationController(load_preset("binaire"))
        ctrl.settings.integrator = name
        ctrl.rebuild()
        ctrl.advance_to(0.5, budget=2.0)
        assert ctrl.sim is not None and ctrl.sim.t >= 0.5 and abs(ctrl.energy_drift()) < 1e-3
    ctrl.settings.auto_dt = False
    ctrl.settings.dt = 0.01
    ctrl.rebuild()
    assert ctrl.sim.dt == pytest.approx(0.01) and ctrl.output_dt == pytest.approx(0.01)


# --- viewer ----------------------------------------------------------------------------------
def test_viewer_modes_do_not_crash(window, qapp):
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    ctrl.scenario.impulses.clear()
    ctrl.set_scenario(load_preset("systeme_solaire"))
    ctrl.advance_to(3.0, budget=5.0)
    for frame in ("inertial", "barycentric", "body", "rotating"):
        view.frame, view.frame_body, view.frame_pair = frame, 4, (0, 4)
        for mode in ("mass", "manual", "real"):
            view.size_mode = mode
            for camera in ("all", "free", "follow"):
                view.camera, view.follow_body = camera, 3
                view.show_velocity = view.show_force = view.show_hill = True
                view.notify()
                qapp.processEvents()
    assert viewer.last_frame_label.startswith("tournant")
    sizes = viewer._sizes(1e-3)
    assert np.all(sizes >= 2.5)  # "real" mode keeps every body visible


def test_viewer_mass_sizes_ordered_and_bounded(window):
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    ctrl.set_scenario(load_preset("systeme_solaire"))
    view.size_mode = "mass"
    sizes = viewer._sizes(1e-3)
    masses = ctrl.scenario.masses
    assert sizes[0] == pytest.approx(view.max_px)  # the most massive body gets the max size
    assert sizes.min() >= 0.8 * view.min_px
    order = np.argsort(masses)
    assert np.all(np.diff(sizes[order]) >= -1e-12)  # monotonic in mass


def test_viewer_frame_places_bodies(window, qapp):
    """Centred frame: the chosen body is at the origin; rotating frame: the pair lies on the x axis."""
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    ctrl.advance_to(2.0, budget=2.0)
    view.frame, view.frame_body = "body", 1
    view.notify()
    pos = np.array([[s.pos().x(), s.pos().y()] for s in viewer.scatter.points()])
    assert np.allclose(pos[1], 0.0, atol=1e-9)
    view.frame, view.frame_pair = "rotating", (0, 1)
    view.notify()
    pos = np.array([[s.pos().x(), s.pos().y()] for s in viewer.scatter.points()])
    assert np.allclose(pos[:, 1], 0.0, atol=1e-9) and pos[0, 0] < 0 < pos[1, 0]


def test_viewer_click_selects(window):
    got = []
    window.viewer.bodyClicked.connect(got.append)
    window.viewer._on_click(None, [window.viewer.scatter.points()[1]], None)
    assert got == [1]


def test_viewer_manual_zoom_leaves_auto_camera(window):
    assert window.view.camera == "all"
    window.viewer._on_manual_range()
    assert window.view.camera == "free"


def test_viewer_empty_system(window, qapp):
    window.ctrl.scenario.bodies.clear()
    window.ctrl.edit()
    qapp.processEvents()
    window.viewer.redraw()
    assert window.ctrl.sim is None


# --- panels and window ---------------------------------------------------------------------------
def editor(window):
    return window.tabs.widget(0)


def test_velocity_fields_stay_synchronised(window):
    ed, ctrl = editor(window), window.ctrl
    ctrl.select(1)
    ed.speed_unit.setCurrentIndex(0)  # UA/an
    body = ctrl.scenario.bodies[1]
    ed.speed.setText("3")
    ed.speed.editingFinished.emit()
    ed.angle.setText("90")
    ed.angle.editingFinished.emit()
    assert body.velocity == pytest.approx([0.0, 3.0], abs=1e-12)
    assert ed.vx.value() == pytest.approx(0.0, abs=1e-12) and ed.vy.value() == pytest.approx(3.0)
    ed.vx.setText("4")
    ed.vx.editingFinished.emit()
    ed.vy.setText("3")
    ed.vy.editingFinished.emit()
    assert ed.speed.value() == pytest.approx(5.0) and ed.angle.value() == pytest.approx(math.degrees(math.atan2(3, 4)))
    ed.speed_unit.setCurrentIndex(1)  # km/s: display changes, the body does not
    assert ed.speed.value() == pytest.approx(5.0 * units.AU_PER_YR_IN_M_S / 1e3)
    assert np.hypot(*body.velocity) == pytest.approx(5.0)


def test_auto_orbital_velocity_button(window):
    ed, ctrl = editor(window), window.ctrl
    ctrl.select(1)
    sc = ctrl.scenario
    sc.bodies[1].velocity = [0.0, 0.0]
    ed.ref.setCurrentText("Soleil")
    ed.ecc.setText("0")
    ed.ecc.editingFinished.emit()
    ed._apply_orbital()
    v = sc.bodies[1].velocity - sc.bodies[0].velocity
    assert np.hypot(*v) == pytest.approx(math.sqrt(units.G * (1 + units.M_JUP) / 5.2), rel=1e-9)
    assert sc.bodies[1].position @ v == pytest.approx(0.0, abs=1e-9)  # perpendicular to the radius
    ed.sense.setCurrentIndex(1)  # clockwise
    ed._apply_orbital()
    r = sc.bodies[1].position - sc.bodies[0].position
    assert (r[0] * (sc.bodies[1].velocity - sc.bodies[0].velocity)[1]
            - r[1] * (sc.bodies[1].velocity - sc.bodies[0].velocity)[0]) < 0
    ed._apply_escape()
    v = sc.bodies[1].velocity - sc.bodies[0].velocity
    assert np.hypot(*v) == pytest.approx(math.sqrt(2 * units.G * (1 + units.M_JUP) / 5.2), rel=1e-9)
    assert "libération" in ed.circ_label.text()


def test_fixed_checkbox_disables_velocity(window):
    ed, ctrl = editor(window), window.ctrl
    ctrl.select(0)
    ed.fixed.setChecked(True)
    assert ctrl.scenario.bodies[0].fixed and not ed.vel_box.isEnabled() and not ed.orbit_box.isEnabled()
    ed.fixed.setChecked(False)
    assert ed.vel_box.isEnabled()


def test_impulse_panel_roundtrip(window, qapp):
    panel = window.tabs.widget(1)
    ctrl = window.ctrl
    panel.body.setCurrentText("Jupiter")
    panel.dv.setInternal(0.25)
    panel.time.setValue(2.5)
    panel._apply(False)
    assert len(ctrl.scenario.impulses) == 1 and panel.items.count() == 1
    imp = ctrl.scenario.impulses[0]
    assert imp.body == "Jupiter" and imp.dv == pytest.approx(0.25) and imp.t == 2.5 and imp.direction == "prograde"
    panel.direction.setCurrentIndex(2)  # absolute angle
    panel.angle.setValue(45.0)
    panel.time.setValue(4.0)
    panel._apply(False)
    assert ctrl.scenario.impulses[1].direction == "angle" and ctrl.scenario.impulses[1].reference is None
    panel.items.setCurrentRow(0)
    panel._delete()
    assert len(ctrl.scenario.impulses) == 1 and panel.items.count() == 1


def test_main_window_runs_and_exports(window, qapp, tmp_path):
    ctrl = window.ctrl
    window.timer.start()
    ctrl.play()
    for _ in range(15):
        window._on_timer()
        qapp.processEvents()
    window.timer.stop()
    assert ctrl.sim.t > 0 and "ΔE/E" in window.status_fidelity.text()
    assert "t =" in window.controls.time_label.text()

    window.load_preset("terre_lune")
    assert ctrl.scenario.names == ["Terre", "Lune"] and window.windowTitle().endswith("Terre – Lune")
    ctrl.advance_to(0.01, budget=2.0)
    path = tmp_path / "t.npz"
    window.ctrl.traj.save_npz(path)
    scen = tmp_path / "s.json"
    ctrl.scenario.save(scen)
    assert path.stat().st_size > 0 and Scenario.load(scen).names == ["Terre", "Lune"]

    window.ctrl.set_pause_on_collision(True)
    window.controls.update_state()
    assert window.controls.collision.isChecked()


def test_info_panel_reports_radial_fall_as_bound(window, qapp):
    ctrl = window.ctrl
    ctrl.set_scenario(collision_scenario())
    ctrl.select(1)
    window.info.update_text()
    text = window.info.text()
    assert "e = 1.0000" in text and "P =" in text and "non liée" not in text


def test_collision_banner_and_journal(window, qapp):
    ctrl = window.ctrl
    ctrl.budget = 60.0
    ctrl.set_scenario(collision_scenario())
    ctrl.set_pause_on_collision(True)
    ctrl.set_speed(0.3)
    ctrl.play()
    for _ in range(60):
        ctrl.tick(0.05)
        qapp.processEvents()
        if not ctrl.playing:
            break
    assert window.banner_row.isVisible() and window.banner.isVisible()  # the text itself, not only the OK button
    assert "Collision" in window.banner.text() and window.banner.width() > 100
    assert "COLLISION" in window.journal.toPlainText()
    ctrl.rebuild()
    assert not window.banner_row.isVisible()


def test_screenshot_of_collision_ring(window, qapp, tmp_path):
    """Overlapping bodies get a highlight ring; the window renders to an image."""
    ctrl = window.ctrl
    ctrl.set_scenario(collision_scenario())
    ctrl.advance_to(0.5, budget=5.0)
    window.view.size_mode = "real"
    window.view.notify()
    ctrl.advance_to(2.0, budget=5.0)
    img = window.grab()
    assert not img.isNull() and img.width() > 800


def test_autotest_mode(qapp, capsys):
    """The self-check used on built executables passes in the development environment."""
    from gravsim.gui.main_window import _autotest

    w = MainWindow(load_preset("soleil_jupiter"))
    w.timer.stop()
    assert _autotest(qapp, w) == 0
    assert "AUTOTEST OK" in capsys.readouterr().out
    w.close()
