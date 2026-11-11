"""Intérpretes de afuera (venv del proyecto, perfiles): no se ejecutan sin confirmación."""

import os
import sys

import pytest

from pyinstaller_gui.core.trust import add_trusted, is_inside, is_trusted, needs_confirmation


def test_reglas_de_confianza(tmp_path):
    ws = tmp_path / "proyecto"
    venv_py = ws / "venv" / "Scripts" / "python.exe"
    system_py = tmp_path / "Python312" / "python.exe"
    for f in (venv_py, system_py):
        f.parent.mkdir(parents=True)
        f.write_bytes(b"binario")
    assert is_inside(str(venv_py), str(ws)) and not is_inside(str(system_py), str(ws))
    assert needs_confirmation(str(venv_py), str(ws))                       # venv del proyecto
    assert not needs_confirmation(str(system_py), str(ws))                 # Python del sistema
    assert needs_confirmation(str(system_py), str(ws), from_profile=True)  # cualquier ruta de un perfil
    assert needs_confirmation(str(system_py), force=True)                  # marcado sin verificar
    trusted = add_trusted([], str(venv_py))
    assert add_trusted(trusted, str(venv_py)) == trusted and len(trusted) == 1
    assert not needs_confirmation(str(venv_py), str(ws), trusted=trusted, force=True)
    assert not needs_confirmation(str(system_py), str(ws), from_profile=True,
                                  trusted=add_trusted([], str(system_py)))
    assert not is_trusted(str(venv_py), [str(venv_py)])                    # ruta sin huella: no alcanza


def test_la_confianza_se_pierde_si_el_venv_cambia(tmp_path):
    py = tmp_path / ".venv" / "Scripts" / "python.exe"
    py.parent.mkdir(parents=True)
    py.write_bytes(b"original")
    cfg = tmp_path / ".venv" / "pyvenv.cfg"
    cfg.write_text("home = /usr/python312", encoding="utf-8")
    trusted = add_trusted([], str(py))
    assert is_trusted(str(py), trusted)
    cfg.write_text("home = /otra/carpeta", encoding="utf-8")   # otro Python base
    assert not is_trusted(str(py), trusted)
    trusted = add_trusted(trusted, str(py))
    assert is_trusted(str(py), trusted) and len(trusted) == 1          # reemplaza la huella vieja
    py.write_bytes(b"reemplazado")                                     # otro ejecutable
    assert not is_trusted(str(py), trusted)


def _fake_venv(ws):
    folder = ws / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    folder.mkdir(parents=True)
    py = folder / ("python.exe" if sys.platform == "win32" else "python3")
    py.write_text("no ejecutar", encoding="utf-8")
    py.chmod(0o755)
    return str(py)


def test_el_buscador_no_ejecuta_el_venv_sin_confirmar(tmp_path, monkeypatch):
    pytest.importorskip("pyinstaller_gui.qt_compat", exc_type=ImportError)
    from pyinstaller_gui import workers
    venv_py = _fake_venv(tmp_path)
    ran = []
    real_run = workers.subprocess.run

    def spy(cmd, *a, **k):
        ran.append(os.path.normcase(os.path.normpath(cmd[0])))
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(workers.subprocess, "run", spy)
    found = []
    worker = workers.PythonLocatorWorker(str(tmp_path))
    worker.versions_found.connect(found.extend)
    worker.run()
    assert os.path.normcase(os.path.normpath(venv_py)) not in ran
    entry = next(p for p in found if p["source"] == "venv")
    assert entry["untrusted"] and entry["version"] == ""

    ran.clear()
    worker = workers.PythonLocatorWorker(str(tmp_path), trusted=add_trusted([], venv_py))
    worker.run()
    assert os.path.normcase(os.path.normpath(venv_py)) in ran   # confirmado: ahora sí se verifica


def test_perfil_con_python_rechazado_no_se_ejecuta(qapp_window, cfg, monkeypatch):
    window, mw = qapp_window
    monkeypatch.setattr(mw.QMessageBox, "question", staticmethod(lambda *a, **k: mw.QMessageBox.No))
    tested = []
    monkeypatch.setattr(window, "test_python", lambda p: tested.append(p) or True)
    window._loading_profile = True
    window.apply_config(cfg)          # cfg.python_path = sys.executable
    assert tested == [] and window.project_python is None

    monkeypatch.setattr(mw.QMessageBox, "question", staticmethod(lambda *a, **k: mw.QMessageBox.Yes))
    window.apply_config(cfg)
    assert window.project_python == cfg.python_path
    window.apply_config(cfg)          # ya confiable: no vuelve a preguntar
    assert is_trusted(cfg.python_path, window._trusted_pythons())


@pytest.fixture
def qapp_window(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qt = pytest.importorskip("pyinstaller_gui.qt_compat", exc_type=ImportError)
    app = qt.QApplication.instance() or qt.QApplication([])
    from pyinstaller_gui.ui import main_window as mw
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(mw.QMessageBox, name, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(mw, "QSettings", lambda *a: qt.QSettings("PyInstallerGUI-tests", "ProBuilder"))
    w = mw.BuilderApp()
    w.settings.clear()
    yield w, mw
    for th in (w._pyinstaller_chk, w._scan_worker, *w._stale_checks):   # no destruir hilos en marcha
        if th is not None:
            th.wait(30000)
    w.close()
    w.settings.clear()
    assert app is not None
