"""Idioma de la interfaz: elección inicial según el sistema, persistencia en QSettings
y traducciones propias de Qt (botones estándar, diálogos de archivo, menú copiar/pegar)."""

from .. import APP_NAME
from ..i18n import LANGUAGES
from ..qt_compat import QLibraryInfo, QLocale, QTranslator
from .theme import app_settings


def get_lang_code() -> str:
    """Idioma guardado; en el primer inicio, el del sistema (fallback: español)."""
    code = app_settings().value("language", "")
    if code not in LANGUAGES:
        code = QLocale.system().name()[:2].lower()
    return code if code in LANGUAGES else "es"


def set_lang_code(code: str) -> None:
    """Guarda el idioma elegido. No se aplica hasta el próximo inicio."""
    app_settings().setValue("language", code)


def install_qt_translations(app, lang: str) -> None:
    """Carga las traducciones de Qt para que QMessageBox, QFileDialog, etc. usen el idioma activo."""
    if lang == "en":
        return
    try:
        path = (QLibraryInfo.path(QLibraryInfo.TranslationsPath)            # PySide6
                if hasattr(QLibraryInfo, "path")
                else QLibraryInfo.location(QLibraryInfo.TranslationsPath))  # PySide2
        app._qt_translators = []
        for base in ("qtbase", "qt"):
            translator = QTranslator(app)
            if translator.load(f"{base}_{lang}", path):
                app.installTranslator(translator)
                app._qt_translators.append(translator)
    except Exception as e:
        print(f"[{APP_NAME}] Traducciones de Qt no disponibles: {e}")
