"""The "Détection" sub-tab of the spectrum page: blind planet counting on the current observations."""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QSplitter, QTabWidget, QVBoxLayout, QWidget)

from ..analysis.detection import DetectionResult, DetectionSettings, detect_observations, match_truth
from ..core import units
from .analysis_tabs import fill_table, make_table
from .plots import BACKGROUND
from .widgets import PALETTE, NumberEdit, format_time

MODEL_COLOR = "#ffd166"
OBS_COLOR = "#ff6b6b"


def _plot(title: str) -> pg.PlotWidget:
    plot = pg.PlotWidget(background=BACKGROUND)
    pi = plot.getPlotItem()
    pi.showGrid(x=True, y=True, alpha=0.15)
    pi.setMenuEnabled(False)
    pi.hideButtons()
    pi.setTitle(title, size="10pt")
    for side in ("left", "bottom"):
        pi.getAxis(side).enableAutoSIPrefix(False)
    pi.addLegend(offset=(-10, 10))
    return plot


def _period_text(p: float) -> str:
    return f"{p:.5g} ans" if p >= 1 else f"{p / units.DAY_YR:.5g} j"


class DetectionPanel(QWidget):
    """Runs ``detection.detect`` on the observations of the spectrum page and shows the result."""

    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page  # SpectrumPage: provides .result (observations, truths) and .compute()
        self.result: DetectionResult | None = None

        self.fap = NumberEdit(1e-3, fmt="{:.3g}", minimum=1e-12, maximum=0.5)
        self.bic = NumberEdit(10.0, fmt="{:.3g}", minimum=0.0, maximum=1e4)
        self.max_planets = QSpinBox()
        self.max_planets.setRange(1, 10)
        self.max_planets.setValue(6)
        self.floor = NumberEdit(0.1, fmt="{:.3g}", minimum=0.0, maximum=50.0)
        self.floor.setToolTip("Les pics plus faibles que ce pourcentage de la planète la plus forte sont ignorés.")
        for w in (self.fap, self.bic, self.floor):
            w.setMaximumWidth(80)
        self.run_btn = QPushButton("Détecter les planètes")
        self.run_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        self.run_btn.clicked.connect(self.run)

        box = QGroupBox("Détection aveugle (la vérité ne sert qu'à noter le résultat)")
        form = QHBoxLayout(box)
        for label, w in (("FAP max", self.fap), ("ΔBIC min", self.bic), ("Planètes max", self.max_planets),
                         ("Plancher (% de la plus forte)", self.floor)):
            sub = QFormLayout()
            sub.addRow(label, w)
            form.addLayout(sub)
        form.addWidget(self.run_btn)

        self.summary = QLabel("<i>Calculez un spectre puis lancez la détection.</i>")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.fit_plot = _plot("Observations et modèle ajusté")
        self.fit_plot.getPlotItem().setLabel("bottom", "t (ans)")
        self.cascade = _plot("Périodogramme des résidus à chaque étape (extraction itérative)")
        self.cascade.getPlotItem().setLabel("bottom", "période (ans)")
        self.cascade.getPlotItem().setLabel("left", "amplitude")
        self.cascade.getPlotItem().setLogMode(x=True, y=False)
        plots = QSplitter(Qt.Orientation.Vertical)
        plots.addWidget(self.fit_plot)
        plots.addWidget(self.cascade)

        self.planets_table = make_table()
        self.planets_table.setMaximumHeight(16777215)
        self.others_table = make_table()
        self.steps_table = make_table()
        self.steps_table.setMaximumHeight(16777215)
        tables = QTabWidget()
        planets_page = QWidget()
        pl = QVBoxLayout(planets_page)
        pl.addWidget(self.planets_table, 2)
        pl.addWidget(QLabel("<b>Signaux non planétaires</b> (interactions, précession, harmoniques)"))
        pl.addWidget(self.others_table, 1)
        tables.addTab(planets_page, "Planètes")
        tables.addTab(self.steps_table, "Étapes")

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(plots)
        split.addWidget(tables)
        split.setSizes([620, 520])
        lay = QVBoxLayout(self)
        lay.addWidget(box)
        lay.addWidget(self.summary)
        lay.addWidget(split, 1)

    def settings(self) -> DetectionSettings:
        return DetectionSettings(fap_threshold=self.fap.value(), bic_threshold=self.bic.value(),
                                 max_planets=self.max_planets.value(), min_amplitude_ratio=self.floor.value() / 100.0)

    def run(self) -> DetectionResult | None:
        spec = self.page.result if self.page.result is not None else self.page.compute()
        if spec is None:
            self.summary.setText("<span style='color:#ff6b6b'>Pas d'observations : calculez d'abord le spectre "
                                 "(onglet Spectre).</span>")
            return None
        sc = self.page.ctrl.scenario
        name = spec.settings.body
        star_mass = sc.body(name).mass if name in sc.names else None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = detect_observations(spec.obs, star_mass=star_mass, settings=self.settings())
        except ValueError as exc:
            self.summary.setText(f"<span style='color:#ff6b6b'>{exc}</span>")
            return None
        finally:
            QApplication.restoreOverrideCursor()
        self.result = result
        self._show(result, spec)
        return result

    # --- display -------------------------------------------------------------------------------------------
    def _show(self, res: DetectionResult, spec) -> None:
        rv = res.kind == "rv"
        unit = "m/s" if rv else "UA"
        match = match_truth(res.planets, spec.truths, res.baseline)
        truth_of = {i: spec.truths[j] for i, j in match.matches}

        color = "#6ad48f" if not res.ambiguous else "#ffb454"
        lines = [f"<span style='font-size:15pt; color:{color}'><b>{res.count_text()}</b></span>"
                 f" &nbsp; ({len(spec.truths)} planète{'s' if len(spec.truths) > 1 else ''} réelle"
                 f"{'s' if len(spec.truths) > 1 else ''} dans la simulation)"]
        for amb in res.ambiguities:
            lines.append(f"<span style='color:#ffb454'>• {amb.text}</span>")
        missed = [spec.truths[j] for j in match.missed]
        if missed:
            noise = float(np.median(spec.obs.error)) if np.any(spec.obs.error > 0) else res.rms_residual
            parts = []
            for tr in missed:
                amp = tr.rv_semi_amplitude if rv else tr.astrometric_amplitude
                snr = amp / noise * math.sqrt(len(spec.obs.t) / 2) if noise > 0 else float("inf")
                parts.append(f"{tr.name} (P = {_period_text(tr.period)}, amplitude {amp:.3g} {unit}, "
                             f"signal/bruit ≈ {snr:.2g})")
            lines.append("Non retrouvée(s) : " + " ; ".join(parts))
        if match.spurious:
            lines.append(f"<span style='color:#ff6b6b'>{len(match.spurious)} détection(s) sans planète réelle "
                         f"correspondante</span>")
        if not np.any(spec.obs.error > 0):
            lines.append("<i>Données sans bruit : les interactions entre planètes laissent des signaux réels que "
                         "l'ajustement képlérien ne peut pas absorber ; ils sont classés non planétaires.</i>")
        reason = res.stop_reason.removeprefix("arrêt : ")
        lines.append(f"<small>Fin de la recherche : {reason} · résidu rms {res.rms_residual:.3g} {unit} · "
                     f"{res.n_obs} observations sur {format_time(res.baseline)}</small>")
        self.summary.setText("<br>".join(lines))

        rows = []
        for i, p in enumerate(res.planets):
            mass = "—"
            if p.mass is not None:
                mass = (f"{p.mass_mjup:.3g} M_Jup" if p.mass_mjup >= 0.1 else f"{p.mass_mearth:.3g} M⊕")
                mass += " (m sin i)" if rv else ""
            tr = truth_of.get(i)
            rows.append([str(i + 1), _period_text(p.period), f"{p.amplitude:.4g}", f"{p.e:.3f}",
                         "—" if math.isnan(p.omega) else f"{math.degrees(p.omega):.0f}", mass,
                         "—" if p.a is None else f"{p.a:.4g}", "—" if p.fap is None else f"{p.fap:.2g}",
                         "—" if p.delta_bic is None else f"{p.delta_bic:.0f}",
                         tr.name if tr is not None else "aucune (fausse détection ?)"])
        fill_table(self.planets_table, ["#", "Période", f"Amplitude ({unit})", "e", "ω (°)", "Masse", "a (UA)", "FAP",
                                        "ΔBIC", "Planète réelle"], rows)
        fill_table(self.others_table, ["Période", f"Amplitude ({unit})", "Raison"],
                   [[_period_text(o.period), f"{o.amplitude:.3g}", o.reason.replace("composante non planétaire : ", "")]
                    for o in res.others])
        fill_table(self.steps_table, ["Étape", "Période du pic", "Amplitude", "FAP", "ΔBIC", "Décision"],
                   [[str(s.index), _period_text(s.period), f"{s.amplitude:.3g}", f"{s.fap:.2g}",
                     "—" if s.delta_bic is None else f"{s.delta_bic:.0f}", s.decision] for s in res.steps])
        self._draw(res, spec)

    def _draw(self, res: DetectionResult, spec) -> None:
        rv = res.kind == "rv"
        obs = spec.obs
        pi = self.fit_plot.getPlotItem()
        pi.clear()
        t_fine = np.linspace(obs.t.min(), obs.t.max(), 4000)
        model = res.model(t_fine)
        if rv:
            pi.setLabel("left", "vitesse radiale (m/s)")
            pi.plot(obs.t, obs.value, pen=None, symbol="o", symbolSize=4, symbolBrush=OBS_COLOR, symbolPen=None,
                    name="observations")
            pi.plot(t_fine, model, pen=pg.mkPen(MODEL_COLOR, width=1.4), name="modèle ajusté")
        else:
            pi.setLabel("left", "position (UA)")
            pi.plot(obs.t, obs.value.real, pen=None, symbol="o", symbolSize=4, symbolBrush=OBS_COLOR, symbolPen=None,
                    name="x observé")
            pi.plot(obs.t, obs.value.imag, pen=None, symbol="t", symbolSize=4, symbolBrush="#4cc9f0", symbolPen=None,
                    name="y observé")
            pi.plot(t_fine, model.real, pen=pg.mkPen(MODEL_COLOR, width=1.4), name="modèle x")
            pi.plot(t_fine, model.imag, pen=pg.mkPen("#9bdeac", width=1.4), name="modèle y")
        pi.enableAutoRange()

        ci = self.cascade.getPlotItem()
        ci.clear()
        for k, step in enumerate(res.steps):
            f, a = step.freq, step.spectrum
            keep = f != 0
            if not keep.any():
                continue
            order = np.argsort(1.0 / np.abs(f[keep]))
            x = (1.0 / np.abs(f[keep]))[order]
            y = a[keep][order]
            kept = step.decision.startswith("retenu")
            pen = pg.mkPen(PALETTE[k % len(PALETTE)], width=1.2 if kept else 0.8,
                           style=Qt.PenStyle.SolidLine if kept else Qt.PenStyle.DotLine)
            ci.plot(x, y, pen=pen, name=f"étape {step.index} : pic à {_period_text(step.period)}")
        ci.enableAutoRange()
