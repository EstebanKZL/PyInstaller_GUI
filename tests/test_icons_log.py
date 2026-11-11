"""Íconos del sistema de diseño, registro a archivo y errores no controlados."""

import logging
import os
import sys

import pytest

from pyinstaller_gui import applog


def test_registro_rotativo_y_errores(tmp_path, monkeypatch):
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        path = applog.setup_logging("PySide6", folder=str(tmp_path))
        assert path == str(tmp_path / applog.LOG_FILENAME) == applog.log_path()
        shown = []
        monkeypatch.setattr(sys, "excepthook", sys.excepthook)
        hook = applog.install_excepthook(lambda error, details: shown.append((error, details)))
        try:
            raise ValueError("falla de prueba")
        except ValueError:
            hook(*sys.exc_info())
        for h in root.handlers:
            h.flush()
        text = open(path, encoding="utf-8").read()
        assert "Inicio" in text and "falla de prueba" in text and "Traceback" in text
        assert shown and shown[0][0] == "falla de prueba" and "ValueError" in shown[0][1]
    finally:
        for h in root.handlers[:]:
            if h not in before:
                root.removeHandler(h)
                h.close()


def test_iconos_de_acciones_existen_y_se_dibujan():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qt = pytest.importorskip("pyinstaller_gui.qt_compat", exc_type=ImportError)
    qt.QApplication.instance() or qt.QApplication([])
    from pyinstaller_gui.ui.icons import ACTION_ICONS, ICON_SVG, icon, set_button_icon
    missing = sorted({name for name in ACTION_ICONS.values() if name not in ICON_SVG})
    assert not missing, missing
    if qt.QSvgRenderer is None:
        pytest.skip("QtSvg no disponible")
    image = icon("save").pixmap(16, 16).toImage()
    assert any(image.pixelColor(x, y).alpha() > 0 for x in range(16) for y in range(16))
    btn = qt.QPushButton("Guardar")
    btn.setObjectName("btnPrimary")
    set_button_icon(btn, "save")
    assert not btn.icon().isNull() and btn.property("hasIcon") is True
