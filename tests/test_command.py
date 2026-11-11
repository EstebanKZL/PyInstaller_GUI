import os
import sys

import pytest

from pyinstaller_gui.core.command import build_command, collect_all_packages
from pyinstaller_gui.core.process import command_to_str

SEP = ";" if sys.platform == "win32" else ":"


def test_basico(cfg):
    cmd, _ = build_command(cfg)
    assert cmd[:4] == [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    assert "--clean" in cmd and "--onedir" in cmd and "--noconsole" in cmd
    assert cmd[-1] == cfg.script
    assert f"--distpath={os.path.join(cfg.workspace, 'dist')}" in cmd
    assert f"--workpath={os.path.join(cfg.workspace, 'build')}" in cmd
    assert f"--specpath={cfg.workspace}" in cmd
    assert "-I" not in cmd   # -I ignora paquetes instalados con pip --user


@pytest.mark.parametrize("attr,flag", [
    ("debug", "--debug=all"), ("strip", "--strip"), ("noupx", "--noupx"),
    ("optimize", "--optimize=1"), ("bootloader_ignore", "--bootloader-ignore-signals"),
    ("uac_admin", "--uac-admin"),
])
def test_flags_booleanos(cfg, attr, flag):
    assert flag not in build_command(cfg)[0]
    setattr(cfg, attr, True)
    assert flag in build_command(cfg)[0]


def test_onefile_y_runtime_tmpdir(cfg):
    cfg.runtime_tmpdir = True
    cmd, notes = build_command(cfg)
    assert not any(c.startswith("--runtime-tmpdir") for c in cmd)
    assert any("solo aplica a --onefile" in n for n in notes)

    cfg.onefile = True
    cfg.runtime_tmpdir_path = "C:\\cache app"
    cmd, _ = build_command(cfg)
    assert "--onefile" in cmd and "--runtime-tmpdir=C:\\cache app" in cmd


def test_runtime_tmpdir_por_defecto_usa_nombre_app(cfg):
    cfg.onefile, cfg.runtime_tmpdir, cfg.name = True, True, "Mi App"
    tmp = next(c for c in build_command(cfg)[0] if c.startswith("--runtime-tmpdir="))
    assert tmp.endswith(os.path.join("", "Mi App"))


def test_icono_existente_e_inexistente(cfg, project):
    ico = project / "icono.ico"
    ico.write_bytes(b"\x00\x00\x01\x00")
    cfg.icon = str(ico)
    cmd, _ = build_command(cfg)
    assert f"--icon={ico}" in cmd and f"--add-data={ico}{SEP}." in cmd

    cfg.icon = str(project / "no_existe.ico")
    cmd, notes = build_command(cfg)
    assert not any(c.startswith("--icon") for c in cmd)
    assert any("no existe" in n for n in notes)


def test_hidden_imports_sin_duplicados_y_collect_all(cfg):
    cfg.hidden_imports = ["requests", "PySide6.QtCore", "requests", "PIL"]
    cmd, _ = build_command(cfg)
    assert cmd.count("--hidden-import=requests") == 1
    assert "--collect-all=PySide6" in cmd and "--collect-all=PIL" in cmd


def test_collect_all_packages():
    assert collect_all_packages(["PyQt5.QtGui", "PyQt5", "numpy", "PIL._tkinter_finder"]) == ["PyQt5", "PIL"]


def test_add_data_con_destino(cfg, project):
    cfg.add_data = [(str(project / "a.txt"), "."), (str(project / "img"), "assets/img")]
    cmd, _ = build_command(cfg)
    assert f"--add-data={project / 'img'}{SEP}assets/img" in cmd


def test_excludes_combinados_y_ordenados(cfg):
    cfg.exclude_modules = ["tkinter", "test"]
    cfg.dep_excludes = ["PIL", "tkinter"]
    cmd, _ = build_command(cfg)
    assert [c for c in cmd if c.startswith("--exclude-module")] == [
        "--exclude-module=PIL", "--exclude-module=test", "--exclude-module=tkinter"]


def test_flags_extra(cfg):
    cfg.extra_flags = '--runtime-hook rh.py --add-binary "lib x.dll;."'
    cmd, _ = build_command(cfg)
    i = cmd.index("--runtime-hook")
    assert cmd[i:i + 4] == ["--runtime-hook", "rh.py", "--add-binary", cmd[i + 3]]
    assert "lib x.dll;." in cmd[i + 3]
    cfg.extra_flags = '--name "sin cerrar'
    if sys.platform != "win32":
        with pytest.raises(ValueError):
            build_command(cfg)


def test_command_to_str_cita_rutas_con_espacios():
    s = command_to_str(["python", "-m", "PyInstaller", os.path.join("Cloud CODE", "main.py")])
    assert '"' in s or "'" in s
