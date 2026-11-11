"""Backend Nuitka y convención de nombres de los artefactos."""

import os
import struct
import sys

import pytest

from pyinstaller_gui.core.builder import BuildRunner
from pyinstaller_gui.core.command import build_command
from pyinstaller_gui.core.config import BuildConfig
from pyinstaller_gui.core.naming import (
    artifact_app_name, artifact_name, binary_arch, clean_version, is_artifact_of, os_label,
)
from pyinstaller_gui.core.nuitka_command import normalize_output, output_filename, standalone_dir
from pyinstaller_gui.core.venv_build import fingerprint


@pytest.fixture
def ncfg(cfg):
    cfg.backend = "nuitka"
    return cfg


# ── Comando ──────────────────────────────────────────────────────────────
def test_comando_basico(ncfg):
    cmd, notes = build_command(ncfg)
    assert cmd[:4] == [sys.executable, "-m", "nuitka", "--assume-yes-for-downloads"]
    assert "--standalone" in cmd and "--onefile" not in cmd and "--remove-output" in cmd
    assert f"--output-dir={os.path.join(ncfg.workspace, 'dist')}" in cmd
    assert f"--output-filename={output_filename(ncfg)}" in cmd
    assert cmd[-1] == ncfg.script
    assert not any(c.startswith("--distpath") or c.startswith("--specpath") for c in cmd)
    assert any("Nuitka compila a C" in n for n in notes)


def test_onefile_y_tmpdir(ncfg):
    ncfg.onefile, ncfg.runtime_tmpdir = True, True
    cmd, _ = build_command(ncfg)
    assert "--onefile" in cmd and "--standalone" not in cmd
    assert f"--onefile-tempdir-spec={{TEMP}}/{ncfg.app_name}" in cmd


def test_opciones_traducidas(ncfg, project, tmp_path):
    data_dir = project / "assets"
    data_dir.mkdir()
    data_file = project / "config.json"
    data_file.write_text("{}", encoding="utf-8")
    ncfg.hidden_imports = ["yaml", "yaml"]
    ncfg.exclude_modules = ["tkinter.test"]
    ncfg.collect_all = ["PySide6", "certifi"]
    ncfg.collect_data = ["certifi"]
    ncfg.copy_metadata = ["requests"]
    ncfg.add_data = [(str(data_dir), "."), (str(data_file), "conf")]
    ncfg.optimize = True
    cmd, notes = build_command(ncfg)
    assert cmd.count("--include-module=yaml") == 1
    assert "--nofollow-import-to=tkinter.test" in cmd
    assert "--enable-plugin=pyside6" in cmd
    assert "--include-package=PySide6" not in cmd          # lo resuelve el plugin
    assert "--include-package=certifi" in cmd and "--include-package-data=certifi" in cmd
    assert "--include-distribution-metadata=requests" in cmd
    assert f"--include-data-dir={data_dir}=assets" in cmd
    assert f"--include-data-files={data_file}=conf/config.json" in cmd
    assert "--python-flag=-O" in cmd
    assert any("pyside6" in n for n in notes)


def test_plugins_detectados_en_el_script(ncfg, project):
    (project / "main.py").write_text("import tkinter\nfrom PySide2.QtWidgets import QApplication\n", encoding="utf-8")
    cmd, _ = build_command(ncfg)
    assert "--enable-plugin=pyside2" in cmd and "--enable-plugin=tk-inter" in cmd


def test_opciones_solo_pyinstaller_avisan(ncfg):
    ncfg.strip, ncfg.noupx = True, True
    cmd, notes = build_command(ncfg)
    assert "--strip" not in cmd and "--noupx" not in cmd
    assert any("strip, noupx" in n for n in notes)


@pytest.mark.skipif(sys.platform != "win32", reason="opciones de Windows")
def test_windows_consola_icono_y_version(ncfg, project):
    ico = project / "app.ico"
    ico.write_bytes(b"\0\0\1\0")
    ncfg.icon = str(ico)
    ncfg.uac_admin = True
    ncfg.version_info, ncfg.app_version, ncfg.company = True, "V2.3.4-beta", "ACME"
    cmd, _ = build_command(ncfg)
    assert "--windows-console-mode=disable" in cmd and "--windows-uac-admin" in cmd
    assert f"--windows-icon-from-ico={ico}" in cmd
    assert "--file-version=2.3.4" in cmd and "--company-name=ACME" in cmd
    ncfg.debug = True
    assert "--windows-console-mode=force" in build_command(ncfg)[0]


def test_perfil_conserva_el_backend(ncfg, tmp_path):
    path = tmp_path / "p.json"
    ncfg.save(str(path))
    assert BuildConfig.load(str(path)).backend == "nuitka"
    assert BuildConfig.from_profile({"backend": "otro"}).backend == "pyinstaller"
    assert BuildConfig.from_profile({}).backend == "pyinstaller"   # perfiles viejos


def test_venv_aislado_distinto_por_backend(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("requests\n", encoding="utf-8")
    assert fingerprint(str(req), "3.12.1") == fingerprint(str(req), "3.12.1", "pyinstaller")
    assert fingerprint(str(req), "3.12.1", "nuitka") != fingerprint(str(req), "3.12.1")


# ── Salida de Nuitka ─────────────────────────────────────────────────────
def test_normaliza_la_carpeta_standalone(ncfg, project):
    ncfg.name = "Mi App"
    src = standalone_dir(ncfg)
    os.makedirs(src)
    open(os.path.join(src, output_filename(ncfg)), "wb").close()
    logs = []
    assert normalize_output(ncfg, logs.append)
    assert not os.path.exists(src)
    assert os.path.isfile(os.path.join(ncfg.dist_dir, "Mi App", output_filename(ncfg)))
    assert normalize_output(ncfg, logs.append)          # idempotente


def test_build_falla_si_nuitka_no_deja_resultado(ncfg):
    # Un "compilador" que termina bien pero no genera nada
    cmd = [sys.executable, "-c", "print('Nuitka: Starting Python compilation')"]
    logs = []
    ok, _ = BuildRunner(ncfg, cmd, log=logs.append).run()
    assert not ok
    assert any("no se encontró el resultado" in line for line in logs)


# ── Convención de nombres ────────────────────────────────────────────────
def test_nombres_de_artefactos():
    assert artifact_app_name("Mi App 2") == "MiApp2"
    assert clean_version("V5.1.0") == "5.1.0" and clean_version("") == "0.0.0"
    if sys.platform == "win32":
        assert os_label("windows7") == "win7" and os_label("windows") == "win" and os_label("linux") == "win"
    else:
        assert os_label("windows7") == os_label("linux") == ("macos" if sys.platform == "darwin" else "linux")
    assert artifact_name("EmuLinks", "6.6.0", "win", "x64", "setup", "exe") == "EmuLinks-6.6.0-win-x64-setup.exe"
    assert artifact_name("EmuLinks", "v6.6.0", "win7", "x86", "portable", ".zip") == \
        "EmuLinks-6.6.0-win7-x86-portable.zip"
    assert artifact_name("EmuLinks", "6.6.0", "linux", "i686", ext="AppImage") == "EmuLinks-6.6.0-linux-i686.AppImage"
    assert is_artifact_of("EmuLinks-6.6.0-linux-x86_64.AppImage", "EmuLinks")
    assert not is_artifact_of("EmuLinks-Pro-6.6.0-win-x64-setup.exe", "EmuLinks")


def _pe(machine):
    head = bytearray(0x40)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x40)
    return bytes(head) + b"PE\0\0" + struct.pack("<H", machine)


def _elf(machine):
    head = bytearray(20)
    head[:4], head[5] = b"\x7fELF", 1
    struct.pack_into("<H", head, 18, machine)
    return bytes(head) + bytes(44)


@pytest.mark.parametrize("content,arch", [
    (_pe(0x8664), "x64"), (_pe(0x014C), "x86"), (_pe(0xAA64), "arm64"),
    (_elf(62), "x86_64"), (_elf(3), "i686"), (b"texto", ""),
])
def test_arquitectura_del_binario(tmp_path, content, arch):
    exe = tmp_path / "app"
    exe.write_bytes(content)
    assert binary_arch(str(exe)) == arch
    assert binary_arch(str(tmp_path / "no-existe")) == ""
