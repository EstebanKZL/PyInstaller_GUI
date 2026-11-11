import os
import subprocess
import sys

import pytest

from pyinstaller_gui.core.builder import BuildRunner
from pyinstaller_gui.core.command import build_command
from pyinstaller_gui.core.venv_build import ensure_venv, fingerprint, venv_dir_for


def test_fingerprint_cambia_con_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("requests\n", encoding="utf-8")
    a = fingerprint(str(req), "3.12.1")
    req.write_text("requests==2.0\n", encoding="utf-8")
    assert fingerprint(str(req), "3.12.1") != a
    assert fingerprint(str(req), "3.13.0") != fingerprint(str(req), "3.12.1")


def test_venv_dir(tmp_path):
    assert venv_dir_for(str(tmp_path), "3.12.4").endswith(os.path.join(".pyinstaller_gui", "venv-py3.12"))


def test_sin_workspace():
    with pytest.raises(RuntimeError):
        ensure_venv(sys.executable, "", run=lambda c: 0, log=print)


@pytest.mark.slow
def test_build_aislado_real(cfg, project):
    """Crea el venv (descarga PyInstaller con pip: necesita internet), compila y
    verifica que el segundo build reutiliza el entorno."""
    (project / "requirements.txt").write_text("# sin dependencias\n", encoding="utf-8")
    cfg.isolated_venv, cfg.noconsole, cfg.name = True, False, "Aislada"
    logs = []
    cmd, _ = build_command(cfg)
    ok, msg = BuildRunner(cfg, cmd, log=logs.append).run()
    assert ok, "\n".join(logs[-40:])
    exe = project / "dist" / "Aislada" / ("Aislada.exe" if sys.platform == "win32" else "Aislada")
    assert "HOLA-TEST" in subprocess.run([str(exe)], capture_output=True, text=True, timeout=120).stdout
    assert any("Compilando con el entorno aislado" in line for line in logs)

    logs.clear()
    ok, _ = BuildRunner(cfg, build_command(cfg)[0], log=logs.append).run()
    assert ok and any("Reutilizando entorno aislado" in line for line in logs)
