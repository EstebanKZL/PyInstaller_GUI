import os
import subprocess
import sys

import pytest

from pyinstaller_gui.core.command import build_spec


def _compiles(text):
    compile(text, "test.spec", "exec")
    return True


@pytest.mark.parametrize("onefile", [False, True])
def test_spec_valido_con_rutas_windows(cfg, onefile):
    # \U, \N, \x en rutas Windows rompían el .spec anterior (escapes inválidos)
    cfg.script = "C:\\Users\\x\\Nuevo\\main.py"
    cfg.add_data = [("C:\\Users\\x\\datos.txt", "."), ("C:\\x\\N.json", "conf")]
    cfg.hidden_imports = ["PIL", "requests"]
    cfg.exclude_modules = ["tkinter"]
    cfg.onefile = onefile
    cfg.runtime_tmpdir = True
    spec = build_spec(cfg)
    assert _compiles(spec)
    assert ("COLLECT(" in spec) is (not onefile)
    assert "exclude_binaries=True" in spec if not onefile else "a.binaries,\n    a.datas," in spec
    assert ("runtime_tmpdir=" in spec) is onefile
    assert "collect_all('PIL')" in spec or "collect_all(_pkg)" in spec


def test_spec_refleja_opciones(cfg):
    cfg.noconsole, cfg.uac_admin, cfg.debug, cfg.noupx, cfg.optimize = False, True, True, True, True
    spec = build_spec(cfg)
    for frag in ("console=True", "uac_admin=True", "debug=True", "upx=False", "optimize=1"):
        assert frag in spec


def test_spec_nombre_por_defecto_es_el_script(cfg):
    assert "name='main'" in build_spec(cfg)


@pytest.mark.slow
@pytest.mark.parametrize("onefile", [False, True])
def test_build_real_desde_spec(cfg, project, tmp_path, onefile):
    pytest.importorskip("PyInstaller")
    cfg.name, cfg.onefile, cfg.noconsole = "Hola App", onefile, False
    spec_path = project / "hola.spec"
    spec_path.write_text(build_spec(cfg), encoding="utf-8")
    dist = tmp_path / "dist"
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(dist),
                        "--workpath", str(tmp_path / "build"), str(spec_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-3000:]
    exe = "Hola App.exe" if sys.platform == "win32" else "Hola App"
    path = dist / exe if onefile else dist / "Hola App" / exe
    assert os.path.isfile(path)
    assert "HOLA-TEST" in subprocess.run([str(path)], capture_output=True, text=True, timeout=120).stdout
