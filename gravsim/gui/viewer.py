"""2D view of the system (pyqtgraph)."""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal

from ..analysis import frames
from ..core.forces import GravityModel
from .controller import SimulationController, locate
from .widgets import ViewSettings, default_color

BACKGROUND = "#0b0d14"
_MAX_TRAIL_POINTS = 1500


def _rotate(vec: np.ndarray, angle: float) -> np.ndarray:
    """Apply R(-angle) to vectors (..., 2): coordinates in a frame rotated by ``angle``."""
    c, s = math.cos(angle), math.sin(angle)
    return np.stack([c * vec[..., 0] + s * vec[..., 1], -s * vec[..., 0] + c * vec[..., 1]], axis=-1)


class SimViewer(pg.PlotWidget):
    bodyClicked = Signal(int)

    def __init__(self, ctrl: SimulationController, view: ViewSettings, parent=None):
        super().__init__(parent, background=BACKGROUND)
        self.ctrl, self.view = ctrl, view
        self._in_redraw = False
        self._force_model: GravityModel | None = None
        self.last_frame_label = "inertiel"

        pi = self.getPlotItem()
        pi.setAspectLocked(True)
        pi.showGrid(x=True, y=True, alpha=0.15)
        pi.setMenuEnabled(False)
        pi.hideButtons()
        for side, label in (("bottom", "x (UA)"), ("left", "y (UA)")):
            axis = pi.getAxis(side)
            axis.setLabel(label)
            axis.enableAutoSIPrefix(False)
        self.vb = pi.getViewBox()
        self.vb.setRange(xRange=(-1, 1), yRange=(-1, 1), padding=0)

        self._trails: list[pg.PlotCurveItem] = []
        self._labels: list[pg.TextItem] = []
        self.hill = pg.PlotCurveItem(pen=pg.mkPen("#5c6b8a", width=1, style=pg.QtCore.Qt.PenStyle.DashLine),
                                     connect="finite")
        self.vel_item = pg.PlotCurveItem(pen=pg.mkPen("#4cc9f0", width=2), connect="pairs")
        self.force_item = pg.PlotCurveItem(pen=pg.mkPen("#ff9f43", width=2), connect="pairs")
        self.bary = pg.ScatterPlotItem(symbol="+", size=14, pen=pg.mkPen("#ffffff", width=1.5), brush=None)
        self.rings = pg.ScatterPlotItem(symbol="o", pen=pg.mkPen("#ff3b3b", width=2), brush=None, pxMode=True)
        self.scatter = pg.ScatterPlotItem(pxMode=True)
        self.scatter.sigClicked.connect(self._on_click)
        for z, item in enumerate((self.hill, self.vel_item, self.force_item, self.bary, self.scatter, self.rings)):
            item.setZValue(10 + z)
            pi.addItem(item)

        ctrl.reset.connect(self._on_reset)
        ctrl.changed.connect(self.redraw)
        ctrl.appearanceChanged.connect(self.redraw)
        view.changed.connect(self.redraw)
        self.vb.sigRangeChanged.connect(self._on_range_changed)
        self.vb.sigRangeChangedManually.connect(self._on_manual_range)
        self._on_reset()

    # --- housekeeping ------------------------------------------------------------
    def _on_reset(self) -> None:
        n = len(self.ctrl.scenario.bodies)
        pi = self.getPlotItem()
        for item in self._trails + self._labels:
            pi.removeItem(item)
        self._trails = [pg.PlotCurveItem(pen=pg.mkPen(self._color(k), width=1.2)) for k in range(n)]
        self._labels = [pg.TextItem(b.name, color=self._color(k), anchor=(0, 1)) for k, b in
                        enumerate(self.ctrl.scenario.bodies)]
        for k in range(n):
            self._trails[k].setZValue(5)
            self._labels[k].setZValue(30)
            pi.addItem(self._trails[k])
            pi.addItem(self._labels[k])
        sim = self.ctrl.sim
        self._force_model = GravityModel(sim.masses, sim.G, sim.model.radii) if sim else None
        self.view.camera = self.view.camera if self.view.camera != "free" else self.view.camera
        self.redraw()

    def _color(self, k: int) -> str:
        return self.ctrl.scenario.bodies[k].color or default_color(k)

    def _on_click(self, _plot, points, _ev) -> None:
        if len(points):
            self.bodyClicked.emit(int(points[0].index()))

    def _on_manual_range(self, *_args) -> None:
        if self.view.camera == "all":
            self.view.camera = "free"
            self.view.notify()

    def _on_range_changed(self, *_args) -> None:
        if not self._in_redraw:
            self.redraw()

    # --- sizes -----------------------------------------------------------------
    def _sizes(self, px_world: float) -> np.ndarray:
        bodies = self.ctrl.scenario.bodies
        mode, v = self.view.size_mode, self.view
        masses = np.array([b.mass for b in bodies])
        if mode == "real":
            radii = np.array([b.radius for b in bodies])
            return np.maximum(2.0 * radii / px_world, 2.5)
        if mode == "manual":
            return np.array([b.display_px if b.display_px else 10.0 for b in bodies], dtype=float)
        ref = masses.max() if masses.size and masses.max() > 0 else 1.0
        s = np.cbrt(masses / ref)
        return np.where(masses > 0, np.maximum(v.min_px, v.max_px * np.sqrt(s)), 0.8 * v.min_px)

    # --- drawing ----------------------------------------------------------------
    def _frame_spec(self):
        v, names = self.view, self.ctrl.scenario.names
        n = len(names)
        if v.frame == "barycentric" and self.ctrl.scenario.total_mass() > 0:
            return "barycentric"
        if v.frame == "body" and 0 <= v.frame_body < n:
            return ("body", names[v.frame_body])
        a, b = v.frame_pair
        if v.frame == "rotating" and 0 <= a < n and 0 <= b < n and a != b:
            return ("rotating", names[a], names[b])
        return "inertial"

    def redraw(self) -> None:
        if self._in_redraw:
            return
        self._in_redraw = True
        try:
            self._redraw()
        finally:
            self._in_redraw = False

    def _clear(self) -> None:
        for t in self._trails:
            t.setData([], [])
        for item in (self.scatter, self.rings, self.bary):
            item.setData([], [])
        for item in (self.hill, self.vel_item, self.force_item):
            item.setData([], [])
        for lab in self._labels:
            lab.setVisible(False)

    def _redraw(self) -> None:
        ctrl, v = self.ctrl, self.view
        traj = ctrl.traj
        bodies = ctrl.scenario.bodies
        n = len(bodies)
        if traj is None or len(traj) == 0 or n == 0 or len(self._trails) != n:
            self._clear()
            return

        tt = traj.t
        i, j, w = locate(tt, ctrl.view_time)
        start = max(0, i - int(v.trail_samples))
        win = traj.window(start, j + 1, events=False)
        spec = self._frame_spec()
        fv = frames.view(win, spec)
        if not np.all(np.isfinite(fv.pos)):
            spec, fv = "inertial", frames.view(win, "inertial")
        self.last_frame_label = fv.label
        li, lj = i - start, j - start
        blend = lambda arr: (1 - w) * arr[li] + w * arr[lj]  # noqa: E731
        pos = blend(fv.pos)
        inertial = blend(win.pos)
        angle = float(blend(fv.angle))
        origin = blend(fv.origin)

        px_world = self.vb.viewPixelSize()[0]
        if not (px_world > 0 and math.isfinite(px_world)):
            px_world = 1e-3

        # trails
        step = max(1, (li + 1) // _MAX_TRAIL_POINTS)
        for k in range(n):
            xs = np.append(fv.pos[: li + 1 : step, k, 0], pos[k, 0])
            ys = np.append(fv.pos[: li + 1 : step, k, 1], pos[k, 1])
            self._trails[k].setData(xs, ys)
            self._trails[k].setPen(pg.mkPen(self._color(k), width=1.2))

        # bodies
        sizes = self._sizes(px_world)
        symbols = ["s" if b.fixed else ("d" if b.mass == 0 else "o") for b in bodies]
        brushes = [pg.mkBrush(self._color(k)) for k in range(n)]
        pens = [pg.mkPen("#ffffff", width=2.5) if k == ctrl.selected else pg.mkPen("#00000080", width=1)
                for k in range(n)]
        self.scatter.setData(pos=pos, size=sizes, symbol=symbols, brush=brushes, pen=pens)

        # overlapping pairs (collisions in progress)
        radii = np.array([b.radius for b in bodies])
        ring_pos, ring_size = [], []
        for a in range(n):
            for b in range(a + 1, n):
                if radii[a] + radii[b] > 0 and np.hypot(*(inertial[a] - inertial[b])) <= radii[a] + radii[b]:
                    ring_pos += [pos[a], pos[b]]
                    ring_size += [sizes[a] + 9, sizes[b] + 9]
        self.rings.setData(pos=np.array(ring_pos).reshape(-1, 2), size=ring_size) if ring_pos else self.rings.setData([], [])

        # names
        for k, lab in enumerate(self._labels):
            lab.setVisible(v.show_names)
            lab.setText(bodies[k].name)
            lab.setPos(pos[k, 0] + 0.5 * sizes[k] * px_world, pos[k, 1] + 0.5 * sizes[k] * px_world)

        # barycentre
        masses = np.array([b.mass for b in bodies])
        if v.show_barycenter and masses.sum() > 0:
            cm = _rotate((masses @ inertial) / masses.sum() - origin, angle)
            self.bary.setData(pos=cm.reshape(1, 2))
        else:
            self.bary.setData([], [])

        # velocity and force vectors (longest one drawn ~70 px)
        self._draw_vectors(self.vel_item, v.show_velocity, pos, blend(fv.vel), px_world)
        if v.show_force and self._force_model is not None:
            force = masses[:, None] * self._force_model.acceleration(inertial)
            self._draw_vectors(self.force_item, True, pos, _rotate(force, angle), px_world)
        else:
            self.force_item.setData([], [])

        self._draw_hill(pos, inertial, masses)
        self._frame_camera(fv, pos, px_world)

    def _draw_vectors(self, item: pg.PlotCurveItem, enabled: bool, pos, vec, px_world: float) -> None:
        norms = np.hypot(vec[:, 0], vec[:, 1])
        if not enabled or not np.any(norms > 0):
            item.setData([], [])
            return
        scale = 70.0 * px_world / norms.max()
        xs, ys = [], []
        for p, u, nrm in zip(pos, vec, norms):
            if nrm <= 0:
                continue
            tip = p + u * scale
            d = (tip - p)
            length = float(np.hypot(*d))
            ang = math.atan2(d[1], d[0])
            for da in (math.radians(150), math.radians(-150)):
                head = tip + 0.25 * length * np.array([math.cos(ang + da), math.sin(ang + da)])
                xs += [tip[0], head[0]]
                ys += [tip[1], head[1]]
            xs += [p[0], tip[0]]
            ys += [p[1], tip[1]]
        item.setData(np.array(xs), np.array(ys))

    def _draw_hill(self, pos, inertial, masses) -> None:
        if not self.view.show_hill:
            self.hill.setData([], [])
            return
        theta = np.linspace(0, 2 * np.pi, 49)
        xs, ys = [], []
        for k in range(len(masses)):
            if masses[k] <= 0:
                continue
            heavier = [q for q in range(len(masses)) if q != k and masses[q] > masses[k]]
            if not heavier:
                continue
            d = np.array([np.hypot(*(inertial[k] - inertial[q])) for q in heavier])
            q = heavier[int(np.argmax(masses[heavier] / np.maximum(d, 1e-30) ** 2))]
            d_kq = np.hypot(*(inertial[k] - inertial[q]))
            r_hill = d_kq * (masses[k] / (3 * masses[q])) ** (1 / 3)
            xs += list(pos[k, 0] + r_hill * np.cos(theta)) + [np.nan]
            ys += list(pos[k, 1] + r_hill * np.sin(theta)) + [np.nan]
        self.hill.setData(np.array(xs), np.array(ys)) if xs else self.hill.setData([], [])

    def _frame_camera(self, fv, pos, px_world: float) -> None:
        v, ctrl = self.view, self.ctrl
        if v.camera == "free":
            return
        if v.camera == "follow":
            k = min(max(v.follow_body, 0), len(pos) - 1)
            (x0, x1), (y0, y1) = self.vb.viewRange()
            cx, cy = pos[k]
            hw, hh = 0.5 * (x1 - x0), 0.5 * (y1 - y0)
            self.vb.setRange(xRange=(cx - hw, cx + hw), yRange=(cy - hh, cy + hh), padding=0)
            return
        pts = np.concatenate([fv.pos.reshape(-1, 2), pos])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        span = np.maximum(hi - lo, 1e-12)
        if span.max() < 1e-9:
            lo, hi = lo - 1.0, hi + 1.0
        self.vb.setRange(xRange=(lo[0], hi[0]), yRange=(lo[1], hi[1]), padding=0.1)
