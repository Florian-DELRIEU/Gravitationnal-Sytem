"""2D view of the system (pyqtgraph)."""

from __future__ import annotations

import math
import time

import contourpy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, QTimer, Signal

from ..analysis import frames, potential
from ..core.forces import GravityModel
from .controller import SimulationController, locate
from .widgets import ViewSettings, default_color

BACKGROUND = "#0b0d14"
_MAX_TRAIL_POINTS = 1500
_FIELD_MIN_INTERVAL = 0.15  # s: minimum time between two recomputations of the background field while playing
_FIELD_OPACITY = 0.75
_N_CONTOURS = 10
_CRITICAL_COLORS = {"L1": "#ff5c5c", "L2": "#ffb454", "L3": "#ffd166"}


def _rotate(vec: np.ndarray, angle: float) -> np.ndarray:
    """Apply R(-angle) to vectors (..., 2): coordinates in a frame rotated by ``angle``."""
    c, s = math.cos(angle), math.sin(angle)
    return np.stack([c * vec[..., 0] + s * vec[..., 1], -s * vec[..., 0] + c * vec[..., 1]], axis=-1)


def frame_spec(view: ViewSettings, scenario):
    """Frame selected in the view settings, as a spec for ``frames.view`` (falls back to inertial if invalid)."""
    names = scenario.names
    n = len(names)
    if view.frame == "barycentric" and scenario.total_mass() > 0:
        return "barycentric"
    if view.frame == "body" and 0 <= view.frame_body < n:
        return ("body", names[view.frame_body])
    a, b = view.frame_pair
    if view.frame == "rotating" and 0 <= a < n and 0 <= b < n and a != b:
        return ("rotating", names[a], names[b])
    return "inertial"


def lagrange_pair(view: ViewSettings, scenario) -> tuple[int, int] | None:
    """Pair (primary, secondary) whose Lagrange points are shown: the rotating frame's pair if it is followed,
    else the chosen pair, else the two most massive bodies. ``None`` if fewer than two bodies have mass."""
    n = len(scenario.names)
    masses = np.array([b.mass for b in scenario.bodies], dtype=float)

    def valid(pair) -> bool:
        a, b = pair
        return 0 <= a < n and 0 <= b < n and a != b and masses[a] > 0 and masses[b] > 0

    if view.lagrange_follow_frame and view.frame == "rotating" and valid(view.frame_pair):
        return tuple(view.frame_pair)
    if valid(view.lagrange_pair):
        return tuple(view.lagrange_pair)
    heavy = np.argsort(-masses, kind="stable")[:2]
    if len(heavy) == 2 and masses[heavy[1]] > 0:
        return int(heavy[0]), int(heavy[1])
    return None


def _unrotate(vec: np.ndarray, angle: float) -> np.ndarray:
    """Apply R(+angle) to vectors (..., 2): inverse of ``_rotate``."""
    return _rotate(vec, -angle)


def _contour_lines(xs, ys, z, levels) -> tuple[np.ndarray, np.ndarray]:
    """Contour polylines of z[ix, iy] at the given levels, joined with NaN separators."""
    gen = contourpy.contour_generator(x=xs, y=ys, z=z.T)
    parts_x, parts_y = [], []
    for level in levels:
        for line in gen.lines(float(level)):
            parts_x += [line[:, 0], [np.nan]]
            parts_y += [line[:, 1], [np.nan]]
    if not parts_x:
        return np.array([]), np.array([])
    return np.concatenate(parts_x), np.concatenate(parts_y)


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

        # background field (potential map, contours) and Lagrange points
        self.field_image = pg.ImageItem()
        self.field_image.setOpacity(_FIELD_OPACITY)
        self.field_contours = pg.PlotCurveItem(pen=pg.mkPen("#ffffff55", width=1), connect="finite")
        self.field_critical = {name: pg.PlotCurveItem(pen=pg.mkPen(color, width=1.6), connect="finite")
                               for name, color in _CRITICAL_COLORS.items()}
        self.field_accessible = pg.PlotCurveItem(
            pen=pg.mkPen("#ffffff", width=1.6, style=pg.QtCore.Qt.PenStyle.DotLine), connect="finite")
        self.lagrange_points = pg.ScatterPlotItem(symbol="x", size=12, pen=pg.mkPen("#ffffff", width=1.8), brush=None)
        self.lagrange_labels = {name: pg.TextItem(name, color="#ffffff", anchor=(0, 1))
                                for name in ("L1", "L2", "L3", "L4", "L5")}
        for z, item in ((-10, self.field_image), (-5, self.field_contours), (-4, self.field_accessible),
                        (25, self.lagrange_points)):
            item.setZValue(z)
            pi.addItem(item, ignoreBounds=True)
        for item in self.field_critical.values():
            item.setZValue(-4)
            pi.addItem(item, ignoreBounds=True)
        for item in self.lagrange_labels.values():
            item.setZValue(26)
            pi.addItem(item, ignoreBounds=True)
        self.field_image.setVisible(False)
        self._field_key = None
        self._field_cmap = None
        self._field_time = 0.0
        self._field_retry = QTimer(self)
        self._field_retry.setSingleShot(True)
        self._field_retry.timeout.connect(self.redraw)

        ctrl.reset.connect(self._on_reset)
        ctrl.changed.connect(self.redraw)
        ctrl.appearanceChanged.connect(self.redraw)
        ctrl.playingChanged.connect(lambda _playing: self.redraw())
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
        self._field_key = None
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
        return frame_spec(self.view, self.ctrl.scenario)

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
        self._clear_field()
        self._clear_lagrange()

    def _clear_field(self) -> None:
        self._field_key = None
        self.field_image.setVisible(False)
        for item in (self.field_contours, self.field_accessible, *self.field_critical.values()):
            item.setData([], [])

    def _clear_lagrange(self) -> None:
        self.lagrange_points.setData([], [])
        for lab in self.lagrange_labels.values():
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
        inertial_vel = blend(win.vel)
        pair, points, notes = self._lagrange_state(inertial, inertial_vel, masses)
        extra = None
        if v.show_lagrange and points is not None:  # keep L1..L5 inside the automatic framing
            extra = _rotate(np.array(list(points.values())) - origin, angle)
        self._frame_camera(fv, pos, px_world, extra)
        # after the camera, so that the field covers the final view range
        self._draw_lagrange_and_field(inertial, inertial_vel, masses, origin, angle, pair, points, notes)

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

    def _frame_camera(self, fv, pos, px_world: float, extra=None) -> None:
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
        pts = np.concatenate([fv.pos.reshape(-1, 2), pos] + ([extra] if extra is not None else []))
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        span = np.maximum(hi - lo, 1e-12)
        if span.max() < 1e-9:
            lo, hi = lo - 1.0, hi + 1.0
        self.vb.setRange(xRange=(lo[0], hi[0]), yRange=(lo[1], hi[1]), padding=0.1)

    # --- Lagrange points and potential field ---------------------------------------
    def _lagrange_state(self, inertial, inertial_vel, masses):
        """Pair, its L1..L5 (inertial frame, or None) and the status messages collected so far."""
        v = self.view
        pair = lagrange_pair(v, self.ctrl.scenario)
        notes: list[str] = []
        if not (v.show_lagrange or v.field == "effective" or v.field_accessible):
            return pair, None, notes
        if pair is None:
            if v.show_lagrange or v.field == "effective":
                notes.append("Il faut au moins deux corps massifs pour définir des points de Lagrange.")
            return pair, None, notes
        try:
            return pair, potential.lagrange_points_inertial(inertial, inertial_vel, masses, *pair), notes
        except ValueError as exc:
            notes.append(str(exc))
            return pair, None, notes

    def _draw_lagrange_and_field(self, inertial, inertial_vel, masses, origin, angle: float, pair, points,
                                 notes) -> None:
        v = self.view
        if v.show_lagrange and points is not None:
            self._draw_lagrange(points, pair, origin, angle, inertial, inertial_vel, masses, notes)
        else:
            self._clear_lagrange()
        if v.field != "none" and (v.field == "potential" or points is not None):
            self._draw_field(inertial, inertial_vel, masses, origin, angle, pair, points, notes)
        else:
            self._clear_field()
            if v.field == "effective" and points is None and not notes:
                notes.append("Fond effectif : il faut une paire de corps massifs.")
        v.set_field_note(" ".join(notes))

    def _draw_lagrange(self, points, pair, origin, angle, inertial, inertial_vel, masses, notes) -> None:
        names = list(points)
        shown = _rotate(np.array([points[k] for k in names]) - origin, angle)
        self.lagrange_points.setData(pos=shown)
        px_world = self.vb.viewPixelSize()[0]
        if not (px_world > 0 and math.isfinite(px_world)):
            px_world = 1e-3
        for k, name in enumerate(names):
            lab = self.lagrange_labels[name]
            lab.setVisible(True)
            lab.setPos(shown[k, 0] + 8 * px_world, shown[k, 1] + 8 * px_world)
        a, b = pair
        fr = potential.pair_frame(inertial, inertial_vel, masses, a, b)
        names_ = self.ctrl.scenario.names
        d1 = float(np.hypot(*(points["L1"] - inertial[b])))
        d2 = float(np.hypot(*(points["L2"] - inertial[b])))
        text = f"Paire {names_[a]}–{names_[b]} : L1 à {d1:.4g} UA et L2 à {d2:.4g} UA de {names_[b]}."
        # instantaneous eccentricity of the pair (two-body, reduced mass)
        mu = self.ctrl.scenario.G * (masses[a] + masses[b])
        dr, dv = inertial[b] - inertial[a], inertial_vel[b] - inertial_vel[a]
        evec = ((dv @ dv) - mu / fr.separation) * dr / mu - (dr @ dv) * dv / mu
        ecc = float(np.hypot(*evec))
        if ecc > 0.05:
            text += f" Orbite excentrique (e = {ecc:.2f}) : positions approchées, exactes pour une orbite circulaire."
        notes.append(text)

    def _draw_field(self, inertial, inertial_vel, masses, origin, angle, pair, points, notes) -> None:
        v, sc = self.view, self.ctrl.scenario
        radii = np.array([b.radius for b in sc.bodies])
        (x0, x1), (y0, y1) = self.vb.viewRange()
        w, h = x1 - x0, y1 - y0
        if not (w > 0 and h > 0 and math.isfinite(w) and math.isfinite(h)):
            return
        sel = self.ctrl.selected
        want_acc = bool(v.field_accessible and v.field == "effective" and 0 <= sel < len(masses))
        key = (tuple(float(f"{q:.6g}") for q in (x0, x1, y0, y1)), self.ctrl.view_time, self._frame_spec(), v.field,
               pair, v.field_resolution, v.field_contours, v.field_critical, want_acc, sel if want_acc else -1,
               hash(inertial.tobytes()), hash(masses.tobytes()), hash(radii.tobytes()))
        if key == self._field_key and self.field_image.isVisible():
            self._field_note(v, notes, pair, want_acc)
            return
        now = time.monotonic()
        if self.ctrl.playing and self._field_key is not None and now - self._field_time < _FIELD_MIN_INTERVAL:
            if not self._field_retry.isActive():
                self._field_retry.start(int(1000 * (_FIELD_MIN_INTERVAL - (now - self._field_time))) + 5)
            self._field_note(v, notes, pair, want_acc)
            return
        self._field_retry.stop()

        n = max(16, int(v.field_resolution))
        nx, ny = (n, max(2, round(n * h / w))) if w >= h else (max(2, round(n * w / h)), n)
        xs = x0 + (np.arange(nx) + 0.5) * (w / nx)
        ys = y0 + (np.arange(ny) + 0.5) * (h / ny)
        shown = np.stack(np.meshgrid(xs, ys, indexing="ij"), axis=-1)  # (nx, ny, 2), shown[ix, iy] = (x, y)
        pts = origin + _unrotate(shown, angle)  # to the inertial frame
        G = sc.G

        crit: dict[str, float] = {}
        acc_level = None
        with np.errstate(all="ignore"):
            if v.field == "potential":
                phi = potential.gravitational_potential(pts, inertial, masses, G, radii)
                z = np.where(phi < 0, np.log10(-np.where(phi < 0, phi, -1.0)), np.nan)
                finite = z[np.isfinite(z)]
                if finite.size == 0:
                    self._clear_field()
                    notes.append("Aucun corps massif : pas de potentiel à afficher.")
                    return
                lo, hi = (float(q) for q in np.percentile(finite, (2, 98)))
                if not hi > lo:
                    hi = lo + 1.0
                cmap, raw = "magma", np.nan_to_num(z, nan=hi, posinf=hi, neginf=lo)
            else:
                frame = potential.pair_frame(inertial, inertial_vel, masses, *pair)
                phi = potential.effective_potential(pts, inertial, masses, G, frame, radii)
                crit = potential.critical_levels(inertial, masses, G, frame, points, radii)
                l4 = float(potential.effective_potential(points["L4"], inertial, masses, G, frame, radii))
                delta = l4 - crit["L1"]
                if not (delta > 0 and math.isfinite(delta)):
                    self._clear_field()
                    return
                lo, hi = crit["L1"] - 1.5 * delta, l4 + 0.1 * delta
                cmap = "viridis"
                big = 10 * delta
                raw = np.clip(np.nan_to_num(phi, nan=hi, posinf=hi + big, neginf=lo - big), lo - big, hi + big)
                if want_acc:
                    acc_level = potential.zero_velocity_level(inertial[sel], inertial_vel[sel], inertial, masses, G,
                                                              frame, radii)
        img = np.clip(raw, lo, hi)
        if cmap != self._field_cmap:
            self.field_image.setColorMap(pg.colormap.get(cmap))
            self._field_cmap = cmap
        self.field_image.setImage(img, levels=(lo, hi), autoLevels=False)
        self.field_image.setRect(QRectF(x0, y0, w, h))
        self.field_image.setVisible(True)

        if v.field_contours:
            levels = np.linspace(lo, hi, _N_CONTOURS + 2)[1:-1]
            self.field_contours.setData(*_contour_lines(xs, ys, img, levels))
        else:
            self.field_contours.setData([], [])
        for name, item in self.field_critical.items():
            if v.field == "effective" and v.field_critical and name in crit:
                item.setData(*_contour_lines(xs, ys, raw, [crit[name]]))
            else:
                item.setData([], [])
        if acc_level is not None and math.isfinite(acc_level):
            self.field_accessible.setData(*_contour_lines(xs, ys, raw, [acc_level]))
        else:
            self.field_accessible.setData([], [])
        self._field_key, self._field_time = key, time.monotonic()
        self._field_note(v, notes, pair, want_acc)

    def _field_note(self, v, notes, pair, want_acc) -> None:
        if v.field == "effective" and v.frame != "rotating":
            notes.append("Fond effectif : à regarder dans le référentiel tournant de la paire.")
        if want_acc:
            name = self.ctrl.scenario.names[self.ctrl.selected]
            notes.append(f"Pointillé : région accessible de {name} (Jacobi, exact pour une particule test et une "
                         "paire circulaire).")
