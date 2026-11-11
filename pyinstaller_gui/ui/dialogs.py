"""Diálogos."""

from ..i18n import tr
from ..qt_compat import QButtonGroup, QDialog, QDialogButtonBox, QHBoxLayout, QRadioButton, QVBoxLayout
from .components import make_badge, make_card, make_label, set_help
from .theme import SP


class PythonSelectorDialog(QDialog):
    """Elige entre los intérpretes Python detectados (venv del proyecto primero)."""

    def __init__(self, python_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.python_select_title"))
        self.setMinimumWidth(640)
        self._selected = None

        v = QVBoxLayout(self)
        v.setSpacing(SP["md"])
        v.setContentsMargins(SP["lg"], SP["lg"], SP["lg"], SP["lg"])
        v.addWidget(make_label(tr("dlg.python_select_heading"), "lblTitle"))
        v.addWidget(make_label(tr("dlg.python_select_hint"), "lblSubtitle", wrap=True))

        self._bg = QButtonGroup(self)
        self._radios = []
        for i, info in enumerate(python_list):
            card, lay = make_card(spacing=SP["xs"])
            row = QHBoxLayout()
            row.setSpacing(SP["md"])
            untrusted = info.get("untrusted", False)
            rb = QRadioButton(tr("dlg.python_untrusted_option") if untrusted else f"Python {info['version']}")
            rb.setChecked(i == 0)
            set_help(rb, "python_option")
            self._bg.addButton(rb, i)
            self._radios.append((rb, info))
            row.addWidget(rb, 1)
            if untrusted:
                row.addWidget(make_badge(tr("badge.python_untrusted"), "warn"))
            elif info.get('has_pyinstaller'):
                row.addWidget(make_badge(tr("badge.has_pyinstaller"), "ok"))
            else:
                row.addWidget(make_badge(tr("badge.no_pyinstaller"), "neutral"))
            lay.addLayout(row)
            lay.addWidget(make_label(info['path'], "lblMono"))
            lay.addWidget(make_label(tr(f"src.{info['source']}", detail=info.get('detail', '')), "lblHint"))
            v.addWidget(card)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setObjectName("btnPrimary")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _on_accept(self):
        idx = self._bg.checkedId()
        if idx >= 0:
            self._selected = self._radios[idx][1]['path']
        self.accept()

    def selected_path(self):
        return self._selected


class AboutDialog(QDialog):
    """Acerca de: versión, entorno y un botón que copia esos datos para reportar un problema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        import platform

        from .. import APP_DEVELOPER, APP_NAME, APP_URL, APP_VERSION
        from ..applog import log_path
        from ..qt_compat import _QT_BACKEND, QApplication, QGridLayout, QLabel, QPushButton, Qt
        from .icons import icon_pixmap, set_button_icon

        self.setWindowTitle(tr("msg.about_title", app=APP_NAME))
        self.setMinimumWidth(520)

        logo = QLabel()
        app_icon = QApplication.windowIcon()
        logo.setPixmap(app_icon.pixmap(48, 48) if not app_icon.isNull() else icon_pixmap("app", 48, "accent"))
        head = QHBoxLayout()
        head.setSpacing(SP["md"])
        head.addWidget(logo, 0, Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(make_label(APP_NAME, "lblTitle"))
        titles.addWidget(make_label(tr("about.version", version=APP_VERSION.lstrip("vV")), "lblSubtitle"))
        head.addLayout(titles, 1)

        info = [
            (tr("about.developer"), APP_DEVELOPER),
            (tr("about.repo"), APP_URL),
            ("Qt", _QT_BACKEND),
            ("Python", platform.python_version()),
            (tr("about.system"), f"{platform.system()} {platform.release()} ({platform.machine()})"),
            (tr("about.log"), log_path() or "-"),
        ]
        self.info_text = "\n".join([f"{APP_NAME} {APP_VERSION}"] + [f"{k}: {v}" for k, v in info])
        grid = QGridLayout()
        grid.setHorizontalSpacing(SP["md"])
        grid.setVerticalSpacing(SP["xs"])
        grid.setColumnMinimumWidth(0, 110)
        grid.setColumnStretch(1, 1)
        for r, (k, v) in enumerate(info):
            key = make_label(k, "lblHint")
            key.setAlignment(Qt.AlignRight | Qt.AlignTop)
            grid.addWidget(key, r, 0)
            val = make_label(v, wrap=True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(val, r, 1)

        btn_copy = QPushButton(tr("about.copy"))
        btn_copy.setObjectName("btnSecondary")
        set_button_icon(btn_copy, "copy")
        set_help(btn_copy, "about_copy")
        btn_copy.clicked.connect(lambda: (QApplication.clipboard().setText(self.info_text),
                                          btn_copy.setText(tr("about.copied"))))
        btn_close = QPushButton(tr("about.close"))
        btn_close.setObjectName("btnPrimary")
        btn_close.setDefault(True)
        set_help(btn_close, "about_close")
        btn_close.clicked.connect(self.accept)
        foot = QHBoxLayout()
        foot.addWidget(btn_copy)
        foot.addStretch(1)
        foot.addWidget(btn_close)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(SP["xl"], SP["xl"], SP["xl"], SP["lg"])
        lay.setSpacing(SP["lg"])
        lay.addLayout(head)
        lay.addWidget(make_label(tr("about.description"), wrap=True))
        lay.addLayout(grid)
        lay.addLayout(foot)
