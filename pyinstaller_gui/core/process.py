"""Utilidades de subprocesos multiplataforma (sin dependencias de Qt)."""

import os
import shlex
import shutil
import subprocess
import sys


def sub_kwargs():
    """ Kwargs extra para suprimir la ventana negra de consola en Windows """
    kw = {}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kw["startupinfo"] = si
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kw

def popen_kwargs():
    """ Kwargs para Popen: sin consola en Windows y grupo de procesos propio en
    Linux/macOS (permite matar a PyInstaller/pip junto con sus subprocesos). """
    kw = sub_kwargs()
    if sys.platform != "win32":
        kw["start_new_session"] = True
    return kw

def kill_process_tree(proc):
    """ Termina un proceso y todos sus hijos sin bloquear la interfaz. """
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10, **sub_kwargs())
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

def command_to_str(cmd):
    """ Comando listo para copiar/pegar en la terminal (rutas con espacios entre comillas). """
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    return shlex.join(cmd)

def find_tool(name):
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        for d in [os.path.join(app_dir, "_internal"),
                  os.path.join(app_dir, "usr", "bin"), app_dir]:
            c = os.path.join(d, name)
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c
    # shutil.which busca en PATH del sistema
    found = shutil.which(name)
    if found:
        return found
    # Rutas fijas conocidas para Windows (independientes del PATH)
    if sys.platform == "win32":
        _WIN_KNOWN = {
            "makensis": [
                r"C:\Program Files (x86)\NSIS\makensis.exe",
                r"C:\Program Files\NSIS\makensis.exe",
            ],
            "ISCC": [
                r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                r"C:\Program Files\Inno Setup 6\ISCC.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
            ],
        }
        for candidate in _WIN_KNOWN.get(name, []):
            if os.path.isfile(candidate):
                return candidate
    return None
