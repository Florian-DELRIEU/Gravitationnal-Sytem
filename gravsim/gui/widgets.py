"""Small reusable widgets and formatting helpers."""

from __future__ import annotations

import math

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from ..core import units

# (label, factor to internal units)
MASS_CHOICES = [("M☉", units.M_SUN), ("M_Jup", units.M_JUP), ("M⊕", units.M_EARTH), ("M_Lune", units.M_MOON)]
LENGTH_CHOICES = [("UA", 1.0), ("R☉", units.R_SUN), ("R_Jup", units.R_JUP), ("R⊕", units.R_EARTH),
                  ("km", 1e3 / units.AU_M)]
SPEED_CHOICES = [("UA/an", 1.0), ("km/s", 1e3 / units.AU_PER_YR_IN_M_S), ("m/s", 1.0 / units.AU_PER_YR_IN_M_S)]

PALETTE = ["#ffd166", "#4cc9f0", "#f78c6b", "#9bdeac", "#c77dff", "#ef476f", "#06d6a0", "#a0c4ff", "#ffadad",
           "#caffbf"]


def format_time(t: float) -> str:
    """Time in years, shown in the most readable unit."""
    a = abs(t)
    if a == 0:
        return "0"
    if a >= 1:
        return f"{t:.5g} ans"
    if a * units.DAY_YR**-1 >= 1:
        return f"{t / units.DAY_YR:.5g} j"
    return f"{t / units.DAY_YR * 24:.5g} h"


def format_speed(yr_per_s: float) -> str:
    """Simulation speed (years of simulated time per second of real time)."""
    a = abs(yr_per_s)
    if a >= 1:
        return f"{yr_per_s:.3g} ans/s"
    if a / units.DAY_YR >= 1:
        return f"{yr_per_s / units.DAY_YR:.3g} j/s"
    return f"{yr_per_s / units.DAY_YR * 24:.3g} h/s"


def format_speed_si(v_au_yr: float) -> str:
    return f"{v_au_yr:.5g} UA/an ({units.au_per_yr_to_m_s(v_au_yr) / 1e3:.5g} km/s)"


def default_color(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


class NumberEdit(QLineEdit):
    """Line edit for a float: accepts '1e-3' and decimal commas, reverts invalid input."""

    valueChanged = Signal(float)

    def __init__(self, value: float = 0.0, fmt: str = "{:.6g}", minimum: float = -math.inf,
                 maximum: float = math.inf, parent=None):
        super().__init__(parent)
        self._fmt, self._min, self._max = fmt, minimum, maximum
        self._value = float(value)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setText(self._fmt.format(self._value))
        self.editingFinished.connect(self._commit)

    def value(self) -> float:
        return self._value

    def setValue(self, value: float) -> None:
        """Set the value without emitting ``valueChanged``."""
        self._value = float(value)
        self.setText(self._fmt.format(self._value))

    def _commit(self) -> None:
        try:
            v = float(self.text().strip().replace(",", ".").replace(" ", ""))
        except ValueError:
            v = math.nan
        if not math.isfinite(v):
            self.setText(self._fmt.format(self._value))
            return
        v = min(max(v, self._min), self._max)
        self.setText(self._fmt.format(v))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)


class QuantityEdit(QWidget):
    """A number with a unit selector. ``internal()`` is always in internal units (Msun, AU, AU/yr)."""

    valueChanged = Signal(float)  # internal units

    def __init__(self, choices, default: int = 0, minimum: float = -math.inf, maximum: float = math.inf, parent=None):
        super().__init__(parent)
        self._factors = [f for _, f in choices]
        self._internal = 0.0
        self._min, self._max = minimum, maximum
        self.edit = NumberEdit(0.0)
        self.unit = QComboBox()
        self.unit.addItems([name for name, _ in choices])
        self.unit.setCurrentIndex(default)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.unit)
        self.edit.valueChanged.connect(self._on_edit)
        self.unit.currentIndexChanged.connect(self._refresh)

    def _factor(self) -> float:
        return self._factors[self.unit.currentIndex()]

    def internal(self) -> float:
        return self._internal

    def setInternal(self, value: float) -> None:
        self._internal = float(value)
        self._refresh()

    def _refresh(self) -> None:
        self.edit.setValue(self._internal / self._factor())

    def _on_edit(self, shown: float) -> None:
        v = min(max(shown * self._factor(), self._min), self._max)
        self._internal = v
        self._refresh()
        self.valueChanged.emit(v)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (Qt naming)
        super().setEnabled(enabled)


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str = "#ffffff", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedWidth(48)
        self._paint()
        self.clicked.connect(self._choose)

    def color(self) -> str:
        return self._color

    def setColor(self, color: str) -> None:
        self._color = color
        self._paint()

    def _paint(self) -> None:
        self.setStyleSheet(f"background-color: {self._color}; border: 1px solid #555; border-radius: 3px;")

    def _choose(self) -> None:
        picked = QColorDialog.getColor(QColor(self._color), self, "Couleur du corps")
        if picked.isValid():
            self.setColor(picked.name())
            self.colorChanged.emit(self._color)


class ViewSettings(QObject):
    """Display options shared by the viewer and its settings panel."""

    changed = Signal()

    SIZE_MODES = ("mass", "manual", "real")
    FRAMES = ("inertial", "barycentric", "body", "rotating")
    CAMERAS = ("all", "free", "follow")

    def __init__(self):
        super().__init__()
        self.size_mode = "mass"
        self.max_px = 22.0
        self.min_px = 4.0
        self.trail_samples = 800
        self.show_velocity = False
        self.show_force = False
        self.show_barycenter = True
        self.show_hill = False
        self.show_names = True
        self.frame = "inertial"
        self.frame_body = 0
        self.frame_pair = (0, 1)
        self.camera = "all"
        self.follow_body = 0

    def notify(self) -> None:
        self.changed.emit()
