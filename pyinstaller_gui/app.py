"""Punto de entrada: sin argumentos abre la GUI; con argumentos usa el modo CLI."""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    """Ruta absoluta de un recurso, funciona en desarrollo y dentro de PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", _PROJECT_ROOT)
    return os.path.join(base_path, relative_path)


def run_gui():
    # Qt se importa recién acá: el modo CLI funciona sin PySide instalado
    try:
        from .qt_compat import _QT_BACKEND, QApplication, QIcon, Qt, _exec
    except ImportError as e:
        print("=" * 65)
        print(f"ERROR FATAL: {e}")
        input("Presioná Enter para salir...")
        return 1
    from . import APP_NAME, APP_VERSION
    from .i18n import check_translations, set_language
    from .ui.theme import migrate_legacy_settings

    # 1) Preferencias de V4.4.0 → QSettings("EstebanKZL", APP_NAME), una sola vez
    migrate_legacy_settings()
    # 2) Idioma: se fija antes de construir cualquier widget (se aplica al reiniciar)
    from .ui.language import get_lang_code, install_qt_translations
    set_language(get_lang_code())
    if not getattr(sys, "frozen", False):
        for problem in check_translations():   # solo en desarrollo
            print(problem)
    # 3) Recién ahora la ventana (THEME ya quedó resuelto al importar ui.theme)
    from .ui.main_window import BuilderApp
    from .ui.theme import setup_appearance

    if sys.platform == "win32":
        # Ícono propio en la barra de tareas de Windows (no el de python.exe)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"estebankzl.{APP_NAME.lower().replace(' ', '')}.{APP_VERSION.replace('.', '')}")
        except Exception:
            pass

    print(f"[PyInstaller GUI PRO] Backend Qt: {_QT_BACKEND}")
    if _QT_BACKEND == "PySide6":
        import warnings
        if hasattr(Qt, "AA_UseHighDpiPixmaps"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    else:
        if hasattr(Qt, "AA_EnableHighDpiScaling"):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, "AA_UseHighDpiPixmaps"):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    setup_appearance(app)          # fuente + paleta + íconos + QSS + cursor (una sola vez)
    from .i18n import LANG
    install_qt_translations(app, LANG)

    for name in ["icono.ico", "icon.ico", "icono.png", "icon.png"]:
        path = resource_path(name)
        if os.path.exists(path):
            app.setWindowIcon(QIcon(path))
            break

    w = BuilderApp()
    w.show()
    if os.environ.get("PYI_GUI_SELFTEST"):
        # Prueba de humo de los paquetes de release: si la ventana se construye,
        # el programa se cierra solo con código 0 (lo usa release/build_release.py)
        from .qt_compat import QTimer
        QTimer.singleShot(2500, lambda: app.exit(0))
    return _exec(app)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        from .cli import main as cli_main
        return cli_main(argv)
    return run_gui()
