"""Display options and the live readout of the selected body."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout, QWidget)

from ..core import kepler, units
from .controller import SimulationController
from .widgets import NumberEdit, ViewSettings, format_speed_si, format_time


class ViewPanel(QWidget):
    SIZE_LABELS = [("mass", "Selon la masse (compressée, bornée)"), ("manual", "Manuelle (par corps)"),
                   ("real", "Échelle réelle (rayons physiques)")]
    FRAME_LABELS = [("inertial", "Inertiel"), ("barycentric", "Barycentrique"), ("body", "Centré sur un corps"),
                    ("rotating", "Tournant avec une paire")]
    CAMERA_LABELS = [("all", "Tout voir (automatique)"), ("free", "Libre"), ("follow", "Suivre un corps")]
    FIELD_LABELS = [("none", "Aucun"), ("potential", "Potentiel gravitationnel"),
                    ("effective", "Potentiel effectif (référentiel tournant)")]

    def __init__(self, ctrl: SimulationController, view: ViewSettings, parent=None):
        super().__init__(parent)
        self.ctrl, self.view = ctrl, view
        self._loading = False

        self.size_mode = self._combo(self.SIZE_LABELS)
        self.max_px = NumberEdit(view.max_px, fmt="{:.4g}", minimum=4, maximum=120)
        self.min_px = NumberEdit(view.min_px, fmt="{:.4g}", minimum=1, maximum=30)
        self.trail = QSpinBox()
        self.trail.setRange(0, 200000)
        self.trail.setSingleStep(100)
        self.trail.setValue(view.trail_samples)
        self.frame = self._combo(self.FRAME_LABELS)
        self.frame_body = QComboBox()
        self.pair_a, self.pair_b = QComboBox(), QComboBox()
        self.camera = self._combo(self.CAMERA_LABELS)
        self.follow = QComboBox()
        self.cb_names = QCheckBox("Noms des corps")
        self.cb_bary = QCheckBox("Barycentre")
        self.cb_vel = QCheckBox("Vecteurs vitesse")
        self.cb_force = QCheckBox("Vecteurs force")
        self.cb_hill = QCheckBox("Sphères de Hill")
        for cb, attr in ((self.cb_names, "show_names"), (self.cb_bary, "show_barycenter"),
                         (self.cb_vel, "show_velocity"), (self.cb_force, "show_force"), (self.cb_hill, "show_hill")):
            cb.setChecked(getattr(view, attr))
            cb.toggled.connect(lambda flag, a=attr: self._set(a, flag))

        self.cb_lagrange = QCheckBox("Points de Lagrange (L1 à L5)")
        self.cb_lag_follow = QCheckBox("Suivre la paire du référentiel tournant")
        self.lag_a, self.lag_b = QComboBox(), QComboBox()
        self.field = self._combo(self.FIELD_LABELS)
        self.cb_contours = QCheckBox("Lignes de niveau")
        self.cb_critical = QCheckBox("Courbes critiques L1, L2, L3")
        self.cb_accessible = QCheckBox("Région accessible du corps sélectionné")
        for cb, attr in ((self.cb_lagrange, "show_lagrange"), (self.cb_lag_follow, "lagrange_follow_frame"),
                         (self.cb_contours, "field_contours"), (self.cb_critical, "field_critical"),
                         (self.cb_accessible, "field_accessible")):
            cb.setChecked(getattr(view, attr))
            cb.toggled.connect(lambda flag, a=attr: self._set(a, flag))
        self.field_note = QLabel()
        self.field_note.setWordWrap(True)

        sizes = QGroupBox("Taille des corps")
        sf = QFormLayout(sizes)
        sf.addRow("Mode", self.size_mode)
        sf.addRow("Taille max (px)", self.max_px)
        sf.addRow("Taille min (px)", self.min_px)
        self.real_hint = QLabel("En échelle réelle, un corps trop petit reste dessiné à 2,5 px minimum.")
        self.real_hint.setWordWrap(True)
        sf.addRow(self.real_hint)
        space = QGroupBox("Référentiel et cadrage")
        spf = QFormLayout(space)
        spf.addRow("Référentiel", self.frame)
        spf.addRow("Corps", self.frame_body)
        spf.addRow("Paire A", self.pair_a)
        spf.addRow("Paire B", self.pair_b)
        spf.addRow("Cadrage", self.camera)
        spf.addRow("Suivre", self.follow)
        lagr = QGroupBox("Points de Lagrange et potentiel")
        lf = QFormLayout(lagr)
        lf.addRow(self.cb_lagrange)
        lf.addRow(self.cb_lag_follow)
        lf.addRow("Primaire", self.lag_a)
        lf.addRow("Secondaire", self.lag_b)
        lf.addRow("Fond", self.field)
        lf.addRow(self.cb_contours)
        lf.addRow(self.cb_critical)
        lf.addRow(self.cb_accessible)
        lf.addRow(self.field_note)
        draw = QGroupBox("Affichage")
        df = QFormLayout(draw)
        df.addRow("Longueur des traînées (échantillons)", self.trail)
        for cb in (self.cb_names, self.cb_bary, self.cb_vel, self.cb_force, self.cb_hill):
            df.addRow(cb)
        lay = QVBoxLayout(self)
        lay.addWidget(sizes)
        lay.addWidget(space)
        lay.addWidget(lagr)
        lay.addWidget(draw)
        lay.addStretch(1)

        self.size_mode.currentIndexChanged.connect(self._on_any)
        self.max_px.valueChanged.connect(self._on_any)
        self.min_px.valueChanged.connect(self._on_any)
        self.trail.valueChanged.connect(self._on_any)
        for c in (self.frame, self.frame_body, self.pair_a, self.pair_b, self.camera, self.follow, self.lag_a,
                  self.lag_b, self.field):
            c.currentIndexChanged.connect(self._on_any)
        self.cb_lag_follow.toggled.connect(self._on_any)
        view.noteChanged.connect(self._show_note)
        ctrl.scenarioEdited.connect(self._refill_bodies)
        ctrl.scenarioReplaced.connect(self._refill_bodies)
        view.changed.connect(self._from_view)  # the viewer can switch the camera to "free"
        self._refill_bodies()

    @staticmethod
    def _combo(labels) -> QComboBox:
        c = QComboBox()
        for key, text in labels:
            c.addItem(text, key)
        return c

    def _set(self, attr: str, value) -> None:
        setattr(self.view, attr, value)
        self.view.notify()

    def _refill_bodies(self) -> None:
        names = self.ctrl.scenario.names
        self._loading = True
        for combo in (self.frame_body, self.pair_a, self.pair_b, self.follow, self.lag_a, self.lag_b):
            keep = combo.currentIndex()
            combo.clear()
            combo.addItems(names)
            combo.setCurrentIndex(min(max(keep, 0), max(len(names) - 1, 0)))
        if len(names) > 1 and self.pair_a.currentIndex() == self.pair_b.currentIndex():
            self.pair_b.setCurrentIndex(1 if self.pair_a.currentIndex() == 0 else 0)
        if len(names) > 1 and self.lag_a.currentIndex() == self.lag_b.currentIndex():
            self.lag_b.setCurrentIndex(1 if self.lag_a.currentIndex() == 0 else 0)
        self._loading = False
        self._on_any()

    def _on_any(self, *_args) -> None:
        if self._loading:
            return
        v = self.view
        v.size_mode = self.size_mode.currentData()
        v.max_px, v.min_px = self.max_px.value(), min(self.min_px.value(), self.max_px.value())
        v.trail_samples = self.trail.value()
        v.frame = self.frame.currentData()
        v.frame_body = max(self.frame_body.currentIndex(), 0)
        v.frame_pair = (max(self.pair_a.currentIndex(), 0), max(self.pair_b.currentIndex(), 0))
        v.camera = self.camera.currentData()
        v.follow_body = max(self.follow.currentIndex(), 0)
        v.lagrange_pair = (max(self.lag_a.currentIndex(), 0), max(self.lag_b.currentIndex(), 0))
        v.field = self.field.currentData()
        self._sync_enabled()
        v.notify()

    def _sync_enabled(self) -> None:
        v = self.view
        self.max_px.setEnabled(v.size_mode == "mass")
        self.min_px.setEnabled(v.size_mode == "mass")
        self.real_hint.setVisible(v.size_mode == "real")
        self.frame_body.setEnabled(v.frame == "body")
        self.pair_a.setEnabled(v.frame == "rotating")
        self.pair_b.setEnabled(v.frame == "rotating")
        self.follow.setEnabled(v.camera == "follow")
        followed = v.lagrange_follow_frame and v.frame == "rotating"
        self.lag_a.setEnabled(not followed)
        self.lag_b.setEnabled(not followed)
        self.cb_lag_follow.setEnabled(v.frame == "rotating")
        effective = v.field == "effective"
        self.cb_contours.setEnabled(v.field != "none")
        self.cb_critical.setEnabled(effective)
        self.cb_accessible.setEnabled(effective)

    def _show_note(self) -> None:
        self.field_note.setText(self.view.field_note)

    def _from_view(self) -> None:
        idx = self.camera.findData(self.view.camera)
        if idx >= 0 and idx != self.camera.currentIndex():
            self._loading = True
            self.camera.setCurrentIndex(idx)
            self._loading = False
            self._sync_enabled()


class InfoPanel(QLabel):
    """Live readout of the selected body (state at the view time, two-body elements about its main attractor)."""

    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setMinimumHeight(110)
        ctrl.changed.connect(self.update_text)
        ctrl.selectionChanged.connect(lambda _i: self.update_text())
        ctrl.reset.connect(self.update_text)
        self.update_text()

    def update_text(self) -> None:
        ctrl, sc = self.ctrl, self.ctrl.scenario
        state = ctrl.state_at_view()
        k = ctrl.selected
        if state is None or not (0 <= k < len(sc.bodies)):
            self.setText("<i>Sélectionnez un corps.</i>")
            return
        pos, vel = state
        b = sc.bodies[k]
        v = 0.0 if b.fixed else float(np.hypot(*vel[k]))
        lines = [f"<b>{b.name}</b> — t = {format_time(ctrl.view_time)}",
                 f"position ({pos[k, 0]:.5g}, {pos[k, 1]:.5g}) UA, |r| = {np.hypot(*pos[k]):.5g} UA",
                 f"vitesse {format_speed_si(v)}"]
        others = [q for q in range(len(sc.bodies)) if q != k and sc.bodies[q].mass > 0]
        if others and not b.fixed:
            d2 = [np.sum((pos[q] - pos[k]) ** 2) for q in others]
            q = others[int(np.argmax([sc.bodies[o].mass / max(x, 1e-300) for o, x in zip(others, d2)]))]
            ref = sc.bodies[q]
            mu = kepler.gravitational_parameter(sc.G, b.mass, ref.mass, ref.fixed)
            vq = np.zeros(2) if ref.fixed else vel[q]
            el = kepler.elements_from_state(pos[k] - pos[q], vel[k] - vq, mu)
            kind = str(el["kind"])
            text = f"autour de {ref.name} : distance {np.hypot(*(pos[k] - pos[q])):.5g} UA, e = {float(el['e']):.4f}"
            if kind == "elliptic":
                text += (f", a = {float(el['a']):.5g} UA, P = {format_time(float(el['period']))}")
            else:
                text += f" ({'parabolique' if kind == 'parabolic' else 'hyperbolique'}, non liée)"
            lines.append(text)
        self.setText("<br>".join(lines))
