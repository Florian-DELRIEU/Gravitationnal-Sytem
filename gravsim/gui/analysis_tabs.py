"""The "Analyse" page: distances, velocities, positions, energy and conservation, orbital elements."""

from __future__ import annotations

from itertools import combinations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..analysis import diagnostics, frames, orbits
from ..core import units
from ..core.trajectory import Trajectory
from .controller import SimulationController
from .plots import Curve, CheckList, SeriesPlot, body_colors
from .viewer import frame_spec
from .widgets import PALETTE, SPEED_CHOICES, ViewSettings, format_time

MAX_FRAME_SAMPLES = 300_000  # frame-dependent plots use the most recent samples only
MAX_STRIDE_SAMPLES = 200_000  # whole-run quantities (energy, drifts) are strided down to this many samples


class Context:
    """Data prepared once per refresh and shared by the tabs (computed lazily, cached)."""

    def __init__(self, ctrl: SimulationController, view: ViewSettings):
        self.ctrl, self.view = ctrl, view
        self.traj: Trajectory = ctrl.traj
        self.scenario = ctrl.scenario
        self.colors = body_colors(ctrl.scenario)
        self._window = self._frame = self._strided = None

    @property
    def window(self) -> Trajectory:
        if self._window is None:
            n = len(self.traj)
            self._window = self.traj.window(max(0, n - MAX_FRAME_SAMPLES), n)
        return self._window

    @property
    def truncated(self) -> bool:
        return len(self.window) < len(self.traj)

    @property
    def frame(self) -> frames.FrameView:
        if self._frame is None:
            spec = frame_spec(self.view, self.scenario)
            fv = frames.view(self.window, spec)
            if not np.all(np.isfinite(fv.pos)):
                fv = frames.view(self.window, "inertial")
            self._frame = fv
        return self._frame

    @property
    def strided(self) -> Trajectory:
        if self._strided is None:
            n = len(self.traj)
            self._strided = self.traj.window(0, n, step=max(1, -(-n // MAX_STRIDE_SAMPLES)))
        return self._strided

    def markers(self) -> tuple[list[float], list[float]]:
        # Up to the simulation's current time, which can lie just beyond the last stored sample.
        t0 = self.window.t[0]
        t1 = max(self.window.t[-1], self.ctrl.sim.t if self.ctrl.sim else self.window.t[-1])
        collisions = [e.t for e in self.traj.collisions if t0 <= e.t <= t1]
        impulses = [e.t for e in self.traj.impulses if t0 <= e.t <= t1]
        return collisions, impulses


def fill_table(table: QTableWidget, headers: list[str], rows: list[list[str]]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(True)


def make_table() -> QTableWidget:
    t = QTableWidget(0, 1)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setMaximumHeight(150)
    return t


class _Tab(QWidget):
    """Base class: ``refill`` rebuilds selectors when the bodies change; ``update_data`` redraws."""

    def refill(self, scenario) -> None:  # noqa: D401
        pass

    def update_data(self, ctx: Context) -> None:
        raise NotImplementedError


def _side_by_side(left: QWidget, right: QWidget) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.addWidget(left)
    lay.addWidget(right, 1)
    return lay


class DistanceTab(_Tab):
    def __init__(self):
        super().__init__()
        self.pairs = CheckList()
        self.plot = SeriesPlot("distance (UA)")
        self.table = make_table()
        self._pairs: list[tuple[int, int]] = []
        right = QVBoxLayout()
        right.addWidget(self.plot, 3)
        right.addWidget(self.table, 1)
        box = QWidget()
        box.setLayout(right)
        self.setLayout(_side_by_side(self.pairs, box))
        self.pairs.itemChanged.connect(lambda _i: self.update_data_again())
        self._ctx = None

    def refill(self, scenario) -> None:
        names = scenario.names
        self._pairs = list(combinations(range(len(names)), 2))
        labels = [f"{names[i]} – {names[j]}" for i, j in self._pairs]
        colors = [PALETTE[k % len(PALETTE)] for k in range(len(labels))]
        self.pairs.fill(labels, colors, lambda k: k < 3)

    def update_data_again(self):
        if self._ctx is not None:
            self.update_data(self._ctx)

    def update_data(self, ctx: Context) -> None:
        self._ctx = ctx
        win, names = ctx.window, ctx.scenario.names
        curves, rows = [], []
        for k in self.pairs.checked():
            i, j = self._pairs[k]
            d = np.hypot(*(win.pos[:, j] - win.pos[:, i]).T)
            label = f"{names[i]} – {names[j]}"
            curves.append(Curve(label, d, PALETTE[k % len(PALETTE)]))
            kmin, kmax = int(np.argmin(d)), int(np.argmax(d))
            rows.append([label, f"{d[kmin]:.6g} (t = {format_time(win.t[kmin])})",
                         f"{d[kmax]:.6g} (t = {format_time(win.t[kmax])})", f"{d[-1]:.6g}"])
        collisions, impulses = ctx.markers()
        self.plot.set_curves(win.t, curves, collisions, impulses)
        fill_table(self.table, ["Paire", "Distance min (UA)", "Distance max (UA)", "Actuelle (UA)"], rows)


class VelocityTab(_Tab):
    MODES = ["Norme", "Composante vx", "Composante vy", "Vitesse relative à un corps"]

    def __init__(self):
        super().__init__()
        self.bodies = CheckList()
        self.mode = QComboBox()
        self.mode.addItems(self.MODES)
        self.ref = QComboBox()
        self.unit = QComboBox()
        self.unit.addItems([n for n, _ in SPEED_CHOICES[:2]])
        self.unit.setCurrentIndex(1)
        self.plot = SeriesPlot("vitesse")
        form = QFormLayout()
        form.addRow("Grandeur", self.mode)
        form.addRow("Corps de référence", self.ref)
        form.addRow("Unité", self.unit)
        top = QWidget()
        top.setLayout(form)
        right = QVBoxLayout()
        right.addWidget(top)
        right.addWidget(self.plot, 1)
        box = QWidget()
        box.setLayout(right)
        self.setLayout(_side_by_side(self.bodies, box))
        for w in (self.mode, self.ref, self.unit):
            w.currentIndexChanged.connect(lambda _i: self._again())
        self.bodies.itemChanged.connect(lambda _i: self._again())
        self._ctx = None

    def _again(self):
        if self._ctx is not None:
            self.update_data(self._ctx)

    def refill(self, scenario) -> None:
        self.bodies.fill(scenario.names, body_colors(scenario), lambda k: True)
        keep = self.ref.currentText()
        self.ref.blockSignals(True)
        self.ref.clear()
        self.ref.addItems(scenario.names)
        if keep in scenario.names:
            self.ref.setCurrentText(keep)
        self.ref.blockSignals(False)

    def update_data(self, ctx: Context) -> None:
        self._ctx = ctx
        win, fv, names = ctx.window, ctx.frame, ctx.scenario.names
        factor = SPEED_CHOICES[self.unit.currentIndex()][1]
        mode = self.mode.currentIndex()
        self.ref.setEnabled(mode == 3)
        ref = max(self.ref.currentIndex(), 0)
        unit_name = self.unit.currentText()
        curves = []
        for k in self.bodies.checked():
            if mode == 3:
                if k == ref:
                    continue
                v = np.hypot(*(win.vel[:, k] - win.vel[:, ref]).T)
                label = f"{names[k]} / {names[ref]}"
            else:
                vel = fv.vel[:, k]
                v = np.hypot(*vel.T) if mode == 0 else vel[:, mode - 1]
                label = names[k]
            curves.append(Curve(label, v / factor, ctx.colors[k]))
        title = ["|v|", "vx", "vy", "|v relative|"][mode]
        self.plot.getPlotItem().setLabel("left", f"{title} ({unit_name})")
        self.plot.getPlotItem().setTitle(f"référentiel : {fv.label}", size="9pt")
        collisions, impulses = ctx.markers()
        self.plot.set_curves(win.t, curves, collisions, impulses)


class PositionTab(_Tab):
    MODES = ["x(t)", "y(t)", "distance à l'origine du référentiel", "trajectoire x – y"]

    def __init__(self):
        super().__init__()
        self.bodies = CheckList()
        self.mode = QComboBox()
        self.mode.addItems(self.MODES)
        self.plot = SeriesPlot("UA")
        form = QFormLayout()
        form.addRow("Grandeur", self.mode)
        top = QWidget()
        top.setLayout(form)
        right = QVBoxLayout()
        right.addWidget(top)
        right.addWidget(self.plot, 1)
        box = QWidget()
        box.setLayout(right)
        self.setLayout(_side_by_side(self.bodies, box))
        self.mode.currentIndexChanged.connect(lambda _i: self._again())
        self.bodies.itemChanged.connect(lambda _i: self._again())
        self._ctx = None

    def _again(self):
        if self._ctx is not None:
            self.update_data(self._ctx)

    def refill(self, scenario) -> None:
        self.bodies.fill(scenario.names, body_colors(scenario), lambda k: True)

    def update_data(self, ctx: Context) -> None:
        self._ctx = ctx
        win, fv, names = ctx.window, ctx.frame, ctx.scenario.names
        mode = self.mode.currentIndex()
        pi = self.plot.getPlotItem()
        pi.setTitle(f"référentiel : {fv.label}", size="9pt")
        selected = self.bodies.checked()
        if mode == 3:
            self.plot.setAspectLocked(True)
            pi.setLabel("bottom", "x (UA)")
            pi.setLabel("left", "y (UA)")
            self.plot.set_xy([(names[k], ctx.colors[k], fv.pos[:, k, 0], fv.pos[:, k, 1]) for k in selected])
            return
        self.plot.setAspectLocked(False)
        pi.setLabel("bottom", "t (ans)")
        pi.setLabel("left", ["x (UA)", "y (UA)", "distance (UA)"][mode])
        curves = []
        for k in selected:
            p = fv.pos[:, k]
            y = p[:, mode] if mode < 2 else np.hypot(*p.T)
            curves.append(Curve(names[k], y, ctx.colors[k]))
        collisions, impulses = ctx.markers()
        self.plot.set_curves(win.t, curves, collisions, impulses)


class EnergyTab(_Tab):
    def __init__(self):
        super().__init__()
        self.energy = SeriesPlot("énergie (M☉ UA²/an²)", title="Énergies")
        self.drift = SeriesPlot("dérive relative |Δ|", title="Jauge de fidélité (dérive relative, hors poussées)",
                                log_y=True)
        self.drift.setXLink(self.energy)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        self.notes.setTextFormat(Qt.TextFormat.RichText)
        lay = QVBoxLayout(self)
        lay.addWidget(self.energy, 1)
        lay.addWidget(self.drift, 1)
        lay.addWidget(self.notes)

    def update_data(self, ctx: Context) -> None:
        tr = ctx.strided
        kin, pot = diagnostics.kinetic_energy(tr), diagnostics.potential_energy(tr)
        collisions, impulses = [e.t for e in ctx.traj.collisions], [e.t for e in ctx.traj.impulses]
        self.energy.set_curves(tr.t, [Curve("cinétique", kin, "#4cc9f0"), Curve("potentielle", pot, "#ef476f"),
                                      Curve("totale", kin + pot, "#ffd166", "dash")], collisions, impulses)
        fid = diagnostics.fidelity(tr)
        floor = 1e-17
        curves = []
        for label, series, color in (("énergie", fid.energy, "#ffd166"), ("moment cinétique", fid.angular_momentum,
                                                                           "#9bdeac"),
                                     ("quantité de mouvement", fid.momentum, "#c77dff")):
            if series is not None:
                curves.append(Curve(label, np.abs(series) + floor, color))
        self.drift.set_curves(tr.t, curves, collisions, impulses)
        worst = fid.summary()
        names_fr = {"energy": "énergie", "angular_momentum": "moment cinétique", "momentum": "quantité de mouvement"}
        shown = [f"{names_fr[k]} : <b>{v:.2e}</b>" for k, v in worst.items() if v is not None]
        extra = "".join(f"<br>• {n}" for n in fid.notes)
        stride = f" (1 échantillon sur {len(ctx.traj) // len(tr)})" if len(tr) < len(ctx.traj) else ""
        self.notes.setText("Dérive maximale — " + " · ".join(shown) + stride + extra)


class OrbitTab(_Tab):
    def __init__(self):
        super().__init__()
        self.body = QComboBox()
        self.ref = QComboBox()
        self.shape = SeriesPlot("UA", title="Demi-grand axe, périastre et apoastre")
        self.ecc = SeriesPlot("excentricité", title="Excentricité")
        self.omega = SeriesPlot("ω (°)", title="Argument du périastre")
        self.ecc.setXLink(self.shape)
        self.omega.setXLink(self.shape)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        form = QFormLayout()
        form.addRow("Corps", self.body)
        form.addRow("Autour de", self.ref)
        top = QWidget()
        top.setLayout(form)
        plots = QSplitter(Qt.Orientation.Vertical)
        for w in (self.shape, self.ecc, self.omega):
            plots.addWidget(w)
        lay = QVBoxLayout(self)
        lay.addWidget(top)
        lay.addWidget(plots, 1)
        lay.addWidget(self.summary)
        self.body.currentIndexChanged.connect(lambda _i: self._again())
        self.ref.currentIndexChanged.connect(lambda _i: self._again())
        self._ctx = None

    def _again(self):
        if self._ctx is not None:
            self.update_data(self._ctx)

    def refill(self, scenario) -> None:
        for combo, extra in ((self.body, []), (self.ref, ["(le plus massif)"])):
            keep = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(extra + scenario.names)
            if keep and combo.findText(keep) >= 0:
                combo.setCurrentText(keep)
            elif combo is self.body and len(scenario.names) > 1:
                combo.setCurrentIndex(1)
            combo.blockSignals(False)

    def update_data(self, ctx: Context) -> None:
        self._ctx = ctx
        sc, win = ctx.scenario, ctx.window
        name = self.body.currentText()
        if not name or name not in sc.names or len(sc.names) < 2:
            self.summary.setText("<i>Il faut au moins deux corps.</i>")
            return
        ref_name = self.ref.currentText()
        ref = None if ref_name.startswith("(") or not ref_name else sc.index(ref_name)
        k = sc.index(name)
        if ref == k:
            self.summary.setText("<i>Le corps et sa référence doivent être différents.</i>")
            return
        if win.fixed[k]:
            self.summary.setText(f"<i>{name} est fixe : pas d'orbite.</i>")
            return
        ref_idx = orbits.default_reference(win, k) if ref is None else ref
        el = orbits.osculating_elements(win, k, ref_idx)
        inf = np.where(np.isfinite(el["apoapsis"]), el["apoapsis"], np.nan)
        collisions, impulses = ctx.markers()
        color = ctx.colors[k]
        self.shape.set_curves(win.t, [Curve("demi-grand axe a", el["a"], color),
                                      Curve("périastre", el["periapsis"], "#9bdeac", "dash"),
                                      Curve("apoastre", inf, "#ef476f", "dash")], collisions, impulses)
        self.ecc.set_curves(win.t, [Curve("e", el["e"], color)], collisions, impulses)
        self.omega.set_curves(win.t, [Curve("ω", np.degrees(np.unwrap(el["omega"])), color)], collisions, impulses)

        pa = orbits.pair_analysis(win, ref_idx, k)
        kinds, counts = np.unique(pa.kind, return_counts=True)
        kind_fr = {"elliptic": "elliptique (liée)", "parabolic": "parabolique", "hyperbolic": "hyperbolique (non liée)"}
        kind_text = ", ".join(f"{c * 100 // len(pa.kind)} % {kind_fr[kd]}" for kd, c in zip(kinds, counts))
        (t_min, d_min), (t_max, d_max) = pa.closest, pa.farthest
        period = el["period"][-1]
        measured, _ = orbits.measure_period(win, k, ref_idx)
        speed_now, escape_now = pa.relative_speed[-1], pa.escape_speed[-1]
        lines = [f"<b>{name}</b> autour de <b>{pa.names[0]}</b> — orbite : {kind_text}",
                 f"masse réduite {pa.reduced_mass:.4g} M☉ · énergie du mouvement relatif {pa.relative_energy[-1]:.4g} "
                 f"M☉ UA²/an²",
                 f"distance : min {d_min:.5g} UA (t = {format_time(t_min)}), max {d_max:.5g} UA (t = {format_time(t_max)})",
                 f"vitesse relative {speed_now:.5g} UA/an ({units.au_per_yr_to_m_s(speed_now) / 1e3:.5g} km/s) · "
                 f"vitesse de libération {escape_now:.5g} UA/an ({units.au_per_yr_to_m_s(escape_now) / 1e3:.5g} km/s)"]
        if np.isfinite(period):
            text = f"période képlérienne actuelle {format_time(float(period))}"
            if np.isfinite(measured):
                text += f" · période moyenne mesurée sur la fenêtre (angle polaire) {format_time(measured)}"
            lines.append(text)
        self.summary.setText("<br>".join(lines))


class AnalysisPage(QWidget):
    """Tabs of graphs, refreshed (throttled) while the simulation runs."""

    REFRESH_MS = 900

    def __init__(self, ctrl: SimulationController, view: ViewSettings, parent=None):
        super().__init__(parent)
        self.ctrl, self.view = ctrl, view
        self.tabs = QTabWidget()
        self.pages: list[tuple[str, _Tab]] = [("Distances", DistanceTab()), ("Vitesses", VelocityTab()),
                                              ("Positions", PositionTab()), ("Énergie et conservation", EnergyTab()),
                                              ("Éléments orbitaux", OrbitTab())]
        for title, tab in self.pages:
            self.tabs.addTab(tab, title)
        self.header = QLabel()
        self.header.setWordWrap(True)
        self.auto = QCheckBox("Actualisation automatique")
        self.auto.setChecked(True)
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(lambda: self.refresh(force=True))
        top = QHBoxLayout()
        top.addWidget(self.header, 1)
        top.addWidget(self.auto)
        top.addWidget(refresh)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.tabs, 1)

        self._dirty = set(range(len(self.pages)))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)
        ctrl.scenarioEdited.connect(self._scenario_changed)
        ctrl.scenarioReplaced.connect(self._scenario_changed)
        ctrl.reset.connect(self._mark_dirty)
        ctrl.changed.connect(self._schedule)
        view.changed.connect(self._schedule)
        ctrl.appearanceChanged.connect(self._schedule)
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        self._scenario_changed()

    def _scenario_changed(self) -> None:
        for _, tab in self.pages:
            tab.refill(self.ctrl.scenario)
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        self._dirty = set(range(len(self.pages)))
        self._schedule()

    def _schedule(self) -> None:
        self._dirty = set(range(len(self.pages)))
        if self.isVisible() and self.auto.isChecked() and not self._timer.isActive():
            self._timer.start(self.REFRESH_MS)

    def _on_timer(self) -> None:
        if self.isVisible() and self.auto.isChecked():
            self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Redraw the current tab if its data is stale (or ``force``)."""
        index = self.tabs.currentIndex()
        traj = self.ctrl.traj
        if traj is None or len(traj) < 2:
            self.header.setText("<i>Aucune trajectoire : lancez la simulation.</i>")
            return
        if not force and index not in self._dirty:
            return
        ctx = Context(self.ctrl, self.view)
        title, tab = self.pages[index]
        try:
            tab.update_data(ctx)
        except Exception as exc:  # a plotting problem must not take the window down
            self.header.setText(f"<span style='color:#ff6b6b'>Erreur d'analyse ({title}) : {exc}</span>")
            return
        self._dirty.discard(index)
        limit = (f" · analyse limitée aux {len(ctx.window):,} derniers échantillons (courbes liées au référentiel)"
                 .replace(",", " ") if ctx.truncated else "")
        self.header.setText(f"{len(traj):,} échantillons, t = {format_time(traj.t[0])} → {format_time(traj.t[-1])} · "
                            f"référentiel : {ctx.frame.label}{limit}  (réglable dans l'onglet Vue)".replace(",", " "))
