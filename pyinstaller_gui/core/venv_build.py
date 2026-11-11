"""Entorno aislado para compilar: un venv limpio creado desde requirements.txt.

El ejecutable solo incluye lo que el proyecto declara (no todo lo que haya instalado
en el Python del sistema), así sale más chico y el build es reproducible.
El venv se guarda en <proyecto>/.pyinstaller_gui/ y se reutiliza mientras
requirements.txt y la versión de Python no cambien.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys

from .process import sub_kwargs
from ..i18n import tr

CACHE_DIRNAME = ".pyinstaller_gui"
_STAMP = "gui_stamp.json"


def venv_python(venv_dir):
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def python_version(python):
    r = subprocess.run([python, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                       capture_output=True, text=True, timeout=20, **sub_kwargs())
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(tr("venv.base_failed", python=python))
    return r.stdout.strip()


# Paquetes que se instalan en el venv aislado según el compilador elegido
BACKEND_PACKAGES = {
    "pyinstaller": ["pyinstaller"],
    "nuitka": ["nuitka", "ordered-set", "zstandard"],   # zstandard: compresión del onefile
}


def fingerprint(requirements_path, version, backend="pyinstaller"):
    h = hashlib.sha256(version.encode())
    if backend != "pyinstaller":   # mismo valor que antes para no recrear venvs existentes
        h.update(backend.encode())
    if requirements_path and os.path.isfile(requirements_path):
        with open(requirements_path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def venv_dir_for(workspace, version):
    major_minor = ".".join(version.split(".")[:2])
    return os.path.join(workspace, CACHE_DIRNAME, f"venv-py{major_minor}")


def ensure_venv(base_python, workspace, run, log, force=False, backend="pyinstaller"):
    """Crea (o reutiliza) el venv aislado y devuelve la ruta de su python.
    run(cmd) ejecuta un comando mostrando la salida y devuelve el código de salida
    (None si se canceló). Lanza RuntimeError si algo falla."""
    if not workspace or not os.path.isdir(workspace):
        raise RuntimeError(tr("venv.need_project"))
    version = python_version(base_python)
    req = os.path.join(workspace, "requirements.txt")
    venv_dir = venv_dir_for(workspace, version)
    vpy = venv_python(venv_dir)
    stamp_path = os.path.join(venv_dir, _STAMP)
    fp = fingerprint(req, version, backend)

    if not force and os.path.isfile(vpy) and os.path.isfile(stamp_path):
        try:
            with open(stamp_path, "r", encoding="utf-8") as f:
                if json.load(f).get("fingerprint") == fp:
                    log(tr("log.venv_reuse", path=venv_dir))
                    return vpy
        except Exception:
            pass
        log(tr("log.venv_changed"))

    if os.path.isdir(venv_dir):
        shutil.rmtree(venv_dir)
    log(tr("log.venv_creating", version=version, path=venv_dir))
    if run([base_python, "-m", "venv", venv_dir]) != 0 or not os.path.isfile(vpy):
        raise RuntimeError(tr("venv.create_failed"))

    install = [vpy, "-m", "pip", "install", "--disable-pip-version-check"]
    install += BACKEND_PACKAGES.get(backend, BACKEND_PACKAGES["pyinstaller"])
    if os.path.isfile(req):
        install += ["-r", req]
    else:
        log(tr("log.venv_no_requirements"))
    log(tr("log.venv_installing"))
    code = run(install)
    if code is None:
        raise RuntimeError(tr("venv.cancelled"))
    if code != 0:
        raise RuntimeError(tr("venv.pip_failed"))

    with open(stamp_path, "w", encoding="utf-8") as f:
        json.dump({"fingerprint": fp, "python": version, "base": base_python}, f, indent=2)
    log(tr("log.venv_ready"))
    return vpy
