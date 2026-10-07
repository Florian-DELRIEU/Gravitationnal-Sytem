"""The "Spectre" page: observe a star's reflex motion, compute its spectrum, compare with the real planets."""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QProgressDialog, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from ..analysis import pipeline
from ..analysis.pipeline import ObservationSettings, SpectrumResult
from ..core import units
from .analysis_tabs import fill_table, make_table
from .controller import SimulationController
from .plots import BACKGROUND
from .widgets import PALETTE, NumberEdit, format_time

CLEAN_COLOR = "#8896b3"
OBS_COLOR = "#ff6b6b"
RETRO_COLOR = "#ffb454"


def _dark_plot(title: str | None = None) -> pg.PlotWidget:
    plot = pg.PlotWidget(background=BACKGROUND)
    pi = plot.getPlotItem()
    pi.showGrid(x=True, y=True, alpha=0.15)
    pi.setMenuEnabled(False)
    pi.hideButtons()
    for side in ("left", "bottom"):
        pi.getAxis(side).enableAutoSIPrefix(False)
    if title:
        pi.setTitle(title, size="10pt")
    return plot


class SpectrumPage(QWidget):
    REFRESH_MS = 1000

    def __init__(self, ctrl: SimulationController, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.result: SpectrumResult | None = None
        self._start_auto = True  # the start follows the last impulse until the user types a value

        # --- settings ---------------------------------------------------------------
        self.body = QComboBox()
        self.signal = QComboBox()
        self.signal.addItem("Vitesse radiale (m/s)", "rv")
        self.signal.addItem("Astrométrie x + iy (UA)", "astrometry")
        self.los = NumberEdit(0.0, fmt="{:.6g}")
        self.incl = NumberEdit(90.0, minimum=0.0, maximum=90.0)
        self.t_start = NumberEdit(0.0, minimum=0.0)
        self.t_end = NumberEdit(0.0, minimum=0.0)
        self.end_auto = QCheckBox("Fin = dernier instant calculé")
        self.end_auto.setChecked(True)
        self.sampling = QComboBox()
        self.sampling.addItem("Régulier (FFT fenêtrée)", "regular")
        self.sampling.addItem("Irrégulier (Lomb-Scargle)", "irregular")
        self.dt = NumberEdit(0.01, fmt="{:.5g}", minimum=1e-9)
        self.n_obs = QSpinBox()
        self.n_obs.setRange(20, 20000)
        self.n_obs.setValue(150)
        self.season = NumberEdit(0.0, fmt="{:.3g}", minimum=0.0, maximum=0.9)
        self.season.setToolTip("Fraction de chaque année pendant laquelle l'étoile est inobservable (0 à 0,9).")
        self.seed = QSpinBox()
        self.seed.setRange(0, 10**6)
        self.seed.setValue(1)
        self.sigma = NumberEdit(0.0, fmt="{:.4g}", minimum=0.0)
        self.sigma_unit = QLabel("m/s")
        self.window = QComboBox()
        self.window.addItem("Hann", "hann")
        self.window.addItem("Aucune", None)
        self.oversample = NumberEdit(10.0, fmt="{:.3g}", minimum=2.0, maximum=50.0)
        self.threshold = NumberEdit(2.0, fmt="{:.3g}", minimum=0.0, maximum=100.0)
        self.threshold.setToolTip("Les pics plus bas que ce pourcentage du plus haut ne sont pas listés.")
        self.use_spectrogram = QCheckBox("Calculer le spectrogramme")
        self.spectro_window = NumberEdit(1.0, fmt="{:.4g}", minimum=1e-6)
        self.freq_axis = QCheckBox("Axe en fréquence (au lieu de la période)")
        self.show_truth = QCheckBox("Marquer les planètes réelles")
        self.show_truth.setChecked(True)
        self.compute_btn = QPushButton("Calculer le spectre")
        self.compute_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        self.complete_btn = QPushButton("Compléter (6 × P max)")
        self.complete_btn.setToolTip("Poursuit la simulation jusqu'à 6 fois la période de la planète la plus lente.")
        self.suggest_btn = QPushButton("Valeurs conseillées")
        self.suggest_btn.setToolTip("Pas d'échantillonnage, début après la dernière poussée, options par défaut.")
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.RichText)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.RichText)

        obs_box = QGroupBox("Observation")
        of = QFormLayout(obs_box)
        of.addRow("Corps observé", self.body)
        of.addRow("Signal", self.signal)
        of.addRow("Ligne de visée φ (°)", self.los)
        of.addRow("Inclinaison i (°)", self.incl)
        of.addRow("Début (ans)", self.t_start)
        of.addRow("Fin (ans)", self.t_end)
        of.addRow(self.end_auto)
        samp_box = QGroupBox("Échantillonnage et bruit")
        sf = QFormLayout(samp_box)
        sf.addRow("Mode", self.sampling)
        sf.addRow("Pas (ans)", self.dt)
        sf.addRow("Nombre d'observations", self.n_obs)
        sf.addRow("Saison inobservable", self.season)
        sf.addRow("Graine du hasard", self.seed)
        sig = QHBoxLayout()
        sig.addWidget(self.sigma, 1)
        sig.addWidget(self.sigma_unit)
        sf.addRow("Bruit blanc σ", sig)
        method_box = QGroupBox("Analyse")
        mf = QFormLayout(method_box)
        mf.addRow("Fenêtre (FFT)", self.window)
        mf.addRow("Suréchantillonnage (LS)", self.oversample)
        mf.addRow("Seuil des pics (% du max)", self.threshold)
        mf.addRow(self.use_spectrogram)
        mf.addRow("Fenêtre du spectrogramme (ans)", self.spectro_window)
        mf.addRow(self.freq_axis)
        mf.addRow(self.show_truth)

        left = QWidget()
        ll = QVBoxLayout(left)
        for w in (obs_box, samp_box, method_box):
            ll.addWidget(w)
        ll.addWidget(self.compute_btn)
        row = QHBoxLayout()
        row.addWidget(self.complete_btn)
        row.addWidget(self.suggest_btn)
        ll.addLayout(row)
        ll.addWidget(self.info)
        ll.addWidget(self.status)
        ll.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(370)
        scroll.setMaximumWidth(430)

        # --- results ----------------------------------------------------------------
        self.signal_plot = _dark_plot("Signal observé")
        self.signal_plot.getPlotItem().setLabel("bottom", "t (ans)")
        self.spec_plot = _dark_plot()
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.signal_plot)
        splitter.addWidget(self.spec_plot)
        splitter.setSizes([260, 420])
        self.spectro_plot = _dark_plot("Spectrogramme (amplitude)")
        self.spectro_image = pg.ImageItem()
        self.spectro_plot.addItem(self.spectro_image)
        self.spectro_plot.getPlotItem().setLabel("bottom", "t (ans)")
        self.spectro_plot.getPlotItem().setLabel("left", "fréquence (cycles/an)")
        self.peaks_table = make_table()
        self.peaks_table.setMaximumHeight(16777215)
        self.truth_table = make_table()
        tables = QWidget()
        tl = QVBoxLayout(tables)
        tl.addWidget(QLabel("<b>Pics détectés</b>"))
        tl.addWidget(self.peaks_table, 3)
        tl.addWidget(QLabel("<b>Planètes réelles</b> (éléments initiaux, formule à deux corps)"))
        tl.addWidget(self.truth_table, 2)
        self.tabs = QTabWidget()
        self.tabs.addTab(splitter, "Spectre")
        self.tabs.addTab(self.spectro_plot, "Spectrogramme")
        self.tabs.addTab(tables, "Pics et planètes")

        lay = QHBoxLayout(self)
        lay.addWidget(scroll)
        lay.addWidget(self.tabs, 1)

        # --- wiring -----------------------------------------------------------------
        self.t_start.valueChanged.connect(lambda _v: setattr(self, "_start_auto", False))  # user edits only
        self.compute_btn.clicked.connect(self.compute)
        self.complete_btn.clicked.connect(self.complete_simulation)
        self.suggest_btn.clicked.connect(lambda: self.apply_suggestions(full=True))
        self.signal.currentIndexChanged.connect(self._sync_enabled)
        self.sampling.currentIndexChanged.connect(self._sync_enabled)
        self.end_auto.toggled.connect(self._sync_enabled)
        self.use_spectrogram.toggled.connect(self._sync_enabled)
        self.body.currentIndexChanged.connect(lambda _i: self._update_info())
        self.freq_axis.toggled.connect(lambda _f: self._redraw())
        self.show_truth.toggled.connect(lambda _f: self._redraw())
        ctrl.reset.connect(self._on_reset)
        ctrl.scenarioEdited.connect(self._refill_bodies)
        ctrl.scenarioReplaced.connect(self._refill_bodies)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._update_info)
        ctrl.changed.connect(self._schedule_info)
        self._refill_bodies()
        self._sync_enabled()

    # --- helpers -----------------------------------------------------------------------
    def _schedule_info(self) -> None:
        if self.isVisible() and not self._timer.isActive():
            self._timer.start(self.REFRESH_MS)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._update_info()

    def _refill_bodies(self) -> None:
        sc = self.ctrl.scenario
        keep = self.body.currentText()
        self.body.blockSignals(True)
        self.body.clear()
        self.body.addItems(sc.names)
        movable = [b for b in sc.bodies if not b.fixed]
        pick = keep if keep in sc.names else (max(movable, key=lambda b: b.mass).name if movable else None)
        if pick:
            self.body.setCurrentText(pick)
        self.body.blockSignals(False)
        self.apply_suggestions()

    def _on_reset(self) -> None:
        self.status.setText("")
        self.apply_suggestions()
        self._update_info()

    def _sync_enabled(self) -> None:
        regular = self.sampling.currentData() == "regular"
        self.dt.setEnabled(regular)
        self.window.setEnabled(regular)
        self.n_obs.setEnabled(not regular)
        self.season.setEnabled(not regular)
        self.seed.setEnabled(True)
        self.oversample.setEnabled(not regular)
        rv = self.signal.currentData() == "rv"
        self.los.setEnabled(rv)
        self.incl.setEnabled(rv)
        self.sigma_unit.setText("m/s" if rv else "10⁻⁶ UA")
        self.t_end.setEnabled(not self.end_auto.isChecked())
        self.spectro_window.setEnabled(self.use_spectrogram.isChecked())

    def _body_index(self) -> int:
        name = self.body.currentText()
        return self.ctrl.scenario.index(name) if name in self.ctrl.scenario.names else -1

    def _suggestions(self) -> dict | None:
        traj = self.ctrl.traj
        if traj is None or self._body_index() < 0 or len(traj) < 1:
            return None
        return pipeline.suggest(traj, self._body_index())

    def apply_suggestions(self, full: bool = False) -> None:
        """Sampling step and start time adapted to the system; ``full`` also resets the other options."""
        traj, sug = self.ctrl.traj, self._suggestions()
        if traj is None:
            return
        self._start_auto = True
        self.t_start.setValue(pipeline.default_start(traj))
        if sug and sug["dt"]:
            self.dt.setValue(sug["dt"])
        if full:
            self.end_auto.setChecked(True)
            self.sigma.setValue(0.0)
            self.season.setValue(0.0)
            self.los.setValue(0.0)
            self.incl.setValue(90.0)
            self.sampling.setCurrentIndex(0)
            self.use_spectrogram.setChecked(False)
        self._update_info()

    def _update_info(self) -> None:
        traj, sug = self.ctrl.traj, self._suggestions()
        if traj is None or sug is None:
            self.info.setText("<i>Aucune simulation.</i>")
            return
        t_end = traj.t[-1]
        if self.end_auto.isChecked():
            self.t_end.setValue(t_end)
        if self._start_auto:  # observations cannot straddle a velocity jump: start after the last applied impulse
            self.t_start.setValue(pipeline.default_start(traj))
        lines = [f"Simulé : <b>{format_time(traj.t[0])} → {format_time(t_end)}</b> ({len(traj)} échantillons)"]
        if sug["p_min"]:
            T = t_end - self.t_start.value()
            lines.append(f"Planète la plus rapide : P = <b>{format_time(sug['p_min'])}</b> · la plus lente : "
                         f"<b>{format_time(sug['p_max'])}</b>")
            if T > 0:
                lines.append(f"Durée d'observation T = {format_time(T)} = {T / sug['p_max']:.2g} × P max · "
                             f"résolution 1/T = {1 / T:.3g} cycle/an")
            if t_end - traj.t[0] < sug["duration"] * 0.999:
                lines.append(f"<span style='color:#ffb454'>Conseillé : simuler jusqu'à {format_time(traj.t[0] + sug['duration'])}"
                             f" (6 × P max). Bouton « Compléter la simulation ».</span>")
        else:
            lines.append("Aucun compagnon lié à ce corps.")
        self.info.setText("<br>".join(lines))

    def _settings(self) -> ObservationSettings:
        rv = self.signal.currentData() == "rv"
        sigma = self.sigma.value() * (1.0 if rv else 1e-6)
        return ObservationSettings(
            body=self.body.currentText(), signal=self.signal.currentData(),
            line_of_sight_deg=self.los.value(), inclination_deg=self.incl.value(),
            t_start=self.t_start.value(), t_end=None if self.end_auto.isChecked() else self.t_end.value(),
            sampling=self.sampling.currentData(), dt=self.dt.value(), n_obs=self.n_obs.value(),
            season_fraction=self.season.value(), seed=self.seed.value(), sigma=sigma,
            window=self.window.currentData(), oversample=self.oversample.value(),
            peak_threshold=self.threshold.value() / 100.0,
            spectrogram_window=self.spectro_window.value() if self.use_spectrogram.isChecked() else None)

    # --- long simulation with progress -------------------------------------------------------
    def complete_simulation(self) -> bool:
        """Simulate far enough for a good spectrum (6 × the slowest period), with a progress dialog."""
        ctrl, sug = self.ctrl, self._suggestions()
        if ctrl.sim is None or sug is None or not sug["duration"]:
            self.status.setText("<span style='color:#ff6b6b'>Rien à compléter : pas de simulation ou de compagnon.</span>")
            return False
        target = ctrl.scenario.t0 + sug["duration"]
        sim = ctrl.sim
        if sim.t >= target:
            self.status.setText("La simulation couvre déjà 6 × P max.")
            return True
        ctrl.pause()
        start = sim.t
        dlg = QProgressDialog("Simulation en cours…", "Annuler", 0, 1000, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        stalled = False
        while sim.t < target - 1e-12 and not dlg.wasCanceled():
            before = sim.t
            ctrl.advance_to(min(target, sim.t + 4000.0 * sim.output_dt), budget=0.15)
            dlg.setValue(int(1000 * (sim.t - start) / (target - start)))
            QApplication.processEvents()
            if sim.t <= before:
                stalled = True
                break
        dlg.close()
        ctrl.go_live()
        self._update_info()
        if stalled:
            self.status.setText("<span style='color:#ffb454'>Simulation interrompue (limite de mémoire ou erreur) : "
                                "voir le journal.</span>")
            return False
        done = sim.t >= target - 1e-9
        self.status.setText(f"Simulation poursuivie jusqu'à {format_time(sim.t)}." if done
                            else "<span style='color:#ffb454'>Simulation annulée avant la fin.</span>")
        return done

    # --- computing and drawing -------------------------------------------------------------------
    def compute(self) -> SpectrumResult | None:
        traj = self.ctrl.traj
        if traj is None:
            self.status.setText("<span style='color:#ff6b6b'>Aucune simulation.</span>")
            return None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = pipeline.run_observation(traj, self._settings())
        except (ValueError, KeyError) as exc:
            self.status.setText(f"<span style='color:#ff6b6b'>{exc}</span>")
            return None
        finally:
            QApplication.restoreOverrideCursor()
        self.result = result
        notes = "".join(f"<br><span style='color:#ffb454'>• {n}</span>" for n in result.notes)
        self.status.setText(f"{len(result.obs.t)} observations · méthode {result.spectrum.method} · "
                            f"{len(result.peaks)} pic(s){notes}")
        self._redraw()
        self._fill_tables(result)
        return result

    def _x_of(self, freq: float) -> float:
        """View coordinate of a frequency, for items pyqtgraph does not transform (lines, texts):
        log10(period) in period mode, the signed frequency otherwise."""
        if self.freq_axis.isChecked():
            return freq
        return math.log10(1.0 / abs(freq))

    def _redraw(self) -> None:
        res = self.result
        if res is None:
            return
        self._draw_signal(res)
        self._draw_spectrum(res)
        self._draw_spectrogram(res)

    def _draw_signal(self, res: SpectrumResult) -> None:
        pi = self.signal_plot.getPlotItem()
        pi.clear()
        rv = res.settings.signal == "rv"
        pi.setLabel("left", "vitesse radiale (m/s)" if rv else "position (UA)")
        if rv:
            pi.plot(res.clean_t, res.clean, pen=pg.mkPen(CLEAN_COLOR, width=1), name="signal sans bruit")
            pi.plot(res.obs.t, res.obs.value, pen=None, symbol="o", symbolSize=4,
                    symbolBrush=OBS_COLOR, symbolPen=None, name="observations")
        else:
            pi.plot(res.clean_t, res.clean.real, pen=pg.mkPen(CLEAN_COLOR, width=1), name="x (sans bruit)")
            pi.plot(res.clean_t, res.clean.imag, pen=pg.mkPen("#4cc9f0", width=1), name="y (sans bruit)")
            pi.plot(res.obs.t, res.obs.value.real, pen=None, symbol="o", symbolSize=4, symbolBrush=OBS_COLOR,
                    symbolPen=None, name="observations x")
            pi.plot(res.obs.t, res.obs.value.imag, pen=None, symbol="t", symbolSize=4, symbolBrush=RETRO_COLOR,
                    symbolPen=None, name="observations y")
        if pi.legend is None:
            pi.addLegend(offset=(10, 10))
        pi.enableAutoRange()

    def _draw_spectrum(self, res: SpectrumResult) -> None:
        pi = self.spec_plot.getPlotItem()
        pi.clear()
        spec = res.spectrum
        in_period = not self.freq_axis.isChecked()
        rv = res.settings.signal == "rv"
        pi.setLogMode(x=in_period, y=False)
        pi.setLabel("left", "amplitude (m/s)" if rv else "amplitude (UA)")
        pi.setLabel("bottom", "période (ans)" if in_period else "fréquence (cycles/an)")
        pi.setTitle(f"Spectre ({spec.method})", size="10pt")
        if pi.legend is None:
            pi.addLegend(offset=(-10, 10))
        f, a = spec.freq, spec.amplitude
        if in_period:
            pos = f > 0
            name = "sens direct" if not rv else "spectre"
            pi.plot(1.0 / f[pos], a[pos], pen=pg.mkPen("#4cc9f0", width=1.3), name=name)
            if not rv:
                neg = f < 0
                pi.plot(1.0 / -f[neg], a[neg], pen=pg.mkPen(RETRO_COLOR, width=1.3), name="sens rétrograde")
        else:
            pi.plot(f, a, pen=pg.mkPen("#4cc9f0", width=1.3), name="spectre")

        if self.show_truth.isChecked():
            for i, tr in enumerate(res.truths):
                color = PALETTE[i % len(PALETTE)]
                sign = tr.direction if (not rv and not in_period) else 1
                for n, style, width in ((1, Qt.PenStyle.SolidLine, 1.4), (2, Qt.PenStyle.DotLine, 1.0),
                                        (3, Qt.PenStyle.DotLine, 1.0)):
                    if n * tr.frequency > res.f_max:
                        continue
                    pen = pg.mkPen(color, width=width, style=style)
                    pi.addItem(pg.InfiniteLine(pos=self._x_of(sign * n * tr.frequency), angle=90, pen=pen),
                               ignoreBounds=True)
                    if n == 1:  # legend entry through an empty curve (a legend cannot draw an InfiniteLine)
                        pi.plot([], [], pen=pen, name=tr.name)
        # peaks
        # Curve data go through pyqtgraph's own log transform (raw period); InfiniteLine and TextItem do not (log10).
        xs = [(1.0 / abs(pk.frequency)) if in_period else pk.frequency for pk in res.peaks if pk.frequency != 0]
        ys = [pk.amplitude for pk in res.peaks if pk.frequency != 0]
        pi.plot(xs, ys, pen=None, symbol="t1", symbolSize=9, symbolBrush=OBS_COLOR, symbolPen=None)
        for k, pk in enumerate(res.peaks[:6]):
            if pk.frequency == 0:
                continue
            text = pg.TextItem(f"{k + 1}", color="#ffffff", anchor=(0.5, 1.4))
            text.setPos(self._x_of(pk.frequency), pk.amplitude)
            pi.addItem(text)
        # visible range: from the highest kept harmonic up to the observation length
        if in_period:
            pi.setXRange(math.log10(1.0 / res.f_max), math.log10(spec.baseline), padding=0.02)
        else:
            lim = res.f_max
            pi.setXRange(-lim if not rv else 0.0, lim, padding=0.02)
        pi.enableAutoRange(axis="y")

    def _draw_spectrogram(self, res: SpectrumResult) -> None:
        if res.spectrogram is None:
            self.spectro_image.clear()
            return
        centres, freq, amp = res.spectrogram
        if len(centres) < 2:
            self.spectro_image.clear()
            return
        step = float(centres[1] - centres[0])
        self.spectro_image.setImage(amp, autoLevels=True)
        self.spectro_image.setColorMap(pg.colormap.get("viridis"))
        self.spectro_image.setRect(QRectF(centres[0] - step / 2, freq[0], centres[-1] - centres[0] + step,
                                          freq[-1] - freq[0]))
        self.spectro_plot.getPlotItem().autoRange()

    def _fill_tables(self, res: SpectrumResult) -> None:
        unit = "m/s" if res.settings.signal == "rv" else "UA"
        rows = []
        for k, (pk, label, fap) in enumerate(zip(res.peaks, res.labels, res.fap)):
            sense = ""
            if res.settings.signal == "astrometry":
                sense = " (rétro)" if pk.frequency < 0 else ""
            rows.append([str(k + 1), f"{pk.period:.6g}{sense}", f"{pk.period / units.DAY_YR:.6g}",
                         f"{pk.amplitude:.5g}", "—" if fap is None else f"{fap:.2g}", label])
        fill_table(self.peaks_table, ["#", "Période (ans)", "Période (j)", f"Amplitude ({unit})", "FAP", "Identification"],
                   rows)
        truth_rows = [[tr.name, f"{tr.period:.6g}", f"{tr.period / units.DAY_YR:.6g}", f"{tr.e:.3f}",
                       f"{tr.rv_semi_amplitude:.5g}", f"{tr.astrometric_amplitude:.4g}",
                       "direct" if tr.direction > 0 else "rétrograde"] for tr in res.truths]
        fill_table(self.truth_table, ["Planète", "P (ans)", "P (j)", "e", "K (m/s)", "Astrom. (UA)", "Sens"], truth_rows)
