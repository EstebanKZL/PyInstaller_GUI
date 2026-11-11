"""Capa de compatibilidad automática PySide6 / PySide2.

Orden de prioridad:
  1. PySide6  → Python 3.10+, Windows 10/11, Linux, macOS
  2. PySide2  → Python 3.8/3.9, Windows 7/8/10, Linux

Ningún otro módulo importa PySide6/PySide2 directamente: todo pasa por acá.
Si se necesita una clase nueva, agregarla en LOS DOS bloques try.
"""


def _optional_svg(backend):
    """QtSvg es opcional: sin él los íconos quedan vacíos pero el programa funciona.
    Imports estáticos a propósito: PyInstaller y Nuitka solo empaquetan lo que ven importado."""
    try:
        if backend == "PySide6":
            from PySide6.QtSvg import QSvgRenderer
        else:
            from PySide2.QtSvg import QSvgRenderer
        return QSvgRenderer
    except ImportError:
        return None


def _import_qt():
    errors = []

    # ── Intento 1: PySide6 ──────────────────────────────────────────────
    try:
        from PySide6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
            QLabel, QPushButton, QToolButton, QLineEdit, QComboBox,
            QScrollArea, QSizePolicy, QSplitter, QStackedWidget,
            QHBoxLayout, QVBoxLayout, QGridLayout,
            QMessageBox, QSpacerItem, QTabWidget, QTabBar,
            QCheckBox, QTextEdit, QPlainTextEdit, QProgressBar, QStatusBar,
            QFileDialog, QListWidget, QListWidgetItem,
            QTableWidget, QTableWidgetItem, QHeaderView,
            QTreeWidget, QTreeWidgetItem,
            QDialog, QDialogButtonBox, QInputDialog,
            QSpinBox, QDoubleSpinBox,
            QRadioButton, QButtonGroup,
            QMenu, QSystemTrayIcon,
        )
        # PySide6/Qt6: QAction se movió de QtWidgets → QtGui
        from PySide6.QtGui import (
            QGuiApplication,
            QAction, QKeySequence,
            QColor, QFont, QFontDatabase, QIcon, QPalette,
            QPainter, QPen, QBrush,
            QPixmap, QImage,
            QTextCursor, QTextCharFormat, QTextDocument,
            QDragEnterEvent, QDropEvent,
        )
        from PySide6.QtCore import (
            Qt, QObject, QEvent, QThread, Signal, QTimer, QByteArray, QSize,
            QSettings, QMimeData, QRectF, QPointF,
            QLocale, QTranslator, QLibraryInfo,
        )
        ns = locals()
        ns["QSvgRenderer"] = _optional_svg("PySide6")
        return "PySide6", ns
    except ImportError as e:
        errors.append(f"PySide6: {e}")

    # ── Intento 2: PySide2 (Windows 7 / Python 3.8) ─────────────────────
    try:
        from PySide2.QtWidgets import (
            QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
            QLabel, QPushButton, QToolButton, QLineEdit, QComboBox,
            QScrollArea, QSizePolicy, QSplitter, QStackedWidget,
            QHBoxLayout, QVBoxLayout, QGridLayout,
            QMessageBox, QSpacerItem, QTabWidget, QTabBar,
            QCheckBox, QTextEdit, QPlainTextEdit, QProgressBar, QStatusBar,
            QFileDialog, QListWidget, QListWidgetItem,
            QTableWidget, QTableWidgetItem, QHeaderView,
            QTreeWidget, QTreeWidgetItem,
            QDialog, QDialogButtonBox, QInputDialog,
            QSpinBox, QDoubleSpinBox,
            QRadioButton, QButtonGroup,
            QMenu, QAction, QSystemTrayIcon,
        )
        from PySide2.QtGui import (
            QGuiApplication,
            QKeySequence,
            QColor, QFont, QFontDatabase, QIcon, QPalette,
            QPainter, QPen, QBrush,
            QPixmap, QImage,
            QTextCursor, QTextCharFormat, QTextDocument,
            QDragEnterEvent, QDropEvent,
        )
        from PySide2.QtCore import (
            Qt, QObject, QEvent, QThread, Signal, QTimer, QByteArray, QSize,
            QSettings, QMimeData, QRectF, QPointF,
            QLocale, QTranslator, QLibraryInfo,
        )
        ns = locals()
        ns["QSvgRenderer"] = _optional_svg("PySide2")
        return "PySide2", ns
    except ImportError as e:
        errors.append(f"PySide2: {e}")

    # Se lanza ImportError (y no sys.exit) para que el llamador decida: la GUI muestra
    # el error y espera Enter; los tests y el modo CLI pueden seguir sin Qt.
    raise ImportError("No se encontró ningún framework Qt compatible.\n"
                      "  Windows 10/11 / Linux (Python 3.10+):  pip install PySide6\n"
                      "  Windows 7 (Python 3.8):                pip install PySide2\n"
                      + "\n".join(f"  · {e}" for e in errors))


_QT_BACKEND, _qt = _import_qt()

# ── Exponer todos los nombres Qt en el namespace del módulo (una sola línea) ──
globals().update({k: v for k, v in _qt.items() if k.startswith("Q") or k == "Signal"})


# ── Helper exec() compatible PySide6 / PySide2 ─────────────────────────
def _exec(widget):
    """Llama exec() o exec_() según lo que soporte el widget/app."""
    if hasattr(widget, 'exec') and callable(widget.exec):
        return widget.exec()
    return widget.exec_()


def _exec_menu(menu, pos) -> None:
    """Muestra QMenu en pos — compatible PySide2 (exec_) y PySide6 (exec)."""
    if hasattr(menu, 'exec') and callable(menu.exec):
        menu.exec(pos)
    else:
        menu.exec_(pos)


# ── Helper globalPos() compatible PySide6 / PySide2 ────────────────────
# PySide6: e.globalPosition().toPoint()  |  PySide2: e.globalPos()
def _global_pos(event):
    if hasattr(event, 'globalPosition'):
        return event.globalPosition().toPoint()
    return event.globalPos()
