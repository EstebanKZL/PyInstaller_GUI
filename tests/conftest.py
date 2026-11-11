import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyinstaller_gui.core.config import BuildConfig  # noqa: E402


@pytest.fixture
def project(tmp_path):
    """Proyecto mínimo con espacios en la ruta (caso real: 'Cloud CODE')."""
    root = tmp_path / "Mi Proyecto"
    root.mkdir()
    script = root / "main.py"
    script.write_text("print('HOLA-TEST')\n", encoding="utf-8")
    return root


@pytest.fixture
def cfg(project):
    return BuildConfig(workspace=str(project), script=str(project / "main.py"), python_path=sys.executable)
