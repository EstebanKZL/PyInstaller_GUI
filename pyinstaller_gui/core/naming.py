"""Convención de nombres de los artefactos de release.

    <AppName>-<versión>-<sistema>-<arq>-<variante>.<ext>

    MiApp-1.2.0-win-x64-setup.exe        instalador Windows 10/11, 64 bits
    MiApp-1.2.0-win7-x86-portable.zip    portable de la línea Windows 7/8, 32 bits
    MiApp-1.2.0-linux-x86_64.AppImage    AppImage (sin variante)
    SHA256SUMS.txt                       verificación de integridad

- AppName: el nombre del programa sin espacios ni caracteres raros.
- versión: sin la "v" inicial.
- sistema: win (Windows 10/11), win7 (línea Windows 7/8), linux o macos.
- arq: en Windows x64 / x86 / arm64; en Linux y macOS x86_64 / i686 / aarch64 / arm64.
"""

import platform as _platform
import re
import struct
import sys

CHECKSUMS_FILE = "SHA256SUMS.txt"

OS_LABELS = ("win", "win7", "linux", "macos")

# Código de máquina del encabezado PE (Windows) y ELF (Linux)
_PE_MACHINES = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}
_ELF_MACHINES = {3: "i686", 62: "x86_64", 183: "aarch64", 40: "armhf"}
# Equivalencias de platform.machine() → (Windows, Linux/macOS)
_HOST_MACHINES = {
    "amd64": ("x64", "x86_64"), "x86_64": ("x64", "x86_64"),
    "x86": ("x86", "i686"), "i386": ("x86", "i686"), "i686": ("x86", "i686"),
    "arm64": ("arm64", "arm64"), "aarch64": ("arm64", "aarch64"),
}


def artifact_app_name(app_name):
    """'Mi App 2' → 'MiApp2': sin espacios y solo caracteres seguros para un archivo."""
    name = re.sub(r"[^A-Za-z0-9._-]", "", app_name.replace(" ", ""))
    return name or "App"


def clean_version(version):
    v = (version or "").strip()
    if v[:1] in ("v", "V") and v[1:2].isdigit():
        v = v[1:]
    return re.sub(r"[^A-Za-z0-9._+-]", "", v) or "0.0.0"


def os_label(target_platform=None):
    """Etiqueta de sistema del build. No hay compilación cruzada: el sistema es siempre el
    de esta máquina, y en Windows la plataforma 'windows7' elige la línea legacy (win7)."""
    if sys.platform == "win32":
        return "win7" if target_platform == "windows7" else "win"
    return "macos" if sys.platform == "darwin" else "linux"


def binary_arch(path):
    """Arquitectura de un ejecutable leyendo su encabezado (PE o ELF), con la
    etiqueta que usa la convención. "" si no se reconoce."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
            if head[:2] == b"MZ" and len(head) >= 64:
                f.seek(struct.unpack_from("<I", head, 0x3C)[0])
                pe = f.read(6)
                if pe[:4] == b"PE\0\0":
                    return _PE_MACHINES.get(struct.unpack_from("<H", pe, 4)[0], "")
            elif head[:4] == b"\x7fELF" and len(head) >= 20:
                endian = "<" if head[5] == 1 else ">"
                return _ELF_MACHINES.get(struct.unpack_from(endian + "H", head, 18)[0], "")
    except (OSError, struct.error):
        pass
    return ""


def host_arch(os_lbl):
    """Arquitectura de este Python, con la etiqueta del sistema pedido."""
    machine = _platform.machine().lower()
    win, unix = _HOST_MACHINES.get(machine, (machine or "x64", machine or "x86_64"))
    if struct.calcsize("P") == 4:   # Python de 32 bits sobre un sistema de 64
        win, unix = "x86", "i686"
    return win if os_lbl in ("win", "win7") else unix


def arch_label(os_lbl, exe_path=""):
    """Arquitectura del binario compilado; si no se puede leer, la de este Python."""
    return (binary_arch(exe_path) if exe_path else "") or host_arch(os_lbl)


def artifact_name(app_name, version, os_lbl, arch, variant="", ext=""):
    """Nombre completo de un artefacto. 'ext' con o sin punto; variant vacío = sin variante."""
    parts = [artifact_app_name(app_name), clean_version(version), os_lbl, arch]
    if variant:
        parts.append(variant)
    ext = ext.lstrip(".")
    return "-".join(parts) + (f".{ext}" if ext else "")


def is_artifact_of(entry, app_name):
    """True si 'entry' sigue la convención y es de esta app (y no de 'MiApp-Lite')."""
    pattern = rf"^{re.escape(artifact_app_name(app_name))}-[^-]+-(?:{'|'.join(OS_LABELS)})-[A-Za-z0-9_]+(?:-[a-z-]+)?\."
    return re.match(pattern, entry) is not None
