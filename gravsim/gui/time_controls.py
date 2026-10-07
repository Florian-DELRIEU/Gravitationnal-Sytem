"""Playback controls and integration settings."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from ..core.integrators import INTEGRATORS
from .controller import SimulationController
from .widgets import NumberEdit, format_speed, format_time

_SPEED_MIN_LOG, _SPEED_MAX_LOG = -5.0, 4.0  # log10(years per second): 3 s/s ... 10 000 yr/s
_SLIDER_STEPS = 900
_SCRUB_STEPS = 2000

INTEGRATOR_LABELS = {"dop853": "DOP853 (adaptatif, très précis)",
                     "yoshida4": "Yoshida 4 (symplectique, longues durées)",
                     "leapfrog": "Leapfrog (symplectique, rapide)"}


class TimeControls(QWidget):
    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self._updating = False

        self.play = QPushButton("▶ Lecture")
        self.play.setMinimumWidth(100)
        self.step = QPushButton("⏭ Pas")
        self.reset = QPushButton("⏮ Réinitialiser")
        self.live = QPushButton("⇥ Direct")
        self.live.setToolTip("Revenir à l'instant le plus récent calculé.")
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(0, _SLIDER_STEPS)
        self.speed.setMinimumWidth(160)
        self.speed_label = QLabel()
        self.speed_label.setMinimumWidth(80)
        self.collision = QCheckBox("Pause à la collision")
        self.scrub = QSlider(Qt.Orientation.Horizontal)
        self.scrub.setRange(0, _SCRUB_STEPS)
        self.time_label = QLabel()
        self.time_label.setMinimumWidth(210)

        top = QHBoxLayout()
        for w in (self.play, self.step, self.reset):
            top.addWidget(w)
        top.addSpacing(12)
        top.addWidget(QLabel("Vitesse"))
        top.addWidget(self.speed)
        top.addWidget(self.speed_label)
        top.addSpacing(12)
        top.addWidget(self.collision)
        top.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.scrub, 1)
        bottom.addWidget(self.live)
        bottom.addWidget(self.time_label)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(top)
        lay.addLayout(bottom)

        self.play.clicked.connect(ctrl.toggle)
        self.step.clicked.connect(ctrl.step)
        self.reset.clicked.connect(ctrl.rebuild)
        self.live.clicked.connect(ctrl.go_live)
        self.speed.valueChanged.connect(self._on_speed)
        self.collision.toggled.connect(ctrl.set_pause_on_collision)
        self.scrub.valueChanged.connect(self._on_scrub)
        ctrl.playingChanged.connect(self._on_playing)
        ctrl.changed.connect(self.update_state)
        ctrl.reset.connect(self.update_state)
        self.update_state()

    # speed <-> slider
    @staticmethod
    def _slider_to_speed(pos: int) -> float:
        return 10.0 ** (_SPEED_MIN_LOG + (_SPEED_MAX_LOG - _SPEED_MIN_LOG) * pos / _SLIDER_STEPS)

    @staticmethod
    def _speed_to_slider(speed: float) -> int:
        frac = (math.log10(max(speed, 1e-12)) - _SPEED_MIN_LOG) / (_SPEED_MAX_LOG - _SPEED_MIN_LOG)
        return int(round(min(max(frac, 0.0), 1.0) * _SLIDER_STEPS))

    def _on_speed(self, pos: int) -> None:
        if self._updating:
            return
        self.ctrl.set_speed(self._slider_to_speed(pos))
        self.speed_label.setText(format_speed(self.ctrl.speed))

    def _on_scrub(self, pos: int) -> None:
        if self._updating or self.ctrl.sim is None:
            return
        t0, t1 = self.ctrl.scenario.t0, self.ctrl.sim.t
        self.ctrl.scrub(t0 + (t1 - t0) * pos / _SCRUB_STEPS)

    def _on_playing(self, playing: bool) -> None:
        self.play.setText("⏸ Pause" if playing else "▶ Lecture")

    def update_state(self) -> None:
        ctrl = self.ctrl
        self._updating = True
        self.speed.setValue(self._speed_to_slider(ctrl.speed))
        self.speed_label.setText(format_speed(ctrl.speed))
        self.collision.setChecked(ctrl.pause_on_collision)
        has_sim = ctrl.sim is not None
        for w in (self.play, self.step, self.scrub, self.live):
            w.setEnabled(has_sim)
        self.play.setText("⏸ Pause" if ctrl.playing else "▶ Lecture")
        if has_sim:
            t0, t1 = ctrl.scenario.t0, ctrl.sim.t
            frac = 0.0 if t1 <= t0 else (ctrl.view_time - t0) / (t1 - t0)
            self.scrub.setValue(int(round(frac * _SCRUB_STEPS)))
            replay = "" if ctrl.live else "  (relecture)"
            self.time_label.setText(f"t = {format_time(ctrl.view_time)}{replay}")
        else:
            self.time_label.setText("t = —")
        self._updating = False


class IntegrationPanel(QWidget):
    """Integrator choice, step and tolerance."""

    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        st = ctrl.settings
        self.integrator = QComboBox()
        for name in INTEGRATORS:
            self.integrator.addItem(INTEGRATOR_LABELS[name], name)
        self.integrator.setCurrentIndex(INTEGRATORS.index(st.integrator))
        self.auto = QCheckBox("Pas automatique (conseillé)")
        self.auto.setChecked(st.auto_dt)
        self.dt = NumberEdit(st.dt, minimum=1e-9)
        self.rtol = NumberEdit(st.rtol, fmt="{:.3g}", minimum=1e-15, maximum=1e-2)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.RichText)

        form = QFormLayout()
        form.addRow("Intégrateur", self.integrator)
        form.addRow(self.auto)
        form.addRow("Pas (ans)", self.dt)
        form.addRow("Tolérance relative (DOP853)", self.rtol)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.info)
        lay.addStretch(1)

        self.integrator.currentIndexChanged.connect(self._changed)
        self.auto.toggled.connect(self._changed)
        self.dt.valueChanged.connect(self._changed)
        self.rtol.valueChanged.connect(self._changed)
        ctrl.reset.connect(self.update_info)
        self._sync_enabled()
        self.update_info()

    def _sync_enabled(self) -> None:
        fixed_step = self.integrator.currentData() != "dop853"
        self.auto.setEnabled(fixed_step)
        self.dt.setEnabled(fixed_step and not self.auto.isChecked())
        self.rtol.setEnabled(not fixed_step)

    def _changed(self, *_args) -> None:
        st = self.ctrl.settings
        st.integrator = self.integrator.currentData()
        st.auto_dt = self.auto.isChecked()
        st.dt = self.dt.value()
        st.rtol = self.rtol.value()
        self._sync_enabled()
        self.ctrl.rebuild()

    def update_info(self) -> None:
        sim = self.ctrl.sim
        if sim is None:
            self.info.setText(f"<i>{self.ctrl.error or 'Aucune simulation.'}</i>")
            return
        step = f"pas = {sim.dt:.4g} an" if sim.dt else "pas adaptatif"
        self.info.setText(
            f"Pas conseillé (pas fixe) : <b>{sim.recommended_dt:.4g} an</b> "
            f"(le plus petit entre P/200 et un vingtième du temps de passage au périastre).<br>"
            f"Actuellement : {step}, échantillonnage {sim.output_dt:.4g} an.<br>"
            "Un pas trop grand dégrade la jauge de fidélité (barre d'état) : le leapfrog est le plus sensible.")
