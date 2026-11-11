import sys

import pytest

from pyinstaller_gui.core.packages import pick_import_name, query_packages, version_satisfies_fallback
from pyinstaller_gui.core.requirements import parse_requirement_full


@pytest.mark.parametrize("line,expected", [
    ("requests", ("requests", "", "requests")),
    ("requests>=2.28 # http", ("requests", ">=2.28", "requests>=2.28")),
    ("uvicorn[standard]==0.30", ("uvicorn", "==0.30", "uvicorn==0.30")),
    ("pywin32; sys_platform == 'win32'", ("pywin32", "", "pywin32")),
    ("# comentario", None), ("-r otros.txt", None), ("", None),
])
def test_parse_requirement(line, expected):
    assert parse_requirement_full(line) == expected


@pytest.mark.parametrize("pkg,modules,expected", [
    ("Pillow", ["PIL"], "PIL"), ("beautifulsoup4", ["bs4"], "bs4"),
    ("opencv-python", ["cv2"], "cv2"), ("PyYAML", ["_yaml", "yaml"], "yaml"),
    ("pyinstaller", ["PyInstaller"], "PyInstaller"), ("python-dateutil", [], "python_dateutil"),
])
def test_pick_import_name(pkg, modules, expected):
    assert pick_import_name(pkg, modules) == expected


def test_version_fallback():
    assert version_satisfies_fallback("==1.2", "1.2")
    assert not version_satisfies_fallback("==1.2", "1.3")
    assert version_satisfies_fallback(">=1.0", "0.1")   # sin 'packaging' no se puede saber → no alarmar


def test_query_packages_python_real():
    info = query_packages(sys.executable, [("pytest", ">=1.0"), ("pytest", "<1.0"), ("paquete-inexistente-xyz", "")])
    assert info["pytest"]["version"]
    assert "pytest" in info["pytest"]["modules"] or "_pytest" in info["pytest"]["modules"]
    assert not info["paquete-inexistente-xyz"]["version"] and not info["paquete-inexistente-xyz"]["modules"]


def test_query_packages_python_invalido():
    assert query_packages("no-existe-python", [("x", "")]) == {}
