"""Sistema de diseño: escalas, temas Grafito (oscuro) / Papel (claro), fuentes, íconos
de controles, paleta Qt, cursor de mano y stylesheet global.

THEME se resuelve UNA vez al importar el módulo (antes de construir widgets) y el
stylesheet se aplica UNA vez con setup_appearance(app). El cambio de tema se guarda
en QSettings y se aplica en el próximo inicio, nunca en caliente.
"""

import os
import tempfile

from .. import APP_NAME
from ..qt_compat import (
    QColor, QEvent, QFont, QFontDatabase, QImage, QObject, QPainter, QPalette, QPen, QPointF, QSettings,
    QCheckBox, QComboBox, QPushButton, QRadioButton, QTabBar, QToolButton, Qt,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ▶  ESCALAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}

SETTINGS_ORG = "EstebanKZL"
LEGACY_SETTINGS = ("PyInstallerGUI", "ProBuilder")   # ubicación usada hasta V4.4.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ▶  TEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEMES = {
    # ── GRAFITO (oscuro) ────────────────────────────────────────────────
    "dark": {
        "bg": "#1e1f22", "bg_panel": "#26282c", "bg_input": "#2c2e33",
        "bg_alt": "#232528", "bg_hover": "#33363b",
        "border": "#3a3d43", "border_strong": "#4b4f56",
        "control_border": "#7b808a",
        "accent": "#2b7bd0", "accent_hover": "#3a8ae0", "accent_pressed": "#2366b0",
        "accent_soft": "#1e3550", "accent_soft_hover": "#25426a", "accent_border": "#3a6ea6", "accent_text": "#e8f1fb",
        "selection": "#1f4a73", "selection_text": "#ffffff",
        "btn_bg": "#303237", "btn_bg_hover": "#3a3d43",
        "text": "#dfe1e5", "text_secondary": "#a4a9b1", "text_muted": "#7a808a",
        "text_on_accent": "#ffffff", "field_label": "#f2f3f5",
        "status_bg": "#2b7bd0", "status_text": "#ffffff",
        "start_bg": "#1f3d2a", "start_border": "#3fa968", "start_hover": "#275034", "start_text": "#dff2e5",
        "stop_bg":  "#4a2224", "stop_border":  "#e0625a", "stop_hover":  "#5a2a2c", "stop_text":  "#fbe6e4",
        "ip": "#6cb0f0", "ok": "#5cc99a", "error": "#f0857a", "counter": "#e2bd72",
        "ok_soft": "#1d3a2c", "error_soft": "#452426", "warn_soft": "#3e3420", "info_soft": "#1f3550",
        "disabled_bg": "#2a2c30", "disabled_text": "#62666e",
    },
    # ── PAPEL (claro: blanco grisáceo neutro) ───────────────────────────
    "light": {
        "bg": "#e4e5e3", "bg_panel": "#f0f0ee", "bg_input": "#f9f9f8",
        "bg_alt": "#eaebe9", "bg_hover": "#dddedb",
        "border": "#c6c7c3", "border_strong": "#a6a8a3",
        "control_border": "#7e807b",
        "accent": "#1d62a3", "accent_hover": "#2771b5", "accent_pressed": "#174f85",
        "accent_soft": "#e1ebf5", "accent_soft_hover": "#d2e1f1", "accent_border": "#7ea3cb", "accent_text": "#232528",
        "selection": "#c9dbef", "selection_text": "#1b1c1e",
        "btn_bg": "#e2e3e0", "btn_bg_hover": "#d6d7d3",
        "text": "#232528", "text_secondary": "#45484d", "text_muted": "#5e6167",
        "text_on_accent": "#ffffff", "field_label": "#232528",
        "status_bg": "#1d62a3", "status_text": "#ffffff",
        "start_bg": "#d7eadc", "start_border": "#3a8d55", "start_hover": "#c8e1ce", "start_text": "#1a4427",
        "stop_bg":  "#f3dbd7", "stop_border":  "#c4554a", "stop_hover":  "#ecccc6", "stop_text":  "#62201a",
        "ip": "#1b5794", "ok": "#1b6b43", "error": "#a52e24", "counter": "#7d5200",
        "ok_soft": "#d4e8db", "error_soft": "#f2d9d5", "warn_soft": "#f0e4c8", "info_soft": "#d5e3f2",
        "disabled_bg": "#dddedb", "disabled_text": "#76787a",
    },
}


def app_settings():
    return QSettings(SETTINGS_ORG, APP_NAME)


def migrate_legacy_settings():
    """Copia una sola vez las preferencias de V4.4.0 (recientes, opciones, ventana)
    a la ubicación estándar QSettings("EstebanKZL", APP_NAME)."""
    new = app_settings()
    if new.value("migrated_from_v4", False, type=bool):
        return
    old = QSettings(*LEGACY_SETTINGS)
    for key in old.allKeys():
        if not new.contains(key):
            new.setValue(key, old.value(key))
    new.setValue("migrated_from_v4", True)


def get_theme_name() -> str:
    """Lee el tema guardado. Default: 'dark'. Ignora valores inválidos."""
    name = app_settings().value("theme", "dark")
    return name if name in THEMES else "dark"


def set_theme_name(name: str) -> None:
    """Guarda el tema elegido. No se aplica hasta el próximo inicio."""
    app_settings().setValue("theme", name)


THEME_NAME = get_theme_name()
THEME = THEMES[THEME_NAME]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ▶  FUENTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UI_FONT_CANDIDATES = ["Segoe UI", "Inter", "Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans", "Arial"]
MONO_FONT_CANDIDATES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "Noto Sans Mono",
                        "Ubuntu Mono", "DejaVu Sans Mono", "Courier New"]


def _font_families() -> set:
    try:
        return set(QFontDatabase.families())       # PySide6 (estático)
    except TypeError:
        return set(QFontDatabase().families())     # PySide2 (instancia)


def pick_font(candidates) -> str:
    """Devuelve la primera fuente instalada de la lista."""
    available = _font_families()
    for name in candidates:
        if name in available:
            return name
    return candidates[-1]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ▶  ÍCONOS DE CONTROLES (tilde y flechas, nítidos en HiDPI)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _draw_icon(path: str, size: int, kind: str, color: str) -> None:
    s = size / 16.0
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8 * s)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    pts = {
        "check": [(3.5, 8.5), (6.5, 11.5), (12.5, 5.0)],
        "down":  [(4.5, 6.5), (8.0, 10.0), (11.5, 6.5)],
        "up":    [(4.5, 9.5), (8.0, 6.0),  (11.5, 9.5)],
    }[kind]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        p.drawLine(QPointF(x1 * s, y1 * s), QPointF(x2 * s, y2 * s))
    p.end()
    img.save(path, "PNG")


def build_theme_icons(t: dict, theme_name: str) -> dict:
    folder = os.path.join(tempfile.gettempdir(), "estebankzl_ui",
                          f"{APP_NAME or 'app'}_{theme_name}".replace(" ", "_"))
    os.makedirs(folder, exist_ok=True)
    spec = {
        "check":          ("check", t["text_on_accent"]),
        "arrow_down":     ("down",  t["text_secondary"]),
        "arrow_up":       ("up",    t["text_secondary"]),
        "arrow_down_dis": ("down",  t["disabled_text"]),
        "arrow_up_dis":   ("up",    t["disabled_text"]),
    }
    paths = {}
    for name, (kind, color) in spec.items():
        base = os.path.join(folder, f"{name}.png")
        _draw_icon(base, 16, kind, color)
        _draw_icon(os.path.join(folder, f"{name}@2x.png"), 32, kind, color)  # HiDPI
        paths[name] = base.replace("\\", "/")   # QSS requiere barras normales
    return paths


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ▶  PALETA Y CURSOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def apply_palette(app, t: dict) -> None:
    pal = QPalette()
    roles = {
        QPalette.Window: t["bg"],            QPalette.WindowText: t["text"],
        QPalette.Base: t["bg_input"],        QPalette.AlternateBase: t["bg_alt"],
        QPalette.Text: t["text"],            QPalette.Button: t["btn_bg"],
        QPalette.ButtonText: t["text"],      QPalette.Highlight: t["selection"],
        QPalette.HighlightedText: t["selection_text"],
        QPalette.ToolTipBase: t["bg_panel"], QPalette.ToolTipText: t["text"],
        QPalette.Link: t["accent"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    if hasattr(QPalette, "PlaceholderText"):
        pal.setColor(QPalette.PlaceholderText, QColor(t["text_muted"]))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(t["disabled_text"]))
    app.setPalette(pal)


class _HandCursorFilter(QObject):
    """Pone cursor de mano en todo control clickeable, una vez, al pulirse."""
    _CLICKABLE = (QPushButton, QToolButton, QCheckBox, QRadioButton, QComboBox, QTabBar)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and isinstance(obj, self._CLICKABLE):
            if not obj.testAttribute(Qt.WA_SetCursor):   # respeta cursores puestos a mano
                obj.setCursor(Qt.PointingHandCursor)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ▶  STYLESHEET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_stylesheet(t: dict, icons: dict, fonts: dict) -> str:
    return f"""
/* ═══════════════ BASE ═══════════════ */
QWidget {{
    color: {t['text']};
    font-family: "{fonts['ui']}";
    font-size: 13px;
    outline: none;
}}
QMainWindow, QDialog {{ background-color: {t['bg']}; }}
QWidget#central      {{ background-color: {t['bg']}; }}

/* ═══════════════ ENCABEZADO ═══════════════ */
QFrame#headerBar {{
    background-color: {t['bg_panel']};
    border: none;
    border-bottom: 1px solid {t['border_strong']};
}}
QLabel#lblAppTitle    {{ font-size: 17px; font-weight: 600; color: {t['text']}; }}
QLabel#lblAppSubtitle {{ font-size: 12px; color: {t['text_secondary']}; }}

/* ═══════════════ TIPOGRAFÍA ═══════════════ */
QLabel {{ color: {t['text']}; background-color: transparent; }}
QLabel:disabled {{ color: {t['disabled_text']}; }}
QLabel#lblTitle    {{ font-size: 18px; font-weight: 600; }}
QLabel#lblSubtitle, QLabel#lblHint {{ font-size: 12px; color: {t['text_secondary']}; }}
QLabel#lblSection  {{ font-size: 12px; font-weight: 600; color: {t['text_secondary']}; }}
QLabel#lblKpi      {{ font-size: 24px; font-weight: 600; color: {t['text']}; }}
QLabel#lblKpiCaption {{ font-size: 12px; color: {t['text_secondary']}; }}
QLabel#emptyState  {{ font-size: 13px; color: {t['text_muted']}; padding: 24px; }}
QLabel#lblOk       {{ color: {t['ok']}; }}
QLabel#lblError    {{ color: {t['error']}; }}
QLabel#lblWarn     {{ color: {t['counter']}; }}
QLabel#lblMono     {{ font-family: "{fonts['mono']}"; font-size: 12px; color: {t['ip']}; }}

/* ═══════════════ TARJETAS Y SEPARADORES ═══════════════ */
QFrame#card {{
    background-color: {t['bg_panel']};
    border: 1px solid {t['border']};
    border-radius: 8px;
}}
QFrame#divider {{
    background-color: {t['border']};
    border: none;
    min-height: 1px; max-height: 1px;
}}

/* ═══════════════ BADGES ═══════════════ */
QLabel#badgeOk, QLabel#badgeError, QLabel#badgeWarn, QLabel#badgeInfo, QLabel#badgeNeutral {{
    border-radius: 10px; padding: 2px 10px; font-size: 12px; font-weight: 600;
}}
QLabel#badgeOk      {{ background-color: {t['ok_soft']};    color: {t['ok']}; }}
QLabel#badgeError   {{ background-color: {t['error_soft']}; color: {t['error']}; }}
QLabel#badgeWarn    {{ background-color: {t['warn_soft']};  color: {t['counter']}; }}
QLabel#badgeInfo    {{ background-color: {t['info_soft']};  color: {t['ip']}; }}
QLabel#badgeNeutral {{ background-color: {t['bg_hover']};   color: {t['text_secondary']}; border: 1px solid {t['border']}; }}

/* ═══════════════ GROUPBOX ═══════════════ */
QGroupBox {{
    background-color: {t['bg_panel']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    margin-top: 24px;
    padding: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px; top: 2px; padding: 0 2px;
    color: {t['accent']};
    background-color: transparent;
}}

/* ═══════════════ BOTONES ═══════════════ */
QPushButton {{
    background-color: {t['btn_bg']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 7px 14px;
    color: {t['text']};
    font-weight: 600;
}}
QPushButton:hover    {{ background-color: {t['btn_bg_hover']}; border-color: {t['border_strong']}; }}
QPushButton:pressed  {{ background-color: {t['bg_hover']}; }}
QPushButton:focus    {{ border-color: {t['accent']}; }}
QPushButton:disabled {{ background-color: {t['disabled_bg']}; color: {t['disabled_text']}; border-color: {t['border']}; }}

QPushButton#btnPrimary {{
    background-color: {t['accent']}; border: 1px solid {t['accent']}; color: {t['text_on_accent']};
    padding: 7px 18px;
}}
QPushButton#btnPrimary:hover    {{ background-color: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
QPushButton#btnPrimary:pressed  {{ background-color: {t['accent_pressed']}; border-color: {t['accent_pressed']}; }}
QPushButton#btnPrimary:disabled {{ background-color: {t['disabled_bg']}; color: {t['disabled_text']}; border-color: {t['border']}; }}

QPushButton#btnStart, QPushButton#btnConnect {{
    background-color: {t['start_bg']}; border: 1px solid {t['start_border']}; color: {t['start_text']};
}}
QPushButton#btnStart:hover,    QPushButton#btnConnect:hover    {{ background-color: {t['start_hover']}; }}
QPushButton#btnStart:pressed,  QPushButton#btnConnect:pressed  {{ background-color: {t['start_border']}; color: {t['text_on_accent']}; }}
QPushButton#btnStart:disabled, QPushButton#btnConnect:disabled {{
    background-color: {t['disabled_bg']}; color: {t['disabled_text']}; border-color: {t['border']};
}}

QPushButton#btnStop, QPushButton#btnDisconnect {{
    background-color: {t['stop_bg']}; border: 1px solid {t['stop_border']}; color: {t['stop_text']};
}}
QPushButton#btnStop:hover,    QPushButton#btnDisconnect:hover    {{ background-color: {t['stop_hover']}; }}
QPushButton#btnStop:pressed,  QPushButton#btnDisconnect:pressed  {{ background-color: {t['stop_border']}; color: {t['text_on_accent']}; }}
QPushButton#btnStop:disabled, QPushButton#btnDisconnect:disabled {{
    background-color: {t['disabled_bg']}; color: {t['disabled_text']}; border-color: {t['border']};
}}

/* Botones con ícono: el ícono va a la izquierda con aire */
QPushButton[hasIcon="true"] {{ padding-left: 10px; }}

QPushButton#btnSecondary, QPushButton#btnGhost {{
    background-color: {t['accent_soft']};
    border: 1px solid {t['accent_border']};
    color: {t['accent_text']};
}}
QPushButton#btnSecondary:hover, QPushButton#btnGhost:hover {{
    background-color: {t['accent_soft_hover']}; border-color: {t['accent']};
}}
QPushButton#btnSecondary:pressed, QPushButton#btnGhost:pressed {{
    background-color: {t['accent']}; border-color: {t['accent']}; color: {t['text_on_accent']};
}}
QPushButton#btnSecondary:disabled, QPushButton#btnGhost:disabled {{
    background-color: {t['disabled_bg']}; border-color: {t['border']}; color: {t['disabled_text']};
}}

QPushButton[hasMenu="true"] {{ padding-right: 28px; }}
QPushButton::menu-indicator {{
    image: url("{icons['arrow_down']}");
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 12px; height: 12px; right: 8px;
}}
QPushButton::menu-indicator:disabled {{ image: url("{icons['arrow_down_dis']}"); }}

QPushButton#btnTable {{
    background-color: {t['accent']}; border: none; border-radius: 4px;
    padding: 3px 10px; color: {t['text_on_accent']}; font-size: 12px;
}}
QPushButton#btnTable:hover   {{ background-color: {t['accent_hover']}; }}
QPushButton#btnTable:pressed {{ background-color: {t['accent_pressed']}; }}

/* Tarjetas de plataforma objetivo (botones checkables) */
QPushButton#platformCard {{
    background-color: {t['bg_panel']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 12px 8px;
    color: {t['text_secondary']};
    min-height: 44px;
}}
QPushButton#platformCard:hover   {{ border-color: {t['border_strong']}; color: {t['text']}; }}
QPushButton#platformCard:checked {{
    background-color: {t['accent_soft']};
    border: 1px solid {t['accent']};
    color: {t['accent_text']};
}}

/* Guía de errores: filas clickeables que copian la solución */
QPushButton#errorCard {{
    text-align: left;
    background-color: {t['bg_panel']};
    border: 1px solid {t['border']};
    padding: 7px 12px;
    font-weight: 400;
}}
QPushButton#errorCard:hover {{ background-color: {t['bg_hover']}; border-color: {t['border_strong']}; }}

QToolButton {{
    background-color: transparent; border: 1px solid transparent; border-radius: 6px;
    padding: 4px 6px; color: {t['text']};
}}
QToolButton:hover   {{ background-color: {t['bg_hover']}; }}
QToolButton:pressed {{ background-color: {t['btn_bg_hover']}; }}

/* ═══════════════ INPUTS ═══════════════ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {t['bg_input']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 6px 8px;
    color: {t['text']};
    selection-background-color: {t['selection']};
    selection-color: {t['selection_text']};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{ border-color: {t['border_strong']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {t['accent']}; }}
QLineEdit:read-only {{ background-color: {t['bg_alt']}; color: {t['text_secondary']}; }}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {t['disabled_bg']}; color: {t['disabled_text']};
}}
QLineEdit[invalid="true"] {{ border-color: {t['error']}; }}

QPlainTextEdit#logView, QTextEdit#logView, QPlainTextEdit#codeView, QTextEdit#codeView {{
    font-family: "{fonts['mono']}";
    font-size: 12px;
    background-color: {t['bg_alt']};
    padding: 8px 10px;
}}
QPlainTextEdit#codeView, QTextEdit#codeView {{ color: {t['ip']}; }}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {t['bg_input']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 5px 8px;
    color: {t['text']};
    min-height: 20px;
}}
QSpinBox, QDoubleSpinBox {{ padding-right: 24px; }}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {t['border_strong']}; }}
QComboBox:focus, QComboBox:on, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {t['accent']}; }}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {t['disabled_bg']}; color: {t['disabled_text']};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 26px; border: none;
}}
QComboBox::down-arrow          {{ image: url("{icons['arrow_down']}");     width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url("{icons['arrow_down_dis']}"); }}
QComboBox QAbstractItemView {{
    background-color: {t['bg_panel']};
    border: 1px solid {t['border']};
    padding: 4px;
    outline: none;
    selection-background-color: {t['selection']};
    selection-color: {t['selection_text']};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border: none; background: transparent; margin: 2px 2px 0 0;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border: none; background: transparent; margin: 0 2px 2px 0;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {t['bg_hover']}; border-radius: 4px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow       {{ image: url("{icons['arrow_up']}");   width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow   {{ image: url("{icons['arrow_down']}"); width: 10px; height: 10px; }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled     {{ image: url("{icons['arrow_up_dis']}"); }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{ image: url("{icons['arrow_down_dis']}"); }}

/* ═══════════════ CHECKBOX / RADIO ═══════════════ */
QCheckBox, QRadioButton {{
    color: {t['text']}; spacing: 8px; background-color: transparent;
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {t['disabled_text']}; }}
QCheckBox::indicator, QAbstractItemView::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    background-color: {t['bg_input']}; border: 1px solid {t['control_border']};
}}
QCheckBox::indicator:hover, QAbstractItemView::indicator:hover {{ border-color: {t['accent']}; }}
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked {{
    background-color: {t['accent']}; border-color: {t['accent']};
    image: url("{icons['check']}");
}}
QCheckBox::indicator:checked:hover, QAbstractItemView::indicator:checked:hover {{ background-color: {t['accent_hover']}; }}
QCheckBox::indicator:disabled, QAbstractItemView::indicator:disabled {{
    background-color: {t['disabled_bg']}; border-color: {t['border_strong']};
}}

QRadioButton::indicator {{
    width: 16px; height: 16px; border-radius: 8px;
    background-color: {t['bg_input']}; border: 1px solid {t['control_border']};
}}
QRadioButton::indicator:hover   {{ border-color: {t['accent']}; }}
QRadioButton::indicator:checked {{
    background-color: {t['text_on_accent']}; border: 5px solid {t['accent']};
    width: 8px; height: 8px;
}}
QRadioButton::indicator:disabled {{ background-color: {t['disabled_bg']}; border-color: {t['border_strong']}; }}

/* ═══════════════ PROGRESS BAR ═══════════════ */
QProgressBar {{
    background-color: {t['bg_alt']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    min-height: 16px;
    text-align: center;
    color: {t['text']};
    font-size: 12px;
}}
QProgressBar::chunk {{ background-color: {t['accent']}; border-radius: 5px; }}

/* ═══════════════ TABLAS / LISTAS / ÁRBOLES ═══════════════ */
QTableView, QListView, QTreeView {{
    background-color: {t['bg_panel']};
    alternate-background-color: {t['bg_alt']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    gridline-color: {t['border']};
    selection-background-color: {t['selection']};
    selection-color: {t['selection_text']};
    outline: none;
}}
QTableView::item, QListView::item, QTreeView::item {{ padding: 4px 8px; border: none; }}
QTableView::item:hover, QListView::item:hover, QTreeView::item:hover {{ background-color: {t['bg_hover']}; }}
QTableView::item:selected, QListView::item:selected, QTreeView::item:selected {{
    background-color: {t['selection']}; color: {t['selection_text']};
}}
QHeaderView {{ background-color: transparent; border: none; }}
QHeaderView::section {{
    background-color: {t['bg_panel']};
    color: {t['text_secondary']};
    border: none;
    border-bottom: 1px solid {t['border_strong']};
    border-right: 1px solid {t['border']};
    padding: 7px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QHeaderView::section:last {{ border-right: none; }}
QTableCornerButton::section {{ background-color: {t['bg_panel']}; border: none; }}

/* ═══════════════ TABS — cuadrados, acento arriba ═══════════════ */
QTabWidget::pane {{
    border: 1px solid {t['border']};
    background-color: {t['bg']};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {t['bg_alt']};
    color: {t['text_secondary']};
    border: 1px solid {t['border']};
    border-bottom: none;
    border-radius: 0;
    padding: 7px 16px;
    margin-right: -1px;
}}
QTabBar::tab:hover    {{ background-color: {t['bg_hover']}; color: {t['text']}; }}
QTabBar::tab:selected {{
    background-color: {t['bg']};
    color: {t['text']};
    border-top: 2px solid {t['accent']};
}}
QTabBar::tab:disabled {{ color: {t['disabled_text']}; }}
/* El contenido desplazable de cada pestaña deja ver el fondo del panel */
QScrollArea#tabScroll {{ background-color: transparent; border: none; }}
QWidget#tabContent    {{ background-color: transparent; }}

/* ═══════════════ SCROLLBARS ═══════════════ */
QScrollBar:vertical   {{ background: transparent; width: 10px;  margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:vertical   {{ background: {t['border_strong']}; min-height: 28px; border-radius: 4px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['border_strong']}; min-width: 28px;  border-radius: 4px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {t['text_secondary']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ═══════════════ SPLITTER ═══════════════ */
QSplitter::handle            {{ background-color: {t['border_strong']}; }}
QSplitter::handle:hover      {{ background-color: {t['accent']}; }}
QSplitter::handle:horizontal {{ width: 4px; margin: 0 4px; border-radius: 2px; }}
QSplitter::handle:vertical   {{ height: 4px; margin: 4px 0; border-radius: 2px; }}

/* ═══════════════ STATUS BAR ═══════════════ */
QStatusBar {{
    background-color: {t['status_bg']};
    color: {t['status_text']};
    font-size: 12px;
    font-weight: 600;
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {t['status_text']}; background-color: transparent; }}

/* ═══════════════ MENÚS ═══════════════ */
QMenuBar {{
    background-color: {t['bg_panel']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
}}
QMenuBar::item          {{ padding: 5px 10px; background: transparent; border-radius: 4px; }}
QMenuBar::item:selected {{ background-color: {t['bg_hover']}; }}
QMenu {{
    background-color: {t['bg_panel']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item          {{ padding: 6px 24px 6px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {t['selection']}; color: {t['selection_text']}; }}
QMenu::item:disabled {{ color: {t['disabled_text']}; }}
QMenu::separator     {{ height: 1px; background-color: {t['border']}; margin: 4px 8px; }}

/* ═══════════════ DIÁLOGOS Y TOOLTIPS ═══════════════ */
QMessageBox {{ background-color: {t['bg']}; }}
QMessageBox QLabel {{ color: {t['text']}; background-color: transparent; }}
QToolTip {{
    background-color: {t['bg_panel']};
    color: {t['text']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    padding: 5px 8px;
}}
"""


def setup_appearance(app) -> None:
    """Aplica fuente, paleta, íconos, stylesheet y cursor. Se llama UNA sola vez."""
    fonts = {"ui": pick_font(UI_FONT_CANDIDATES), "mono": pick_font(MONO_FONT_CANDIDATES)}
    base_font = QFont(fonts["ui"])
    base_font.setPixelSize(13)
    app.setFont(base_font)

    apply_palette(app, THEME)
    icons = build_theme_icons(THEME, THEME_NAME)
    app.setStyleSheet(build_stylesheet(THEME, icons, fonts))

    app._hand_cursor_filter = _HandCursorFilter(app)   # mantener referencia viva
    app.installEventFilter(app._hand_cursor_filter)
