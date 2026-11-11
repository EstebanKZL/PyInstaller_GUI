import sys

import pytest

from pyinstaller_gui.core.command import build_command, build_spec
from pyinstaller_gui.core.imports_scan import analyze, scan_imports
from pyinstaller_gui.core.knowledge import hints_for
from pyinstaller_gui.core.packages import query_modules
from pyinstaller_gui.core.postbuild import diagnose_log, human_size, parse_warn_file, size_report, smoke_test


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def code_project(project):
    _write(project / "main.py",
           "import os, json\nimport requests\nfrom PIL import Image\nimport helpers\n"
           "from paquete.sub import cosa\nimport importlib\n"
           "plugin = importlib.import_module('mis_plugins.csv')\nimport uvicorn\n")
    _write(project / "helpers.py", "import cv2\n")
    _write(project / "paquete" / "__init__.py", "")
    _write(project / "paquete" / "sub.py", "cosa = 1\n")
    _write(project / "roto.py", "def (:\n")
    _write(project / ".venv" / "lib" / "ajeno.py", "import no_deberia_verse\n")
    _write(project / "build" / "x.py", "import tampoco\n")
    _write(project / "tests" / "test_algo.py", "import pytest\n")
    _write(project / "test_suelto.py", "import hypothesis\n")
    return project


def test_scan_imports(code_project):
    scan = scan_imports(str(code_project))
    tops = scan.top_level
    assert {"os", "json", "requests", "PIL", "helpers", "paquete", "cv2", "uvicorn"} <= tops
    assert "no_deberia_verse" not in tops and "tampoco" not in tops    # venv y build/ se ignoran
    assert "pytest" not in tops and "hypothesis" not in tops           # los tests no van en el ejecutable
    assert {"helpers", "paquete", "main"} <= scan.local_modules
    assert "mis_plugins.csv" in scan.dynamic
    assert len(scan.errors) == 1 and "roto.py" in scan.errors[0]
    assert "PIL.Image" in scan.imports


def test_analyze_faltantes_sin_uso_y_sugerencias(code_project):
    scan = scan_imports(str(code_project))
    reqs = [("requests", "", "requests"), ("Pillow", "", "Pillow"), ("numpy", "", "numpy"),
            ("pyinstaller", "", "pyinstaller")]
    pkg_info = {"Pillow": {"modules": ["PIL"]}, "requests": {"modules": ["requests"]}, "numpy": {"modules": ["numpy"]}}
    module_info = {"cv2": {"importable": True, "dists": ["opencv-python"]}, "uvicorn": {"importable": False, "dists": []}}
    rep = analyze(scan, reqs, pkg_info, module_info)
    missing = {m["module"]: m for m in rep.missing}
    assert set(missing) == {"cv2", "uvicorn"}               # os/json = stdlib, helpers/paquete = locales
    assert missing["cv2"]["dists"] == ["opencv-python"] and missing["cv2"]["files"] == ["helpers.py"]
    assert rep.unused == ["numpy"]                          # pyinstaller es herramienta de build
    assert [d["module"] for d in rep.dynamic] == ["mis_plugins.csv"]
    hint_mods = {h["module"] for h in rep.hints}
    assert {"uvicorn", "PIL"} <= hint_mods


def test_hints_for_nombres_con_puntos():
    assert [k for k, _ in hints_for(["win32serviceutil"])] == ["win32serviceutil"]
    assert hints_for(["os", "json"]) == []


def test_query_modules_python_real():
    info = query_modules(sys.executable, ["pytest", "json", "modulo_inexistente_xyz"])
    assert info["pytest"]["importable"] and "pytest" in info["pytest"]["dists"]
    assert not info["modulo_inexistente_xyz"]["importable"]


def test_parse_warn_file(tmp_path, project):
    script = project / "main.py"
    warn = tmp_path / "warn-main.txt"
    warn.write_text(
        "This file lists modules PyInstaller was not able to find.\n\n"
        f"missing module named opcional - imported by {script} (optional)\n"
        f"missing module named falta_de_verdad - imported by {script} (top-level), helpers (delayed)\n"
        "missing module named pwd - imported by posixpath (delayed, conditional, optional), shutil (delayed, optional)\n"
        "missing module named 'org.python' - imported by copy (optional)\n"
        "missing module named de_helpers - imported by helpers (top-level)\n", encoding="utf-8")
    mods = parse_warn_file(str(warn), str(project), local_modules={"helpers", "main"})
    by = {m.module: m for m in mods}
    assert set(by) == {"opcional", "falta_de_verdad", "pwd", "org.python", "de_helpers"}
    assert by["falta_de_verdad"].important and by["de_helpers"].important
    assert by["opcional"].from_project and not by["opcional"].important
    assert not by["pwd"].from_project and by["pwd"].importers[0] == ("posixpath", ["delayed", "conditional", "optional"])
    assert mods[0].important and mods[1].important     # importantes primero
    assert parse_warn_file(str(tmp_path / "no.txt")) == []


def test_size_report(tmp_path):
    app = tmp_path / "App"
    _write(app / "App.exe", "x" * 100)
    _write(app / "_internal" / "PySide6" / "a.dll", "x" * 5000)
    _write(app / "_internal" / "PySide6" / "b" / "c.dll", "x" * 1000)
    _write(app / "_internal" / "python3.dll", "x" * 300)
    rep = size_report(str(app))
    assert rep[0] == ("PySide6", 6000) and ("python3.dll", 300) in rep and ("App.exe", 100) in rep
    assert human_size(1536) == "1.5 KB" and human_size(10) == "10 B"


def test_diagnose_log():
    log = ("Traceback...\nModuleNotFoundError: No module named 'babel.numbers'\n"
           "ModuleNotFoundError: No module named 'babel.numbers'\n"
           "importlib.metadata.PackageNotFoundError: No package metadata was found for streamlit\n"
           "qt.qpa.plugin: Could not find the Qt platform plugin \"windows\" in \"\"\n")
    d = diagnose_log(log)
    assert [x["action"] for x in d] == [("hidden_import", "babel.numbers"), ("copy_metadata", "streamlit"), None]


@pytest.mark.parametrize("code,status", [("import time; time.sleep(30)", "running"),
                                         ("print('hola')", "exited"),
                                         ("import sys; print('boom'); sys.exit(3)", "crashed")])
def test_smoke_test(tmp_path, code, status):
    # Se usa el intérprete como "ejecutable" para no tener que compilar
    script = tmp_path / "s.py"
    script.write_text(code, encoding="utf-8")
    exe = tmp_path / ("run.bat" if sys.platform == "win32" else "run.sh")
    if sys.platform == "win32":
        exe.write_text(f'@"{sys.executable}" "{script}"\n', encoding="utf-8")
    else:
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n', encoding="utf-8")
        exe.chmod(0o755)
    r = smoke_test(str(exe), seconds=4)
    assert r["status"] == status, r
    if status == "crashed":
        assert r["code"] == 3 and "boom" in r["output"]


def test_collect_data_y_copy_metadata_en_comando_y_spec(cfg):
    cfg.collect_data, cfg.copy_metadata, cfg.collect_all = ["customtkinter"], ["streamlit"], ["plyer"]
    cmd, _ = build_command(cfg)
    assert {"--collect-data=customtkinter", "--copy-metadata=streamlit", "--collect-all=plyer"} <= set(cmd)
    spec = build_spec(cfg)
    compile(spec, "x.spec", "exec")
    assert "collect_data_files" in spec and "copy_metadata(_pkg)" in spec and "'plyer'" in spec


@pytest.mark.parametrize("line,level", [
    ("123 INFO: Analyzing x", ""), ("123 WARNING: lib", "warning"), ("456 ERROR: boom", "error"),
    ("Traceback (most recent call last):", "error"), ("ModuleNotFoundError: No module named 'x'", "error"),
    ("[X] Error en PyInstaller.", "error"), ("[!] cuidado", "warning"), ("[OK] listo", "ok"),
    ("[✓] Movido", "ok"), ("[i] info", "info"), ("=== COMPILANDO V4.4.0 ===", "info"), ("texto común", ""),
])
def test_log_level(line, level):
    from pyinstaller_gui.core.postbuild import log_level
    assert log_level(line) == level
