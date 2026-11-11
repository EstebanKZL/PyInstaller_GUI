"""Hilos de trabajo (QThread): nada de esto bloquea la interfaz."""

import glob
import os
import shutil
import subprocess
import sys

from .core.builder import BuildRunner
from .core.imports_scan import analyze, scan_imports
from .core.postbuild import (
    app_target, diagnose_log, executable_path, parse_warn_file, size_report, smoke_test, warn_file_path,
)
from .core.packages import BUILD_TOOLS, pick_import_name, query_modules, query_packages, version_satisfies_fallback
from .core.process import kill_process_tree, popen_kwargs, sub_kwargs
from .core.requirements import parse_requirement_full
from .core.trust import needs_confirmation
from .i18n import tr
from .qt_compat import QThread, Signal


class PythonLocatorWorker(QThread):
    """Busca intérpretes Python. El venv del proyecto NO se ejecuta si el usuario todavía
    no lo confirmó (trusted): se informa con untrusted=True y sin versión."""
    versions_found = Signal(list)

    def __init__(self, workspace, trusted=()):
        super().__init__()
        self.workspace = workspace
        self.trusted = list(trusted)

    def test_python(self, path):
        try:
            r = subprocess.run([path, "-c", "print('OK')"],
                               capture_output=True, text=True, timeout=2,
                               **sub_kwargs())
            return r.returncode == 0 and "OK" in r.stdout
        except Exception:
            return False

    def detect_workspace_python(self, folder):
        for name in ["venv", ".venv", "env", ".env", "virtualenv", ".pipenv"]:
            vp = os.path.join(folder, name)
            if not os.path.isdir(vp):
                continue
            cands = ([os.path.join(vp, "Scripts", "python.exe")]
                     if sys.platform == "win32"
                     else [os.path.join(vp, "bin", "python3"), os.path.join(vp, "bin", "python")])
            for c in cands:
                if os.path.isfile(c) and os.access(c, os.X_OK):
                    return c
        return None

    def run(self):
        seen   = set()
        result = []

        def _get_version(exe):
            try:
                r = subprocess.run(
                    [exe, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
                    capture_output=True, text=True, timeout=2, **sub_kwargs())
                return r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                return ""

        def _has_pyinstaller(exe):
            try:
                r = subprocess.run(
                    [exe, "-c", "import PyInstaller; print('ok')"],
                    capture_output=True, text=True, timeout=2, **sub_kwargs())
                return r.returncode == 0 and "ok" in r.stdout
            except Exception:
                return False

        def _add(exe, source, detail=""):
            exe = os.path.normpath(exe)
            if exe in seen or not os.path.isfile(exe):
                return
            if not self.test_python(exe):
                return
            seen.add(exe)
            ver = _get_version(exe)
            if not ver:
                return
            result.append({
                "path": exe, "version": ver, "source": source, "detail": detail,
                "has_pyinstaller": _has_pyinstaller(exe),
            })

        if self.workspace:
            vp = self.detect_workspace_python(self.workspace)
            if vp and needs_confirmation(vp, self.workspace, trusted=self.trusted, force=True):
                vp = os.path.normpath(vp)
                seen.add(vp)
                result.append({"path": vp, "version": "", "source": "venv", "detail": "",
                               "has_pyinstaller": False, "untrusted": True})
            elif vp:
                _add(vp, "venv")

        for name in ("python3", "python"):
            found = shutil.which(name)
            if found:
                _add(found, "path", name)

        if sys.platform == "win32":
            py_launcher = shutil.which("py")
            if py_launcher:
                try:
                    r = subprocess.run([py_launcher, "--list-paths"], capture_output=True, text=True, timeout=3, **sub_kwargs())
                    for ln in r.stdout.splitlines():
                        parts = ln.strip().split()
                        if len(parts) >= 2:
                            exe_path = parts[-1].strip('"')
                            if os.path.isfile(exe_path):
                                _add(exe_path, "launcher", parts[0])
                except Exception:
                    pass

            try:
                import winreg
                for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    for base in (r"SOFTWARE\Python\PythonCore", r"SOFTWARE\WOW6432Node\Python\PythonCore"):
                        try:
                            with winreg.OpenKey(hive, base) as core:
                                i = 0
                                while True:
                                    try:
                                        ver_key = winreg.EnumKey(core, i)
                                        i += 1
                                        with winreg.OpenKey(core, f"{ver_key}\\InstallPath") as ip:
                                            install_dir, _ = winreg.QueryValueEx(ip, "")
                                            exe = os.path.join(install_dir.rstrip("\\"), "python.exe")
                                            _add(exe, "registry", ver_key)
                                    except OSError:
                                        break
                        except Exception:
                            pass
            except ImportError:
                pass

            paths_windows = [
                "C:\\Python3*\\python.exe",
                "C:\\Program Files\\Python3*\\python.exe",
                "C:\\Program Files (x86)\\Python3*\\python.exe",
                "C:\\Users\\*\\AppData\\Local\\Programs\\Python\\Python3*\\python.exe"
            ]
            for pattern in paths_windows:
                for exe in sorted(glob.glob(pattern), reverse=True):
                    _add(exe, "known")
        else:
            paths_unix = [
                "/usr/bin/python3*",
                "/usr/local/bin/python3*",
                "/opt/homebrew/bin/python3*"
            ]
            for pattern in paths_unix:
                for exe in sorted(glob.glob(pattern), reverse=True):
                    if os.access(exe, os.X_OK):
                        _add(exe, "system")

        _add(sys.executable, "current")

        def _sort_key(d):
            is_venv = 1 if d["source"] == "venv" else 0
            try:
                parts = [int(x) for x in d["version"].split(".")]
            except Exception:
                parts = [0, 0, 0]
            return (-is_venv, [-p for p in parts])

        result.sort(key=_sort_key)
        self.versions_found.emit(result)

class PyInstallerCheckWorker(QThread):
    """Versión del compilador (PyInstaller o Nuitka) en un intérprete. Emite (estado, versión):
    estado = 'ok' | 'missing' | 'error'."""
    check_finished = Signal(str, str)

    _PROBES = {
        "pyinstaller": ("import PyInstaller; print(PyInstaller.__version__)", 3),
        "nuitka": ("from nuitka.Version import getNuitkaVersion; print(getNuitkaVersion())", 10),
    }

    def __init__(self, python_path, backend="pyinstaller"):
        super().__init__()
        self.python_path = python_path
        self.backend = backend if backend in self._PROBES else "pyinstaller"

    def run(self):
        code, timeout = self._PROBES[self.backend]
        try:
            r = subprocess.run(
                [self.python_path, "-c", code],
                capture_output=True, text=True, timeout=timeout, **sub_kwargs())
            ver = r.stdout.strip()
            if r.returncode == 0 and ver:
                self.check_finished.emit("ok", ver)
            else:
                self.check_finished.emit("missing", "")
        except Exception:
            self.check_finished.emit("error", "")


class BuildWorker(QThread):
    """Ejecuta un BuildRunner en segundo plano y reenvía su progreso como señales."""
    log_signal      = Signal(str)
    finished_signal = Signal(bool, str)
    progress_signal = Signal(int)
    status_signal   = Signal(str)

    def __init__(self, cfg, cmd, recreate_venv=False):
        super().__init__()
        self.runner = BuildRunner(cfg, cmd,
                                  log=self.log_signal.emit,
                                  progress=self.progress_signal.emit,
                                  status=self.status_signal.emit,
                                  recreate_venv=recreate_venv)

    @property
    def _process(self):
        return self.runner.process

    def cancel(self):
        self.runner.cancel()

    def run(self):
        ok, msg = self.runner.run()
        self.finished_signal.emit(ok, msg)


class ScanWorker(QThread):
    # (paquete, módulo, instalado, marcar, estado, especificador, versión, módulos)
    # estado = 'ok' | 'mismatch' | 'missing' | 'build'  — la interfaz decide texto y color
    item_ready    = Signal(str, str, bool, bool, str, str, str, list)
    scan_complete = Signal(bool, int, int)
    log_signal    = Signal(str)
    progress_sig  = Signal(int, int)

    BUILD_TOOLS = BUILD_TOOLS

    def __init__(self, folder, python_exe):
        super().__init__()
        self.folder     = folder
        self.python_exe = python_exe
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        req = os.path.join(self.folder, "requirements.txt")
        if not os.path.exists(req):
            self.scan_complete.emit(False, 0, 0)
            return

        with open(req, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        entries = []
        for ln in lines:
            r = parse_requirement_full(ln)
            if r: entries.append(r)

        total = len(entries)
        found, installed_count = False, 0
        self.progress_sig.emit(0, total)

        # Una sola consulta al Python del proyecto para todos los paquetes
        info = query_packages(self.python_exe, [(pkg, spec) for pkg, spec, _ in entries],
                              timeout=30 + 2 * total)
        if total and not info:
            self.log_signal.emit(tr("log.scan_query_failed"))

        for idx, (pkg, req_spec, full_line) in enumerate(entries):
            if self._cancelled:
                break
            self.progress_sig.emit(idx + 1, total)

            pi       = info.get(pkg, {})
            modules  = pi.get("modules") or []
            inst_ver = pi.get("version") or ""
            ok       = bool(inst_ver or modules)
            iname    = pick_import_name(pkg, modules)

            if ok:
                found = True
                installed_count += 1
                line = tr("log.scan_ok", line=full_line, version=inst_ver or "?")
            else:
                line = tr("log.scan_missing", line=full_line)
            if modules and modules != [pkg]:
                line += "  " + tr("log.scan_imports", modules=", ".join(modules))
            self.log_signal.emit(line)

            is_build = (pkg.lower() in self.BUILD_TOOLS or pkg.lower().startswith('pyinstaller'))
            if is_build:
                auto, state = False, "build"
            elif not ok:
                auto, state = False, "missing"
            else:
                sat = pi.get("satisfies")
                ver_ok = sat if sat is not None else version_satisfies_fallback(req_spec, inst_ver) if req_spec and inst_ver else True
                auto, state = True, ("mismatch" if req_spec and not ver_ok else "ok")

            self.item_ready.emit(pkg, iname, ok, auto, state, req_spec, inst_ver, modules)

        self.scan_complete.emit(found, total, installed_count)

# ─── DepItem ─────────────────────────────────────────────────────────────────
class DepItem:
    def __init__(self, pkg_name, installed, import_name, req_spec="", installed_version="", modules=None):
        self.pkg_name          = pkg_name
        self.installed         = installed
        self.import_name       = import_name
        self.req_spec          = req_spec
        self.installed_version = installed_version
        self.modules           = list(modules or [import_name])

    @property
    def display_label(self):
        if self.installed_version:
            return f"{self.pkg_name}=={self.installed_version}"
        if self.req_spec:
            return f"{self.pkg_name}{self.req_spec}"
        return self.pkg_name


class InstallWorker(QThread):
    log_signal      = Signal(str)
    finished_signal = Signal(bool, str)
    progress_signal = Signal(int, int)

    def __init__(self, packages, python_exe, upgrade=False):
        super().__init__()
        self.packages    = packages
        self.python_exe  = python_exe
        self.upgrade     = upgrade
        self._cancelled  = False
        self._process    = None

    def cancel(self):
        self._cancelled = True
        kill_process_tree(self._process)

    def run(self):
        total, ok_count, errors = len(self.packages), 0, []
        for idx, pkg in enumerate(self.packages):
            if self._cancelled:
                self.log_signal.emit(tr("log.install_cancelled"))
                self.finished_signal.emit(False, tr("msg.install_cancelled"))
                return

            self.progress_signal.emit(idx + 1, total)
            self.log_signal.emit(tr("log.pip_package", i=idx + 1, total=total, pkg=pkg))

            cmd = [self.python_exe, "-m", "pip", "install"]
            if self.upgrade:
                cmd.append("--upgrade")
            cmd.append(pkg)

            try:
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, universal_newlines=True,
                    errors="replace", **popen_kwargs()
                )

                for line in self._process.stdout:
                    if self._cancelled:
                        break
                    self.log_signal.emit(line.rstrip())

                self._process.wait()

                if self._process.returncode == 0:
                    ok_count += 1
                    self.log_signal.emit(tr("log.pip_ok", pkg=pkg))
                else:
                    errors.append(pkg)
                    self.log_signal.emit(tr("log.pip_error", pkg=pkg))
            except Exception as e:
                errors.append(pkg)
                self.log_signal.emit(tr("log.pip_exception", pkg=pkg, error=e))

        if errors:
            self.finished_signal.emit(False, tr("msg.install_with_errors", pkgs=", ".join(errors)))
        else:
            self.finished_signal.emit(True, tr("msg.install_ok", n=ok_count))


class ImportAnalysisWorker(QThread):
    """Análisis estático de imports del proyecto vs requirements.txt."""
    finished_signal = Signal(object)   # ImportReport o str (error)

    def __init__(self, workspace, python_exe):
        super().__init__()
        self.workspace  = workspace
        self.python_exe = python_exe

    def run(self):
        try:
            scan = scan_imports(self.workspace)
            reqs = []
            req = os.path.join(self.workspace, "requirements.txt")
            if os.path.isfile(req):
                with open(req, "r", encoding="utf-8", errors="replace") as f:
                    reqs = [r for r in (parse_requirement_full(ln) for ln in f) if r]
            pkg_info = query_packages(self.python_exe, [(p, s) for p, s, _ in reqs])
            candidates = [m for m in scan.top_level if m not in scan.local_modules]
            module_info = query_modules(self.python_exe, candidates)
            self.finished_signal.emit(analyze(scan, reqs, pkg_info, module_info))
        except Exception as e:
            self.finished_signal.emit(tr("analysis.error", error=e))


class PostBuildWorker(QThread):
    """Lee warn-<app>.txt, mide dist/ y diagnostica el log después de un build."""
    finished_signal = Signal(object)   # dict

    def __init__(self, cfg, log_text, success):
        super().__init__()
        self.cfg, self.log_text, self.success = cfg, log_text, success

    def run(self):
        cfg = self.cfg
        result = {"success": self.success, "missing": [], "sizes": [], "diagnostics": [],
                  "target": "", "exe": "", "error": ""}
        try:
            local = scan_imports(cfg.workspace).local_modules if cfg.workspace else set()
            local.add(os.path.splitext(os.path.basename(cfg.script))[0])
            if cfg.build_dir:
                result["missing"] = parse_warn_file(warn_file_path(cfg.build_dir, cfg.app_name), cfg.workspace, local)
            # Si se movió a la carpeta de salida automática, el resultado está ahí
            dist = cfg.destination_dir if cfg.destination_dir and os.path.isdir(cfg.destination_dir) else cfg.dist_dir
            result["target"] = app_target(dist, cfg.app_name, cfg.onefile) if dist else ""
            result["exe"] = executable_path(dist, cfg.app_name, cfg.onefile) if dist else ""
            result["sizes"] = size_report(result["target"])
            result["diagnostics"] = diagnose_log(self.log_text)
        except Exception as e:
            result["error"] = str(e)
        self.finished_signal.emit(result)


class SmokeTestWorker(QThread):
    """Ejecuta el binario generado unos segundos para ver si arranca."""
    finished_signal = Signal(object)   # dict de smoke_test()

    def __init__(self, exe, seconds=8):
        super().__init__()
        self.exe, self.seconds = exe, seconds
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        self.finished_signal.emit(smoke_test(self.exe, self.seconds, cancelled=lambda: self._cancelled))
