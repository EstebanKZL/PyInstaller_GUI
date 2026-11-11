"""Análisis posterior al build: módulos faltantes (warn-*.txt), tamaño por paquete,
diagnóstico del log y prueba del ejecutable generado."""

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import List

from .process import kill_process_tree, popen_kwargs
from ..i18n import tr

# ── warn-<app>.txt ───────────────────────────────────────────────────────
_WARN_LINE = re.compile(r"^missing module named (?P<mod>\S+) - imported by (?P<by>.+)$")
_IMPORTER = re.compile(r"(?P<who>.+?) \((?P<kinds>[a-z, -]+)\)(?:, |$)")


@dataclass
class MissingModule:
    module: str
    importers: List[tuple] = field(default_factory=list)   # [(importador, [tipos])]
    from_project: bool = False

    @property
    def important(self):
        """Importado a nivel superior (no opcional) por código del proyecto: casi seguro rompe en runtime."""
        return self.from_project and any("top-level" in k and "optional" not in k for _, k in self.importers)


def warn_file_path(build_dir, app_name):
    return os.path.join(build_dir, app_name, f"warn-{app_name}.txt")


def parse_warn_file(path, workspace="", local_modules=()):
    """Lista de MissingModule, los importantes primero. [] si el archivo no existe."""
    if not path or not os.path.isfile(path):
        return []
    ws = os.path.normcase(os.path.abspath(workspace)) if workspace else ""
    local = set(local_modules)
    result = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _WARN_LINE.match(line.strip())
            if not m:
                continue
            mm = MissingModule(module=m.group("mod").strip("'\""))
            for im in _IMPORTER.finditer(m.group("by")):
                who = im.group("who").strip()
                kinds = [k.strip() for k in im.group("kinds").split(",")]
                mm.importers.append((who, kinds))
                is_path = os.sep in who or "/" in who
                if (is_path and ws and os.path.normcase(os.path.abspath(who)).startswith(ws)) or \
                   (not is_path and who.split(".")[0] in local):
                    mm.from_project = True
            result.append(mm)
    result.sort(key=lambda x: (not x.important, not x.from_project, x.module))
    return result


# ── Tamaño por paquete ───────────────────────────────────────────────────
def app_target(dist_dir, app_name, onefile):
    """Ruta del resultado del build (carpeta onedir, .exe/.app o binario onefile)."""
    if onefile:
        for name in (f"{app_name}.exe", f"{app_name}.app", app_name):
            p = os.path.join(dist_dir, name)
            if os.path.exists(p):
                return p
        return ""
    p = os.path.join(dist_dir, app_name)
    return p if os.path.isdir(p) else ""


def executable_path(dist_dir, app_name, onefile):
    target = app_target(dist_dir, app_name, onefile)
    if not target:
        return ""
    if onefile:
        return target
    exe = os.path.join(target, f"{app_name}.exe" if sys.platform == "win32" else app_name)
    return exe if os.path.isfile(exe) else ""


def _dir_size(path):
    total = 0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def size_report(target):
    """[(nombre, bytes)] ordenado de mayor a menor. En onedir agrupa por carpeta/archivo
    de _internal/ (un paquete = una entrada); en onefile devuelve solo el total."""
    if not target or not os.path.exists(target):
        return []
    if os.path.isfile(target):
        return [(os.path.basename(target), os.path.getsize(target))]
    root = os.path.join(target, "_internal") if os.path.isdir(os.path.join(target, "_internal")) else target
    entries = []
    for name in os.listdir(root):
        p = os.path.join(root, name)
        entries.append((name, _dir_size(p) if os.path.isdir(p) else os.path.getsize(p)))
    if root != target:
        for name in os.listdir(target):
            p = os.path.join(target, name)
            if name != "_internal":
                entries.append((name, _dir_size(p) if os.path.isdir(p) else os.path.getsize(p)))
    return sorted(entries, key=lambda e: -e[1])


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ── Diagnóstico del log ──────────────────────────────────────────────────
# (regex, mensaje, acción) — acción: (tipo, valor) aplicable desde la GUI o None
# (regex, clave del mensaje en i18n → diag.<clave>, acción aplicable o None)
_DIAGNOSTICS = [
    (r"ModuleNotFoundError: No module named '(?P<x>[\w\.]+)'", "module_missing", "hidden_import"),
    (r"No package metadata was found for (?P<x>[\w\.\-]+)", "metadata", "copy_metadata"),
    (r"The '(?P<x>[\w\.\-]+)[^']*' distribution was not found", "pkg_resources", "copy_metadata"),
    (r"Could not (?:find|load) the Qt platform plugin", "qt_plugin", None),
    (r"DLL load failed while importing (?P<x>\w+)", "dll", None),
    (r"FileNotFoundError: .*?['\"](?P<x>[^'\"]+)['\"]", "file_missing", None),
    (r"RecursionError: maximum recursion depth exceeded", "recursion", None),
    (r"PermissionError: \[WinError (?:5|32)\]", "locked", None),
]


def diagnose_log(text):
    """[{line, key, x, message, action}] sin duplicados, en orden de aparición."""
    found, seen = [], set()
    for line in text.splitlines():
        for pattern, msg_key, action in _DIAGNOSTICS:
            m = re.search(pattern, line)
            if not m:
                continue
            x = m.groupdict().get("x", "")
            key = (pattern, x)
            if key in seen:
                continue
            seen.add(key)
            found.append({"line": line.strip()[:300], "key": msg_key, "x": x,
                          "message": tr(f"diag.{msg_key}", x=x),
                          "action": (action, x) if action and x else None})
    return found


# ── Prueba del ejecutable ────────────────────────────────────────────────
def smoke_test(exe, seconds=8, cancelled=lambda: False):
    """Ejecuta el binario y espera 'seconds'. Si sigue vivo se considera que arrancó bien
    (apps GUI / servidores) y se cierra. Devuelve {status, code, output, elapsed}:
    status = 'running' | 'exited' | 'crashed' | 'error'."""
    if not exe or not os.path.isfile(exe):
        return {"status": "error", "code": None, "output": tr("smoke.no_exe", exe=exe), "elapsed": 0.0}
    t0 = time.time()
    try:
        proc = subprocess.Popen([exe], cwd=os.path.dirname(exe), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **popen_kwargs())
    except Exception as e:
        return {"status": "error", "code": None, "output": str(e), "elapsed": 0.0}
    while proc.poll() is None and time.time() - t0 < seconds and not cancelled():
        time.sleep(0.1)
    if proc.poll() is None:
        kill_process_tree(proc)
        try:
            out = proc.communicate(timeout=10)[0]
        except Exception:
            out = b""
        status, code = "running", None
    else:
        out = proc.communicate()[0]
        code = proc.returncode
        status = "exited" if code == 0 else "crashed"
    text = (out or b"").decode("utf-8", errors="replace")
    return {"status": status, "code": code, "output": text[-6000:], "elapsed": round(time.time() - t0, 1)}


# ── Nivel de cada línea del log (para colorearlo) ────────────────────────
_PYI_LEVEL = re.compile(r"^\d+\s+(INFO|WARNING|ERROR|CRITICAL|DEBUG):")
_ERROR_HINTS = ("Traceback (most recent call last)", "Error:", "Exception:", "error:")


def log_level(line):
    """'error' | 'warning' | 'ok' | 'info' | '' (normal)."""
    s = line.lstrip()
    m = _PYI_LEVEL.match(s)
    if m:
        return {"ERROR": "error", "CRITICAL": "error", "WARNING": "warning"}.get(m.group(1), "")
    if s.startswith(("[X]", "✗")) or any(h in s for h in _ERROR_HINTS):
        return "error"
    if s.startswith(("[!]", "[⚠]", "WARNING")):
        return "warning"
    if s.startswith(("[OK]", "[✓]", "✓")) or "completed successfully" in s:
        return "ok"
    if s.startswith(("[i]", "===", "[check]", "[pip]", "[sign]", "[test]")):
        return "info"
    return ""
