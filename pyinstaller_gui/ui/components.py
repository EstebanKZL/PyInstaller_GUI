"""Componentes estándar del sistema de diseño. Se diferencian solo por objectName:
el stylesheet global (theme.py) hace el resto. Ningún color se escribe acá."""

from ..i18n import tr, tr_opt
from ..qt_compat import (
    QAction, QCheckBox, QFrame, QLabel, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget, Qt,
)
from .theme import SP, THEME

_HELP_WIDGET_TYPES = (QPushButton, QToolButton, QCheckBox, QRadioButton)


def set_help(widget, key: str, shortcut: str = None) -> None:
    """Ayuda contextual traducida para un widget o QAction:
      · tip.<key>        → explicación (obligatoria)
      · tip.<key>.title  → título (opcional; en botones/checkbox se usa su propio texto)
    También la copia a la barra de estado (statusTip)."""
    body = tr(f"tip.{key}")
    title = tr_opt(f"tip.{key}.title")
    if not title and isinstance(widget, _HELP_WIDGET_TYPES + (QAction,)):
        title = widget.text().replace("&", "").replace("\n", " ")
    html = "<qt>"
    if title:
        html += f"<b>{title}</b>"
    if shortcut:
        html += f'&nbsp;&nbsp;&nbsp;<span style="color:{THEME["text_muted"]};">{shortcut}</span>'
    if title or shortcut:
        html += "<br>"
    html += f'<span style="color:{THEME["text_secondary"]};">{body}</span></qt>'
    widget.setToolTip(html)
    widget.setStatusTip(body)


def repolish(w) -> None:
    """Necesario al cambiar objectName/propiedades en caliente para que el estilo se actualice."""
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def make_card(section_title: str = None, spacing: int = SP["md"]):
    """Tarjeta con padding estándar y etiqueta de sección opcional. Devuelve (frame, layout)."""
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(SP["lg"], SP["md"] + 2, SP["lg"], SP["lg"])
    lay.setSpacing(spacing)
    if section_title:
        lbl = QLabel(section_title.upper())
        lbl.setObjectName("lblSection")
        lay.addWidget(lbl)
    return card, lay


def make_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    return line


def make_label(text: str = "", name: str = None, wrap: bool = False) -> QLabel:
    """QLabel con rol tipográfico (lblHint, lblSection, lblTitle, lblOk, lblError, lblWarn, lblMono…)."""
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def make_hint(text: str = "") -> QLabel:
    return make_label(text, "lblHint", wrap=True)


def make_section(text: str) -> QLabel:
    return make_label(text.upper(), "lblSection")


def make_button(text: str, name: str = None, clicked=None, help_key: str = None, shortcut: str = None,
                icon_name=None) -> QPushButton:
    """name: btnPrimary | btnSecondary | btnStart | btnStop | btnTable | None (neutro).
    icon_name: ícono del catálogo; por defecto el de la acción (ACTION_ICONS[help_key]); False = sin ícono."""
    from .icons import ACTION_ICONS, set_button_icon   # import local: icons depende de theme
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if icon_name is None:
        icon_name = ACTION_ICONS.get(help_key)
    if icon_name:
        set_button_icon(b, icon_name)
    if clicked is not None:
        b.clicked.connect(clicked)
    if help_key:
        set_help(b, help_key, shortcut)
    return b


def make_badge(text: str, kind: str = "neutral") -> QLabel:
    """kind: ok | error | warn | info | neutral"""
    lbl = QLabel(text)
    lbl.setObjectName(f"badge{kind.capitalize()}")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return lbl


def set_badge(lbl: QLabel, text: str, kind: str) -> None:
    lbl.setText(text)
    lbl.setObjectName(f"badge{kind.capitalize()}")
    repolish(lbl)


def set_label_role(lbl: QLabel, text: str, name: str) -> None:
    """Cambia texto y rol de color (lblOk / lblError / lblWarn / lblHint) en caliente."""
    lbl.setText(text)
    lbl.setObjectName(name)
    repolish(lbl)


def make_empty_state(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("emptyState")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def make_tab_scroll():
    """Contenido desplazable de una pestaña: devuelve (scroll_area, layout_del_contenido)."""
    scroll = QScrollArea()
    scroll.setObjectName("tabScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName("tabContent")
    lay = QVBoxLayout(content)
    lay.setContentsMargins(SP["lg"], SP["sm"], SP["lg"], SP["lg"])
    lay.setSpacing(SP["sm"])
    scroll.setWidget(content)
    return scroll, lay
