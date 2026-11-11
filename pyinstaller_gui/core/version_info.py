"""Archivo de versión de Windows (VSVersionInfo) generado desde un formulario.

Es lo que muestra Windows en Propiedades → Detalles del .exe (empresa, producto,
versión, copyright). Reemplaza tener que escribir version.txt a mano.
"""

import os
import re
import tempfile

from .outputs import safe_app_name


def parse_version(text):
    """'1.2' → (1, 2, 0, 0). Ignora sufijos no numéricos ('1.2.3-beta' → (1, 2, 3, 0))."""
    nums = [int(n) for n in re.findall(r"\d+", text or "")][:4]
    nums = [min(n, 65535) for n in nums]
    return tuple(nums + [0] * (4 - len(nums)))


def version_string(text):
    return ".".join(str(n) for n in parse_version(text))


def generate_version_info(app_name, version="1.0.0", company="", product="", description="", copyright=""):
    v = parse_version(version)
    vs = version_string(version)
    strings = [
        ("CompanyName", company),
        ("FileDescription", description or product or app_name),
        ("FileVersion", vs),
        ("InternalName", app_name),
        ("LegalCopyright", copyright),
        ("OriginalFilename", f"{app_name}.exe"),
        ("ProductName", product or app_name),
        ("ProductVersion", vs),
    ]
    body = ",\n".join(f"          StringStruct({k!r}, {val!r})" for k, val in strings)
    return (
        "# UTF-8\n"
        "# Generado por PyInstaller GUI PRO Builder\n"
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers={v},\n"
        f"    prodvers={v},\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable(\n"
        "        '040904B0',\n"
        "        [\n"
        f"{body}\n"
        "        ])\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n"
    )


def version_file_path(cfg):
    base = os.path.join(cfg.workspace, ".pyinstaller_gui") if cfg.workspace else tempfile.gettempdir()
    return os.path.join(base, f"version_info_{safe_app_name(cfg.app_name)}.txt")


def write_version_file(cfg):
    """Escribe el archivo de versión de cfg y devuelve su ruta."""
    path = version_file_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = generate_version_info(cfg.app_name, cfg.app_version, cfg.company, cfg.product,
                                 cfg.description, cfg.copyright)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
