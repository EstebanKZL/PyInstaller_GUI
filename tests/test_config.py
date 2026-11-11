import json
import os

from pyinstaller_gui.core.config import MODE_ONEFILE_LABEL, BuildConfig


def test_valores_derivados(cfg):
    assert cfg.app_name == "main"
    cfg.name = " Mi App "
    assert cfg.app_name == "Mi App"
    assert cfg.dist_dir == os.path.join(cfg.workspace, "dist")
    cfg.dist_path = "D:\\salida"
    assert cfg.dist_dir == "D:\\salida"
    assert BuildConfig().app_name == "App" and BuildConfig().dist_dir == ""


def test_destino_por_plataforma(cfg):
    assert cfg.destination_dir == ""
    cfg.dest_folder, cfg.platform, cfg.name = "E:\\builds", "windows7", "App"
    assert cfg.destination_dir == os.path.join("E:\\builds", "Compilacion", "Windows 7", "App")


def test_perfil_ida_y_vuelta(cfg, tmp_path):
    cfg.onefile, cfg.uac_admin, cfg.name = True, True, "X"
    cfg.add_data = [("a.txt", "."), ("img", "assets")]
    cfg.hidden_imports = ["PIL", "requests"]
    cfg.dep_excludes = ["numpy"]   # no se persiste
    path = tmp_path / "perfil.json"
    cfg.save(path)
    loaded = BuildConfig.load(path)
    cfg.dep_excludes = []
    assert loaded == cfg


def test_perfil_compatible_con_v4(tmp_path):
    """Perfil guardado por la versión 4.4.0 (claves 'mode' y 'add_data_paths')."""
    old = {
        "workspace": "C:\\p", "script": "C:\\p\\main.py", "name": "App", "mode": MODE_ONEFILE_LABEL,
        "noconsole": False, "clean": True, "platform": "windows", "python_path": None,
        "add_data_paths": ["C:\\p\\a.txt"], "hidden_imports": ["PIL"], "exclude_modules": ["tkinter"],
        "checked_imports": ["PIL"], "clave_desconocida": 1,
    }
    path = tmp_path / "v4.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    cfg = BuildConfig.load(path)
    assert cfg.onefile and not cfg.noconsole and cfg.python_path == ""
    assert cfg.add_data == [("C:\\p\\a.txt", ".")]
    assert cfg.hidden_imports == ["PIL"] and cfg.exclude_modules == ["tkinter"]


def test_perfil_conserva_claves_legibles_por_v4(cfg):
    data = cfg.to_profile()
    assert data["mode"] and "add_data_paths" in data and "checked_imports" in data
    assert "dep_excludes" not in data
