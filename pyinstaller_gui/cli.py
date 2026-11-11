"""Modo CLI (sin interfaz): compila a partir de un perfil JSON guardado desde la GUI.

Ejemplos:
    python -m pyinstaller_gui --profile mi_app_profile.json            # muestra el comando
    python -m pyinstaller_gui --profile mi_app_profile.json --build    # compila
    python -m pyinstaller_gui --profile mi_app_profile.json --spec app.spec
"""

import argparse
import os
import sys

from . import APP_NAME, APP_VERSION
from .core.builder import BuildRunner
from .core.command import build_command, build_spec
from .core.config import BuildConfig
from .core.process import command_to_str


def _parser():
    p = argparse.ArgumentParser(
        prog="pyinstaller_gui",
        description=f"{APP_NAME} {APP_VERSION} — modo sin interfaz. Sin argumentos se abre la GUI.")
    p.add_argument("--profile", required=True, help="Perfil JSON guardado desde la GUI")
    p.add_argument("--build", action="store_true", help="Compilar (sin esto solo se muestra el comando)")
    p.add_argument("--spec", metavar="ARCHIVO", help="Guardar el .spec equivalente en ARCHIVO")
    p.add_argument("--python", help="Intérprete Python a usar (reemplaza el del perfil)")
    p.add_argument("--onefile", action="store_true", default=None, help="Forzar modo onefile")
    p.add_argument("--onedir", action="store_true", default=None, help="Forzar modo onedir")
    p.add_argument("--dist", help="Carpeta dist (reemplaza la del perfil)")
    p.add_argument("--isolated", action="store_true", help="Compilar en un venv limpio creado desde requirements.txt")
    p.add_argument("--recreate-venv", action="store_true", help="Con --isolated: recrear el venv aunque no haya cambios")
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        cfg = BuildConfig.load(args.profile)
    except Exception as e:
        print(f"[X] No se pudo cargar el perfil: {e}", file=sys.stderr)
        return 2

    if args.python:
        cfg.python_path = args.python
    if not cfg.python_path or not os.path.isfile(cfg.python_path):
        cfg.python_path = sys.executable
    if args.onefile:
        cfg.onefile = True
    if args.onedir:
        cfg.onefile = False
    if args.dist:
        cfg.dist_path = args.dist
    if args.isolated:
        cfg.isolated_venv = True

    if not cfg.script or not os.path.isfile(cfg.script):
        print(f"[X] Script principal no encontrado: {cfg.script!r}", file=sys.stderr)
        return 2

    try:
        cmd, notes = build_command(cfg)
    except ValueError as e:
        print(f"[X] {e}", file=sys.stderr)
        return 2

    for note in notes:
        print(note)
    print(f"Comando:\n{command_to_str(cmd)}\n")

    if args.spec:
        with open(args.spec, "w", encoding="utf-8") as f:
            f.write(build_spec(cfg))
        print(f"[OK] .spec guardado: {args.spec}")

    if not args.build:
        return 0

    runner = BuildRunner(cfg, cmd, log=print, status=lambda m: print(f"[*] {m}"),
                         recreate_venv=args.recreate_venv)
    try:
        ok, msg = runner.run()
    except KeyboardInterrupt:
        runner.cancel()
        ok, msg = False, "Compilacion cancelada."
    print(("[OK] " if ok else "[X] ") + msg)
    return 0 if ok else 1
