"""BuildConfig: única fuente de verdad de un build.

La GUI, el modo CLI, el generador de comando, el de .spec y los perfiles JSON
trabajan todos sobre este mismo objeto, así nunca se contradicen.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import List, Tuple

MODE_ONEDIR_LABEL  = "Directorio (onedir)"
MODE_ONEFILE_LABEL = "Archivo unico (onefile)"

PROFILE_SCHEMA = 2

# Compiladores soportados: PyInstaller empaqueta el intérprete con el bytecode;
# Nuitka traduce a C y compila un binario nativo.
BACKENDS = ("pyinstaller", "nuitka")
BACKEND_LABELS = {"pyinstaller": "PyInstaller", "nuitka": "Nuitka"}

# Plataforma objetivo → subcarpeta de la carpeta de salida automática
PLATFORM_FOLDERS = {
    "linux":    "Linux",
    "windows":  "Windows 11",
    "windows7": "Windows 7",
    "macos":    "Mac",
    "docker":   "Cross-compilate",
}


def default_platform():
    if sys.platform.startswith("linux"):
        return "linux"
    return "windows" if sys.platform == "win32" else "macos"


@dataclass
class BuildConfig:
    # Proyecto
    workspace: str = ""
    script: str = ""
    name: str = ""
    python_path: str = ""
    onefile: bool = False
    platform: str = field(default_factory=default_platform)
    backend: str = "pyinstaller"     # pyinstaller | nuitka

    # Recursos
    icon: str = ""
    version_file: str = ""
    appimage_icon: str = ""

    # Opciones de compilación
    noconsole: bool = True
    debug: bool = False
    clean: bool = True
    strip: bool = False
    noupx: bool = False
    bootloader_ignore: bool = False
    optimize: bool = False
    uac_admin: bool = False
    runtime_tmpdir: bool = False
    runtime_tmpdir_path: str = ""
    extra_flags: str = ""

    # Entorno aislado: compilar en un venv limpio creado desde requirements.txt
    isolated_venv: bool = False

    # Información de versión (Windows) generada desde el formulario
    version_info: bool = False
    app_version: str = "1.0.0"
    company: str = ""
    product: str = ""
    description: str = ""
    copyright: str = ""

    # Empaquetado posterior
    create_appimage: bool = False
    nsis: bool = False
    inno: bool = False
    dest_folder: str = ""

    # Firma de código (la contraseña del .pfx se lee de una variable de entorno, nunca del perfil)
    sign: bool = False
    sign_mode: str = "auto"          # auto | thumbprint | pfx
    sign_cert: str = ""              # huella SHA1, ruta del .pfx o identidad de codesign (macOS)
    sign_password_env: str = "PYI_GUI_SIGN_PASSWORD"
    sign_timestamp: str = "http://timestamp.digicert.com"

    # Release
    make_zip: bool = False
    make_checksums: bool = False

    # Directorios
    dist_path: str = ""
    build_path: str = ""
    venv_path: str = ""

    # Contenido
    add_data: List[Tuple[str, str]] = field(default_factory=list)
    hidden_imports: List[str] = field(default_factory=list)
    exclude_modules: List[str] = field(default_factory=list)
    collect_all: List[str] = field(default_factory=list)    # --collect-all agregados por el usuario
    collect_data: List[str] = field(default_factory=list)   # --collect-data
    copy_metadata: List[str] = field(default_factory=list)  # --copy-metadata
    # Módulos de dependencias desmarcadas en el escáner (no se guardan en el perfil:
    # el escaneo los recalcula al abrir el proyecto)
    dep_excludes: List[str] = field(default_factory=list)

    # ── Valores derivados ───────────────────────────────────────────────
    @property
    def is_nuitka(self):
        return self.backend == "nuitka"

    @property
    def backend_label(self):
        return BACKEND_LABELS.get(self.backend, "PyInstaller")

    @property
    def app_name(self):
        """Nombre real del ejecutable: --name o, si está vacío, el nombre del script
        (es lo que usa PyInstaller cuando no recibe --name)."""
        if self.name.strip():
            return self.name.strip()
        return Path(self.script).stem if self.script.strip() else "App"

    @property
    def dist_dir(self):
        if self.dist_path.strip():
            return self.dist_path.strip()
        return os.path.join(self.workspace, "dist") if self.workspace else ""

    @property
    def build_dir(self):
        if self.build_path.strip():
            return self.build_path.strip()
        return os.path.join(self.workspace, "build") if self.workspace else ""

    @property
    def effective_runtime_tmpdir(self):
        """Ruta de --runtime-tmpdir, o "" si no aplica (solo onefile)."""
        if not (self.runtime_tmpdir and self.onefile):
            return ""
        return self.runtime_tmpdir_path.strip() or os.path.join(tempfile.gettempdir(), self.app_name)

    @property
    def all_excludes(self):
        return sorted(set(self.exclude_modules) | set(self.dep_excludes))

    @property
    def make_nsis(self):
        return self.nsis and sys.platform == "win32" and not self.onefile

    @property
    def make_inno(self):
        return self.inno and sys.platform == "win32" and not self.onefile

    @property
    def make_appimage(self):
        return self.create_appimage and sys.platform.startswith("linux")

    @property
    def destination_dir(self):
        """Carpeta final si hay carpeta de salida automática configurada."""
        if not self.dest_folder.strip():
            return ""
        sub = PLATFORM_FOLDERS.get(self.platform, "Linux")
        return os.path.join(self.dest_folder.strip(), "Compilacion", sub, self.app_name)

    # ── Perfiles JSON ───────────────────────────────────────────────────
    def to_profile(self):
        """Dict para guardar como perfil. Mantiene las claves de versiones anteriores
        (mode, add_data_paths, checked_imports) para que los perfiles sigan siendo compatibles."""
        data = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "dep_excludes"}
        data["schema"] = PROFILE_SCHEMA
        data["mode"] = MODE_ONEFILE_LABEL if self.onefile else MODE_ONEDIR_LABEL
        data["add_data"] = [list(e) for e in self.add_data]
        data["add_data_paths"] = [src for src, _ in self.add_data]
        data["checked_imports"] = list(self.hidden_imports)
        return data

    @classmethod
    def from_profile(cls, data):
        cfg = cls()
        names = {f.name for f in fields(cls)} - {"add_data", "dep_excludes", "onefile"}
        for key in names:
            if key in data and data[key] is not None:
                default = getattr(cfg, key)
                value = data[key]
                if isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, list):
                    value = [str(v) for v in value]
                else:
                    value = str(value)
                setattr(cfg, key, value)
        if cfg.backend not in BACKENDS:
            cfg.backend = "pyinstaller"
        if "onefile" in data:
            cfg.onefile = bool(data["onefile"])
        elif "mode" in data:
            cfg.onefile = data["mode"] == MODE_ONEFILE_LABEL
        if data.get("add_data"):
            cfg.add_data = [(str(s), str(d)) for s, d in data["add_data"]]
        else:
            cfg.add_data = [(str(p), ".") for p in data.get("add_data_paths", [])]
        return cfg

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_profile(), f, indent=4, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_profile(json.load(f))
