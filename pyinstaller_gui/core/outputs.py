"""Archivos que genera un build: identificación, limpieza segura y movido."""

import os
import re
import shutil

from .naming import CHECKSUMS_FILE, is_artifact_of
from ..i18n import tr


def safe_app_name(app_name):
    return re.sub(r'[^A-Za-z0-9._-]', '_', app_name)

def is_app_output(entry, app_name):
    """ True si 'entry' (nombre dentro de dist/) pertenece a la app compilada:
    carpeta onedir, ejecutable onefile, .app, .AppDir, .AppImage, instaladores, ZIP portable
    y SHA256SUMS.txt (genérico de la carpeta de release). """
    safe = safe_app_name(app_name)
    exact = {
        app_name, f"{app_name}.exe", f"{app_name}.app", f"{app_name}.AppDir",
        f"{safe}_Setup.exe", f"{safe}_setup.nsi", f"{safe}_Setup_Inno.exe", f"{safe}_setup.iss",
        f"{safe}-SHA256SUMS.txt",
    }
    if entry in exact or entry == CHECKSUMS_FILE:
        return True
    # Artefactos con la convención <App>-<versión>-<sistema>-<arq>[-<variante>].<ext>
    if is_artifact_of(entry, app_name):
        return True
    # ZIP de release de versiones anteriores: <safe>-<versión>-<plataforma>.zip
    if entry.startswith(safe + "-") and entry.endswith(".zip"):
        return True
    # appimagetool nombra la salida como <Name>-<arch>.AppImage
    return entry.endswith(".AppImage") and (entry.startswith(app_name) or entry.startswith(safe))

def _remove_path(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)

def clean_app_outputs(dist_dir, build_dir, app_name):
    """ Borra SOLO lo que generó un build anterior de esta app: las entradas de
    dist/ que le pertenecen y build/<app_name>/. Nunca borra carpetas completas
    elegidas por el usuario. Devuelve (borrados, errores). """
    removed, errors = [], []
    if dist_dir and os.path.isdir(dist_dir):
        for entry in os.listdir(dist_dir):
            if is_app_output(entry, app_name):
                try:
                    _remove_path(os.path.join(dist_dir, entry))
                    removed.append(os.path.join(os.path.basename(dist_dir), entry))
                except Exception as e:
                    errors.append(f"{entry}: {e}")
    if build_dir:
        work = os.path.join(build_dir, app_name)
        if os.path.isdir(work):
            try:
                shutil.rmtree(work)
                removed.append(os.path.join(os.path.basename(build_dir), app_name))
            except Exception as e:
                errors.append(f"{work}: {e}")
    return removed, errors


def move_to_destination(dist_dir, dest_final, app_name, log):
    """Mueve SOLO las salidas de la app desde dist/ a dest_final. Devuelve True si no hubo errores."""
    if not dist_dir or not os.path.isdir(dist_dir):
        log(tr("log.no_dist_to_move"))
        return False
    try:
        os.makedirs(dest_final, exist_ok=True)
        moved = []
        for item in [e for e in os.listdir(dist_dir) if is_app_output(e, app_name)]:
            src = os.path.join(dist_dir, item)
            dst = os.path.join(dest_final, item)
            if os.path.exists(dst):
                _remove_path(dst)
            shutil.move(src, dst)
            moved.append(item)
        log(tr("log.moved", path=dest_final, files=", ".join(moved)))
        return True
    except Exception as e:
        log(tr("log.move_error", error=e))
        return False
