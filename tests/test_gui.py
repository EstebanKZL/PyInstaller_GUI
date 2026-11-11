"""Pruebas de humo de la GUI en modo offscreen (se saltean si no hay PySide)."""

import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
qt = pytest.importorskip("pyinstaller_gui.qt_compat", exc_type=ImportError)

from pyinstaller_gui.core.config import BuildConfig  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return qt.QApplication.instance() or qt.QApplication([])


@pytest.fixture
def window(qapp, monkeypatch):
    from pyinstaller_gui.ui import main_window as mw
    # Diálogos no bloqueantes y QSettings aislado (no tocar las preferencias reales del usuario)
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(mw.QMessageBox, name, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(mw.QMessageBox, "question", staticmethod(lambda *a, **k: mw.QMessageBox.Yes))
    monkeypatch.setattr(mw, "QSettings", lambda *a: qt.QSettings("PyInstallerGUI-tests", "ProBuilder"))
    w = mw.BuilderApp()
    yield w
    w.close()
    w.settings.clear()


def _wait(qapp, pred, secs):
    t = time.time()
    while time.time() - t < secs:
        qapp.processEvents()
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_config_ida_y_vuelta_por_la_interfaz(window, cfg):
    cfg.name, cfg.onefile, cfg.uac_admin, cfg.noupx = "X", True, sys.platform == "win32", True
    cfg.add_data = [(cfg.script, "conf")]
    cfg.hidden_imports = ["PIL", "requests"]
    cfg.exclude_modules = ["tkinter"]
    window._loading_profile = True
    window.apply_config(cfg)
    got = window.collect_config()
    for attr in ("workspace", "script", "name", "onefile", "uac_admin", "noupx", "add_data", "exclude_modules"):
        assert getattr(got, attr) == getattr(cfg, attr), attr
    assert sorted(got.hidden_imports) == ["PIL", "requests"]


def test_pil_sugeridos_desmarcados(window):
    assert window.collect_config().hidden_imports == []


def test_comando_y_spec_desde_la_interfaz(window, cfg, project, qapp):
    (project / "requirements.txt").write_text("pytest\npaquete-inexistente-xyz\n", encoding="utf-8")
    window.current_workspace = str(project)
    window.set_python_path(sys.executable, validated=True)
    assert _wait(qapp, lambda: window._scan_worker and not window._scan_worker.isRunning() and window.dep_items, 60)
    deps = {d.pkg_name: d for d in window.dep_items}
    assert deps["pytest"].installed and not deps["paquete-inexistente-xyz"].installed

    cmd, built_cfg = window.generate_command()
    assert cmd and cmd[-1] == str(project / "main.py")
    compile(window.spec_output.toPlainText(), "x.spec", "exec")
    assert isinstance(built_cfg, BuildConfig)


def _items(lst):
    return [lst.item(i) for i in range(lst.count())]


@pytest.mark.slow
def test_flujo_analisis_completo(window, cfg, project, qapp):
    """Import dinámico → el exe falla → el diagnóstico lo detecta → se aplica → el exe funciona."""
    pytest.importorskip("PyInstaller")
    pytest.importorskip("pyflakes")
    (project / "main.py").write_text(
        "import importlib, pyflakes\n"
        "importlib.import_module('plugin_local')\n"
        "print('FLUJO-OK')\n", encoding="utf-8")
    (project / "plugin_local.py").write_text("X = 1\n", encoding="utf-8")
    (project / "requirements.txt").write_text("pyinstaller\n", encoding="utf-8")

    window.current_workspace = str(project)
    window.set_python_path(sys.executable, validated=True)
    assert _wait(qapp, lambda: window._scan_worker and not window._scan_worker.isRunning() and window.dep_items, 60)
    window.noconsole.setChecked(False)
    tab = window.analysis_tab

    # 1) Análisis estático
    tab.run_import_analysis()
    assert _wait(qapp, lambda: tab.btn_analyze.isEnabled() and tab.imports_list.count(), 60)
    texts = [it.text() for it in _items(tab.imports_list)]
    assert any("[FALTA]  pyflakes" in t for t in texts), texts
    assert any("[DINÁMICO]  plugin_local" in t for t in texts), texts
    for it in _items(tab.imports_list):           # dejar solo el requirement marcado
        if "DINÁMICO" in it.text():
            it.setCheckState(qt.Qt.Unchecked)
    tab._apply_checked(tab.imports_list)
    assert "pyflakes" in (project / "requirements.txt").read_text(encoding="utf-8")

    def build_and_test():
        window.run_build()
        assert _wait(qapp, lambda: window.worker and not window.worker.isRunning() and window.btn_build.isEnabled(), 400)
        assert _wait(qapp, lambda: tab.btn_smoke.isEnabled(), 60), tab.post_summary.text()
        tab.run_smoke_test()
        assert _wait(qapp, lambda: tab._smoke_worker and not tab._smoke_worker.isRunning(), 60)
        qapp.processEvents()
        return tab.smoke_result

    # 2) Primer build: el import dinámico no se empaquetó → el exe se cae
    result = build_and_test()
    assert result.objectName() == "lblError" and "código" in result.text(), result.text()
    assert window.collect_config().hidden_imports == []
    assert any("Size" not in it.text() for it in _items(tab.size_list)) and tab.size_list.count() > 0
    diag = [it for it in _items(tab.diag_list) if bool(it.data(qt.Qt.UserRole + 2))]
    assert diag and "plugin_local" in diag[0].text(), [it.text() for it in _items(tab.diag_list)]

    # 3) Aplicar el diagnóstico (hidden import) y recompilar → funciona
    tab._apply_checked(tab.diag_list)
    assert "plugin_local" in window.collect_config().hidden_imports
    result = build_and_test()
    assert result.objectName() == "lblOk", result.text()
    assert "FLUJO-OK" in window.log_output.toPlainText()


# ── Fase 4: distribución y pulido de interfaz ────────────────────────────
def test_distribucion_ida_y_vuelta(window, cfg):
    cfg.version_info, cfg.app_version, cfg.company, cfg.copyright = True, "2.3.4", "ACME", "© ACME"
    cfg.sign, cfg.sign_mode, cfg.sign_cert, cfg.sign_timestamp = True, "pfx", "C:/certs/cert.pfx", ""
    cfg.make_zip, cfg.make_checksums = True, True
    cfg.inno = sys.platform == "win32"
    window._loading_profile = True
    window.apply_config(cfg)
    got = window.collect_config()
    for attr in ("version_info", "app_version", "company", "copyright", "sign", "sign_mode", "sign_cert",
                 "sign_timestamp", "make_zip", "make_checksums", "inno"):
        assert getattr(got, attr) == getattr(cfg, attr), attr


def test_bloqueo_de_modo(window):
    w = window
    w.mode_combo.setCurrentIndex(1)                       # el usuario eligió onefile
    w.runtime_tmpdir_cb.setChecked(True)
    assert w.mode_combo.currentIndex() == 1 and not w.mode_combo.isEnabled()
    if sys.platform == "win32":
        w.nsis_cb.setChecked(True)                         # onedir gana sobre runtime-tmpdir
        w.inno_cb.setChecked(True)
        assert w.mode_combo.currentIndex() == 0 and "NSIS / Inno Setup" in w.mode_combo.toolTip()
        w.nsis_cb.setChecked(False)                        # Inno sigue pidiendo onedir
        assert w.mode_combo.currentIndex() == 0 and not w.mode_combo.isEnabled()
        w.inno_cb.setChecked(False)                        # vuelve a mandar runtime-tmpdir
        assert w.mode_combo.currentIndex() == 1
    w.runtime_tmpdir_cb.setChecked(False)
    assert w.mode_combo.isEnabled() and w.mode_combo.currentIndex() == 1   # se respeta la elección


def test_convertir_icono(window, project):
    from pyinstaller_gui.core.icons import ICO_SIZES, read_ico_sizes
    img = qt.QImage(300, 200, qt.QImage.Format_ARGB32)     # no cuadrado: se centra
    img.fill(qt.QColor("#007acc"))
    png = project / "logo.png"
    assert img.save(str(png), "PNG")
    window.current_workspace = str(project)
    ico, icns = window.distribution_tab.convert_icon(str(png))
    assert read_ico_sizes(ico) == list(ICO_SIZES)
    assert open(icns, "rb").read(4) == b"icns"
    assert window.icon_input.text() == ico


def test_generar_workflow_desde_la_pestana(window, cfg, project):
    window._loading_profile = True
    window.apply_config(cfg)
    written = window.distribution_tab.generate_workflow()
    assert any(p.replace("\\", "/").endswith(".github/workflows/build-main.yml") for p in written)
    assert (project / "main.ci.spec").is_file()


def test_log_coloreado_y_busqueda(window):
    log = window.log_output
    log.clear()
    for line in ("1234 INFO: Analyzing", "1234 WARNING: lib not found", "[X] Error en PyInstaller.",
                 "[OK] listo", "Buscame aqui", "otra linea buscame"):
        log.append(line)
    doc = log.document()
    colors = [doc.findBlockByNumber(i).begin().fragment().charFormat().foreground().color().name()
              for i in range(doc.blockCount())]
    from pyinstaller_gui.ui.theme import THEME
    assert colors[:4] == [THEME["text"], THEME["counter"], THEME["error"], THEME["ok"]]
    assert log.objectName() == "logView" and log.maximumBlockCount() > 0
    window.log_search.setText("buscame")
    window._find_in_log(False)
    assert window.log_search_count.text().startswith("2 ")
    assert log.textCursor().selectedText().lower() == "buscame"


def test_atajos(window):
    keys = {a.shortcut().toString() for a in window.actions()}
    assert {"Ctrl+B", "Ctrl+S", "Ctrl+O", "Ctrl+F", "F5", "Esc", "Ctrl+1", "Ctrl+7"} <= keys
