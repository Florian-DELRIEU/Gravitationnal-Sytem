"""Crée « Simulateur Gravitationnel.app » : un lanceur macOS à double-cliquer.

À exécuter une fois, avec l'environnement conda actif :
    python scripts/creer_app.py [dossier_de_destination]

L'application ne contient pas Python : elle lance le Python de l'environnement qui a servi à la créer
(le paquet gravsim y est installé en mode éditable, donc les modifications du code sont prises en compte).
Si l'environnement conda est supprimé ou déplacé, relancer ce script.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_NAME = "Simulateur Gravitationnel"
BUNDLE_ID = "local.gravsim.simulateur"


def draw_icon(path: Path, size: int = 1024) -> None:
    """Dark rounded square with a star, an elliptical orbit and a planet."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPen

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (must stay alive while painting)
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#0b0d14"))
    margin = size * 0.06
    p.drawRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin), size * 0.2, size * 0.2)
    c = QPointF(size / 2, size / 2)
    p.save()
    p.translate(c)
    p.rotate(-25)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#4cc9f0"), size * 0.012))
    p.drawEllipse(QRectF(-size * 0.34, -size * 0.2, size * 0.68, size * 0.4))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#4cc9f0")))
    p.drawEllipse(QPointF(size * 0.34 * 0.5, -size * 0.2 * 0.866), size * 0.04, size * 0.04)
    p.restore()
    p.setBrush(QColor("#ffd166"))
    p.drawEllipse(QPointF(c.x() - size * 0.06, c.y()), size * 0.085, size * 0.085)
    p.end()
    img.save(str(path))


def make_icns(png: Path, icns: Path) -> bool:
    """Build an .icns with the system's iconutil. Returns False if unavailable."""
    if shutil.which("iconutil") is None:
        return False
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    base = QImage(str(png))
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icone.iconset"
        iconset.mkdir()
        for s in (16, 32, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                px = s * scale
                base.scaled(px, px, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation).save(str(iconset / f"icon_{s}x{s}{suffix}.png"))
        return subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)]).returncode == 0


def build(destination: Path) -> Path:
    app = destination / f"{APP_NAME}.app"
    if app.exists():
        shutil.rmtree(app)
    macos, resources = app / "Contents" / "MacOS", app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    python = Path(sys.executable).resolve()
    log = "$HOME/Library/Logs/gravsim.log"
    launcher = macos / "lancer"
    launcher.write_text(
        "#!/bin/bash\n"
        "# Lanceur généré par scripts/creer_app.py\n"
        f'mkdir -p "$HOME/Library/Logs"\n'
        f'exec "{python}" -m gravsim >> "{log}" 2>&1\n',
        encoding="utf-8")
    launcher.chmod(0o755)

    png = resources / "icone.png"
    draw_icon(png)
    has_icon = make_icns(png, resources / "icone.icns")
    png.unlink()

    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "CFBundleExecutable": "lancer",
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    }
    if has_icon:
        info["CFBundleIconFile"] = "icone"
    with open(app / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump(info, fh)
    # Make Finder pick up the new icon.
    app.touch()
    return app


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    destination = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else root
    destination.mkdir(parents=True, exist_ok=True)
    app = build(destination)
    print(f"Application créée : {app}")
    print(f"Python utilisé    : {Path(sys.executable).resolve()}")
    print("Double-cliquez dessus, ou glissez-la dans le Dock / le dossier Applications.")
    print("En cas de problème, le journal est dans ~/Library/Logs/gravsim.log")


if __name__ == "__main__":
    main()
