"""Construcción del comando de PyInstaller y del .spec a partir de un BuildConfig."""

import os
import shlex
import sys

from .nuitka_command import build_nuitka_command
from .spec import generate_spec_content
from .version_info import write_version_file
from ..i18n import tr

QT_BINDINGS = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6'}


def collect_all_packages(imports, extra=()):
    """Paquetes que necesitan --collect-all: los bindings Qt y PIL detectados en los
    hidden imports, más los que agregó el usuario. Sin duplicados."""
    result = []
    for imp in imports:
        pkg_base = imp.split('.')[0]
        if (pkg_base in QT_BINDINGS or pkg_base == 'PIL') and pkg_base not in result:
            result.append(pkg_base)
    for pkg in extra:
        if pkg and pkg not in result:
            result.append(pkg)
    return result


def _existing(path):
    path = path.strip()
    return path if path and os.path.isfile(path) else ""


def _version_file(cfg):
    """version.txt elegido a mano, o el generado desde el formulario (se escribe ahora)."""
    explicit = _existing(cfg.version_file)
    if explicit:
        return explicit
    if cfg.version_info:
        return write_version_file(cfg)
    return ""


def build_command(cfg, python=None):
    """Devuelve (cmd, notas). 'notas' son líneas informativas para el log
    ([i] info, [!] advertencia). Lanza ValueError si los flags extra no se pueden parsear.
    Con cfg.backend == "nuitka" devuelve el comando de Nuitka."""
    if cfg.is_nuitka:
        return build_nuitka_command(cfg, python)
    notes = []
    python = python or cfg.python_path
    cmd = [python, "-m", "PyInstaller", "--noconfirm"]

    if cfg.clean:
        cmd.append("--clean")
    cmd.append("--onefile" if cfg.onefile else "--onedir")

    # Runtime tmpdir: carpeta temp fija para onefile más rápido
    if cfg.runtime_tmpdir:
        if cfg.onefile:
            tmpdir_val = cfg.effective_runtime_tmpdir
            cmd.append(f"--runtime-tmpdir={tmpdir_val}")
            notes.append(tr("note.tmpdir", path=tmpdir_val))
        else:
            notes.append(tr("note.tmpdir_onedir"))

    if cfg.noconsole:
        cmd.append("--noconsole")
    if cfg.debug:
        cmd.append("--debug=all")
    if cfg.strip:
        cmd.append("--strip")
    if cfg.noupx:
        cmd.append("--noupx")
    if cfg.optimize:
        cmd.append("--optimize=1")
    if cfg.bootloader_ignore:
        cmd.append("--bootloader-ignore-signals")
    if cfg.uac_admin:
        cmd.append("--uac-admin")

    sep_path = ";" if sys.platform == "win32" else ":"

    icon = _existing(cfg.icon)
    if icon:
        cmd.append(f"--icon={icon}")
        # El ícono también va como dato para que resource_path() lo encuentre en runtime
        cmd.append(f"--add-data={icon}{sep_path}.")
        notes.append(tr("note.icon_bundled", name=os.path.basename(icon)))
    elif cfg.icon.strip():
        notes.append(tr("note.icon_missing", path=cfg.icon.strip()))

    ver = _version_file(cfg)
    if ver:
        cmd.append(f"--version-file={ver}")
        if cfg.version_info and not cfg.version_file.strip():
            notes.append(tr("note.version_generated", version=cfg.app_version, path=ver))

    if cfg.name.strip():
        cmd.append(f"--name={cfg.name.strip()}")

    if cfg.dist_dir:
        cmd.append(f"--distpath={cfg.dist_dir}")
    if cfg.build_dir:
        cmd.append(f"--workpath={cfg.build_dir}")
    if cfg.workspace:
        cmd.append(f"--specpath={cfg.workspace}")

    imports = list(dict.fromkeys(cfg.hidden_imports))
    for imp in imports:
        cmd.append(f"--hidden-import={imp}")

    for pkg_base in collect_all_packages(imports, cfg.collect_all):
        cmd.append(f"--collect-all={pkg_base}")
        if pkg_base in cfg.collect_all:
            continue
        notes.append(tr("note.collect_pil" if pkg_base == "PIL" else "note.collect_qt", pkg=pkg_base))
    for pkg in dict.fromkeys(cfg.collect_data):
        cmd.append(f"--collect-data={pkg}")
    for pkg in dict.fromkeys(cfg.copy_metadata):
        cmd.append(f"--copy-metadata={pkg}")

    for src, dst in cfg.add_data:
        cmd.append(f"--add-data={src}{sep_path}{dst}")

    excludes = cfg.all_excludes
    if excludes:
        notes.append(tr("note.excluded", n=len(excludes), items=", ".join(excludes)))
    for exc in excludes:
        cmd.append(f"--exclude-module={exc}")

    extra = cfg.extra_flags.strip()
    if extra:
        try:
            cmd += shlex.split(extra, posix=(sys.platform != "win32"))
        except ValueError as e:
            raise ValueError(tr("note.flags_error", error=e)) from e

    cmd.append(cfg.script.strip())

    if cfg.onefile:
        notes.append(tr("note.onefile_slow"))
    return cmd, notes


def build_spec(cfg):
    """.spec equivalente al comando generado por build_command()."""
    icon = _existing(cfg.icon)
    data = list(cfg.add_data)
    if icon:
        data.append((icon, "."))
    imports = list(dict.fromkeys(cfg.hidden_imports))
    return generate_spec_content(
        cfg.app_name, cfg.script.strip(), imports, cfg.onefile,
        cfg.noconsole, icon, data, cfg.all_excludes,
        cfg.strip, cfg.noupx,
        collect_all=collect_all_packages(imports, cfg.collect_all),
        collect_data=list(dict.fromkeys(cfg.collect_data)),
        copy_metadata=list(dict.fromkeys(cfg.copy_metadata)),
        debug=cfg.debug,
        bootloader_ignore=cfg.bootloader_ignore,
        uac_admin=cfg.uac_admin,
        version_file=_version_file(cfg),
        runtime_tmpdir=cfg.effective_runtime_tmpdir,
        optimize=cfg.optimize,
    )
