"""Comando de Nuitka a partir del mismo BuildConfig que usa PyInstaller.

Nuitka traduce el Python a C y lo compila a un binario nativo: no queda .py ni .pyc
legible en el paquete. Las opciones del formulario se traducen así:

    onedir / onefile        → --standalone / --onefile
    sin consola             → --windows-console-mode=disable (Windows)
    ícono                   → --windows-icon-from-ico / --linux-icon
    información de versión  → --company-name, --product-name, --file-version…
    hidden imports          → --include-module
    excluir módulos         → --nofollow-import-to
    collect-all             → plugin de Qt (PySide6, PyQt5…) o --include-package + datos
    collect-data            → --include-package-data
    copy-metadata           → --include-distribution-metadata
    archivos de datos       → --include-data-files / --include-data-dir

Nuitka nombra la carpeta standalone según el script (main.dist). BuildRunner la
renombra después a dist/<app>/ para que instaladores, AppImage y análisis encuentren
el resultado en el mismo lugar que con PyInstaller (ver normalize_output()).
"""

import ast
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

from ..i18n import tr

QT_PLUGINS = {"PySide6": "pyside6", "PySide2": "pyside2", "PyQt5": "pyqt5", "PyQt6": "pyqt6"}

# Opciones del formulario que no existen en Nuitka (se avisa en las notas)
PYINSTALLER_ONLY = ("strip", "noupx", "bootloader_ignore")


def _existing(path):
    path = (path or "").strip()
    return path if path and os.path.isfile(path) else ""


def _script_imports(script):
    """Módulos de primer nivel que importa el script principal (sin ejecutarlo)."""
    try:
        with open(script, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def output_filename(cfg):
    """Nombre del ejecutable que genera Nuitka (con .exe en Windows)."""
    return f"{cfg.app_name}.exe" if sys.platform == "win32" else cfg.app_name


def _version_numbers(version):
    """Nuitka exige versiones numéricas de hasta 4 partes: 'V5.1.0-beta' → '5.1.0'."""
    nums = re.findall(r"\d+", version or "")[:4]
    return ".".join(nums) if nums else "1.0.0"


def build_nuitka_command(cfg, python=None):
    """Devuelve (cmd, notas), igual que build_command(). Lanza ValueError si los flags
    extra no se pueden parsear."""
    notes = []
    python = python or cfg.python_path
    win = sys.platform == "win32"
    cmd = [python, "-m", "nuitka", "--assume-yes-for-downloads"]

    cmd.append("--onefile" if cfg.onefile else "--standalone")
    if cfg.clean:
        cmd.append("--remove-output")

    if cfg.runtime_tmpdir:
        if cfg.onefile:
            spec = cfg.runtime_tmpdir_path.strip() or "{TEMP}/" + cfg.app_name
            cmd.append(f"--onefile-tempdir-spec={spec}")
            notes.append(tr("note.tmpdir", path=spec))
        else:
            notes.append(tr("note.tmpdir_onedir"))

    if win:
        if cfg.debug:
            cmd.append("--windows-console-mode=force")
        elif cfg.noconsole:
            cmd.append("--windows-console-mode=disable")
        if cfg.uac_admin:
            cmd.append("--windows-uac-admin")
    elif cfg.debug:
        notes.append(tr("note.nuitka_debug"))
    if cfg.optimize:
        cmd.append("--python-flag=-O")

    skipped = [opt for opt in PYINSTALLER_ONLY if getattr(cfg, opt)]
    if skipped:
        notes.append(tr("note.nuitka_skipped", items=", ".join(skipped)))

    icon = _existing(cfg.icon)
    if icon and win and icon.lower().endswith(".ico"):
        cmd.append(f"--windows-icon-from-ico={icon}")
        notes.append(tr("note.icon_bundled", name=os.path.basename(icon)))
    elif cfg.icon.strip() and not icon:
        notes.append(tr("note.icon_missing", path=cfg.icon.strip()))
    if not win:
        png = _existing(cfg.appimage_icon) or (icon if icon.lower().endswith(".png") else "")
        if png:
            cmd.append(f"--linux-icon={png}")
    if icon:
        # El ícono también va como dato para que resource_path() lo encuentre en runtime
        cmd.append(f"--include-data-files={icon}={os.path.basename(icon)}")

    if cfg.version_info and win:
        ver = _version_numbers(cfg.app_version)
        cmd += [f"--file-version={ver}", f"--product-version={ver}"]
        for flag, value in (("--company-name", cfg.company), ("--product-name", cfg.product or cfg.app_name),
                            ("--file-description", cfg.description), ("--copyright", cfg.copyright)):
            if value.strip():
                cmd.append(f"{flag}={value.strip()}")
    if cfg.version_file.strip():
        notes.append(tr("note.nuitka_version_file"))

    cmd.append(f"--output-filename={output_filename(cfg)}")
    if cfg.dist_dir:
        cmd.append(f"--output-dir={cfg.dist_dir}")
    if cfg.build_path.strip():
        notes.append(tr("note.nuitka_build_dir"))

    # Plugins: bindings de Qt y tkinter detectados en el script, los hidden imports o collect-all
    imports = list(dict.fromkeys(cfg.hidden_imports))
    seen = _script_imports(cfg.script.strip()) | {i.split(".")[0] for i in imports} | set(cfg.collect_all)
    plugins = [QT_PLUGINS[b] for b in QT_PLUGINS if b in seen]
    if len(plugins) > 1:
        notes.append(tr("note.nuitka_many_qt", items=", ".join(plugins)))
        plugins = plugins[:1]
    if "tkinter" in seen:
        plugins.append("tk-inter")
    for plugin in plugins:
        cmd.append(f"--enable-plugin={plugin}")
        notes.append(tr("note.nuitka_plugin", plugin=plugin))

    for imp in imports:
        cmd.append(f"--include-module={imp}")
    for pkg in dict.fromkeys(cfg.collect_all):
        if pkg in QT_PLUGINS:
            continue   # lo resuelve el plugin, incluir el paquete entero inflaría el binario
        cmd += [f"--include-package={pkg}", f"--include-package-data={pkg}"]
    for pkg in dict.fromkeys(cfg.collect_data):
        cmd.append(f"--include-package-data={pkg}")
    for pkg in dict.fromkeys(cfg.copy_metadata):
        cmd.append(f"--include-distribution-metadata={pkg}")

    for src, dst in cfg.add_data:
        dst = (dst or ".").strip().replace("\\", "/").strip("/") or "."
        if os.path.isdir(src):
            target = os.path.basename(os.path.normpath(src)) if dst == "." else dst
            cmd.append(f"--include-data-dir={src}={target}")
        else:
            name = os.path.basename(src)
            cmd.append(f"--include-data-files={src}={name if dst == '.' else dst + '/' + name}")

    excludes = cfg.all_excludes
    if excludes:
        notes.append(tr("note.excluded", n=len(excludes), items=", ".join(excludes)))
    for exc in excludes:
        cmd.append(f"--nofollow-import-to={exc}")

    extra = cfg.extra_flags.strip()
    if extra:
        try:
            cmd += shlex.split(extra, posix=not win)
        except ValueError as e:
            raise ValueError(tr("note.flags_error", error=e)) from e

    cmd.append(cfg.script.strip())
    notes.append(tr("note.nuitka_slow"))
    return cmd, notes


def standalone_dir(cfg):
    """Carpeta que crea Nuitka con --standalone: <dist>/<script>.dist"""
    return os.path.join(cfg.dist_dir, Path(cfg.script.strip()).stem + ".dist")


def build_dirs(cfg):
    """Carpetas de trabajo de Nuitka (se borran con --remove-output o al limpiar)."""
    stem = Path(cfg.script.strip()).stem
    return [os.path.join(cfg.dist_dir, f"{stem}.build"), os.path.join(cfg.dist_dir, f"{stem}.onefile-build")]


def normalize_output(cfg, log=print):
    """Deja el resultado de Nuitka donde lo espera el resto del programa:
    onedir → dist/<app>/<app>.exe   ·   onefile → dist/<app>.exe (Nuitka ya lo deja ahí).
    Devuelve True si el resultado quedó en su lugar."""
    if cfg.onefile:
        return os.path.isfile(os.path.join(cfg.dist_dir, output_filename(cfg)))
    src = standalone_dir(cfg)
    dst = os.path.join(cfg.dist_dir, cfg.app_name)
    if not os.path.isdir(src):
        return os.path.isdir(dst)
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return True
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.rename(src, dst)
    log(tr("log.nuitka_moved", src=os.path.basename(src), dst=cfg.app_name))
    return True
