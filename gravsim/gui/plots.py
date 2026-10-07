"""Time-series plot helper shared by the analysis tabs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from .widgets import default_color

BACKGROUND = "#0b0d14"
COLLISION_COLOR = "#ff5c5c"
IMPULSE_COLOR = "#ffb454"


def decimate_minmax(t: np.ndarray, series: list[np.ndarray], max_points: int = 4000):
    """Reduce to about ``max_points`` samples, keeping the extremes of every bin in every series.

    Plain striding would erase narrow features such as a periapsis dip in a distance curve.
    Returns (t', [y', ...]) sharing one time axis.
    """
    n = len(t)
    if n <= max_points:
        return t, series
    nbins = max(1, max_points // (2 * max(1, len(series))))
    width = n // nbins
    base = np.arange(nbins) * width
    keep = {0, n - 1}
    for y in series:
        block = np.asarray(y[: nbins * width], dtype=float).reshape(nbins, width)
        lo = np.where(np.isnan(block), np.inf, block).argmin(axis=1)
        hi = np.where(np.isnan(block), -np.inf, block).argmax(axis=1)
        keep.update((base + lo).tolist())
        keep.update((base + hi).tolist())
    idx = np.array(sorted(keep))
    return t[idx], [np.asarray(y)[idx] for y in series]


@dataclass
class Curve:
    label: str
    y: np.ndarray
    color: str
    style: str = "solid"  # 'solid' | 'dash' | 'dot'


class SeriesPlot(pg.PlotWidget):
    """A dark plot of several curves against time, with collision / impulse markers.

    A curve that is constant to numerical precision (a circular orbit's distance, say) is shown flat:
    the vertical range never shrinks below ``MIN_RELATIVE_SPAN`` of the plotted values, so rounding noise
    is not blown up into fake oscillations.
    """

    MIN_RELATIVE_SPAN = 2e-3

    _STYLES = {"solid": Qt.PenStyle.SolidLine, "dash": Qt.PenStyle.DashLine, "dot": Qt.PenStyle.DotLine}

    def __init__(self, ylabel: str, xlabel: str = "t (ans)", title: str | None = None, log_y: bool = False,
                 parent=None):
        super().__init__(parent, background=BACKGROUND)
        pi = self.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.15)
        pi.setMenuEnabled(False)
        pi.hideButtons()
        pi.addLegend(offset=(10, 10))
        if title:
            pi.setTitle(title, size="10pt")
        pi.setLabel("left", ylabel)
        pi.setLabel("bottom", xlabel)
        for side in ("left", "bottom"):
            pi.getAxis(side).enableAutoSIPrefix(False)
        self._log_y = log_y
        if log_y:
            pi.setLogMode(y=True)
        self._markers: list[pg.InfiniteLine] = []

    def set_curves(self, t: np.ndarray, curves: list[Curve], collisions=(), impulses=()) -> None:
        pi = self.getPlotItem()
        pi.clear()
        self._markers = []
        if len(t) == 0 or not curves:
            return
        ts, ys = decimate_minmax(np.asarray(t), [c.y for c in curves])
        for c, y in zip(curves, ys):
            y = np.asarray(y, dtype=float)
            y = np.where(np.isfinite(y), y, np.nan)
            pen = pg.mkPen(c.color, width=1.5, style=self._STYLES[c.style])
            pi.plot(ts, y, pen=pen, name=c.label, connect="finite")
        self._mark(collisions, COLLISION_COLOR, Qt.PenStyle.DashLine, "collision")
        self._mark(impulses, IMPULSE_COLOR, Qt.PenStyle.DotLine, "poussée")
        pi.enableAutoRange()
        if not self._log_y:
            self._limit_zoom_on_noise(ys)

    def _limit_zoom_on_noise(self, series) -> None:
        finite = np.concatenate([np.asarray(y, dtype=float)[np.isfinite(y)] for y in series] or [np.empty(0)])
        if finite.size == 0:
            return
        lo, hi = float(finite.min()), float(finite.max())
        scale = max(abs(lo), abs(hi))
        if scale > 0 and hi - lo < self.MIN_RELATIVE_SPAN * scale:
            mid, half = 0.5 * (lo + hi), 0.5 * self.MIN_RELATIVE_SPAN * scale
            self.getPlotItem().setYRange(mid - half, mid + half, padding=0)

    def _mark(self, times, color: str, style, label: str) -> None:
        pen = pg.mkPen(color, width=1, style=style)
        for k, t in enumerate(times):
            if k == 0:
                # A legend sample can only draw curves, not an InfiniteLine (that crashes the painter):
                # an empty curve with the same pen provides the entry.
                self.getPlotItem().plot([], [], pen=pen, name=label)
            line = pg.InfiniteLine(pos=float(t), angle=90, pen=pen)
            self.addItem(line, ignoreBounds=True)
            self._markers.append(line)

    def set_xy(self, curves: list[tuple[str, str, np.ndarray, np.ndarray]]) -> None:
        """Trajectories x-y with equal axes. ``curves``: (label, color, x, y)."""
        pi = self.getPlotItem()
        pi.clear()
        self._markers = []
        for label, color, x, y in curves:
            stride = max(1, len(x) // 4000)
            pi.plot(np.asarray(x)[::stride], np.asarray(y)[::stride], pen=pg.mkPen(color, width=1.3), name=label)
        pi.enableAutoRange()


class CheckList(QListWidget):
    """A list of names with checkboxes and colour swatches; selection survives refills by name."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(210)
        self.setMinimumWidth(130)

    def fill(self, names: list[str], colors: list[str], default_checked) -> None:
        previous = {self.item(k).text(): self.item(k).checkState() for k in range(self.count())}
        self.blockSignals(True)
        self.clear()
        for k, (name, color) in enumerate(zip(names, colors)):
            item = QListWidgetItem(name)
            item.setForeground(pg.mkColor(color))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = previous.get(name, Qt.CheckState.Checked if default_checked(k) else Qt.CheckState.Unchecked)
            item.setCheckState(checked)
            self.addItem(item)
        self.blockSignals(False)

    def checked(self) -> list[int]:
        return [k for k in range(self.count()) if self.item(k).checkState() == Qt.CheckState.Checked]


def body_colors(scenario) -> list[str]:
    return [b.color or default_color(k) for k, b in enumerate(scenario.bodies)]
