"""Point d'entrée de l'exécutable autonome (PyInstaller). En développement : ``python -m gravsim``."""

import sys

from gravsim.gui.main_window import main

if __name__ == "__main__":
    sys.exit(main())
