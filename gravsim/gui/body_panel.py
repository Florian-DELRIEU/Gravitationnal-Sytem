"""Panels to define bodies, orbital velocities and impulses."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from ..core import kepler, units
from ..core.events import Impulse
from ..core.scenario import Scenario
from .controller import SimulationController
from .widgets import (LENGTH_CHOICES, MASS_CHOICES, SPEED_CHOICES, ColorButton, NumberEdit, QuantityEdit,
                      default_color, format_speed_si, format_time)


def _swatch(color: str) -> QIcon:
    pix = QPixmap(14, 14)
    pix.fill(QColor(color))
    return QIcon(pix)


class BodyListPanel(QWidget):
    """List of bodies with add / duplicate / remove, plus whole-system actions."""

    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._row_changed)
        add, dup, rem = QPushButton("＋ Ajouter"), QPushButton("Dupliquer"), QPushButton("Supprimer")
        add.clicked.connect(ctrl.add_body)
        dup.clicked.connect(lambda: ctrl.selected >= 0 and ctrl.duplicate_body(ctrl.selected))
        rem.clicked.connect(lambda: ctrl.selected >= 0 and ctrl.remove_body(ctrl.selected))
        row = QHBoxLayout()
        for b in (add, dup, rem):
            row.addWidget(b)

        zero = QPushButton("Annuler la quantité de mouvement totale")
        zero.setToolTip("Retire la vitesse du barycentre : indispensable pour l'analyse spectrale\n"
                        "(sinon l'étoile dérive en plus d'osciller).")
        zero.clicked.connect(ctrl.zero_momentum)
        center = QPushButton("Centrer le système sur le barycentre")
        center.clicked.connect(ctrl.center_on_barycenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        lay.addWidget(zero)
        lay.addWidget(center)

        ctrl.scenarioEdited.connect(self.refresh)
        ctrl.scenarioReplaced.connect(self.refresh)
        ctrl.appearanceChanged.connect(self.refresh)
        ctrl.selectionChanged.connect(self._select_from_ctrl)
        self.refresh()

    def refresh(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for k, b in enumerate(self.ctrl.scenario.bodies):
            flags = " 📌" if b.fixed else ("  (test)" if b.mass == 0 else "")
            item = QListWidgetItem(_swatch(b.color or default_color(k)), f"{b.name}{flags}")
            self.list.addItem(item)
        if 0 <= self.ctrl.selected < self.list.count():
            self.list.setCurrentRow(self.ctrl.selected)
        self.list.blockSignals(False)

    def _row_changed(self, row: int) -> None:
        self.ctrl.select(row)

    def _select_from_ctrl(self, index: int) -> None:
        self.list.blockSignals(True)
        self.list.setCurrentRow(index)
        self.list.blockSignals(False)


class BodyEditor(QWidget):
    """Form editing the selected body of the scenario."""

    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self._loading = False

        self.name = QLineEdit()
        self.color = ColorButton()
        self.fixed = QCheckBox("Corps fixe (exerce la gravité, jamais accéléré)")
        self.mass = QuantityEdit(MASS_CHOICES, minimum=0.0)
        self.radius = QuantityEdit(LENGTH_CHOICES, default=1, minimum=0.0)
        density = QPushButton("depuis la densité…")
        density.setToolTip("Calcule le rayon d'une sphère homogène de cette masse et d'une densité donnée.")
        density.clicked.connect(self._radius_from_density)
        self.display_px = NumberEdit(0.0, minimum=0.0)
        self.display_px.setToolTip("Diamètre affiché en pixels (mode de taille « manuelle »). 0 = 10 px.")
        self.x = QuantityEdit(LENGTH_CHOICES)
        self.y = QuantityEdit(LENGTH_CHOICES)

        self.speed = NumberEdit(0.0, minimum=0.0)
        self.angle = NumberEdit(0.0, fmt="{:.6g}")
        self.vx, self.vy = NumberEdit(0.0), NumberEdit(0.0)
        self.speed_unit = QComboBox()
        self.speed_unit.addItems([n for n, _ in SPEED_CHOICES])
        self.speed_unit.setCurrentIndex(1)
        self.circ_label = QLabel()
        self.circ_label.setWordWrap(True)

        self.ref = QComboBox()
        self.ecc = NumberEdit(0.0, minimum=0.0, maximum=50.0)
        self.apsis = QComboBox()
        self.apsis.addItems(["périastre", "apoastre"])
        self.sense = QComboBox()
        self.sense.addItems(["antihoraire", "horaire"])
        orbit_btn = QPushButton("Appliquer la vitesse orbitale")
        orbit_btn.setToolTip("Vitesse relative au corps de référence, perpendiculaire à la direction qui les relie,\n"
                             "la position actuelle étant le périastre (ou l'apoastre).\n"
                             "Avec plus de deux corps, c'est une approximation à deux corps.")
        orbit_btn.clicked.connect(self._apply_orbital)
        escape_btn = QPushButton("Vitesse de libération")
        escape_btn.clicked.connect(self._apply_escape)

        # --- layout ---
        ident = QFormLayout()
        row = QHBoxLayout()
        row.addWidget(self.name, 1)
        row.addWidget(self.color)
        ident.addRow("Nom", row)
        ident.addRow(self.fixed)
        ident.addRow("Masse", self.mass)
        rad = QHBoxLayout()
        rad.addWidget(self.radius, 1)
        rad.addWidget(density)
        ident.addRow("Rayon", rad)
        ident.addRow("Taille affichée (px)", self.display_px)
        pos_box = QGroupBox("Position")
        pf = QFormLayout(pos_box)
        pf.addRow("x", self.x)
        pf.addRow("y", self.y)

        self.vel_box = QGroupBox("Vitesse")
        vf = QFormLayout(self.vel_box)
        vf.addRow("Unité", self.speed_unit)
        vf.addRow("Norme", self.speed)
        vf.addRow("Direction (°, antihoraire depuis +x)", self.angle)
        vf.addRow("Composante vx", self.vx)
        vf.addRow("Composante vy", self.vy)

        self.orbit_box = QGroupBox("Vitesse orbitale automatique")
        of = QFormLayout(self.orbit_box)
        of.addRow("Autour de", self.ref)
        of.addRow("Excentricité", self.ecc)
        of.addRow("Position actuelle =", self.apsis)
        of.addRow("Sens", self.sense)
        of.addRow(self.circ_label)
        btns = QHBoxLayout()
        btns.addWidget(orbit_btn)
        btns.addWidget(escape_btn)
        of.addRow(btns)

        lay = QVBoxLayout(self)
        lay.addLayout(ident)
        lay.addWidget(pos_box)
        lay.addWidget(self.vel_box)
        lay.addWidget(self.orbit_box)
        lay.addStretch(1)

        # --- wiring ---
        self.name.editingFinished.connect(self._on_name)
        self.color.colorChanged.connect(self._on_color)
        self.fixed.toggled.connect(self._on_fixed)
        self.mass.valueChanged.connect(lambda v: self._set("mass", v))
        self.radius.valueChanged.connect(lambda v: self._set("radius", v))
        self.display_px.valueChanged.connect(self._on_display_px)
        self.x.valueChanged.connect(lambda v: self._set_pos(0, v))
        self.y.valueChanged.connect(lambda v: self._set_pos(1, v))
        self.speed.valueChanged.connect(self._on_polar)
        self.angle.valueChanged.connect(self._on_polar)
        self.vx.valueChanged.connect(self._on_cartesian)
        self.vy.valueChanged.connect(self._on_cartesian)
        self.speed_unit.currentIndexChanged.connect(self._refresh_velocity)
        self.ref.currentIndexChanged.connect(self._refresh_circular)

        ctrl.selectionChanged.connect(lambda _i: self.load())
        ctrl.scenarioEdited.connect(self.load)
        ctrl.scenarioReplaced.connect(self.load)
        self.load()

    # --- current body ---------------------------------------------------------------
    def _body(self):
        k = self.ctrl.selected
        bodies = self.ctrl.scenario.bodies
        return bodies[k] if 0 <= k < len(bodies) else None

    def _factor(self) -> float:
        return SPEED_CHOICES[self.speed_unit.currentIndex()][1]

    def load(self) -> None:
        b = self._body()
        self.setEnabled(b is not None)
        if b is None:
            return
        self._loading = True
        sc = self.ctrl.scenario
        k = self.ctrl.selected
        self.name.setText(b.name)
        self.color.setColor(b.color or default_color(k))
        self.fixed.setChecked(b.fixed)
        self.mass.setInternal(b.mass)
        self.radius.setInternal(b.radius)
        self.display_px.setValue(b.display_px or 0.0)
        self.x.setInternal(b.position[0])
        self.y.setInternal(b.position[1])
        self.ref.blockSignals(True)
        self.ref.clear()
        others = [o.name for o in sc.bodies if o.name != b.name]
        self.ref.addItems(others)
        if others:
            self.ref.setCurrentText(sc.default_reference(b.name))
        self.ref.blockSignals(False)
        self.orbit_box.setEnabled(bool(others) and not b.fixed)
        self.vel_box.setEnabled(not b.fixed)
        self._refresh_velocity()
        self._refresh_circular()
        self._loading = False

    def _refresh_velocity(self) -> None:
        b = self._body()
        if b is None:
            return
        f = self._factor()
        was, self._loading = self._loading, True
        self.speed.setValue(b.speed / f)
        self.angle.setValue(b.direction_deg if b.speed > 0 else 0.0)
        self.vx.setValue(b.velocity[0] / f)
        self.vy.setValue(b.velocity[1] / f)
        self._loading = was

    def _refresh_circular(self) -> None:
        b, sc = self._body(), self.ctrl.scenario
        if b is None or b.fixed or self.ref.count() == 0 or not self.ref.currentText():
            self.circ_label.setText("")
            return
        try:
            vc = sc.circular_speed(b.name, self.ref.currentText())
            self.circ_label.setText(f"Vitesse circulaire de référence : {format_speed_si(vc)}\n"
                                    f"Vitesse de libération : {format_speed_si(math.sqrt(2) * vc)}")
        except (ValueError, ZeroDivisionError):
            self.circ_label.setText("Vitesse circulaire indéterminée (corps superposés ou sans masse).")

    # --- edits ------------------------------------------------------------------------
    def _set(self, attr: str, value: float) -> None:
        b = self._body()
        if b is None or self._loading:
            return
        setattr(b, attr, value)
        self.ctrl.edit()
        self._refresh_circular()

    def _set_pos(self, axis: int, value: float) -> None:
        b = self._body()
        if b is None or self._loading:
            return
        b.position[axis] = value
        self.ctrl.edit()
        self._refresh_circular()

    def _on_name(self) -> None:
        if self._loading or self._body() is None:
            return
        if not self.ctrl.rename_body(self.ctrl.selected, self.name.text()):
            self.name.setText(self._body().name)

    def _on_color(self, color: str) -> None:
        b = self._body()
        if b is not None:
            b.color = color
            self.ctrl.edit(reset=False)

    def _on_display_px(self, value: float) -> None:
        b = self._body()
        if b is not None and not self._loading:
            b.display_px = value or None
            self.ctrl.edit(reset=False)

    def _on_fixed(self, flag: bool) -> None:
        b = self._body()
        if b is None or self._loading:
            return
        b.fixed = flag
        self.ctrl.edit()

    def _on_polar(self, _value: float) -> None:
        b = self._body()
        if b is None or self._loading:
            return
        f = self._factor()
        b.set_velocity_polar(self.speed.value() * f, self.angle.value())
        self.ctrl.edit()
        self._refresh_velocity()
        self._refresh_circular()

    def _on_cartesian(self, _value: float) -> None:
        b = self._body()
        if b is None or self._loading:
            return
        f = self._factor()
        b.velocity = [self.vx.value() * f, self.vy.value() * f]
        self.ctrl.edit()
        self._refresh_velocity()

    def _radius_from_density(self) -> None:
        b = self._body()
        if b is None or b.mass <= 0:
            self.ctrl.log("Le rayon depuis la densité demande une masse non nulle.", "warning")
            return
        value, ok = QInputDialog.getDouble(self, "Densité", "Densité moyenne (g/cm³) :", 5.5, 0.01, 50.0, 3)
        if ok:
            self._set("radius", units.radius_from_density(b.mass, value))
            self.radius.setInternal(b.radius)

    def _apply_orbital(self) -> None:
        b = self._body()
        if b is None or not self.ref.currentText():
            return
        try:
            self.ctrl.scenario.set_orbital_velocity(
                b.name, self.ref.currentText(), e=self.ecc.value(),
                at="periapsis" if self.apsis.currentIndex() == 0 else "apoapsis",
                clockwise=self.sense.currentIndex() == 1)
        except ValueError as exc:
            self.ctrl.log(f"Vitesse orbitale impossible : {exc}", "warning")
            return
        self.ctrl.edit()
        self._refresh_velocity()

    def _apply_escape(self) -> None:
        b = self._body()
        if b is None or not self.ref.currentText():
            return
        try:
            self.ctrl.scenario.set_escape_velocity(b.name, self.ref.currentText(),
                                                   clockwise=self.sense.currentIndex() == 1)
        except ValueError as exc:
            self.ctrl.log(f"Vitesse de libération impossible : {exc}", "warning")
            return
        self.ctrl.edit()
        self._refresh_velocity()


class ImpulsePanel(QWidget):
    """Velocity kicks: immediate or scheduled, with the list of all impulses of the scenario."""

    DIRECTIONS = [("prograde", "prograde / rétrograde (selon le signe)"),
                  ("radial", "radiale (vers l'extérieur si > 0)"),
                  ("angle", "angle absolu")]

    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.body = QComboBox()
        self.dv = QuantityEdit(SPEED_CHOICES, default=1)
        self.dv.setInternal(1e3 / units.AU_PER_YR_IN_M_S)  # 1 km/s
        self.direction = QComboBox()
        self.direction.addItems([label for _, label in self.DIRECTIONS])
        self.ref = QComboBox()
        self.angle = NumberEdit(0.0)
        self.time = NumberEdit(0.0, fmt="{:.6g}")
        self.time.setToolTip("Instant en années depuis le début de la simulation.")
        self.status = QLabel()
        self.status.setWordWrap(True)
        now = QPushButton("Appliquer maintenant")
        sched = QPushButton("Programmer à t")
        now.clicked.connect(lambda: self._apply(True))
        sched.clicked.connect(lambda: self._apply(False))
        self.items = QListWidget()
        delete = QPushButton("Supprimer la poussée sélectionnée")
        delete.clicked.connect(self._delete)

        form = QFormLayout()
        form.addRow("Corps", self.body)
        form.addRow("Δv (signé)", self.dv)
        form.addRow("Direction", self.direction)
        form.addRow("Référence", self.ref)
        form.addRow("Angle (°)", self.angle)
        form.addRow("t programmé (ans)", self.time)
        row = QHBoxLayout()
        row.addWidget(now)
        row.addWidget(sched)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self.status)
        lay.addWidget(QLabel("Poussées du scénario :"))
        lay.addWidget(self.items, 1)
        lay.addWidget(delete)

        ctrl.scenarioEdited.connect(self.refresh)
        ctrl.scenarioReplaced.connect(self.refresh)
        ctrl.impulsesChanged.connect(self.refresh)
        ctrl.selectionChanged.connect(self._follow_selection)
        ctrl.changed.connect(self._update_applied_marks)
        self.direction.currentIndexChanged.connect(self._update_enabled)
        self.refresh()

    def refresh(self) -> None:
        sc = self.ctrl.scenario
        for combo, extra in ((self.body, []), (self.ref, ["(le plus massif)"])):
            combo.blockSignals(True)
            keep = combo.currentText()
            combo.clear()
            combo.addItems(extra + sc.names)
            if keep and combo.findText(keep) >= 0:
                combo.setCurrentText(keep)
            combo.blockSignals(False)
        self._follow_selection(self.ctrl.selected)
        self._update_enabled()
        self._refill_list()

    def _follow_selection(self, index: int) -> None:
        names = self.ctrl.scenario.names
        if 0 <= index < len(names):
            self.body.setCurrentText(names[index])

    def _update_enabled(self) -> None:
        kind = self.DIRECTIONS[self.direction.currentIndex()][0]
        self.angle.setEnabled(kind == "angle")
        self.ref.setEnabled(kind != "angle")

    def _refill_list(self) -> None:
        self.items.clear()
        now = self.ctrl.sim.t if self.ctrl.sim else 0.0
        for imp in sorted(self.ctrl.scenario.impulses, key=lambda i: i.t):
            done = imp.t <= now
            label = {"prograde": "prograde" if imp.dv >= 0 else "rétrograde", "radial": "radiale",
                     "angle": f"angle {imp.angle_deg:g}°"}[imp.direction]
            text = (f"t = {format_time(imp.t)} · {imp.body} · Δv = {imp.dv:.4g} UA/an ({label})"
                    + ("  ✔ appliquée" if done else ""))
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, imp)
            if done:
                item.setForeground(QColor("#888888"))
            self.items.addItem(item)

    def _update_applied_marks(self) -> None:
        if self.ctrl.sim is None:
            return
        applied = sum(1 for k in range(self.items.count())
                      if self.items.item(k).data(Qt.ItemDataRole.UserRole).t <= self.ctrl.sim.t)
        shown = sum(1 for k in range(self.items.count()) if "✔" in self.items.item(k).text())
        if applied != shown:
            self._refill_list()

    def _make(self) -> Impulse:
        kind = self.DIRECTIONS[self.direction.currentIndex()][0]
        ref = self.ref.currentText()
        return Impulse(self.body.currentText(), self.dv.internal(), self.time.value(), kind,
                       None if (ref.startswith("(") or not ref or kind == "angle") else ref,
                       self.angle.value())

    def _apply(self, now: bool) -> None:
        if not self.body.currentText():
            return
        imp = self._make()
        message = self.ctrl.apply_impulse(imp, now)
        self.status.setText(message)

    def _delete(self) -> None:
        item = self.items.currentItem()
        if item is not None:
            self.ctrl.remove_impulse(item.data(Qt.ItemDataRole.UserRole))
