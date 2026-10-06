"""Smoke tests: the package and its dependencies import correctly."""

import importlib
import subprocess
import sys

import pytest


def test_package_imports():
    import gravsim

    assert gravsim.__version__


@pytest.mark.parametrize("module", ["gravsim.core", "gravsim.analysis", "gravsim.presets"])
def test_headless_subpackages_import(module):
    importlib.import_module(module)


@pytest.mark.parametrize("module", ["numpy", "scipy.integrate", "scipy.signal", "matplotlib"])
def test_scientific_dependencies(module):
    importlib.import_module(module)


@pytest.mark.parametrize("module", ["PySide6.QtWidgets", "pyqtgraph"])
def test_gui_dependencies(module):
    importlib.import_module(module)


def test_core_does_not_import_qt():
    """core/ and analysis/ must stay usable without Qt (scripts, campaigns, tests).

    Checked in a fresh interpreter, since other tests load Qt in this one.
    """
    code = (
        "import sys, pkgutil, importlib, gravsim.core, gravsim.analysis\n"
        "for pkg in (gravsim.core, gravsim.analysis):\n"
        "    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + '.'):\n"
        "        importlib.import_module(m.name)\n"
        "qt = [n for n in sys.modules if n.startswith(('PySide6', 'pyqtgraph'))]\n"
        "assert not qt, qt\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
