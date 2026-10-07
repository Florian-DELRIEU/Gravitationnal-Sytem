"""Lagrange points and potential background in the viewer (headless)."""

import itertools
import time

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gravsim.core.scenario import load_preset  # noqa: E402
from gravsim.gui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = MainWindow(load_preset("troyens"))
    w.timer.stop()
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def markers(viewer):
    return {name: np.array([lab.pos().x(), lab.pos().y()]) for name, lab in viewer.lagrange_labels.items()}


def marker_points(viewer):
    return np.array([[p.pos().x(), p.pos().y()] for p in viewer.lagrange_points.points()])


def body_points(viewer):
    return np.array([[p.pos().x(), p.pos().y()] for p in viewer.scatter.points()])


# 1 -----------------------------------------------------------------------------------
def test_every_combination_paints(window, qapp):
    view = window.view
    window.ctrl.advance_to(1.0, budget=5.0)
    for lagrange, field, contours, frame in itertools.product(
            (False, True), ("none", "potential", "effective"), (False, True), ("inertial", "rotating")):
        view.show_lagrange, view.field, view.field_contours, view.frame = lagrange, field, contours, frame
        view.frame_pair = (0, 1)
        view.field_accessible = field == "effective"
        view.notify()
        qapp.processEvents()
        assert not window.viewer.grab().isNull()
        assert window.viewer.field_image.isVisible() == (field != "none")
        assert len(marker_points(window.viewer)) == (5 if lagrange else 0)


# 2 -----------------------------------------------------------------------------------
def test_trojans_on_markers_and_fixed_in_rotating_frame(window, qapp):
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    view.frame, view.frame_pair, view.show_lagrange = "rotating", (0, 1), True
    view.notify()
    qapp.processEvents()
    pts = marker_points(viewer)
    assert len(pts) == 5
    bodies = body_points(viewer)
    assert np.hypot(*(pts[3] - bodies[2])) < 5e-3  # L4 / Troyen L4
    assert np.hypot(*(pts[4] - bodies[3])) < 5e-3  # L5 / Troyen L5
    before = pts.copy()
    ctrl.advance_to(10.0, budget=30.0)
    ctrl.scrub(10.0)
    qapp.processEvents()
    assert np.max(np.hypot(*(marker_points(viewer) - before).T)) < 1e-3
    assert not viewer.grab().isNull()


# 3 -----------------------------------------------------------------------------------
def test_effective_field_on_binary(window, qapp):
    window.ctrl.set_scenario(load_preset("binaire"))
    view, viewer = window.view, window.viewer
    view.frame, view.frame_pair, view.field = "rotating", (0, 1), "effective"
    view.field_critical = True
    view.notify()
    qapp.processEvents()
    lo, hi = viewer.field_image.levels
    assert np.isfinite([lo, hi]).all() and lo < hi
    xs, ys = viewer.field_critical["L1"].getData()
    assert xs is not None and np.isfinite(xs).sum() > 10
    # the critical L1 curve is a closed "8" around both stars: crosses the axis at L1 and encloses both stars
    assert xs[np.isfinite(xs)].min() < -0.5 and xs[np.isfinite(xs)].max() > 0.5
    assert not viewer.grab().isNull()


# 4 -----------------------------------------------------------------------------------
def test_invalid_pair_gives_message_not_crash(window, qapp):
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    ctrl.set_scenario(load_preset("soleil_fixe_comete"))
    view.show_lagrange, view.field = True, "effective"
    view.lagrange_follow_frame, view.lagrange_pair = False, (0, 0)
    view.notify()
    qapp.processEvents()
    assert not viewer.grab().isNull()
    # one massive body only: no pair at all
    only = load_preset("soleil_jupiter")
    only.body("Jupiter").mass = 0.0
    ctrl.set_scenario(only)
    view.notify()
    qapp.processEvents()
    assert len(marker_points(viewer)) == 0
    assert view.field_note
    assert not viewer.field_image.isVisible()
    assert not viewer.grab().isNull()
    # same body twice falls back to the two most massive bodies
    ctrl.set_scenario(load_preset("soleil_jupiter"))
    view.lagrange_pair = (1, 1)
    view.notify()
    assert len(marker_points(viewer)) == 5


# 5 -----------------------------------------------------------------------------------
def test_performance_and_throttling(window, qapp):
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    ctrl.set_scenario(load_preset("systeme_solaire"))
    ctrl.advance_to(1.0, budget=10.0)
    view.field, view.field_resolution, view.field_contours = "potential", 160, True
    view.notify()
    qapp.processEvents()
    t0 = time.perf_counter()
    viewer._field_key = None
    viewer.redraw()
    assert time.perf_counter() - t0 < 0.1

    calls = []
    original = viewer.field_image.setImage
    viewer.field_image.setImage = lambda *a, **k: (calls.append(1), original(*a, **k))[1]
    ctrl.playing = True
    t_start, wall0, k = ctrl.view_time, time.monotonic(), 0
    while time.monotonic() - wall0 < 1.0:  # one second of "playback" at ~40 redraws/s
        k += 1
        ctrl.view_time = t_start + 0.001 * k
        viewer.redraw()
        time.sleep(0.02)
    ctrl.playing = False
    assert k >= 20 and 1 <= len(calls) <= 8


# 6 -----------------------------------------------------------------------------------
def test_accessible_region_and_panel_note(window, qapp):
    ctrl, view, viewer = window.ctrl, window.view, window.viewer
    ctrl.select(2)
    view.frame, view.frame_pair, view.field, view.field_accessible = "rotating", (0, 1), "effective", True
    view.notify()
    qapp.processEvents()
    assert "Pointillé" in view.field_note
    view.frame = "inertial"
    view.notify()
    assert "référentiel tournant" in view.field_note
    assert not viewer.grab().isNull()
