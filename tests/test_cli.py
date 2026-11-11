import os
import subprocess
import sys

import pytest

from pyinstaller_gui.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cli_muestra_comando_y_guarda_spec(cfg, tmp_path, capsys):
    profile = tmp_path / "p.json"
    cfg.save(profile)
    spec = tmp_path / "out.spec"
    assert main(["--profile", str(profile), "--spec", str(spec), "--onefile"]) == 0
    out = capsys.readouterr().out
    assert "--onefile" in out and "PyInstaller" in out
    compile(spec.read_text(encoding="utf-8"), "out.spec", "exec")


def test_cli_errores(tmp_path, capsys):
    assert main(["--profile", str(tmp_path / "no_existe.json")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text('{"script": "no_existe.py"}', encoding="utf-8")
    assert main(["--profile", str(bad)]) == 2


def test_cli_no_importa_qt():
    """El modo CLI tiene que funcionar en CI/servidores sin PySide instalado."""
    code = ("import sys; sys.modules['PySide6'] = None; sys.modules['PySide2'] = None; "
            "from pyinstaller_gui.cli import main; print('OK')")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr


@pytest.mark.slow
def test_cli_build_real(cfg, project, tmp_path):
    pytest.importorskip("PyInstaller")
    cfg.name, cfg.noconsole = "CliApp", False
    profile = tmp_path / "p.json"
    cfg.save(profile)
    r = subprocess.run([sys.executable, "-m", "pyinstaller_gui", "--profile", str(profile), "--build"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    exe = "CliApp.exe" if sys.platform == "win32" else "CliApp"
    assert os.path.isfile(project / "dist" / "CliApp" / exe)
