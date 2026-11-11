"""Base de conocimiento de errores frecuentes de PyInstaller.

Cada clave tiene su título y su solución en i18n.py (err.<clave>.title / err.<clave>.fix).
"""

COMMON_ERRORS = [
    "module_not_found",
    "file_not_found",
    "dll_not_found",
    "pillow",
    "antivirus",
    "recursion",
    "spec_conflict",
    "icon_missing",
    "onefile_slow",
    "import_error",
]
