"""Widgets reutilizables."""

import os

from ..core.postbuild import log_level
from ..qt_compat import (
    QColor, QLineEdit, QPainter, QPen, QPlainTextEdit, QTextCharFormat, QTextCursor, QTextDocument, QWidget, Qt,
    Signal, _global_pos,
)
from .theme import THEME


class DropLineEdit(QLineEdit):
    """QLineEdit que acepta arrastrar y soltar archivos o carpetas."""
    path_dropped = Signal(str)

    def __init__(self, accept_dirs=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.accept_dirs = accept_dirs
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if self.accept_dirs and os.path.isdir(path):
            self.setText(path)
            self.path_dropped.emit(path)
        elif os.path.isfile(path):
            self.setText(path)
            self.path_dropped.emit(path)


class DotGripWidget(QWidget):
    """Grip de redimensión con puntos en la esquina inferior derecha.
    bg_color : None = transparente | THEME["status_bg"] = sobre la status bar.
    dot_color: None → THEME["status_text"] si hay bg_color, THEME["text_muted"] si es transparente."""

    def __init__(self, parent=None, bg_color=None, dot_color=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._bg_color = bg_color
        if dot_color is None:
            dot_color = THEME["status_text"] if bg_color else THEME["text_muted"]
        self._dot_color = QColor(dot_color)
        self._hovered = self._dragging = False
        self._drag_pos = self._drag_size = None
        self.setMouseTracking(True)

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = _global_pos(e)
            self._drag_size = self.window().size()

    def mouseMoveEvent(self, e):
        if self._dragging:
            d = _global_pos(e) - self._drag_pos
            win = self.window()
            win.resize(max(win.minimumWidth(), self._drag_size.width() + d.x()),
                       max(win.minimumHeight(), self._drag_size.height() + d.y()))

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._bg_color:
            p.fillRect(self.rect(), QColor(self._bg_color))
        dot_r, spacing, cols, rows = 2, 5, 3, 3
        ox = self.width() - cols * spacing + 1
        oy = self.height() - rows * spacing + 1
        color = QColor(self._dot_color)
        color.setAlpha(220 if self._hovered else 130)
        if self._hovered:
            halo = QColor(self._dot_color)
            halo.setAlpha(30)
            p.setPen(QPen(halo, 0))
            p.setBrush(halo)
            p.drawEllipse(0, 0, self.width(), self.height())
        p.setPen(QPen(color, 0))
        p.setBrush(color)
        for row in range(rows):
            for col in range(cols):
                if row + col < 2:
                    continue
                p.drawEllipse(ox + col * spacing - dot_r, oy + row * spacing - dot_r, dot_r * 2, dot_r * 2)


class LogView(QPlainTextEdit):
    """Log monoespaciado de solo lectura (objectName logView) que colorea cada línea
    según su nivel. El nivel sale de marcadores fijos ([X], [!], [OK], [i]) y de la
    salida de PyInstaller (INFO/WARNING/ERROR), nunca de palabras traducidas."""
    LEVEL_COLORS = {"error": "error", "warning": "counter", "ok": "ok", "info": "ip", "": "text"}
    MAX_BLOCKS = 20000   # suficiente para un build grande, sin crecer sin límite

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logView")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)

    def append(self, text):
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(THEME[self.LEVEL_COLORS[log_level(text.split("\n", 1)[0])]]))
        cur = QTextCursor(self.document())
        cur.movePosition(QTextCursor.End)
        if not self.document().isEmpty():
            cur.insertBlock()
        cur.insertText(text, fmt)
        if at_bottom:
            bar.setValue(bar.maximum())

    def find_text(self, text, backward=False):
        """Busca con vuelta al principio/final. Devuelve la cantidad total de coincidencias."""
        if not text:
            return 0
        # find() sin flags = hacia adelante (compatible PySide2/PySide6)
        search = (lambda: self.find(text, QTextDocument.FindBackward)) if backward else (lambda: self.find(text))
        if not search():
            cur = self.textCursor()
            cur.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.setTextCursor(cur)
            search()
        return self.toPlainText().lower().count(text.lower())
