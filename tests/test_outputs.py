from pyinstaller_gui.core.outputs import clean_app_outputs, is_app_output, move_to_destination


def _touch(p, text=""):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_is_app_output():
    for name in ("Mi App", "Mi App.exe", "Mi App.app", "Mi App.AppDir", "Mi_App_Setup.exe",
                 "Mi_App_setup.nsi", "Mi App-x86_64.AppImage"):
        assert is_app_output(name, "Mi App"), name
    for name in ("Notas_2024.docx", "Mi App foto.png", "Mi App_backup", "otra.exe", "Mi Appendice.txt"):
        assert not is_app_output(name, "Mi App"), name


def test_limpieza_no_toca_archivos_ajenos(tmp_path):
    dist, build = tmp_path / "Escritorio", tmp_path / "build"
    _touch(dist / "documento importante.txt", "no borrar")
    _touch(dist / "Mi App foto.png")
    _touch(dist / "Mi App" / "x.dll")
    _touch(dist / "Mi App.exe")
    _touch(build / "Mi App" / "cache.toc")
    _touch(build / "otro proyecto" / "cache.toc")

    removed, errors = clean_app_outputs(str(dist), str(build), "Mi App")
    assert not errors
    assert sorted(p.name for p in dist.iterdir()) == ["Mi App foto.png", "documento importante.txt"]
    assert [p.name for p in build.iterdir()] == ["otro proyecto"]
    assert len(removed) == 3


def test_limpieza_con_carpetas_inexistentes(tmp_path):
    assert clean_app_outputs(str(tmp_path / "no"), str(tmp_path / "tampoco"), "App") == ([], [])


def test_mover_solo_salidas_de_la_app(tmp_path):
    dist, dest = tmp_path / "dist", tmp_path / "out" / "Compilacion" / "Windows 11" / "App"
    _touch(dist / "App" / "App.exe")
    _touch(dist / "ajeno.txt")
    _touch(dest / "App" / "viejo.dll")   # build anterior en destino: se reemplaza
    logs = []
    assert move_to_destination(str(dist), str(dest), "App", logs.append)
    assert [p.name for p in dist.iterdir()] == ["ajeno.txt"]
    assert sorted(p.name for p in (dest / "App").iterdir()) == ["App.exe"]
