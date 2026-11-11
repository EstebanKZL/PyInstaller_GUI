"""Firma de código: signtool (Windows) y codesign (macOS).

La contraseña del certificado .pfx NUNCA se guarda en el perfil: se lee de una
variable de entorno cuyo nombre sí se guarda (por defecto PYI_GUI_SIGN_PASSWORD).
"""

import glob
import os
import subprocess
import sys

from .process import find_tool, sub_kwargs
from ..i18n import tr

DEFAULT_TIMESTAMP = "http://timestamp.digicert.com"
DEFAULT_PASSWORD_ENV = "PYI_GUI_SIGN_PASSWORD"


def find_signtool():
    tool = find_tool("signtool")
    if tool:
        return tool
    if sys.platform == "win32":
        arch = "x64" if sys.maxsize > 2**32 else "x86"
        for root in (r"C:\Program Files (x86)\Windows Kits\10\bin", r"C:\Program Files\Windows Kits\10\bin"):
            found = sorted(glob.glob(os.path.join(root, "10.*", arch, "signtool.exe")))
            if found:
                return found[-1]   # el SDK más nuevo
    return None


def signtool_command(tool, path, mode="auto", cert="", password="", timestamp=DEFAULT_TIMESTAMP):
    """mode: 'auto' (/a: el mejor certificado del almacén), 'thumbprint' (/sha1) o 'pfx' (/f archivo)."""
    cmd = [tool, "sign", "/fd", "SHA256"]
    if mode == "thumbprint":
        cmd += ["/sha1", cert.replace(" ", "")]
    elif mode == "pfx":
        cmd += ["/f", cert]
        if password:
            cmd += ["/p", password]
    else:
        cmd += ["/a"]
    if timestamp:
        cmd += ["/tr", timestamp, "/td", "SHA256"]
    return cmd + [path]


def codesign_command(identity, path):
    cmd = ["codesign", "--force", "--timestamp", "--options", "runtime", "--sign", identity or "-"]
    if path.endswith(".app"):
        cmd.insert(2, "--deep")
    return cmd + [path]


def redact(cmd):
    """Comando para mostrar en el log sin la contraseña."""
    out = list(cmd)
    if "/p" in out:
        out[out.index("/p") + 1] = "********"
    return out


def sign_files(cfg, files, log):
    """Firma cada archivo. Devuelve True si todos se firmaron."""
    files = [f for f in files if f and os.path.exists(f)]
    if not files:
        log(tr("log.sign_nothing"))
        return False
    if sys.platform == "win32":
        tool = find_signtool()
        if not tool:
            log(tr("log.sign_no_signtool"))
            return False
        password = os.environ.get(cfg.sign_password_env or DEFAULT_PASSWORD_ENV, "")
        if cfg.sign_mode == "pfx" and not os.path.isfile(cfg.sign_cert):
            log(tr("log.sign_no_pfx", path=cfg.sign_cert))
            return False
        make = lambda p: signtool_command(tool, p, cfg.sign_mode, cfg.sign_cert, password, cfg.sign_timestamp)  # noqa: E731
    elif sys.platform == "darwin":
        make = lambda p: codesign_command(cfg.sign_cert, p)  # noqa: E731
    else:
        log(tr("log.sign_unsupported"))
        return False

    ok = True
    for path in files:
        cmd = make(path)
        log("[sign] " + " ".join(redact(cmd)))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **sub_kwargs())
        except Exception as e:
            log(tr("log.sign_error", file=os.path.basename(path), error=e))
            ok = False
            continue
        if r.returncode == 0:
            log(tr("log.signed", path=path))
        else:
            ok = False
            log(tr("log.sign_failed", file=os.path.basename(path), output=(r.stdout + r.stderr).strip()))
    return ok
