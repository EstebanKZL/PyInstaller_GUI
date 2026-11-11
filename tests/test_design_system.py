"""Reglas del sistema de diseño (Prompt de diseño PySide6/PySide2 v5.4) verificadas en tests,
para que no se vuelvan a romper: colores solo en THEME, textos solo por tr(), ayuda en
cada control, ventana de 1280×720 como mínimo."""

import glob
import io
import os
import re
import subprocess
import sys

import pytest

from pyinstaller_gui import i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "pyinstaller_gui")
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def _sources(*parts):
    return [f for f in glob.glob(os.path.join(PKG, *parts), recursive=True) if f.endswith(".py")]


# ── Reglas estáticas (sin Qt) ────────────────────────────────────────────
def test_sin_colores_hex_fuera_del_tema():
    offenders = []
    for f in _sources("**", "*.py"):
        if f.endswith(os.path.join("ui", "theme.py")):
            continue
        for n, line in enumerate(io.open(f, encoding="utf-8"), 1):
            if HEX.search(line) and not line.lstrip().startswith("#"):
                offenders.append(f"{os.path.relpath(f, ROOT)}:{n}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_sin_setstylesheet_inline_en_la_interfaz():
    offenders = [f"{os.path.relpath(f, ROOT)}:{n}" for f in _sources("ui", "*.py")
                 for n, line in enumerate(io.open(f, encoding="utf-8"), 1)
                 if ".setStyleSheet(" in line and not f.endswith("theme.py")]
    assert not offenders, offenders


def test_sin_imports_directos_de_pyside():
    offenders = [os.path.relpath(f, ROOT) for f in _sources("**", "*.py")
                 if not f.endswith("qt_compat.py")
                 and re.search(r"^\s*(from|import) (PySide2|PySide6|PyQt5|PyQt6)", io.open(f, encoding="utf-8").read(), re.M)]
    assert not offenders, offenders


def test_traducciones_completas():
    assert i18n.check_translations() == []
    assert set(i18n.STRINGS["es"]) == set(i18n.STRINGS["en"])
    # Los parámetros {x} tienen que ser los mismos en los dos idiomas
    for key in i18n.STRINGS["es"]:
        es = set(re.findall(r"\{(\w+)\}", i18n.STRINGS["es"][key]))
        en = set(re.findall(r"\{(\w+)\}", i18n.STRINGS["en"][key]))
        assert es == en, f"{key}: {es} != {en}"


def test_tr_fallback_y_parametros():
    old = i18n.LANG
    try:
        i18n.set_language("en")
        assert i18n.tr("btn.build") == "Build"
        assert i18n.tr("clave.inexistente") == "clave.inexistente"
        assert i18n.tr("status.matches", n=3) == "3 match(es)"
        i18n.set_language("xx")
        assert i18n.LANG == "es"
    finally:
        i18n.set_language(old)


def test_nucleo_sin_qt_aun_traducido():
    """El núcleo usa tr() sin importar Qt: el CLI sigue funcionando sin PySide."""
    code = ("import sys; sys.modules['PySide6'] = None; sys.modules['PySide2'] = None; "
            "from pyinstaller_gui import i18n; i18n.set_language('en'); "
            "from pyinstaller_gui.core.postbuild import diagnose_log; "
            "print(diagnose_log(\"ModuleNotFoundError: No module named 'abc'\")[0]['message'])")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "hidden import" in r.stdout


# ── Reglas en la interfaz real (offscreen) ───────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
qt = pytest.importorskip("pyinstaller_gui.qt_compat", exc_type=ImportError)


def test_temas_con_las_mismas_claves_y_qss_valido():
    from pyinstaller_gui.ui.theme import THEMES, build_stylesheet
    assert set(THEMES["dark"]) == set(THEMES["light"])
    icons = {k: "x.png" for k in ("check", "arrow_down", "arrow_up", "arrow_down_dis", "arrow_up_dis")}
    for t in THEMES.values():
        qss = build_stylesheet(t, icons, {"ui": "Segoe UI", "mono": "Consolas"})
        assert "QWidget {" in qss and "background-color" not in qss.split("QWidget {", 1)[1].split("}", 1)[0]
        for color in t.values():
            assert color in qss or color in (t["field_label"], t["selection_text"])


@pytest.fixture(scope="module")
def qapp():
    app = qt.QApplication.instance() or qt.QApplication([])
    from pyinstaller_gui.ui.theme import setup_appearance
    setup_appearance(app)
    return app


def _window(monkeypatch):
    from pyinstaller_gui.ui import main_window as mw
    monkeypatch.setattr(mw, "QSettings", lambda *a: qt.QSettings("PyInstallerGUI-tests", "ProBuilder"))
    return mw.BuilderApp()


def test_ventana_1280x720_y_estructura(qapp, monkeypatch):
    w = _window(monkeypatch)
    try:
        assert w.minimumWidth() >= 1280 and w.minimumHeight() >= 720
        assert w.centralWidget().objectName() == "central"
        assert w.findChild(qt.QFrame, "headerBar") is not None
        assert [m.title() for m in w.menuBar().findChildren(qt.QMenu) if m.parent() is w.menuBar()]
        primaries = [b for b in w.findChildren(qt.QPushButton) if b.objectName() == "btnPrimary"
                     and b.window() is w and b.parent() is w.btn_build.parent()]
        assert primaries == [w.btn_build]   # una sola acción primaria en la barra inferior
    finally:
        w.settings.clear()


def test_todo_control_interactivo_tiene_ayuda(qapp, monkeypatch):
    w = _window(monkeypatch)
    try:
        types = (qt.QPushButton, qt.QCheckBox, qt.QRadioButton, qt.QLineEdit, qt.QComboBox, qt.QSpinBox)
        missing = []
        for widget in w.findChildren(qt.QWidget):
            if not isinstance(widget, types):
                continue
            parent = widget.parent()
            if isinstance(parent, (qt.QComboBox, qt.QSpinBox)):   # editor interno del combo/spin
                continue
            if not widget.toolTip():
                missing.append(f"{type(widget).__name__} '{getattr(widget, 'text', lambda: '')()}'")
        assert not missing, missing
        # Recorrido desde la barra de menús (findChildren(QMenu) en PySide2 puede devolver
        # envoltorios de menús ya destruidos)
        def menu_actions(container):
            for a in container.actions():
                if a.menu() is not None:
                    yield from menu_actions(a.menu())
                elif not a.isSeparator() and a.isEnabled():
                    yield a
        actions = list(menu_actions(w.menuBar()))
        assert actions and all(a.toolTip() for a in actions)
    finally:
        w.settings.clear()


@pytest.mark.parametrize("lang", ["es", "en"])
def test_interfaz_sin_claves_crudas(qapp, monkeypatch, lang):
    key = re.compile(r"\b(?:tip|lbl|btn|msg|tab|section|ph|hint|chk|status|badge|an|dist|log|dlg|filter|src|deps|"
                     r"menu|action|err|kb|diag|note|ci|platform|mode)\.[a-z_]+\b")
    old = i18n.LANG
    i18n.set_language(lang)
    try:
        w = _window(monkeypatch)
        texts = [w.tabs.tabText(i) for i in range(w.tabs.count())]
        for obj in w.findChildren(qt.QWidget) + w.findChildren(qt.QAction):
            for getter in ("text", "toolTip", "placeholderText", "title"):
                f = getattr(obj, getter, None)
                if callable(f):
                    try:
                        v = f()
                    except TypeError:
                        continue
                    if isinstance(v, str):
                        texts.append(v)
        raw = sorted({key.search(t).group(0) for t in texts if key.search(t)})
        assert not raw, raw
        if lang == "en":
            assert w.btn_build.text() == "Build" and w.tabs.tabText(0) == "Main"
        w.settings.clear()
    finally:
        i18n.set_language(old)
