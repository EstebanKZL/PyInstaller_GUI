"""Ejecución de un build completo, sin Qt: limpieza, PyInstaller o Nuitka, instaladores y movido.

La GUI lo usa desde BuildWorker (en un hilo) y el modo CLI lo usa directamente.
"""

import os
import shutil
import subprocess
import sys

from . import nuitka_command
from .installers import create_appimage, create_inno_installer, create_nsis_installer, find_license
from .naming import CHECKSUMS_FILE, arch_label, artifact_name, os_label
from .outputs import clean_app_outputs, move_to_destination
from .postbuild import app_target, executable_path
from .release import make_zip, write_checksums
from .signing import sign_files
from .process import kill_process_tree, popen_kwargs
from .venv_build import ensure_venv
from ..i18n import tr

# Texto que imprime cada compilador en el log → clave del mensaje de estado
_PHASES = {
    "pyinstaller": (
        ("Analyzing",  "phase.analyzing"),
        ("Processing", "phase.processing"),
        ("Building",   "phase.building"),
        ("Copying",    "phase.copying"),
    ),
    "nuitka": (
        ("Starting Python compilation", "phase.analyzing"),
        ("Completed Python level compilation", "phase.processing"),
        ("Running C compilation", "phase.c_compiling"),
        ("Backend C compiler", "phase.c_compiling"),
        ("Copying", "phase.copying"),
        ("Creating single file", "phase.onefile"),
    ),
}


def _noop(*_):
    pass


class BuildRunner:
    def __init__(self, cfg, cmd, log=print, progress=_noop, status=_noop, recreate_venv=False):
        self.cfg       = cfg
        self.cmd       = cmd
        self.log       = log
        self.progress  = progress
        self.status    = status
        self.recreate_venv = recreate_venv
        self._cancelled = False
        self._process   = None
        self._temp_dirs = []

    def cancel(self):
        """No bloquea: mata el árbol de procesos; la limpieza la hace run() al salir."""
        self._cancelled = True
        kill_process_tree(self._process)

    @property
    def process(self):
        return self._process

    def clean_previous(self):
        """Borra SOLO las salidas previas de esta app (y su .spec), nunca carpetas completas."""
        cfg = self.cfg
        cleaned, errors = clean_app_outputs(cfg.dist_dir, cfg.build_dir, cfg.app_name)
        if cfg.is_nuitka and cfg.dist_dir and cfg.script.strip():
            for d in [nuitka_command.standalone_dir(cfg)] + nuitka_command.build_dirs(cfg):
                if os.path.isdir(d):
                    try:
                        shutil.rmtree(d)
                        cleaned.append(os.path.basename(d))
                    except Exception as e:
                        errors.append(f"{os.path.basename(d)}: {e}")
        if cfg.workspace:
            spec = os.path.join(cfg.workspace, f"{cfg.app_name}.spec")
            if os.path.isfile(spec):
                try:
                    os.remove(spec)
                    cleaned.append(f"{cfg.app_name}.spec")
                except Exception as e:
                    errors.append(f"{cfg.app_name}.spec: {e}")
        if cleaned:
            self.log(tr("log.cleaned", items=", ".join(cleaned)))
        for e in errors:
            self.log(tr("log.clean_failed", error=e))

    def _cleanup(self):
        for d in self._temp_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                    self.log(tr("log.temp_cleaned", path=d))
                except Exception as e:
                    self.log(tr("log.clean_failed", error=f"{d}: {e}"))

    def _stream(self, cmd, track_phases=False):
        """Ejecuta cmd mostrando su salida en el log. Devuelve el código de salida,
        o None si se canceló."""
        if self._cancelled:
            return None
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True,
            errors="replace", **popen_kwargs()
        )
        if self._cancelled:   # cancelado mientras arrancaba el proceso
            kill_process_tree(self._process)
        lc = 0
        phases = _PHASES.get(self.cfg.backend, _PHASES["pyinstaller"])
        for line in self._process.stdout:
            if self._cancelled:
                break
            self.log(line.rstrip())
            if track_phases:
                lc += 1
                self.progress(min(90, lc // 5))
                for key, msg_key in phases:
                    if key in line:
                        self.status(tr(msg_key))
                        break
        self._process.wait()
        return None if self._cancelled else self._process.returncode

    def _prepare_isolated(self):
        """Compila con el python de un venv limpio en lugar del Python del proyecto."""
        self.status(tr("status.preparing_isolated"))
        vpy = ensure_venv(self.cfg.python_path or self.cmd[0], self.cfg.workspace, self._stream, self.log,
                          force=self.recreate_venv, backend=self.cfg.backend)
        self.cmd = [vpy] + self.cmd[1:]
        self.log(tr("log.using_isolated", path=vpy))

    def _post_build(self):
        """Pasos posteriores a PyInstaller: firma, AppImage/instaladores, movido y release.
        Devuelve (ok, mensaje)."""
        cfg, log = self.cfg, self.log
        problems, done = [], []
        # Nombres de los artefactos: <App>-<versión>-<sistema>-<arq>-<variante>.<ext>
        os_lbl = os_label(cfg.platform)
        arch = arch_label(os_lbl, executable_path(cfg.dist_dir, cfg.app_name, cfg.onefile))
        appimage_name = artifact_name(cfg.app_name, cfg.app_version, "linux", arch, ext="AppImage")

        def name(variant, ext=""):
            return artifact_name(cfg.app_name, cfg.app_version, os_lbl, arch, variant, ext)

        # 1) Firma del ejecutable (antes de empaquetarlo en un instalador)
        if cfg.sign:
            self.status(tr("status.signing"))
            target = app_target(cfg.dist_dir, cfg.app_name, cfg.onefile)
            if sys.platform == "darwin" and target.endswith(".app"):
                to_sign = [target]
            else:
                to_sign = [executable_path(cfg.dist_dir, cfg.app_name, cfg.onefile)]
            if sign_files(cfg, to_sign, log):
                done.append(tr("extra.signed"))
            else:
                problems.append(tr("problem.sign"))

        # 2) AppImage / instaladores
        if cfg.make_appimage:
            log(tr("log.making_appimage"))
            self.status(tr("status.making_appimage"))
            if create_appimage(cfg.dist_dir, cfg.app_name, cfg.appimage_icon.strip(), log, self._temp_dirs,
                               out_name=appimage_name, arch=arch):
                done.append("AppImage")
            else:
                problems.append(tr("problem.failed", what="AppImage"))
        installers = []
        lic = find_license(cfg.workspace)
        # Con los dos instaladores activos, el de NSIS lleva otra variante para no pisarse
        nsis_variant = "nsis-setup" if cfg.make_inno else "setup"
        for enabled, label, fn, variant in ((cfg.make_nsis, "NSIS", create_nsis_installer, nsis_variant),
                                            (cfg.make_inno, "Inno Setup", create_inno_installer, "setup")):
            if not enabled:
                continue
            log(tr("log.making_installer", label=label))
            self.status(tr("status.making_installer", label=label))
            out = fn(cfg.dist_dir, cfg.app_name, log, version=cfg.app_version, publisher=cfg.company,
                     license_file=lic, icon=cfg.icon.strip(), output_base=name(variant),
                     x64=arch in ("x64", "arm64"))
            if out:
                installers.append(out)
                done.append(tr("extra.installer", label=label))
            else:
                problems.append(tr("problem.failed", what=label))
        if cfg.sign and installers:
            self.status(tr("status.signing_installers"))
            if not sign_files(cfg, installers, log):
                problems.append(tr("problem.sign_installer"))

        # 3) Movido a la carpeta de salida automática
        final_dir = cfg.dist_dir
        if cfg.destination_dir:
            if move_to_destination(cfg.dist_dir, cfg.destination_dir, cfg.app_name, log):
                self.status(tr("status.moved", path=cfg.destination_dir))
                final_dir = cfg.destination_dir
            else:
                problems.append(tr("problem.move"))

        # 4) Release: ZIP portable + SHA256SUMS.txt
        if cfg.make_zip or cfg.make_checksums:
            self.status(tr("status.release"))
            target = app_target(final_dir, cfg.app_name, cfg.onefile)
            artifacts = [os.path.join(final_dir, os.path.basename(p)) for p in installers]
            image = os.path.join(final_dir, appimage_name)
            if os.path.isfile(image):
                artifacts.append(image)
            try:
                if cfg.make_zip and target:
                    z = make_zip(target, os.path.join(final_dir, name("portable", "zip")))
                    artifacts.append(z)
                    log(tr("log.release_zip", path=z))
                    done.append("ZIP")
                elif os.path.isfile(target):
                    artifacts.append(target)
                if cfg.make_checksums and artifacts:
                    sums = write_checksums(artifacts, os.path.join(final_dir, CHECKSUMS_FILE))
                    log(tr("log.release_sums", path=sums))
                    done.append("SHA256")
            except Exception as e:
                log(tr("log.release_error", error=e))
                problems.append(tr("problem.failed", what="release"))

        if problems:
            return False, tr("msg.build_partial", problems=", ".join(problems))
        if done:
            return True, tr("msg.build_ok_extras", extras=", ".join(done))
        return True, tr("msg.build_ok")

    def run(self):
        """Ejecuta el build. Devuelve (ok, mensaje)."""
        cfg = self.cfg
        try:
            self.clean_previous()
            if cfg.isolated_venv:
                try:
                    self._prepare_isolated()
                except RuntimeError as e:
                    if self._cancelled:
                        return False, tr("msg.build_cancelled")
                    self.log(tr("log.error_line", error=e))
                    return False, tr("msg.isolated_failed", error=e)
            if cfg.is_nuitka:
                # Nuitka trabaja dentro de dist/ (<script>.build); se borra al terminar
                if cfg.clean and cfg.dist_dir:
                    self._temp_dirs.extend(nuitka_command.build_dirs(cfg))
            elif cfg.build_dir:
                # Solo la subcarpeta de trabajo de esta app, nunca build/ completo
                self._temp_dirs.append(os.path.join(cfg.build_dir, cfg.app_name))

            tool = cfg.backend_label
            self.status(tr("status.starting_backend", tool=tool))
            returncode = self._stream(self.cmd, track_phases=True)

            if returncode is None:
                self.log(tr("log.build_cancelled"))
                self._cleanup()
                return False, tr("msg.build_cancelled")

            if returncode != 0:
                self.progress(0)
                self.log(tr("log.backend_error", tool=tool))
                return False, tr("msg.build_failed")

            if cfg.is_nuitka and not nuitka_command.normalize_output(cfg, self.log):
                self.progress(0)
                self.log(tr("log.nuitka_no_output", path=cfg.dist_dir))
                return False, tr("msg.build_failed")

            self.progress(95)
            self.log(tr("log.backend_ok", tool=tool))

            ok, msg = self._post_build()
            self.progress(100)
            return ok, msg

        except Exception as e:
            self.log(tr("log.critical", error=e))
            self.progress(0)
            return False, tr("msg.critical", error=e)
