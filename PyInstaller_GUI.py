#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyInstaller GUI - PRO Builder
Compatibilidad: Windows 7 / 10 / 11 / Linux / macOS (PySide6 / PySide2)
Autor: EstebanKZL

Lanzador: el código vive en el paquete pyinstaller_gui/.
Sin argumentos abre la GUI; con argumentos usa el modo CLI (ver --help).
"""

import sys

from pyinstaller_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
