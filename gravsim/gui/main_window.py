"""Main window of the simulator."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut, QTextCharFormat
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from ..core.scenario import Scenario, list_presets, load_preset
from ..analysis import export
from .analysis_tabs import AnalysisPage
from .body_panel import BodyEditor, BodyListPanel, ImpulsePanel
from .controller import SimulationController
from .spectral_tab import SpectrumPage
from .time_controls import IntegrationPanel, TimeControls
from .view_panel import InfoPanel, ViewPanel
from .viewer import SimViewer, frame_spec
from .widgets import ViewSettings, format_time

TICK_MS = 25
_LEVEL_COLORS = {"info": "#c8d0e0", "warning": "#ffb454", "collision": "#ff6b6b", "error": "#ff4d4d"}

_STYLE = """
QMainWindow, QDockWidget, QWidget { font-size: 12px; }
QDockWidget::title { padding: 4px; background: #1b2030; color: #e6e9f2; }
QLabel#banner { background: #8b1a1a; color: white; padding: 6px 10px; font-weight: bold; }
"""


def _preset_titles() -> dict[str, str]:
    folder = Path(__file__).resolve().parent.parent / "presets"
    titles = {}
    for stem in list_presets():
        try:
            titles[stem] = json.loads((folder / f"{stem}.json").read_text(encoding="utf-8")).get("name", stem)
        except (OSError, ValueError):
            titles[stem] = stem
    return titles


class MainWindow(QMainWindow):
    def __init__(self, scenario: Scenario | None = None):
        super().__init__()
        self.setWindowTitle("Simulateur gravitationnel 2D")
        self.resize(1500, 920)
        self.setStyleSheet(_STYLE)

        self.ctrl = SimulationController(scenario if scenario is not None else load_preset("soleil_jupiter"))
        self.view = ViewSettings()
        self.viewer = SimViewer(self.ctrl, self.view)
        self.controls = TimeControls(self.ctrl)
        self.info = InfoPanel(self.ctrl)
        self._presets = _preset_titles()

        self.banner = QLabel()
        self.banner.setObjectName("banner")
        dismiss = QPushButton("OK")
        dismiss.setFixedWidth(50)
        dismiss.clicked.connect(lambda: self.banner_row.setVisible(False))
        self.banner_row = QWidget()
        row = QHBoxLayout(self.banner_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.banner, 1)
        row.addWidget(dismiss)
        self.banner_row.setVisible(False)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.banner_row)
        lay.addWidget(self.viewer, 1)
        lay.addWidget(self.controls)
        self.analysis = AnalysisPage(self.ctrl, self.view)
        self.spectrum = SpectrumPage(self.ctrl)
        self.pages = QTabWidget()
        self.pages.addTab(central, "Simulation")
        self.pages.addTab(self.analysis, "Analyse")
        self.pages.addTab(self.spectrum, "Spectre")
        self.setCentralWidget(self.pages)
        self._dock_memory: dict[QDockWidget, bool] = {}
        self._previous_page = 0

        self._build_docks()
        self._build_menus()
        self._build_status()
        self._build_shortcuts()

        self.pages.currentChanged.connect(self._on_page_changed)
        ctrl = self.ctrl
        ctrl.eventLogged.connect(self._log)
        ctrl.collisionOccurred.connect(self._on_collision)
        ctrl.reset.connect(lambda: self.banner_row.setVisible(False))
        ctrl.changed.connect(self._update_status)
        ctrl.scenarioReplaced.connect(self._update_title)
        self.viewer.bodyClicked.connect(ctrl.select)
        self._update_title()
        self._update_status()

        self._last_tick = time.perf_counter()
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start()

    # --- construction ------------------------------------------------------------
    def _dock(self, title: str, widget: QWidget, area) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(area, dock)
        return dock

    def _build_docks(self) -> None:
        # left: bodies + presets
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        preset_box = QGroupBox("Scénario")
        pl = QHBoxLayout(preset_box)
        self.preset_combo = QComboBox()
        for stem, title in self._presets.items():
            self.preset_combo.addItem(title, stem)
        current = self.ctrl.scenario.name
        for k in range(self.preset_combo.count()):
            if self.preset_combo.itemText(k) == current:
                self.preset_combo.setCurrentIndex(k)
        load = QPushButton("Charger")
        load.clicked.connect(lambda: self.load_preset(self.preset_combo.currentData()))
        pl.addWidget(self.preset_combo, 1)
        pl.addWidget(load)
        ll.addWidget(preset_box)
        ll.addWidget(BodyListPanel(self.ctrl), 1)
        ll.addWidget(self.info)
        self.left_dock = self._dock("Corps", left, Qt.DockWidgetArea.LeftDockWidgetArea)

        # right: tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(BodyEditor(self.ctrl), "Corps")
        self.tabs.addTab(ImpulsePanel(self.ctrl), "Poussées")
        self.tabs.addTab(ViewPanel(self.ctrl, self.view), "Vue")
        self.tabs.addTab(IntegrationPanel(self.ctrl), "Intégration")
        self.right_dock = self._dock("Propriétés", self.tabs, Qt.DockWidgetArea.RightDockWidgetArea)

        # bottom: journal
        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMaximumBlockCount(2000)
        self.journal.setMaximumHeight(130)
        self.journal.setStyleSheet("background: #0b0d14; color: #c8d0e0;")
        self.bottom_dock = self._dock("Journal des événements", self.journal, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.resizeDocks([self.left_dock, self.right_dock], [300, 380], Qt.Orientation.Horizontal)

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&Fichier")
        for text, slot, shortcut in (("Ouvrir un scénario…", self.open_scenario, QKeySequence.StandardKey.Open),
                                     ("Enregistrer le scénario…", self.save_scenario, QKeySequence.StandardKey.Save),
                                     ("Exporter la trajectoire (.npz)…", self.export_trajectory, None),
                                     ("Exporter l'analyse (.csv)…", self.export_analysis, None)):
            act = QAction(text, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(slot)
            file_menu.addAction(act)
        file_menu.addSeparator()
        quit_act = QAction("Quitter", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        presets = bar.addMenu("&Presets")
        for stem, title in self._presets.items():
            act = QAction(title, self)
            act.triggered.connect(lambda _checked=False, s=stem: self.load_preset(s))
            presets.addAction(act)

        view_menu = bar.addMenu("&Affichage")
        for dock in (self.left_dock, self.right_dock, self.bottom_dock):
            view_menu.addAction(dock.toggleViewAction())

        help_menu = bar.addMenu("&Aide")
        about = QAction("À propos", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _build_status(self) -> None:
        self.status_time = QLabel()
        self.status_rate = QLabel()
        self.status_fidelity = QLabel()
        self.status_frame = QLabel()
        sb = self.statusBar()
        for w in (self.status_time, self.status_rate, self.status_fidelity, self.status_frame):
            sb.addPermanentWidget(w)

    def _build_shortcuts(self) -> None:
        for key, slot in (("Space", self.ctrl.toggle), ("S", self.ctrl.step), ("R", self.ctrl.rebuild),
                          ("L", self.ctrl.go_live)):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(slot)

    # --- slots ----------------------------------------------------------------------
    def _on_timer(self) -> None:
        now = time.perf_counter()
        dt, self._last_tick = now - self._last_tick, now
        self.ctrl.tick(min(dt, 0.1))

    def _on_page_changed(self, index: int) -> None:
        """Give the analysis pages the room: the side panels only matter on the simulation page.

        The Vue panel stays available on "Analyse" (it chooses the reference frame); "Spectre" has its own controls.
        """
        docks = (self.left_dock, self.right_dock, self.bottom_dock)
        if self._previous_page == 0 and index != 0:
            self._dock_memory = {d: not d.isHidden() for d in docks}
        self._previous_page = index
        if index == 0:
            for dock, visible in self._dock_memory.items():
                dock.setVisible(visible)
            return
        self.left_dock.hide()
        self.bottom_dock.hide()
        self.right_dock.setVisible(self._dock_memory.get(self.right_dock, True) if index == 1 else False)

    def _log(self, text: str, level: str) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(_LEVEL_COLORS.get(level, "#c8d0e0")))
        cursor = self.journal.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        self.journal.verticalScrollBar().setValue(self.journal.verticalScrollBar().maximum())
        if level in ("warning", "error"):
            self.statusBar().showMessage(text, 8000)

    def _on_collision(self, ev) -> None:
        names = self.ctrl.scenario.names
        self.banner.setText(f"⚠ Collision : {names[ev.i]} – {names[ev.j]} à t = {format_time(ev.t)}"
                            + ("  — simulation en pause" if self.ctrl.pause_on_collision else ""))
        self.banner_row.setVisible(True)

    def _update_status(self) -> None:
        ctrl = self.ctrl
        sim = ctrl.sim
        if sim is None:
            self.status_time.setText("  Simulation indisponible  ")
            self.status_rate.setText("")
            self.status_fidelity.setText("")
            return
        self.status_time.setText(f"  t = {format_time(ctrl.view_time)} · {len(sim.trajectory)} échantillons  ")
        rate = ctrl.achieved_rate if ctrl.playing else 0.0
        limited = ctrl.playing and rate > 0 and rate < 0.9 * ctrl.speed
        self.status_rate.setText(f"  vitesse réelle {rate:.3g} ans/s{' (limitée par le calcul)' if limited else ''}  "
                                 if ctrl.playing else "")
        drift = ctrl.energy_drift()
        if drift is None:
            self.status_fidelity.setText("")
        else:
            color = "#6ad48f" if abs(drift) < 1e-6 else ("#ffb454" if abs(drift) < 1e-3 else "#ff6b6b")
            self.status_fidelity.setText(f"  ΔE/E = <span style='color:{color}'>{drift:.2e}</span>  ")
        self.status_frame.setText(f"  référentiel : {self.viewer.last_frame_label}  ")

    def _update_title(self) -> None:
        name = self.ctrl.scenario.name
        self.setWindowTitle(f"Simulateur gravitationnel 2D — {name}" if name else "Simulateur gravitationnel 2D")

    # --- files ------------------------------------------------------------------------
    def load_preset(self, stem: str) -> None:
        self.ctrl.set_scenario(load_preset(stem))
        self.ctrl.log(f"Preset chargé : {self.ctrl.scenario.name}")

    def open_scenario(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un scénario", "", "Scénario (*.json)")
        if not path:
            return
        try:
            self.ctrl.set_scenario(Scenario.load(path))
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Scénario invalide", str(exc))
            return
        self.ctrl.log(f"Scénario ouvert : {path}")

    def save_scenario(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le scénario", "scenario.json", "Scénario (*.json)")
        if path:
            self.ctrl.scenario.save(path)
            self.ctrl.log(f"Scénario enregistré : {path}")

    def export_trajectory(self) -> None:
        traj = self.ctrl.traj
        if traj is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter la trajectoire", "trajectoire.npz", "NumPy (*.npz)")
        if path:
            traj.save_npz(path)
            self.ctrl.log(f"Trajectoire exportée : {path} ({len(traj)} échantillons)")

    def export_analysis(self) -> None:
        """Table of positions, velocities, energies, distances and drifts in the frame chosen in the Vue tab."""
        traj = self.ctrl.traj
        if traj is None:
            return
        step = 1
        if len(traj) > 200_000:
            step, ok = QInputDialog.getInt(self, "Export CSV", f"{len(traj):,} échantillons : en garder un sur…".replace(",", " "),
                                           max(1, len(traj) // 100_000), 1, 10_000)
            if not ok:
                return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter l'analyse", "analyse.csv", "CSV (*.csv)")
        if not path:
            return
        spec = frame_spec(self.view, self.ctrl.scenario)
        main_path, events_path = export.export_csv(traj, path, frame=spec, step=step)
        extra = f" et {events_path.name}" if events_path else ""
        self.ctrl.log(f"Analyse exportée : {main_path}{extra}")

    def _about(self) -> None:
        QMessageBox.about(
            self, "À propos",
            "<b>Simulateur gravitationnel 2D à N corps</b><br>Unités internes : UA, M☉, an (G = 4π²).<br><br>"
            "Raccourcis : <b>Espace</b> lecture/pause · <b>S</b> pas · <b>R</b> réinitialiser · <b>L</b> direct.<br>"
            "Clic sur un corps pour le sélectionner ; molette pour zoomer, glisser pour déplacer.")


def _autotest(app: QApplication, window: MainWindow) -> int:
    """Headless self-check, meant for built executables: presets, simulation, rendering. Exit code 0 = OK."""
    ctrl = window.ctrl
    problems = []
    stems = list_presets()
    if len(stems) < 5:
        problems.append(f"presets introuvables ({len(stems)})")
    for stem in stems:
        try:
            ctrl.set_scenario(load_preset(stem))
            ctrl.budget = 30.0
            ctrl.advance_to(ctrl.scenario.t0 + 5 * ctrl.sim.output_dt)
        except Exception as exc:  # report every failing preset, then fail
            problems.append(f"{stem}: {type(exc).__name__}: {exc}")
    for integrator in ("dop853", "yoshida4", "leapfrog"):
        ctrl.set_scenario(load_preset("soleil_jupiter"))
        ctrl.settings.integrator = integrator
        ctrl.rebuild()
        ctrl.budget = 30.0
        ctrl.advance_to(1.0)
        drift = ctrl.energy_drift()
        if ctrl.sim is None or ctrl.sim.t < 1.0 or drift is None or abs(drift) > 1e-6:
            problems.append(f"{integrator}: simulation incorrecte (dérive {drift})")
    # Analysis, spectrum and export: these pull in scipy.signal / scipy.optimize, which a frozen build must bundle.
    try:
        import tempfile
        from pathlib import Path

        from ..analysis.pipeline import ObservationSettings, run_observation

        ctrl.set_scenario(load_preset("soleil_jupiter"))
        ctrl.budget = 60.0
        ctrl.advance_to(72.0)
        result = run_observation(ctrl.traj, ObservationSettings("Soleil"))
        if not result.labels or result.labels[0] != "Jupiter":
            problems.append(f"spectre : pic principal mal identifié ({result.labels[:1]})")
        window.show()
        for page in (1, 2):
            window.pages.setCurrentIndex(page)
            if page == 1:
                for tab in range(window.analysis.tabs.count()):
                    window.analysis.tabs.setCurrentIndex(tab)
                    window.analysis.refresh(force=True)
                    if "Erreur" in window.analysis.header.text():
                        problems.append(f"analyse : {window.analysis.header.text()}")
            else:
                window.spectrum.compute()
                found = window.spectrum.detection.run()
                if found is None or found.count != 1:
                    problems.append(f"détection : {None if found is None else found.count_text()} au lieu d'1 planète")
            app.processEvents()
            if window.grab().isNull():
                problems.append(f"rendu de la page {page} impossible")
        with tempfile.TemporaryDirectory() as tmp:
            export.export_csv(ctrl.traj, Path(tmp) / "analyse.csv")
            if not (Path(tmp) / "analyse.csv").exists():
                problems.append("export CSV absent")
    except Exception as exc:
        problems.append(f"analyse/spectre/export : {type(exc).__name__}: {exc}")
    window.show()
    app.processEvents()
    if window.grab().isNull():
        problems.append("rendu de la fenêtre impossible")
    print("AUTOTEST " + ("OK" if not problems else "ÉCHEC : " + " | ".join(problems)))
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    autotest = "--autotest" in argv
    if autotest:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"  # must be set before the QApplication exists
        argv.remove("--autotest")
    app = QApplication.instance() or QApplication(argv)
    window = MainWindow()
    if autotest:
        window.timer.stop()
        return _autotest(app, window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
