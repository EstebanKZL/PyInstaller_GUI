"""Registro a archivo y errores no controlados (sin Qt: lo usa también el arranque).

El log de la pestaña Log es para el usuario; este archivo es para diagnosticar:
inicio del programa, compilaciones y errores no controlados con su traceback.
"""

import logging
import logging.handlers
import os
import platform
import sys
import traceback

from . import APP_DEVELOPER, APP_NAME, APP_VERSION

LOG_FILENAME = "PyInstallerGUI.log"
_log_path = ""


def app_data_dir():
    """Carpeta de datos del usuario: %LOCALAPPDATA%\\EstebanKZL\\PyInstallerGUI en Windows,
    ~/Library/Application Support/... en macOS y $XDG_STATE_HOME (o ~/.local/state)/... en Linux."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    path = os.path.join(base, APP_DEVELOPER, "PyInstallerGUI")
    os.makedirs(path, exist_ok=True)
    return path


def log_path():
    return _log_path


def setup_logging(qt_backend="", folder=None):
    """Log rotativo (2 MB × 3 archivos). Devuelve la ruta, o "" si no se pudo crear."""
    global _log_path
    try:
        path = os.path.join(folder or app_data_dir(), LOG_FILENAME)
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return ""
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    logging.info("Inicio %s %s (%s, Python %s, %s)", APP_NAME, APP_VERSION, qt_backend or "sin Qt",
                 platform.python_version(), platform.platform())
    _log_path = path
    return path


def install_excepthook(show=None):
    """Todo error no controlado se registra en el archivo y, si se pasa show(texto, detalle),
    se muestra en un diálogo en vez de cerrar el programa sin aviso."""
    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.error("Error no controlado:\n%s", details)
        if show is not None:
            try:
                show(str(exc) or exc_type.__name__, details)
            except Exception:
                sys.__excepthook__(exc_type, exc, tb)
        else:
            sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = _hook
    return _hook
