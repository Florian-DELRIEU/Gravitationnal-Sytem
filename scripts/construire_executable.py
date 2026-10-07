"""Construit une application autonome (sans Python à installer) pour le système courant.

    python scripts/construire_executable.py

Résultat, dans ``dist/`` :
    Windows : « Simulateur Gravitationnel\\Simulateur Gravitationnel.exe » (dossier à copier en entier)
    macOS   : « Simulateur Gravitationnel.app »
    Linux   : « Simulateur Gravitationnel/Simulateur Gravitationnel »

PyInstaller ne fait pas de compilation croisée : pour obtenir le .exe Windows, ce script doit être lancé
sous Windows (voir aussi .github/workflows/construire.yml, qui le fait automatiquement).
Prérequis : ``pip install -e ".[gui,build]"`` (ajoute PyInstaller).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from creer_app import APP_NAME, draw_icon, make_icns  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Modules lourds que l'interface n'utilise pas (matplotlib ne sert qu'aux scripts d'étude).
EXCLUDES = ["matplotlib", "tkinter", "pytest", "IPython", "PyQt5", "PyQt6", "PySide2"]


def icon_for_platform(workdir: Path) -> Path | None:
    png = workdir / "icone.png"
    draw_icon(png)
    if sys.platform == "darwin":
        icns = workdir / "icone.icns"
        return icns if make_icns(png, icns) else None
    if sys.platform == "win32":
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage

        ico = workdir / "icone.ico"
        QImage(str(png)).scaled(256, 256, Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation).save(str(ico))
        return ico if ico.exists() else None
    return png  # Linux: PyInstaller ignores the icon, harmless


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller est absent. Installez-le : pip install pyinstaller  (ou pip install -e \".[build]\")")
        return 1

    dist, build = ROOT / "dist", ROOT / "build"
    with tempfile.TemporaryDirectory() as tmp:
        icon = icon_for_platform(Path(tmp))
        cmd = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
            "--name", APP_NAME,
            "--distpath", str(dist), "--workpath", str(build), "--specpath", str(build),
            # Les presets sont lus par chemin relatif au paquet : il faut les embarquer.
            "--add-data", f"{ROOT / 'gravsim' / 'presets'}{os.pathsep}gravsim/presets",
            "--paths", str(ROOT),
            "--hidden-import", "gravsim.gui.main_window",
        ]
        for mod in EXCLUDES:
            cmd += ["--exclude-module", mod]
        if icon is not None:
            cmd += ["--icon", str(icon)]
        cmd.append(str(ROOT / "scripts" / "lancer_gui.py"))
        print("Construction (quelques minutes)…")
        code = subprocess.run(cmd, cwd=ROOT).returncode
    if code != 0:
        print("Échec de la construction.")
        return code

    if sys.platform == "darwin":
        # PyInstaller also leaves a bare executable folder next to the .app: keep only the bundle.
        shutil.rmtree(dist / APP_NAME, ignore_errors=True)
        result = dist / f"{APP_NAME}.app"
    elif sys.platform == "win32":
        result = dist / APP_NAME / f"{APP_NAME}.exe"
    else:
        result = dist / APP_NAME / APP_NAME
    print(f"\nApplication autonome : {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
