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
