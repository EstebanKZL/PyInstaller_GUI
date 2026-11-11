"""Ventana principal de PyInstaller GUI - PRO Builder."""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .. import APP_DEVELOPER, APP_NAME, APP_VERSION
from ..core.command import build_command, build_spec
from ..core.config import BACKEND_LABELS, BACKENDS, BuildConfig
from ..core.errors import COMMON_ERRORS
from ..core.icons import validate_icon_file
from ..core.packages import pick_import_name, query_packages
from ..core.process import command_to_str, find_tool, sub_kwargs
from ..core.requirements import parse_requirement_full
from ..core.trust import add_trusted, needs_confirmation
from ..i18n import LANGUAGES, tr
from ..qt_compat import (
    QAction, QApplication, QButtonGroup, QCheckBox, QColor, QComboBox, QDialog, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QKeySequence, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSettings,
    QSplitter, QSystemTrayIcon, QTabWidget, QTextCursor, QTextEdit, QTimer, QVBoxLayout, QWidget, Qt, _exec,
    _exec_menu,
)
from ..workers import (
    BuildWorker, DepItem, InstallWorker, PyInstallerCheckWorker, PythonLocatorWorker, ScanWorker,
)
from .analysis_tab import AnalysisTab
from .components import (
    make_badge, make_button, make_hint, make_label, make_section, make_tab_scroll, set_badge, set_help,
)
from .dialogs import AboutDialog, PythonSelectorDialog
from .icons import ACTION_ICONS, icon
from .distribution_tab import DistributionTab
from .language import get_lang_code, set_lang_code
from .theme import SETTINGS_ORG, SP, THEME, get_theme_name, set_theme_name
from .widgets import DotGripWidget, DropLineEdit, LogView

MAX_RECENT = 5
MODE_ONEFILE_INDEX = 1   # índice del combo de modo: 0 = onedir, 1 = onefile


def _fmt_duration(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def _form(rows, label_width=150):
    """QGridLayout de formulario: labels alineados a la derecha y control a la izquierda.
    rows: [(texto_label, widget_o_layout), ...]"""
    grid = QGridLayout()
    grid.setHorizontalSpacing(SP["md"])
    grid.setVerticalSpacing(SP["sm"])
    grid.setColumnMinimumWidth(0, label_width)
    grid.setColumnStretch(1, 1)
    for r, (text, field) in enumerate(rows):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl, r, 0)
        if isinstance(field, QWidget):
            grid.addWidget(field, r, 1)
        else:
            grid.addLayout(field, r, 1)
    return grid


def _row(*items, stretch_first=True):
    """Fila horizontal con espaciado estándar; el primer elemento se estira."""
    h = QHBoxLayout()
    h.setSpacing(SP["sm"])
    for i, it in enumerate(items):
        h.addWidget(it, 1 if (i == 0 and stretch_first) else 0)
    return h


class BuilderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1280, 720)
        self.setMinimumSize(1280, 720)

        self.dep_items          = []
        self.current_workspace  = ""
        self.worker             = None
        self._scan_worker       = None
        self._install_worker    = None
        self._python_locator    = None
        self._pyinstaller_chk   = None
        self._stale_checks      = []   # chequeos reemplazados que siguen corriendo (no destruirlos)
        self.project_python     = None
        self._pyinstaller_ok    = None
        self.previous_mode_idx  = 0
        self._platform_target   = "linux"
        self._loading_profile   = False

        self.settings = QSettings(SETTINGS_ORG, APP_NAME)
        self._init_widgets()
        self.init_ui()
        self.restore_settings()

    # ── Controles ────────────────────────────────────────────────────────
    def _init_widgets(self):
        self.workspace_input = DropLineEdit(accept_dirs=True)
        self.workspace_input.setPlaceholderText(tr("ph.workspace"))
        self.workspace_input.path_dropped.connect(self._on_workspace_dropped)
        set_help(self.workspace_input, "workspace")

        self.script_input = DropLineEdit(accept_dirs=False)
        self.script_input.setPlaceholderText(tr("ph.script"))
        self.script_input.path_dropped.connect(self._on_script_dropped)
        set_help(self.script_input, "script")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("ph.name"))
        set_help(self.name_input, "name")

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([tr("mode.onedir"), tr("mode.onefile")])
        set_help(self.mode_combo, "mode")

        # Compilador: PyInstaller o Nuitka (la lógica usa el id guardado como dato, no el texto)
        self.backend_combo = QComboBox()
        for backend in BACKENDS:
            self.backend_combo.addItem(tr(f"backend.{backend}"), backend)
        set_help(self.backend_combo, "backend")

        self.icon_input = DropLineEdit(accept_dirs=False)
        self.icon_input.setPlaceholderText(tr("ph.icon"))
        set_help(self.icon_input, "icon")

        self.version_file_input = DropLineEdit(accept_dirs=False)
        self.version_file_input.setPlaceholderText(tr("ph.version_file"))
        set_help(self.version_file_input, "version_file")

        self.appimage_icon_input = DropLineEdit(accept_dirs=False)
        self.appimage_icon_input.setPlaceholderText(tr("ph.appimage_icon"))
        set_help(self.appimage_icon_input, "appimage_icon")

        self.python_path_input = QLineEdit()
        self.python_path_input.setReadOnly(True)
        self.python_path_input.setPlaceholderText(tr("ph.python"))
        set_help(self.python_path_input, "python")
        self.python_badge = make_badge(tr("badge.py_none"), "neutral")
        set_help(self.python_badge, "python_badge")

        def chk(key, checked=False):
            cb = QCheckBox(tr(f"chk.{key}"))
            cb.setChecked(checked)
            set_help(cb, key)
            return cb

        self.noconsole = chk("noconsole", True)
        self.debug_cb = chk("debug")
        self.clean = chk("clean", True)
        self.strip_cb = chk("strip")
        self.noupx_cb = chk("noupx")
        self.bootloader_ignore_cb = chk("bootloader")
        self.optimize_cb = chk("optimize")
        self.uac_admin_cb = chk("uac")
        if sys.platform != "win32":
            self.uac_admin_cb.setEnabled(False)
        # Opciones que solo existen en PyInstaller: se desactivan al elegir Nuitka
        self._pyinstaller_only = ((self.strip_cb, "strip"), (self.noupx_cb, "noupx"),
                                  (self.bootloader_ignore_cb, "bootloader"))
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)

        # ── Runtime tmpdir (onefile con carpeta de extracción fija) ──────
        self.runtime_tmpdir_cb = chk("tmpdir")
        self.runtime_tmpdir_input = QLineEdit()
        self.runtime_tmpdir_input.setPlaceholderText(tr("ph.tmpdir"))
        self.runtime_tmpdir_input.setEnabled(False)
        set_help(self.runtime_tmpdir_input, "tmpdir_path")
        self.runtime_tmpdir_cb.toggled.connect(self.runtime_tmpdir_input.setEnabled)
        self.runtime_tmpdir_cb.toggled.connect(self._on_runtime_tmpdir_toggled)

        # ── Entorno aislado: venv limpio desde requirements.txt ─────────
        self.isolated_venv_cb = chk("isolated")
        self.recreate_venv_cb = chk("recreate")
        self.recreate_venv_cb.setEnabled(False)
        self.isolated_venv_cb.toggled.connect(self.recreate_venv_cb.setEnabled)

        # ── Instalador NSIS (Windows, onedir) y AppImage (Linux) ─────────
        self.nsis_cb = chk("nsis")
        if sys.platform != "win32":
            self.nsis_cb.setEnabled(False)
        else:
            self.nsis_cb.toggled.connect(self._on_nsis_toggled)
        self.create_appimage_cb = chk("appimage")
        self.create_appimage_cb.toggled.connect(self._on_appimage_toggled)

        self.extra_flags_input = QLineEdit()
        self.extra_flags_input.setPlaceholderText(tr("ph.extra_flags"))
        set_help(self.extra_flags_input, "extra_flags")

        self.dist_path_input = QLineEdit()
        self.dist_path_input.setPlaceholderText(tr("ph.dist"))
        set_help(self.dist_path_input, "dist")
        self.build_path_input = QLineEdit()
        self.build_path_input.setPlaceholderText(tr("ph.build"))
        set_help(self.build_path_input, "build_dir")

        self.dest_folder_input = DropLineEdit(accept_dirs=True)
        self.dest_folder_input.setPlaceholderText(tr("ph.dest"))
        set_help(self.dest_folder_input, "dest")

        self.venv_path_input = QLineEdit()
        self.venv_path_input.setPlaceholderText(tr("ph.venv"))
        set_help(self.venv_path_input, "venv")

        self.add_data_list = QListWidget()
        self.add_data_list.setMaximumHeight(130)
        self.add_data_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.add_data_list.customContextMenuRequested.connect(lambda p: self._list_ctx(self.add_data_list, p))

        self.hidden_import_list = QListWidget()
        self.hidden_import_list.setMaximumHeight(130)
        self.hidden_import_input = QLineEdit()
        self.hidden_import_input.setPlaceholderText(tr("ph.hidden"))
        self.hidden_import_input.returnPressed.connect(self.add_hidden_import)
        set_help(self.hidden_import_input, "hidden_input")
        self.hidden_import_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hidden_import_list.customContextMenuRequested.connect(lambda p: self._list_ctx(self.hidden_import_list, p))
        # PIL y PIL._tkinter_finder como sugeridos (checkable). Vienen DESMARCADOS:
        # se activan solos si el escaneo detecta Pillow, así no inflan builds sin Pillow.
        self._SUGGESTED_HIDDEN = ["PIL", "PIL._tkinter_finder"]
        self._add_suggested_hidden()

        self.exclude_module_list = QListWidget()
        self.exclude_module_list.setMaximumHeight(110)
        self.exclude_module_input = QLineEdit()
        self.exclude_module_input.setPlaceholderText(tr("ph.exclude"))
        self.exclude_module_input.returnPressed.connect(self.add_exclude_module)
        set_help(self.exclude_module_input, "exclude_input")
        self.exclude_module_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.exclude_module_list.customContextMenuRequested.connect(lambda p: self._list_ctx(self.exclude_module_list, p))

        self.cmd_output = QTextEdit()
        self.cmd_output.setReadOnly(True)
        self.cmd_output.setObjectName("codeView")
        self.spec_output = QTextEdit()
        self.spec_output.setReadOnly(True)
        self.spec_output.setObjectName("codeView")
        self.install_script_output = QTextEdit()
        self.install_script_output.setReadOnly(True)
        self.install_script_output.setObjectName("codeView")
        self.install_script_output.setMaximumHeight(96)

        self.log_output = LogView()   # monoespaciado, coloreado por nivel

        self.deps_list = QListWidget()
        self.deps_list.setSelectionMode(QListWidget.SingleSelection)
        self.deps_list.itemDoubleClicked.connect(self._on_dep_double_clicked)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p%")

        # Badge de PyInstaller en el encabezado
        self.pyinstaller_label = make_badge(tr("badge.pyi_unknown", tool="PyInstaller"), "neutral")
        set_help(self.pyinstaller_label, "pyi_badge")

        self.dep_count_label = make_label("", "lblHint")

        self.btn_build = make_button(tr("btn.build"), "btnPrimary", self.run_build, "build", "Ctrl+B")
        self.btn_build.setMinimumWidth(128)
        self.btn_cancel = make_button(tr("btn.cancel"), "btnStop", self.cancel_build, "cancel", "Esc")
        self.btn_cancel.setVisible(False)

        # Cronómetro del build
        self.elapsed_label = make_label("", "lblHint")
        self._build_started = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self.btn_detect_python = make_button(tr("btn.detect_python"), "btnSecondary", self.auto_detect_python,
                                             "detect_python")

    # ── Estructura: encabezado → cuerpo → barra de estado ────────────────
    def init_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(SP["lg"], SP["md"], SP["lg"], SP["md"])
        body_lay.setSpacing(SP["md"])
        root.addWidget(body, 1)

        self.tabs = QTabWidget()
        self.main_tab = self._tab_main()
        self.deps_tab = self._tab_deps()
        self.advanced_tab = self._tab_avanzado()
        self.distribution_tab = DistributionTab(self)
        self.cmd_tab = self._tab_cmd()
        self.log_tab = self._tab_log()
        self.analysis_tab = AnalysisTab(self)
        for widget, key in ((self.main_tab, "main"), (self.deps_tab, "deps"), (self.advanced_tab, "advanced"),
                            (self.distribution_tab, "distribution"), (self.cmd_tab, "command"),
                            (self.log_tab, "log"), (self.analysis_tab, "analysis")):
            self.tabs.addTab(widget, tr(f"tab.{key}"))
        # Inno Setup (pestaña DISTRIBUCIÓN) también fuerza onedir y depende de la plataforma
        self.inno_cb = self.distribution_tab.inno_cb
        self.inno_cb.toggled.connect(self._update_mode_lock)
        self._select_platform(self._platform_target)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        body_lay.addWidget(self.tabs, 1)
        body_lay.addLayout(self._build_action_bar())

        self._build_menus()
        self._build_status_bar()
        self.update_pyinstaller_version()
        self._setup_shortcuts()

    def _build_header(self):
        header = QFrame()
        header.setObjectName("headerBar")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(SP["lg"] + 4, SP["md"], SP["lg"] + 4, SP["md"])
        lay.setSpacing(SP["md"])
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(make_label(APP_NAME, "lblAppTitle"))
        titles.addWidget(make_label(tr("app.subtitle"), "lblAppSubtitle"))
        lay.addLayout(titles)
        lay.addStretch(1)
        lay.addWidget(self.pyinstaller_label, 0, Qt.AlignVCenter)
        lay.addWidget(make_badge(APP_VERSION, "info"), 0, Qt.AlignVCenter)
        return header

    def _build_action_bar(self):
        """Barra inferior: perfiles a la izquierda; vistas, cancelar y la acción primaria
        (Compilar) a la derecha de todo."""
        row = QHBoxLayout()
        row.setSpacing(SP["sm"])
        row.addWidget(make_button(tr("btn.save_profile"), "btnSecondary", self.save_profile, "save_profile", "Ctrl+S"))
        row.addWidget(make_button(tr("btn.load_profile"), "btnSecondary", lambda: self.load_profile(),
                                  "load_profile", "Ctrl+O"))
        row.addSpacing(SP["md"])
        row.addWidget(self.progress_bar, 1)
        row.addWidget(self.elapsed_label)
        row.addStretch(1)
        row.addWidget(make_button(tr("btn.show_command"), None,
                                  lambda: (self.generate_command(), self.tabs.setCurrentWidget(self.cmd_tab)),
                                  "show_command"))
        row.addWidget(make_button(tr("btn.show_spec"), None, self.show_full_spec, "show_spec"))
        row.addWidget(make_button(tr("btn.open_dist"), None, self.open_dist_folder, "open_dist"))
        row.addSpacing(SP["md"])
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_build)
        return row

    def _build_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.setSizeGripEnabled(False)
        sep = "&nbsp;&nbsp;│&nbsp;&nbsp;"
        credit = QLabel()
        credit.setTextFormat(Qt.RichText)
        credit.setText(f'<span style="font-weight:400;">{APP_VERSION}{sep}{APP_DEVELOPER}</span>')
        credit.setContentsMargins(0, 0, SP["xl"], 0)   # deja lugar al grip
        self.status_bar.addPermanentWidget(credit)
        self._set_status(tr("status.ready"))
        self._grip = DotGripWidget(self, bg_color=THEME["status_bg"])
        self._reposition_grip()

    # ── Menús ────────────────────────────────────────────────────────────
    def _action(self, text_key, slot, help_key=None, shortcut=None, menu=None):
        act = QAction(tr(text_key), self)
        if help_key in ACTION_ICONS:
            act.setIcon(icon(ACTION_ICONS[help_key]))
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
            act.setShortcutContext(Qt.WindowShortcut)
        if help_key:
            set_help(act, help_key, shortcut)
        act.triggered.connect(slot)
        if menu is not None:
            menu.addAction(act)
        self.addAction(act)   # el atajo funciona aunque el menú no esté abierto
        return act

    def _build_menus(self):
        bar = self.menuBar()
        m_file = bar.addMenu(tr("menu.file"))
        m_build = bar.addMenu(tr("menu.build"))
        m_view = bar.addMenu(tr("menu.view"))
        m_help = bar.addMenu(tr("menu.help"))
        for m in (m_file, m_build, m_view, m_help):
            m.setToolTipsVisible(True)   # sin esto, QMenu no muestra tooltips

        self._action("action.open_project", self.select_workspace, "open_project", menu=m_file)
        self.recent_menu = m_file.addMenu(tr("menu.recent"))
        self.recent_menu.setToolTipsVisible(True)
        self.recent_menu.aboutToShow.connect(self._populate_recent_menu)
        m_file.addSeparator()
        self._action("action.save_profile", self.save_profile, "save_profile", "Ctrl+S", m_file)
        self._action("action.load_profile", lambda: self.load_profile(), "load_profile", "Ctrl+O", m_file)
        m_file.addSeparator()
        self._action("action.exit", self.close, "exit", menu=m_file)

        self._action("action.build", lambda: self.btn_build.isEnabled() and self.run_build(), "build", "Ctrl+B", m_build)
        self._action("action.cancel", lambda: self.worker and self.worker.isRunning() and self.cancel_build(),
                     "cancel", "Esc", m_build)
        m_build.addSeparator()
        self._action("action.show_command",
                     lambda: (self.generate_command(), self.tabs.setCurrentWidget(self.cmd_tab)), "show_command",
                     menu=m_build)
        self._action("action.show_spec", self.show_full_spec, "show_spec", menu=m_build)
        self._action("action.open_dist", self.open_dist_folder, "open_dist", menu=m_build)
        self._action("action.rescan", self.force_rescan, "rescan", "F5", m_build)
        m_build.addSeparator()
        self._action("action.reset", self._confirm_reset, "reset", menu=m_build)

        self._action("action.theme", self._change_theme, "theme", menu=m_view)
        self._build_language_menu(m_view)
        m_view.addSeparator()
        self._action("action.find_log", self._focus_log_search, "find_log", "Ctrl+F", m_view)

        self._action("action.shortcuts", self._show_shortcuts, "shortcuts", menu=m_help)
        self._action("action.about", self._show_about, "about", menu=m_help)

    def _build_language_menu(self, menu_view):
        menu_lang = menu_view.addMenu(tr("menu.language"))
        menu_lang.setToolTipsVisible(True)
        self._lang_actions = {}
        for code, name in LANGUAGES.items():   # los nombres de idioma no se traducen
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(code == get_lang_code())
            act.setToolTip(tr("tip.language"))
            act.triggered.connect(lambda checked=False, c=code: self._change_language(c))
            menu_lang.addAction(act)
            self._lang_actions[code] = act

    def _change_language(self, code):
        for c, act in self._lang_actions.items():
            act.setChecked(c == code)
        if code == get_lang_code():
            return
        set_lang_code(code)
        QMessageBox.information(self, tr("msg.restart_title"), tr("msg.lang_changed", app=APP_NAME))

    def _change_theme(self):
        new = "light" if get_theme_name() == "dark" else "dark"
        set_theme_name(new)
        QMessageBox.information(self, tr("msg.restart_title"),
                                tr("msg.theme_changed", theme=tr(f"theme.{new}"), app=APP_NAME))

    def _show_about(self):
        _exec(AboutDialog(self))

    def _show_shortcuts(self):
        QMessageBox.information(self, tr("msg.shortcuts_title"), tr("msg.shortcuts_body"))

    def _populate_recent_menu(self):
        self.recent_menu.clear()
        recent = self._load_recent()
        if not recent:
            empty = self.recent_menu.addAction(tr("menu.recent_empty"))
            empty.setEnabled(False)
            return
        for path in recent:
            act = self.recent_menu.addAction(icon("folder"), path)
            act.triggered.connect(lambda checked=False, p=path: self._open_recent(p))

    def _confirm_reset(self):
        r = QMessageBox.question(self, tr("msg.reset_title"), tr("msg.reset_body"), QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            self.reset_fields()

    # ── Atajos que no están en los menús ─────────────────────────────────
    def _setup_shortcuts(self):
        for i in range(self.tabs.count()):
            act = QAction(self)
            act.setShortcut(QKeySequence(f"Ctrl+{i + 1}"))
            act.setShortcutContext(Qt.WindowShortcut)
            act.triggered.connect(lambda checked=False, i=i: self.tabs.setCurrentIndex(i))
            self.addAction(act)

    def _focus_log_search(self):
        self.tabs.setCurrentWidget(self.log_tab)
        self.log_search.setFocus()
        self.log_search.selectAll()

    def _find_in_log(self, backward):
        text = self.log_search.text()
        total = self.log_output.find_text(text, backward)
        self.log_search_count.setText(tr("status.matches", n=total) if text else "")

    # ── Cronómetro y aviso de fin de build ───────────────────────────────
    def _tick_elapsed(self):
        if self._build_started is not None:
            self.elapsed_label.setText(tr("badge.elapsed", t=_fmt_duration(time.monotonic() - self._build_started)))

    def _notify_done(self, success, msg):
        """Si la ventana no está en primer plano: parpadeo en la barra de tareas y
        notificación del sistema (bandeja), para no tener que vigilar builds largos."""
        if self.isActiveWindow():
            return
        QApplication.alert(self, 0)
        icon = QApplication.windowIcon()
        if icon.isNull() or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if getattr(self, "_tray", None) is None:
            self._tray = QSystemTrayIcon(icon, self)
        self._tray.show()
        self._tray.showMessage(tr("notify.done") if success else tr("notify.failed"), msg)

    # ── Helpers de construcción ──────────────────────────────────────────
    def _mk_btn(self, label, obj_name=None, clicked=None, help_key=None):
        return make_button(label, obj_name, clicked, help_key)

    def _browse_btn(self, slot, help_key="browse"):
        return make_button(tr("btn.browse"), None, slot, help_key)

    def _copy_btn(self, label, get_fn):
        def _go():
            QApplication.clipboard().setText(get_fn())
            self._set_status(tr("status.copied"), timeout=3000)
        return make_button(label, None, _go, "copy")

    def _list_ctx(self, lst, pos):
        item = lst.itemAt(pos)
        if not item:
            return
        m = QMenu(self)
        a = QAction(tr("action.remove"), self)
        a.triggered.connect(lambda: lst.takeItem(lst.row(item)))
        m.addAction(a)
        _exec_menu(m, lst.viewport().mapToGlobal(pos))

    def _reposition_grip(self) -> None:
        if hasattr(self, '_grip'):
            self._grip.move(self.width() - self._grip.width(), self.height() - self._grip.height())
            self._grip.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_grip()

    def _set_status(self, msg, color=None, timeout=0):
        self.status_bar.showMessage(msg, timeout)

    def _on_tab_changed(self, index):
        """Regenera el comando cada vez que se abre la pestaña Comando, para que siempre
        refleje el estado actual de todos los campos."""
        if self.tabs.widget(index) is self.cmd_tab:
            try:
                if self.script_input.text().strip() and self.project_python:
                    self.generate_command()
            except Exception:
                pass  # Si faltan campos, no hacer nada

    # ── Pestaña Principal ────────────────────────────────────────────────
    def _tab_main(self):
        scroll, v = make_tab_scroll()

        grp = QGroupBox(tr("section.project"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        self._btn_recent = make_button(tr("btn.recent"), "btnSecondary", self._show_recent_menu, "recent")
        ws_row = _row(self.workspace_input,
                      make_button(tr("btn.select_folder"), None, self.select_workspace, "open_project"),
                      self._btn_recent)
        g.addLayout(_form([
            (tr("lbl.workspace"), ws_row),
            (tr("lbl.script"), _row(self.script_input, self._browse_btn(self.select_script))),
            (tr("lbl.name"), self.name_input),
            (tr("lbl.backend"), self.backend_combo),
            (tr("lbl.mode"), self.mode_combo),
        ]))
        g.addWidget(make_hint(tr("hint.workspace")))
        v.addWidget(grp)

        grp_py = QGroupBox(tr("section.python"))
        gp = QVBoxLayout(grp_py)
        gp.addLayout(_row(self.python_path_input, self.python_badge, self.btn_detect_python,
                          make_button(tr("btn.browse"), None, self.select_python_manual, "browse_python")))
        v.addWidget(grp_py)

        grp_ico = QGroupBox(tr("section.resources"))
        gi = QVBoxLayout(grp_ico)
        gi.addLayout(_form([
            (tr("lbl.icon"), _row(self.icon_input, self._browse_btn(self.select_icon))),
            (tr("lbl.appimage_icon"), _row(self.appimage_icon_input, self._browse_btn(self.select_appimage_icon))),
            (tr("lbl.version_file"), _row(self.version_file_input, self._browse_btn(self.select_version_file))),
        ]))
        v.addWidget(grp_ico)

        grp_opt = QGroupBox(tr("section.options"))
        go = QVBoxLayout(grp_opt)
        cols = QHBoxLayout()
        cols.setSpacing(SP["xl"])
        for widgets in ((self.noconsole, self.debug_cb, self.clean, self.strip_cb, self.noupx_cb,
                         self.create_appimage_cb),
                        (self.bootloader_ignore_cb, self.optimize_cb, self.uac_admin_cb, self.nsis_cb,
                         self.runtime_tmpdir_cb, self.isolated_venv_cb, self.recreate_venv_cb)):
            col = QVBoxLayout()
            col.setSpacing(SP["sm"])
            for w in widgets:
                col.addWidget(w)
            col.addStretch(1)
            cols.addLayout(col, 1)
        go.addLayout(cols)
        go.addLayout(_form([(tr("lbl.tmpdir"), self.runtime_tmpdir_input)]))
        v.addWidget(grp_opt)

        grp_fl = QGroupBox(tr("section.extra_flags"))
        QVBoxLayout(grp_fl).addWidget(self.extra_flags_input)
        v.addWidget(grp_fl)

        grp_dest = QGroupBox(tr("section.output"))
        gd = QVBoxLayout(grp_dest)
        gd.addLayout(_row(self.dest_folder_input,
                          make_button(tr("btn.select_folder"), None, self._browse_dest_folder, "select_folder")))
        gd.addWidget(make_hint(tr("hint.output")))
        v.addWidget(grp_dest)

        v.addStretch(1)
        return scroll

    # ── Pestaña Dependencias ─────────────────────────────────────────────
    def _tab_deps(self):
        scroll, v = make_tab_scroll()

        grp_data = QGroupBox(tr("section.add_data"))
        gd = QVBoxLayout(grp_data)
        gd.addWidget(make_hint(tr("hint.add_data")))
        gd.addWidget(self.add_data_list)
        self.add_data_input = QLineEdit()
        self.add_data_input.setPlaceholderText(tr("ph.add_data"))
        self.add_data_input.returnPressed.connect(self._add_data_from_text)
        set_help(self.add_data_input, "add_data_input")
        gd.addLayout(_row(self.add_data_input,
                          make_button(tr("btn.add_file"), None, self._add_data_browse, "add_file"),
                          make_button(tr("btn.remove"), None, lambda: self._remove_selected(self.add_data_list),
                                      "remove")))
        v.addWidget(grp_data)

        grp_hi = QGroupBox(tr("section.hidden"))
        gh = QVBoxLayout(grp_hi)
        gh.addWidget(make_hint(tr("hint.hidden")))
        gh.addWidget(self.hidden_import_list)
        gh.addLayout(_row(self.hidden_import_input,
                          make_button(tr("btn.add"), None, self.add_hidden_import, "add"),
                          make_button(tr("btn.remove"), None, lambda: self._remove_selected(self.hidden_import_list),
                                      "remove")))
        v.addWidget(grp_hi)

        grp_ex = QGroupBox(tr("section.exclude"))
        ge = QVBoxLayout(grp_ex)
        ge.addWidget(self.exclude_module_list)
        ge.addLayout(_row(self.exclude_module_input,
                          make_button(tr("btn.add"), None, self.add_exclude_module, "add"),
                          make_button(tr("btn.remove"), None, lambda: self._remove_selected(self.exclude_module_list),
                                      "remove")))
        v.addWidget(grp_ex)

        grp_col = QGroupBox(tr("section.collect"))
        gc = QVBoxLayout(grp_col)
        gc.addWidget(make_hint(tr("hint.collect")))
        self.collect_list = QListWidget()
        self.collect_list.setMaximumHeight(100)
        self.collect_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.collect_list.customContextMenuRequested.connect(lambda p: self._list_ctx(self.collect_list, p))
        gc.addWidget(self.collect_list)
        self.collect_kind_combo = QComboBox()
        self.collect_kind_combo.addItems(list(self.COLLECT_KINDS))
        set_help(self.collect_kind_combo, "collect_kind")
        self.collect_input = QLineEdit()
        self.collect_input.setPlaceholderText(tr("ph.collect"))
        self.collect_input.returnPressed.connect(self._add_collect_from_input)
        set_help(self.collect_input, "collect_input")
        row = QHBoxLayout()
        row.setSpacing(SP["sm"])
        row.addWidget(self.collect_kind_combo)
        row.addWidget(self.collect_input, 1)
        row.addWidget(make_button(tr("btn.add"), None, self._add_collect_from_input, "add"))
        row.addWidget(make_button(tr("btn.remove"), None, lambda: self._remove_selected(self.collect_list), "remove"))
        gc.addLayout(row)
        v.addWidget(grp_col)

        grp_req = QGroupBox(tr("section.requirements"))
        gr = QVBoxLayout(grp_req)
        info = QHBoxLayout()
        info.addWidget(make_hint(tr("hint.requirements")), 1)
        info.addWidget(self.dep_count_label, 0, Qt.AlignTop)
        gr.addLayout(info)
        gr.addWidget(self.deps_list)
        rb = QHBoxLayout()
        rb.setSpacing(SP["sm"])
        rb.addWidget(make_button(tr("btn.select_all"), None, self.select_all_deps, "select_all"))
        rb.addWidget(make_button(tr("btn.select_none"), None, self.deselect_all_deps, "select_none"))
        rb.addWidget(make_button(tr("btn.add_manual"), None, self.add_manual_import, "add_manual"))
        rb.addStretch(1)
        rb.addWidget(make_button(tr("btn.rescan"), "btnSecondary", self.force_rescan, "rescan", "F5"))
        gr.addLayout(rb)
        v.addWidget(grp_req)

        grp_install = QGroupBox(tr("section.install"))
        gi = QVBoxLayout(grp_install)
        gi.addWidget(make_hint(tr("hint.install")))
        ri = QHBoxLayout()
        ri.setSpacing(SP["sm"])
        ri.addWidget(make_button(tr("btn.install_missing"), "btnSecondary", self._install_missing_deps, "install_missing"))
        ri.addWidget(make_button(tr("btn.install_selected"), None, self._install_selected_deps, "install_selected"))
        ri.addWidget(make_button(tr("btn.install_all"), None, self._install_all_deps, "install_all"))
        ri.addWidget(make_button(tr("btn.upgrade_all"), None, self._upgrade_all_deps, "upgrade_all"))
        ri.addStretch(1)
        self._btn_cancel_install = make_button(tr("btn.cancel"), "btnStop", self._cancel_install, "cancel_install")
        self._btn_cancel_install.setVisible(False)
        ri.addWidget(self._btn_cancel_install)
        gi.addLayout(ri)
        self._install_progress = QProgressBar()
        self._install_progress.setRange(0, 100)
        self._install_progress.setVisible(False)
        self._install_progress.setFormat("%v / %m")
        gi.addWidget(self._install_progress)
        v.addWidget(grp_install)

        v.addStretch(1)
        return scroll

    # ── Pestaña Avanzado ─────────────────────────────────────────────────
    def _tab_avanzado(self):
        scroll, v = make_tab_scroll()

        grp_plat = QGroupBox(tr("section.platform"))
        gp = QHBoxLayout(grp_plat)
        gp.setSpacing(SP["sm"])
        self._platform_buttons = {}
        self._platform_group = QButtonGroup(self)
        self._platform_group.setExclusive(True)
        # La clave 'docker' se conserva por compatibilidad con perfiles anteriores
        for key in ("linux", "windows", "windows7", "macos", "docker"):
            btn = QPushButton(tr(f"platform.{key}"))
            btn.setObjectName("platformCard")
            btn.setCheckable(True)
            set_help(btn, "platform")
            btn.clicked.connect(lambda checked=False, k=key: self._select_platform(k))
            self._platform_group.addButton(btn)
            self._platform_buttons[key] = btn
            gp.addWidget(btn, 1)
        v.addWidget(grp_plat)

        grp_dir = QGroupBox(tr("section.dirs"))
        gdv = QVBoxLayout(grp_dir)
        gdv.addLayout(_form([
            (tr("lbl.dist"), _row(self.dist_path_input,
                                  make_button(tr("btn.select_folder"), None, self._browse_dist, "select_folder"))),
            (tr("lbl.build"), _row(self.build_path_input,
                                   make_button(tr("btn.select_folder"), None, self._browse_build, "select_folder"))),
        ]))
        v.addWidget(grp_dir)

        grp_venv = QGroupBox(tr("section.venv"))
        QVBoxLayout(grp_venv).addLayout(_row(self.venv_path_input,
                                             make_button(tr("btn.select_folder"), None, self._browse_venv,
                                                         "select_folder")))
        v.addWidget(grp_venv)

        v.addStretch(1)
        self._select_platform("linux" if sys.platform.startswith("linux") else "windows" if sys.platform == "win32" else "macos")
        return scroll

    def _select_platform(self, key):
        self._platform_target = key
        for k, b in self._platform_buttons.items():
            b.setChecked(k == key)

        # ── Habilitar/deshabilitar opciones según plataforma objetivo ───
        # 'docker' = multiplataforma vía GitHub Actions: el build local sigue siendo del SO actual
        is_win   = key in ("windows", "windows7") or (key == "docker" and sys.platform == "win32")
        is_linux = key == "linux" or (key == "docker" and sys.platform.startswith("linux"))

        self.uac_admin_cb.setEnabled(is_win)
        if not is_win:
            self.uac_admin_cb.setChecked(False)
        self.nsis_cb.setEnabled(is_win)
        if not is_win:
            self.nsis_cb.setChecked(False)
        self.create_appimage_cb.setEnabled(is_linux)
        if not is_linux:
            self.create_appimage_cb.setChecked(False)
        # Inno Setup (pestaña DISTRIBUCIÓN): solo Windows
        inno = getattr(self, "inno_cb", None)
        if inno is not None:
            inno.setEnabled(is_win)
            if not is_win:
                inno.setChecked(False)
        self._update_mode_lock()

        if key == "docker":
            self.log_output.append(tr("log.cross_compile"))
        if key == "windows" and sys.platform != "win32":
            self.log_output.append(tr("log.windows_from_windows"))

    def _browse_dist(self):
        d = QFileDialog.getExistingDirectory(self, tr("lbl.dist"))
        if d:
            self.dist_path_input.setText(d)

    def _browse_dest_folder(self):
        d = QFileDialog.getExistingDirectory(self, tr("section.output"))
        if d:
            self.dest_folder_input.setText(d)

    def _browse_build(self):
        d = QFileDialog.getExistingDirectory(self, tr("lbl.build"))
        if d:
            self.build_path_input.setText(d)

    def _browse_venv(self):
        d = QFileDialog.getExistingDirectory(self, tr("section.venv"))
        if d:
            self.venv_path_input.setText(d)

    # ── Pestaña Comando ──────────────────────────────────────────────────
    def _tab_cmd(self):
        w = QWidget()
        w.setObjectName("tabContent")
        v = QVBoxLayout(w)
        v.setSpacing(SP["sm"])
        v.setContentsMargins(SP["lg"], SP["md"], SP["lg"], SP["lg"])

        v.addWidget(make_section(tr("section.command")))
        v.addWidget(self.cmd_output, 1)
        v.addLayout(_row(self._copy_btn(tr("btn.copy_command"), self.cmd_output.toPlainText), stretch_first=False))
        v.addSpacing(SP["sm"])
        v.addWidget(make_section(tr("section.spec")))
        v.addWidget(self.spec_output, 2)
        rb = QHBoxLayout()
        rb.setSpacing(SP["sm"])
        rb.addWidget(self._copy_btn(tr("btn.copy_spec"), self.spec_output.toPlainText))
        rb.addWidget(make_button(tr("btn.save_spec"), None, self.save_spec_file, "save_spec"))
        rb.addStretch(1)
        v.addLayout(rb)
        v.addSpacing(SP["sm"])
        v.addWidget(make_section(tr("section.install_script")))
        v.addWidget(self.install_script_output)
        v.addLayout(_row(self._copy_btn(tr("btn.copy_script"), self.install_script_output.toPlainText),
                         stretch_first=False))
        return w

    # ── Pestaña Log ──────────────────────────────────────────────────────
    def _tab_log(self):
        w = QWidget()
        w.setObjectName("tabContent")
        root = QVBoxLayout(w)
        root.setSpacing(0)
        root.setContentsMargins(SP["lg"], SP["md"], SP["lg"], SP["lg"])

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        top_w = QWidget()
        top_v = QVBoxLayout(top_w)
        top_v.setContentsMargins(0, 0, 0, 0)
        top_v.setSpacing(SP["sm"])
        top_v.addWidget(make_section(tr("section.log")))
        top_v.addWidget(self.log_output, 1)
        rb = QHBoxLayout()
        rb.setSpacing(SP["sm"])
        rb.addWidget(make_button(tr("btn.clear_log"), None, self.log_output.clear, "clear_log"))
        rb.addWidget(make_button(tr("btn.save_log"), None, self.save_log, "save_log"))
        rb.addStretch(1)
        self.log_search = QLineEdit()
        self.log_search.setPlaceholderText(tr("ph.log_search"))
        self.log_search.setMinimumWidth(260)
        self.log_search.addAction(icon("search", "text_muted"), QLineEdit.LeadingPosition)
        self.log_search.returnPressed.connect(lambda: self._find_in_log(False))
        set_help(self.log_search, "log_search", "Ctrl+F")
        self.log_search_count = make_label("", "lblHint")
        rb.addWidget(self.log_search)
        rb.addWidget(make_button(tr("btn.find_prev"), None, lambda: self._find_in_log(True), "find_prev"))
        rb.addWidget(make_button(tr("btn.find_next"), None, lambda: self._find_in_log(False), "find_next"))
        rb.addWidget(self.log_search_count)
        top_v.addLayout(rb)
        splitter.addWidget(top_w)

        bot_w = QWidget()
        bot_v = QVBoxLayout(bot_w)
        bot_v.setContentsMargins(0, SP["sm"], 0, 0)
        bot_v.setSpacing(SP["sm"])
        hdr = QHBoxLayout()
        hdr.addWidget(make_section(tr("section.errors")))
        hdr.addSpacing(SP["md"])
        hdr.addWidget(make_label(tr("hint.errors"), "lblHint"), 1)
        bot_v.addLayout(hdr)

        error_scroll = QScrollArea()
        error_scroll.setObjectName("tabScroll")
        error_scroll.setWidgetResizable(True)
        error_scroll.setFrameShape(QFrame.NoFrame)
        error_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        error_container = QWidget()
        error_container.setObjectName("tabContent")
        error_layout = QVBoxLayout(error_container)
        error_layout.setSpacing(SP["xs"])
        error_layout.setContentsMargins(0, 0, SP["xs"], 0)
        for key in COMMON_ERRORS:
            title, fix = tr(f"err.{key}.title"), tr(f"err.{key}.fix")
            btn = QPushButton(f"{title}  —  {fix}")
            btn.setObjectName("errorCard")
            set_help(btn, "error_card")
            btn.clicked.connect(lambda checked=False, t=title, s=fix: (
                QApplication.clipboard().setText(f"{t}: {s}"), self._set_status(tr("status.copied"), timeout=3000)))
            error_layout.addWidget(btn)
        error_layout.addStretch(1)
        error_scroll.setWidget(error_container)
        bot_v.addWidget(error_scroll, 1)
        splitter.addWidget(bot_w)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)
        return w

    def _on_workspace_dropped(self, path):
        if os.path.isdir(path):
            self._set_workspace(path)
            self._set_status(f"Proyecto cargado: {path}")

    def _on_script_dropped(self, path):
        if path.endswith('.py') and os.path.isfile(path):
            self.script_input.setText(path)
            if not self.name_input.text().strip():
                self.name_input.setText(Path(path).stem)

    def _load_recent(self):
        raw = self.settings.value("recent_workspaces", [])
        if isinstance(raw, str):
            raw = [raw]
        return [r for r in (raw or []) if os.path.isdir(r)]

    def _add_recent(self, path):
        r = self._load_recent()
        if path in r:
            r.remove(path)
        r.insert(0, path)
        self.settings.setValue("recent_workspaces", r[:MAX_RECENT])

    def _show_recent_menu(self):
        recent = self._load_recent()
        if not recent:
            QMessageBox.information(self, tr("menu.recent"), tr("menu.recent_empty"))
            return
        m = QMenu(self)
        for path in recent:
            a = QAction(icon("folder"), path, self)
            a.triggered.connect(lambda ch, p=path: self._open_recent(p))
            m.addAction(a)
        _exec_menu(m, self._btn_recent.mapToGlobal(self._btn_recent.rect().bottomLeft()))   # FIX V4.2.0

    def _open_recent(self, path):
        if os.path.isdir(path):
            self._set_workspace(path)
        else:
            QMessageBox.warning(self, "Carpeta no encontrada", f"La carpeta ya no existe:\n{path}")

    def restore_settings(self):
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        self.noconsole.setChecked(self.settings.value("noconsole", True,  type=bool))
        self.debug_cb .setChecked(self.settings.value("debug",     False, type=bool))
        self.clean    .setChecked(self.settings.value("clean",     True,  type=bool))
        self.strip_cb .setChecked(self.settings.value("strip",     False, type=bool))
        self.noupx_cb .setChecked(self.settings.value("noupx",     False, type=bool))
        self.bootloader_ignore_cb.setChecked(self.settings.value("bootloader_ignore", False, type=bool))
        self.optimize_cb.setChecked(self.settings.value("optimize", False, type=bool))
        self.uac_admin_cb.setChecked(self.settings.value("uac_admin", False, type=bool))
        self.create_appimage_cb.setChecked(self.settings.value("create_appimage", False, type=bool))
        self.runtime_tmpdir_cb.setChecked(self.settings.value("runtime_tmpdir", False, type=bool))
        self.runtime_tmpdir_input.setText(self.settings.value("runtime_tmpdir_path", "", type=str))
        self.isolated_venv_cb.setChecked(self.settings.value("isolated_venv", False, type=bool))
        self.nsis_cb.setChecked(self.settings.value("nsis", False, type=bool))
        self.dest_folder_input.setText(self.settings.value("dest_folder", "", type=str))
        self._set_backend(self.settings.value("backend", "pyinstaller", type=str))

    def save_current_settings(self):
        self.settings.setValue("geometry",          self.saveGeometry())
        self.settings.setValue("noconsole",         self.noconsole.isChecked())
        self.settings.setValue("debug",             self.debug_cb.isChecked())
        self.settings.setValue("clean",             self.clean.isChecked())
        self.settings.setValue("strip",             self.strip_cb.isChecked())
        self.settings.setValue("noupx",             self.noupx_cb.isChecked())
        self.settings.setValue("bootloader_ignore", self.bootloader_ignore_cb.isChecked())
        self.settings.setValue("optimize",             self.optimize_cb.isChecked())
        self.settings.setValue("uac_admin",          self.uac_admin_cb.isChecked())
        self.settings.setValue("create_appimage",   self.create_appimage_cb.isChecked())
        self.settings.setValue("runtime_tmpdir",    self.runtime_tmpdir_cb.isChecked())
        self.settings.setValue("runtime_tmpdir_path", self.runtime_tmpdir_input.text())
        self.settings.setValue("isolated_venv", self.isolated_venv_cb.isChecked())
        self.settings.setValue("nsis",              self.nsis_cb.isChecked())
        self.settings.setValue("backend",           self.current_backend())
        self.settings.setValue("dest_folder",       self.dest_folder_input.text())

    def _update_mode_lock(self, *_):
        """Bloquea el modo según las opciones activas: AppImage, NSIS e Inno Setup necesitan
        onedir; --runtime-tmpdir necesita onefile (si chocan, gana onedir). Al liberarse
        se vuelve al modo que el usuario tenía elegido."""
        inno = getattr(self, "inno_cb", None)
        needs_onedir = [name for name, cb in (("AppImage", self.create_appimage_cb), ("NSIS", self.nsis_cb),
                                              ("Inno Setup", inno)) if cb is not None and cb.isChecked()]
        if needs_onedir:
            target, why = 0, tr("tip.mode_locked_onedir", tools=" / ".join(needs_onedir))
        elif self.runtime_tmpdir_cb.isChecked():
            target, why = 1, tr("tip.mode_locked_onefile")
        else:
            target, why = None, ""
        if target is not None:
            if self.mode_combo.isEnabled():
                self.previous_mode_idx = self.mode_combo.currentIndex()
            self.mode_combo.setCurrentIndex(target)
            self.mode_combo.setEnabled(False)
        elif not self.mode_combo.isEnabled():
            self.mode_combo.setEnabled(True)
            self.mode_combo.setCurrentIndex(self.previous_mode_idx)
        if why:
            self.mode_combo.setToolTip(why)
        else:
            set_help(self.mode_combo, "mode")

    _on_appimage_toggled = _on_runtime_tmpdir_toggled = _on_nsis_toggled = _update_mode_lock

    # ── Compilador (PyInstaller / Nuitka) ────────────────────────────────
    def current_backend(self):
        return self.backend_combo.currentData() or "pyinstaller"

    def _set_backend(self, backend):
        idx = self.backend_combo.findData(backend if backend in BACKENDS else "pyinstaller")
        self.backend_combo.setCurrentIndex(max(idx, 0))
        self._on_backend_changed()

    def _on_backend_changed(self, *_):
        nuitka = self.current_backend() == "nuitka"
        for cb, key in self._pyinstaller_only:
            cb.setEnabled(not nuitka)
            if nuitka:
                cb.setToolTip(tr("tip.pyinstaller_only"))
            else:
                set_help(cb, key)
        if hasattr(self, "pyinstaller_label"):
            self.update_pyinstaller_version()

    def _add_data_browse(self):
        start = self.current_workspace or ""
        path, _ = QFileDialog.getOpenFileName(self, tr("dlg.add_data"), start, tr("filter.all"))
        if path:
            self._add_data_file(path)

    def _add_data_from_text(self):
        text = self.add_data_input.text().strip()
        if not text:
            return
        if not os.path.isabs(text) and self.current_workspace:
            candidate = os.path.join(self.current_workspace, text)
            if os.path.isfile(candidate):
                text = candidate
        if os.path.isfile(text):
            self._add_data_file(text)
        else:
            reply = QMessageBox.question(self, tr("msg.file_missing_title"), tr("msg.file_missing_body", path=text),
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._add_data_file(text, verify=False)
        self.add_data_input.clear()

    def _add_data_file(self, path, verify=True, dest="."):
        if verify and not os.path.isfile(path):
            return
        for i in range(self.add_data_list.count()):
            if self.add_data_list.item(i).data(Qt.UserRole) == path:
                return
        display = os.path.basename(path)
        item = QListWidgetItem(f"  {display}")
        item.setData(Qt.UserRole, path)
        item.setData(Qt.UserRole + 1, dest or ".")
        item.setToolTip(path if dest in ("", ".") else f"{path}  →  {dest}")
        self.add_data_list.addItem(item)

    def _get_add_data_entries(self):
        result = []
        for i in range(self.add_data_list.count()):
            it = self.add_data_list.item(i)
            src = it.data(Qt.UserRole)
            if src:
                result.append((src, it.data(Qt.UserRole + 1) or "."))
        return result

    def _add_suggested_hidden(self, checked=False):
        for name in self._SUGGESTED_HIDDEN:
            it = QListWidgetItem(tr("lbl.suggested_item", name=name))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            it.setForeground(QColor(THEME["ip"]))
            it.setToolTip(tr("tip.suggested_item", name=name))
            it.setData(Qt.UserRole + 1, name)
            it.setData(Qt.UserRole + 2, True)   # marcador checkable (compatible PySide2/6)
            self.hidden_import_list.addItem(it)

    def _set_suggested_hidden_checked(self, checked, names=None):
        for i in range(self.hidden_import_list.count()):
            it = self.hidden_import_list.item(i)
            name = it.data(Qt.UserRole + 1)
            if name and bool(it.data(Qt.UserRole + 2)) and (names is None or name in names):
                it.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def add_hidden_import(self):
        t = self.hidden_import_input.text().strip()
        if not t:
            return
        self.hidden_import_input.clear()
        if not self.add_hidden_import_name(t):
            self._set_status(tr("status.already_listed", name=t))

    def add_hidden_import_name(self, name):
        """Agrega un hidden import (o marca el sugerido equivalente). False si ya estaba."""
        for i in range(self.hidden_import_list.count()):
            it = self.hidden_import_list.item(i)
            existing = it.data(Qt.UserRole + 1) or it.text().strip()
            if existing == name:
                if bool(it.data(Qt.UserRole + 2)) and it.checkState() != Qt.Checked:
                    it.setCheckState(Qt.Checked)
                    return True
                return False
        self.hidden_import_list.addItem(QListWidgetItem(name))
        return True

    # ── Recolección extra: --collect-all / --collect-data / --copy-metadata ──
    COLLECT_KINDS = ("collect-all", "collect-data", "copy-metadata")

    def add_collect_entry(self, kind, pkg):
        pkg = pkg.strip()
        if kind not in self.COLLECT_KINDS or not pkg:
            return False
        for i in range(self.collect_list.count()):
            if self.collect_list.item(i).data(Qt.UserRole) == [kind, pkg]:
                return False
        it = QListWidgetItem(f"  --{kind}={pkg}")
        it.setData(Qt.UserRole, [kind, pkg])
        self.collect_list.addItem(it)
        return True

    def _add_collect_from_input(self):
        if self.add_collect_entry(self.collect_kind_combo.currentText(), self.collect_input.text()):
            self.collect_input.clear()

    def _collect_values(self, kind):
        vals = []
        for i in range(self.collect_list.count()):
            k, pkg = self.collect_list.item(i).data(Qt.UserRole)
            if k == kind:
                vals.append(pkg)
        return vals

    def add_requirement_lines(self, lines):
        """Agrega paquetes al requirements.txt del proyecto (con confirmación).
        Devuelve la lista de lo agregado."""
        if not self.current_workspace:
            return []
        req = os.path.join(self.current_workspace, "requirements.txt")
        existing = ""
        if os.path.isfile(req):
            with open(req, "r", encoding="utf-8", errors="replace") as f:
                existing = f.read()
        present = {(parse_requirement_full(ln) or ("",))[0].lower() for ln in existing.splitlines()}
        new = [ln for ln in dict.fromkeys(lines) if ln.lower() not in present]
        if not new:
            return []
        r = QMessageBox.question(self, tr("msg.add_req_title"),
                                 tr("msg.add_req_body", items="\n".join(f"  • {ln}" for ln in new)),
                                 QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return []
        with open(req, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            for ln in new:
                f.write(f"{ln}\n")
        self.force_rescan()
        return [f"requirements.txt += {ln}" for ln in new]

    def _on_dep_double_clicked(self, item):
        """Doble clic en una dependencia → agrega su módulo real a los imports ocultos."""
        dep = item.data(Qt.UserRole)
        if not dep or not isinstance(dep, DepItem):
            return
        module_name = dep.import_name
        for i in range(self.hidden_import_list.count()):
            it = self.hidden_import_list.item(i)
            existing = it.data(Qt.UserRole + 1) or it.text().strip()
            if existing == module_name:
                self._set_status(tr("status.already_hidden", name=module_name))
                self.tabs.setCurrentWidget(self.deps_tab)
                return
        new_item = QListWidgetItem(module_name)
        new_item.setForeground(QColor(THEME["ip"]))
        new_item.setToolTip(tr("tip.added_from_deps", pkg=dep.pkg_name))
        self.hidden_import_list.addItem(new_item)
        self._set_status(tr("status.added_hidden", name=module_name))

    def add_exclude_module(self):
        t = self.exclude_module_input.text().strip()
        if t:
            self.exclude_module_list.addItem(QListWidgetItem(t))
            self.exclude_module_input.clear()

    def _remove_selected(self, lst):
        for it in lst.selectedItems():
            lst.takeItem(lst.row(it))

    def _get_list_items(self, lst):
        """Para hidden_import_list, los ítems checkables (PIL, etc.) solo se incluyen
        si están marcados. Los ítems normales (manuales, doble clic) siempre se incluyen.

        Usa UserRole+2 como marcador de 'es checkable' en lugar de it.flags() para
        evitar incompatibilidades entre PySide2 (ItemFlag no acepta int()) y PySide6
        (el resultado de & siempre es un objeto, sin importar el valor).
        """
        result = []
        for i in range(lst.count()):
            it = lst.item(i)
            if it is None:
                continue
            clean_name = it.data(Qt.UserRole + 1)
            is_checkable = bool(it.data(Qt.UserRole + 2))
            if is_checkable:
                if it.checkState() == Qt.Checked:
                    result.append(clean_name or it.text().strip())
            else:
                result.append(it.text().strip())
        return result

    def test_python(self, path):
        try:
            r = subprocess.run([path, "-c", "print('OK')"], capture_output=True, text=True, timeout=5, **sub_kwargs())
            return r.returncode == 0 and "OK" in r.stdout
        except Exception:
            return False

    # ── Confianza en intérpretes de afuera (venv del proyecto, perfiles) ──
    def _trusted_pythons(self):
        value = self.settings.value("trusted_pythons", [])
        if isinstance(value, str):
            value = [value]
        return [str(v) for v in (value or [])]

    def _trust_python(self, path):
        self.settings.setValue("trusted_pythons", add_trusted(self._trusted_pythons(), path))

    def _confirm_python(self, path, from_profile=False, force=False):
        """True si 'path' se puede ejecutar: es confiable o el usuario lo confirma ahora."""
        if not needs_confirmation(path, self.current_workspace, from_profile, self._trusted_pythons(), force):
            return True
        origin = tr("trust.origin_profile" if from_profile else "trust.origin_project")
        answer = QMessageBox.question(self, tr("msg.python_trust_title"),
                                      tr("msg.python_trust_body", path=path, origin=origin),
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            self._set_status(tr("status.python_not_trusted"))
            return False
        self._trust_python(path)
        return True

    def set_python_path(self, path, from_auto=True, validated=False):
        """validated=True cuando PythonLocatorWorker ya lo probó: evita volver a
        lanzar el intérprete en el hilo de la interfaz."""
        if not path or not os.path.isfile(path) or not (validated or self.test_python(path)):
            self.python_path_input.setText(path or "")
            self._set_python_badge("py_invalid")
            self.project_python = None
            self.update_pyinstaller_version()
            self._set_status(tr("status.python_invalid"))
            return

        self.project_python = path
        self.python_path_input.setText(path)
        if from_auto:
            in_venv = any(part in ("venv", ".venv", "env", ".env", "virtualenv", ".pipenv")
                          for part in Path(path).parts)
            self._set_python_badge("py_venv" if in_venv else "py_system")
            self._set_status(tr("status.python_set", path=path))
        else:
            self._set_python_badge("py_manual")
            self._set_status(tr("status.python_manual", path=path))

        if self.current_workspace and not self._loading_profile:
            self.scan_workspace(self.current_workspace)
        self.update_pyinstaller_version()

    def update_pyinstaller_version(self):
        """Verifica en segundo plano que el compilador elegido esté instalado en el Python del proyecto."""
        self._pyinstaller_ok = None   # None = desconocido / verificando
        backend = self.current_backend()
        tool = BACKEND_LABELS[backend]
        if not self.project_python:
            set_badge(self.pyinstaller_label, tr("badge.pyi_unknown", tool=tool), "neutral")
            return
        set_badge(self.pyinstaller_label, tr("badge.pyi_checking", tool=tool), "info")
        self._keep_until_finished(self._pyinstaller_chk)
        self._pyinstaller_chk = PyInstallerCheckWorker(self.project_python, backend)
        self._pyinstaller_chk.check_finished.connect(self._on_pyinstaller_checked)
        self._pyinstaller_chk.start()

    def _keep_until_finished(self, thread):
        """Un QThread destruido mientras corre aborta el programa: si se reemplaza un chequeo
        en marcha, se guarda la referencia hasta que termine."""
        if thread is None or not thread.isRunning():
            return
        self._stale_checks.append(thread)
        thread.finished.connect(lambda t=thread: t in self._stale_checks and self._stale_checks.remove(t))

    def _on_pyinstaller_checked(self, status, version):
        worker = self.sender()
        backend = getattr(worker, "backend", self.current_backend())
        if backend != self.current_backend():
            return   # resultado de un chequeo anterior al cambio de compilador
        tool = BACKEND_LABELS[backend]
        if status == "ok":
            self._pyinstaller_ok = True
            set_badge(self.pyinstaller_label, tr("badge.pyi_version", tool=tool, version=version), "ok")
        elif status == "missing":
            self._pyinstaller_ok = False
            set_badge(self.pyinstaller_label, tr("badge.pyi_missing", tool=tool), "error")
        else:
            self._pyinstaller_ok = None
            set_badge(self.pyinstaller_label, tr("badge.pyi_error", tool=tool), "warn")

    def auto_detect_python(self):
        if not self.current_workspace:
            QMessageBox.information(self, tr("msg.no_project_title"), tr("msg.no_project_body"))
            return
        self._set_status(tr("status.searching_python"))
        self.btn_detect_python.setEnabled(False)
        self.python_path_input.clear()
        self.python_path_input.setPlaceholderText(tr("ph.python"))

        self._keep_until_finished(self._python_locator)
        self._python_locator = PythonLocatorWorker(self.current_workspace, self._trusted_pythons())
        self._python_locator.versions_found.connect(self._on_python_detected)
        self._python_locator.start()

    def _on_python_detected(self, pythons):
        if self.sender() is not self._python_locator:
            return   # resultado de una búsqueda anterior (se cambió de proyecto mientras tanto)
        self.btn_detect_python.setEnabled(True)
        if not pythons:
            self.set_python_path(sys.executable, from_auto=True)
            return

        if len(pythons) == 1:
            choice = pythons[0]
        else:
            dlg = PythonSelectorDialog(pythons, parent=self)
            selected = dlg.selected_path() if _exec(dlg) == QDialog.Accepted else None
            choice = next((p for p in pythons if p["path"] == selected), pythons[0])

        if choice.get("untrusted"):
            # El venv del proyecto todavía no se ejecutó: confirmar y verificarlo recién ahora
            if self._confirm_python(choice["path"], force=True):
                self.set_python_path(choice["path"], from_auto=True)
                return
            others = [p for p in pythons if not p.get("untrusted")]
            if not others:
                self.set_python_path(sys.executable, from_auto=True)
                return
            choice = others[0]
        self.set_python_path(choice["path"], from_auto=True, validated=True)

    def select_python_manual(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dlg.python"), "", tr("filter.executables"))
        if path:
            self._trust_python(path)   # elegido a mano por el usuario: confiable
            self.set_python_path(path, from_auto=False)

    def select_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, tr("dlg.workspace"))
        if folder:
            self._set_workspace(folder)

    def _deferred_script_selection(self):
        """QInputDialog fuera del contexto de una señal de hilo: evita bloqueos y ventanas
        duplicadas en Windows 7 con PySide2."""
        folder = getattr(self, '_pending_folder', self.current_workspace)
        py_files = getattr(self, '_pending_py_files', [])
        if py_files:
            chosen, ok = QInputDialog.getItem(self, tr("lbl.script"), tr("dlg.choose_script"), py_files, 0, False)
            if not ok:
                chosen = py_files[0]
            self.script_input.setText(os.path.join(folder, chosen))
            self.name_input.setText(Path(chosen).stem)
        self._scan_workspace_continue(folder, scan_only=True)

    @staticmethod
    def _should_autofill_icon(current, folder):
        current = current.strip()
        return not current or not os.path.isfile(current)

    @staticmethod
    def _is_inside(path, folder):
        try:
            return os.path.commonpath([os.path.abspath(path), os.path.abspath(folder)]) == os.path.abspath(folder)
        except ValueError:   # distinta unidad en Windows
            return False

    def _set_workspace(self, path):
        """Cambia de proyecto. Los íconos que pertenecían al proyecto anterior se
        limpian para que se autodetecten los del nuevo; uno elegido fuera se conserva."""
        old = self.current_workspace
        if old and os.path.normcase(os.path.abspath(old)) != os.path.normcase(os.path.abspath(path)):
            for w in (self.icon_input, self.appimage_icon_input):
                if w.text().strip() and self._is_inside(w.text().strip(), old):
                    w.clear()
        self.current_workspace = path
        self.workspace_input.setText(path)
        self._add_recent(path)
        self.distribution_tab.refresh_project_info()
        self.auto_detect_python()

    def _scan_workspace_continue(self, folder, scan_only=False):
        """Parte del scan que no necesita diálogos — siempre segura de llamar."""
        try:
            files = os.listdir(folder)
        except Exception:
            return
        al = {f.lower(): f for f in files}
        # Autodetectar íconos solo si el campo está vacío o el archivo ya no existe:
        # así no se pisa el ícono elegido a mano o cargado desde un perfil.
        if self._should_autofill_icon(self.icon_input.text(), folder):
            ico = al.get('icon.ico') or al.get('icono.ico') or next((f for f in files if f.lower().endswith('.ico')), None)
            self.icon_input.setText(os.path.join(folder, ico) if ico else "")
        if self._should_autofill_icon(self.appimage_icon_input.text(), folder):
            png = al.get('icon.png') or al.get('icono.png') or next((f for f in files if f.lower().endswith('.png')), None)
            self.appimage_icon_input.setText(os.path.join(folder, png) if png else "")
        req = os.path.join(folder, "requirements.txt")
        if not os.path.exists(req):
            self._deps_info_item(tr("deps.no_requirements"))
            self._set_status(tr("status.no_requirements"))
            return
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait()
        self._deps_info_item(tr("deps.scanning"))
        self._set_status(tr("status.scanning"))
        self._scan_worker = ScanWorker(folder, self.project_python)
        self._scan_worker.item_ready.connect(self._on_item_ready)
        self._scan_worker.scan_complete.connect(self._on_scan_done)
        self._scan_worker.log_signal.connect(self.append_log)
        self._scan_worker.progress_sig.connect(self._on_scan_progress)
        self._scan_worker.start()

    def scan_workspace(self, folder, auto_select_script=True):
        """El QInputDialog de script se difiere con singleShot para evitar bloqueos en
        Windows 7 cuando se llama desde la señal de un hilo."""
        self.deps_list.clear()
        self.dep_items.clear()
        self.dep_count_label.setText("")

        if not self.project_python:
            self._deps_info_item(tr("deps.no_python"), "error")
            return

        self.log_output.append(tr("log.checking_with", path=self.project_python))

        try:
            files = os.listdir(folder)
        except Exception:
            return

        if auto_select_script:
            py_files = [f for f in files if f.endswith('.py')]
            if len(py_files) == 1:
                chosen = py_files[0]
                self.script_input.setText(os.path.join(folder, chosen))
                self.name_input.setText(Path(chosen).stem)
            elif len(py_files) > 1:
                for pref in ('main.py', 'app.py', '__main__.py'):
                    if pref in py_files:
                        self.script_input.setText(os.path.join(folder, pref))
                        self.name_input.setText(Path(pref).stem)
                        break
                else:
                    self._pending_py_files = py_files
                    self._pending_folder = folder
                    self._pending_auto = auto_select_script
                    QTimer.singleShot(60, self._deferred_script_selection)
                    return  # continúa desde _deferred_script_selection

        self._scan_workspace_continue(folder)

    def _on_scan_progress(self, cur, total):
        if total:
            self.dep_count_label.setText(tr("deps.progress", cur=cur, total=total))

    # Estado de cada dependencia → (color del tema, prefijo corto, clave del tooltip)

    _DEP_STATES = {
        "ok":       ("ok",      "OK",  "tip.dep_ok"),
        "mismatch": ("counter", "!",   "tip.dep_mismatch"),
        "missing":  ("error",   "X",   "tip.dep_missing"),
        "build":    ("ip",      "B",   "tip.dep_build"),
        "manual":   ("ip",      "+",   "tip.dep_manual"),
    }

    def _on_item_ready(self, pkg, iname, installed, auto, state, req_spec, inst_ver, modules):
        if self.deps_list.count() == 1 and self.deps_list.item(0).data(Qt.UserRole + 3) == "info":
            self.deps_list.clear()

        dep = DepItem(pkg, installed, iname, req_spec, inst_ver, modules)
        if installed and "PIL" in dep.modules:
            self._set_suggested_hidden_checked(True)   # Pillow en el proyecto → activar PIL sugeridos
        self.dep_items.append(dep)
        self.deps_list.addItem(self._dep_list_item(dep, state, auto))

    def _on_scan_done(self, found, total, installed):
        miss = total - installed
        s = tr("deps.summary", installed=installed, total=total)
        if miss:
            s += "  ·  " + tr("deps.summary_missing", n=miss)
        self.dep_count_label.setText(s)
        if not found:
            self.log_output.append(tr("log.no_installed"))
            self._set_status(tr("status.no_installed"))
        else:
            self._set_status(tr("status.scan_done", summary=s))
        self.log_output.append(tr("log.scan_end"))

    def select_all_deps(self):
        for i in range(self.deps_list.count()):
            it = self.deps_list.item(i)
            if bool(it.data(Qt.UserRole + 2)):
                it.setCheckState(Qt.Checked)

    def deselect_all_deps(self):
        for i in range(self.deps_list.count()):
            it = self.deps_list.item(i)
            if bool(it.data(Qt.UserRole + 2)):
                it.setCheckState(Qt.Unchecked)

    def force_rescan(self):
        if self.current_workspace:
            self.scan_workspace(self.current_workspace)
        else:
            QMessageBox.information(self, tr("msg.no_project_title"), tr("msg.no_project_body"))

    def add_manual_import(self):
        pkg_raw, ok = QInputDialog.getText(self, tr("dlg.manual_title"), tr("dlg.manual_label"))
        if not ok or not pkg_raw.strip():
            return
        parsed = parse_requirement_full(pkg_raw.strip())
        if not parsed:
            QMessageBox.warning(self, tr("msg.invalid_format_title"), tr("msg.invalid_format_body"))
            return
        pkg_name, req_spec, full_line = parsed
        iname = pkg_name.replace('-', '_')

        for i in range(self.deps_list.count()):
            d = self.deps_list.item(i).data(Qt.UserRole)
            if d and isinstance(d, DepItem) and d.pkg_name.lower() == pkg_name.lower():
                QMessageBox.information(self, tr("msg.exists_title"), tr("msg.exists_body", pkg=pkg_name))
                return

        inst_ver, modules = "", []
        if self.project_python:
            pi = query_packages(self.project_python, [(pkg_name, req_spec)], timeout=10).get(pkg_name, {})
            inst_ver, modules = pi.get("version") or "", pi.get("modules") or []
            iname = pick_import_name(pkg_name, modules)

        if not req_spec and inst_ver:
            reply = QMessageBox.question(self, tr("msg.version_found_title"),
                                         tr("msg.version_found_body", pkg=pkg_name, version=inst_ver),
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                req_spec = f"=={inst_ver}"
                full_line = f"{pkg_name}=={inst_ver}"

        installed = bool(inst_ver or modules)
        dep = DepItem(pkg_name, installed, iname, req_spec, inst_ver, modules)
        self.dep_items.append(dep)
        self.deps_list.addItem(self._dep_list_item(dep, "manual" if installed else "missing", installed))

        req_path = os.path.join(self.current_workspace, "requirements.txt") if self.current_workspace else ""
        if req_path and os.path.exists(req_path):
            with open(req_path, 'r', encoding='utf-8') as f:
                existing = f.read()
            already_there = any((parse_requirement_full(ln) or (None,))[0] == pkg_name for ln in existing.splitlines())
            if not already_there:
                reply2 = QMessageBox.question(self, tr("msg.add_req_title"),
                                              tr("msg.add_req_body", items=f"  • {full_line}"),
                                              QMessageBox.Yes | QMessageBox.No)
                if reply2 == QMessageBox.Yes:
                    with open(req_path, 'a', encoding='utf-8') as f:
                        if not existing.endswith('\n'):
                            f.write('\n')
                        f.write(f"{full_line}\n")
                    self._set_status(tr("status.req_added", line=full_line))

    def _get_checked_imports(self):
        """V4.4.0: solo devuelve módulos de la lista 'Librerías Ocultas' que el usuario
        agregó explícitamente. Los paquetes del scanner de dependencias (deps_list)
        NO se inyectan como --hidden-import; solo controlan --exclude-module
        (si están desmarcados). Esto evita que librerías instaladas pero no deseadas
        (ej. PyQt5) aparezcan en la compilación sin haber sido pedidas.
        """
        return list(dict.fromkeys(self._get_list_items(self.hidden_import_list)))

    def select_script(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("lbl.script"), "", tr("filter.python"))
        if path:
            self.script_input.setText(path)
            if not self.name_input.text().strip():
                self.name_input.setText(Path(path).stem)

    def select_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("lbl.icon"), "", tr("filter.icons"))
        if path:
            if path.lower().endswith('.ico') and not validate_icon_file(path, '.ico'):
                QMessageBox.warning(self, tr("msg.invalid_icon_title"), tr("msg.invalid_ico_body"))
            else:
                self.icon_input.setText(path)

    def select_appimage_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("lbl.appimage_icon"), "", tr("filter.png"))
        if path and validate_icon_file(path, '.png'):
            self.appimage_icon_input.setText(path)
        elif path:
            QMessageBox.warning(self, tr("msg.invalid_icon_title"), tr("msg.invalid_png_body"))

    def select_version_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("lbl.version_file"), "", tr("filter.text"))
        if path:
            self.version_file_input.setText(path)

    def collect_config(self):
        """Estado actual de la interfaz como BuildConfig."""
        cfg = BuildConfig(
            workspace=self.current_workspace,
            script=self.script_input.text().strip(),
            name=self.name_input.text().strip(),
            python_path=self.project_python or "",
            onefile=self.mode_combo.currentIndex() == MODE_ONEFILE_INDEX,
            platform=self._platform_target,
            backend=self.current_backend(),
            icon=self.icon_input.text().strip(),
            version_file=self.version_file_input.text().strip(),
            appimage_icon=self.appimage_icon_input.text().strip(),
            noconsole=self.noconsole.isChecked(),
            debug=self.debug_cb.isChecked(),
            clean=self.clean.isChecked(),
            strip=self.strip_cb.isChecked(),
            noupx=self.noupx_cb.isChecked(),
            bootloader_ignore=self.bootloader_ignore_cb.isChecked(),
            optimize=self.optimize_cb.isChecked(),
            uac_admin=self.uac_admin_cb.isChecked(),
            runtime_tmpdir=self.runtime_tmpdir_cb.isChecked(),
            runtime_tmpdir_path=self.runtime_tmpdir_input.text().strip(),
            extra_flags=self.extra_flags_input.text().strip(),
            create_appimage=self.create_appimage_cb.isChecked(),
            nsis=self.nsis_cb.isChecked(),
            dest_folder=self.dest_folder_input.text().strip(),
            dist_path=self.dist_path_input.text().strip(),
            build_path=self.build_path_input.text().strip(),
            venv_path=self.venv_path_input.text().strip(),
            add_data=self._get_add_data_entries(),
            hidden_imports=self._get_checked_imports(),
            exclude_modules=self._get_list_items(self.exclude_module_list),
            collect_all=self._collect_values("collect-all"),
            collect_data=self._collect_values("collect-data"),
            copy_metadata=self._collect_values("copy-metadata"),
            isolated_venv=self.isolated_venv_cb.isChecked(),
            dep_excludes=self._get_dep_excludes(),
        )
        return self.distribution_tab.fill_config(cfg)

    def apply_config(self, cfg):
        """Carga un BuildConfig en la interfaz (perfiles)."""
        self.add_data_list.clear()
        self.hidden_import_list.clear()
        self.exclude_module_list.clear()

        if cfg.workspace and os.path.isdir(cfg.workspace):
            self.current_workspace = cfg.workspace
            self.workspace_input.setText(cfg.workspace)
        if cfg.script and os.path.isfile(cfg.script):
            self.script_input.setText(cfg.script)
        self.name_input.setText(cfg.name)
        self.mode_combo.setCurrentIndex(MODE_ONEFILE_INDEX if cfg.onefile else 0)
        self._set_backend(cfg.backend)
        self.icon_input.setText(cfg.icon)
        self.version_file_input.setText(cfg.version_file)
        self.appimage_icon_input.setText(cfg.appimage_icon)
        if cfg.python_path and os.path.isfile(cfg.python_path) and \
                self._confirm_python(cfg.python_path, from_profile=True):
            self.set_python_path(cfg.python_path, from_auto=False)

        for cb, value in ((self.noconsole, cfg.noconsole), (self.debug_cb, cfg.debug), (self.clean, cfg.clean),
                          (self.strip_cb, cfg.strip), (self.noupx_cb, cfg.noupx),
                          (self.bootloader_ignore_cb, cfg.bootloader_ignore), (self.optimize_cb, cfg.optimize),
                          (self.uac_admin_cb, cfg.uac_admin), (self.create_appimage_cb, cfg.create_appimage),
                          (self.runtime_tmpdir_cb, cfg.runtime_tmpdir), (self.nsis_cb, cfg.nsis),
                          (self.isolated_venv_cb, cfg.isolated_venv)):
            cb.setChecked(value)
        for le, value in ((self.runtime_tmpdir_input, cfg.runtime_tmpdir_path), (self.dest_folder_input, cfg.dest_folder),
                          (self.extra_flags_input, cfg.extra_flags), (self.dist_path_input, cfg.dist_path),
                          (self.build_path_input, cfg.build_path), (self.venv_path_input, cfg.venv_path)):
            le.setText(value)
        self._select_platform(cfg.platform)
        self.distribution_tab.apply_config(cfg)

        for src, dst in cfg.add_data:
            self._add_data_file(src, verify=False, dest=dst)
        self._add_suggested_hidden()
        for e in cfg.hidden_imports:
            if e in self._SUGGESTED_HIDDEN:
                self._set_suggested_hidden_checked(True, names={e})
            else:
                self.hidden_import_list.addItem(QListWidgetItem(e))
        for e in cfg.exclude_modules:
            self.exclude_module_list.addItem(QListWidgetItem(e))
        self.collect_list.clear()
        for kind, values in (("collect-all", cfg.collect_all), ("collect-data", cfg.collect_data),
                             ("copy-metadata", cfg.copy_metadata)):
            for pkg in values:
                self.add_collect_entry(kind, pkg)

    def _get_dep_excludes(self):
        """Módulos de dependencias instaladas que el usuario desmarcó en el escáner."""
        excluded = []
        for i in range(self.deps_list.count()):
            list_item = self.deps_list.item(i)
            dep = list_item.data(Qt.UserRole) if list_item else None
            if not isinstance(dep, DepItem) or not dep.installed:
                continue
            is_checked = bool(list_item.data(Qt.UserRole + 2)) and list_item.checkState() == Qt.Checked
            if not is_checked:
                # Se excluyen los módulos reales (ej. Pillow → PIL), no el nombre del paquete
                excluded.extend(dep.modules)
        return excluded

    def _validate(self):
        ok = True
        script = self.script_input.text().strip()
        self.script_input.setProperty("invalid", "true" if not script or not os.path.isfile(script) else "false")
        self.script_input.style().unpolish(self.script_input)
        self.script_input.style().polish(self.script_input)
        if not script or not os.path.isfile(script):
            ok = False
        if not self.project_python or not os.path.isfile(self.project_python):
            self._set_python_badge("py_invalid" if self.python_path_input.text() else "py_none")
            ok = False
        if not ok:
            self._set_status(tr("status.fix_fields"))
        return ok

    def generate_command(self):
        """Arma comando y .spec desde el BuildConfig actual. Devuelve (cmd, cfg) o ([], None)."""
        cfg = self.collect_config()
        if not cfg.script or not os.path.exists(cfg.script):
            QMessageBox.warning(self, tr("msg.error_title"), tr("msg.no_script"))
            return [], None
        if not cfg.python_path or not os.path.isfile(cfg.python_path):
            QMessageBox.critical(self, tr("msg.error_title"), tr("msg.no_python"))
            return [], None
        # Se usa el resultado del chequeo asíncrono (no se bloquea la interfaz)
        if self._pyinstaller_ok is False:
            r = QMessageBox.question(self, tr("msg.pyi_missing_title", tool=cfg.backend_label),
                                     tr("msg.pyi_missing_body", tool=cfg.backend_label, package=cfg.backend),
                                     QMessageBox.Yes | QMessageBox.No)
            if r == QMessageBox.No:
                return [], None
        try:
            cmd, notes = build_command(cfg)
        except ValueError as e:
            QMessageBox.warning(self, tr("msg.flags_title"), str(e))
            return [], None

        for note in notes:
            self.log_output.append(note)
        self.cmd_output.setText(command_to_str(cmd))
        self.spec_output.setText(tr("spec.nuitka_na") if cfg.is_nuitka else build_spec(cfg))
        script = os.path.basename(cfg.script)
        if cfg.is_nuitka:
            mode = "--onefile" if cfg.onefile else "--standalone"
            install = f"pip install nuitka ordered-set zstandard\npython -m nuitka {mode} {script}\n"
        else:
            install = f"pip install pyinstaller\npyinstaller --noconfirm --clean {script}\n"
        self.install_script_output.setText(f"#!/bin/bash\n# {tr('script.comment')}\n{install}")
        return cmd, cfg

    def run_build(self):
        if not self._validate():
            return
        cmd, cfg = self.generate_command()
        if not cmd:
            return

        if cfg.make_appimage and not find_tool("appimagetool"):
            self.log_output.append(tr("log.no_appimagetool"))
        if cfg.nsis and sys.platform == "win32" and not cfg.make_nsis:
            self.log_output.append(tr("log.nsis_needs_onedir"))
        if cfg.make_nsis and not find_tool("makensis"):
            self.log_output.append(tr("log.no_makensis"))

        self.log_output.clear()
        # El comando siempre se re-genera aquí para que el log refleje exactamente lo que se ejecuta
        self.log_output.append(tr("log.build_header", version=APP_VERSION))
        self.log_output.append(tr("log.command", cmd=command_to_str(cmd)))
        self.tabs.setCurrentWidget(self.log_tab)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_cancel.setVisible(True)
        self.btn_build.setEnabled(False)
        self._set_status(tr("status.building"))
        self._build_started = time.monotonic()
        self.elapsed_label.setText(tr("badge.elapsed", t="0s"))
        self._elapsed_timer.start()

        # La limpieza de salidas previas, PyInstaller, instaladores y el movido
        # a la carpeta de salida corren en el hilo del worker (BuildRunner)
        self._last_build_cfg = cfg
        self.worker = BuildWorker(cfg, cmd, recreate_venv=self.isolated_venv_cb.isChecked() and self.recreate_venv_cb.isChecked())
        self.recreate_venv_cb.setChecked(False)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self._on_build_done)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.status_signal.connect(self._set_status)
        self.worker.start()

    def cancel_build(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.append_log(tr("log.cancel_requested"))
            self.btn_cancel.setEnabled(False)   # _on_build_done restablece los botones
        else:
            self.btn_build.setEnabled(True)
            self.btn_cancel.setVisible(False)

    def append_log(self, text):
        self.log_output.append(text)
        self.log_output.moveCursor(QTextCursor.End)

    def _on_build_done(self, success, msg):
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.btn_build.setEnabled(True)
        self._elapsed_timer.stop()
        if self._build_started is not None:
            took = _fmt_duration(time.monotonic() - self._build_started)
            self._build_started = None
            msg = f"{msg}  ({took})"
            self.elapsed_label.setText(tr("badge.elapsed", t=took))
            self.append_log(tr("log.total_time", t=took))
        self._notify_done(success, msg)

        # Análisis del resultado (warn-*.txt, tamaño, diagnóstico) en segundo plano
        if getattr(self, "_last_build_cfg", None) is not None:
            self.analysis_tab.start_post_build(self._last_build_cfg, self.log_output.toPlainText(), success)

        self._set_status(msg)
        if success:
            QMessageBox.information(self, tr("notify.done"), msg)
        else:
            QMessageBox.critical(self, tr("notify.failed"), msg)

    def show_full_spec(self):
        if self.generate_command()[0]:
            self.tabs.setCurrentWidget(self.cmd_tab)

    def save_spec_file(self):
        name = self.name_input.text().strip() or "app"
        path, _ = QFileDialog.getSaveFileName(self, tr("btn.save_spec"), f"{name}.spec", tr("filter.spec"))
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.spec_output.toPlainText())
            QMessageBox.information(self, tr("msg.saved_title"), tr("msg.saved_body", path=path))

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("btn.save_log"), f"build_log_{datetime.now():%Y%m%d_%H%M%S}.txt",
                                              tr("filter.text"))
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.log_output.toPlainText())
            QMessageBox.information(self, tr("msg.saved_title"), tr("msg.saved_body", path=path))

    def open_dist_folder(self):
        dp = self.dist_path_input.text().strip()
        d = dp if dp else (os.path.join(self.current_workspace, "dist") if self.current_workspace else "")
        if d and os.path.isdir(d):
            if sys.platform.startswith('linux'):
                subprocess.Popen(["xdg-open", d])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                os.startfile(d)
        else:
            QMessageBox.information(self, tr("msg.no_dist_title"), tr("msg.no_dist_body"))

    def save_profile(self):
        if not self.current_workspace:
            QMessageBox.warning(self, tr("msg.no_project_title"), tr("msg.no_project_body"))
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("action.save_profile"),
                                              f"{Path(self.current_workspace).name}_profile.json", tr("filter.json"))
        if path:
            try:
                self.collect_config().save(path)
            except Exception as e:
                QMessageBox.critical(self, tr("msg.error_title"), tr("msg.profile_save_error", error=e))
                return
            self._set_status(tr("status.profile_saved", path=path))
            QMessageBox.information(self, tr("msg.saved_title"), tr("msg.saved_body", path=path))

    def load_profile(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, tr("action.load_profile"), "", tr("filter.json"))
        if not path:
            return
        try:
            cfg = BuildConfig.load(path)
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error_title"), tr("msg.profile_load_error", error=e))
            return

        self._loading_profile = True
        self.deps_list.clear()
        self.dep_items.clear()
        self.apply_config(cfg)
        self._loading_profile = False
        if self.current_workspace:
            self.scan_workspace(self.current_workspace, auto_select_script=False)
        self._set_status(tr("status.profile_loaded", path=path))
        QMessageBox.information(self, tr("msg.profile_loaded_title"), tr("msg.profile_loaded_body", path=path))

    def reset_fields(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait()

        self.current_workspace = ""
        self.dep_items.clear()
        self.project_python = None

        for w in [self.workspace_input, self.script_input, self.name_input,
                  self.icon_input, self.version_file_input, self.appimage_icon_input,
                  self.extra_flags_input, self.dist_path_input, self.build_path_input,
                  self.venv_path_input, self.add_data_input, self.hidden_import_input,
                  self.exclude_module_input]:
            w.clear()

        self.python_path_input.clear()
        self._set_python_badge("py_none")

        self.cmd_output.clear()
        self.log_output.clear()
        self.spec_output.clear()
        self.install_script_output.clear()

        self.deps_list.clear()
        self.add_data_list.clear()
        self.hidden_import_list.clear()
        self._add_suggested_hidden()
        self.exclude_module_list.clear()
        self.dep_count_label.setText("")

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_build.setEnabled(True)

        self.mode_combo.setEnabled(True)
        set_help(self.mode_combo, "mode")
        self.mode_combo.setCurrentIndex(0)
        self.previous_mode_idx = 0

        self.noconsole.setChecked(True)
        self.debug_cb.setChecked(False)
        self.clean.setChecked(True)
        self.strip_cb.setChecked(False)
        self.noupx_cb.setChecked(False)
        self.bootloader_ignore_cb.setChecked(False)
        self.optimize_cb.setChecked(False)
        self.uac_admin_cb.setChecked(False)
        self.create_appimage_cb.setChecked(False)
        self.runtime_tmpdir_cb.setChecked(False)
        self.runtime_tmpdir_input.clear()
        self.runtime_tmpdir_input.setEnabled(False)
        self.nsis_cb.setChecked(False)
        self.dest_folder_input.clear()
        self.collect_list.clear()
        self.isolated_venv_cb.setChecked(False)
        self._set_backend("pyinstaller")
        self.distribution_tab.reset()

        self._select_platform("linux" if sys.platform.startswith("linux") else "windows" if sys.platform == "win32" else "macos")
        self.update_pyinstaller_version()
        self._set_status(tr("status.reset_done"))

    def _get_packages_from_req(self):
        if not self.current_workspace:
            return []

        req = os.path.join(self.current_workspace, "requirements.txt")
        if not os.path.exists(req):
            return []

        packages = []
        with open(req, 'r', encoding='utf-8') as f:
            for ln in f:
                r = parse_requirement_full(ln)
                if r:
                    packages.append(r[2])
        return packages

    def _get_missing_packages(self):
        missing = []
        for i in range(self.deps_list.count()):
            it = self.deps_list.item(i)
            dep = it.data(Qt.UserRole) if it else None
            if dep and isinstance(dep, DepItem) and not dep.installed:
                pkg = dep.pkg_name
                if dep.req_spec:
                    pkg += dep.req_spec
                missing.append(pkg)
        return missing

    def _get_checked_packages(self):
        result = []
        for i in range(self.deps_list.count()):
            it = self.deps_list.item(i)
            if not it or not bool(it.data(Qt.UserRole + 2)):
                continue
            if it.checkState() != Qt.Checked:
                continue
            dep = it.data(Qt.UserRole)
            if dep and isinstance(dep, DepItem):
                pkg = dep.pkg_name
                if dep.req_spec:
                    pkg += dep.req_spec
                result.append(pkg)
        return result

    def _start_install(self, packages, upgrade=False):
        if not packages:
            QMessageBox.information(self, tr("msg.no_packages_title"), tr("msg.no_packages_body"))
            return
        if not self.project_python:
            QMessageBox.warning(self, tr("msg.error_title"), tr("msg.no_python"))
            return
        if self._install_worker and self._install_worker.isRunning():
            QMessageBox.information(self, tr("msg.installing_title"), tr("msg.installing_body"))
            return

        items = "\n".join(f"  • {p}" for p in packages[:12])
        if len(packages) > 12:
            items += "\n" + tr("msg.and_more", n=len(packages) - 12)
        reply = QMessageBox.question(
            self, tr("msg.upgrade_title" if upgrade else "msg.install_title"),
            tr("msg.upgrade_body" if upgrade else "msg.install_body", n=len(packages), items=items,
               python=self.project_python),
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self.tabs.setCurrentWidget(self.log_tab)
        self.log_output.append(tr("log.pip_upgrading" if upgrade else "log.pip_installing", n=len(packages)))
        self._install_progress.setRange(0, len(packages))
        self._install_progress.setValue(0)
        self._install_progress.setVisible(True)
        self._btn_cancel_install.setVisible(True)
        self._set_status(tr("status.installing", n=len(packages)))

        self._install_worker = InstallWorker(packages, self.project_python, upgrade)
        self._install_worker.log_signal.connect(self.append_log)
        self._install_worker.finished_signal.connect(self._on_install_done)
        self._install_worker.progress_signal.connect(lambda cur, total: self._install_progress.setValue(cur))
        self._install_worker.start()

    def _install_selected_deps(self):
        self._start_install(self._get_checked_packages())

    def _install_missing_deps(self):
        self._start_install(self._get_missing_packages())

    def _install_all_deps(self):
        self._start_install(self._get_packages_from_req())

    def _upgrade_all_deps(self):
        self._start_install(self._get_packages_from_req(), upgrade=True)

    def _cancel_install(self):
        if self._install_worker and self._install_worker.isRunning():
            self._install_worker.cancel()
        self._btn_cancel_install.setVisible(False)

    def _on_install_done(self, success, msg):
        self._install_progress.setVisible(False)
        self._btn_cancel_install.setVisible(False)
        self._set_status(msg)
        if success:
            QMessageBox.information(self, tr("msg.install_done_title"), msg)
        else:
            QMessageBox.warning(self, tr("msg.install_errors_title"), msg)
        if self.current_workspace:
            self.scan_workspace(self.current_workspace, auto_select_script=False)

    def _set_python_badge(self, kind_key):
        kinds = {"py_venv": "ok", "py_system": "warn", "py_manual": "info", "py_invalid": "error", "py_none": "neutral"}
        set_badge(self.python_badge, tr(f"badge.{kind_key}"), kinds[kind_key])

    def _deps_info_item(self, text, kind="hint"):
        """Fila informativa (no es una dependencia) en la lista de dependencias."""
        it = QListWidgetItem(text)
        it.setForeground(QColor(THEME["error"] if kind == "error" else THEME["text_secondary"]))
        it.setData(Qt.UserRole + 3, "info")   # marcador: fila informativa, se reemplaza al llegar resultados
        it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable)
        self.deps_list.addItem(it)
        return it

    def _dep_list_item(self, dep, state, checked):
        color_key, prefix, tip_key = self._DEP_STATES[state]
        item = QListWidgetItem(f"[{prefix}]  {dep.display_label}")
        if dep.installed or state == "manual":
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            item.setData(Qt.UserRole + 2, True)   # marcador checkable
        else:
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
        item.setForeground(QColor(THEME[color_key]))
        tip = tr(tip_key, pkg=dep.pkg_name, version=dep.installed_version or "?", spec=dep.req_spec or "-")
        if dep.modules and dep.import_name != dep.pkg_name:
            tip += "\n" + tr("tip.dep_imports_as", modules=", ".join(dep.modules))
        item.setToolTip(tip)
        item.setData(Qt.UserRole, dep)
        return item

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            r = QMessageBox.question(self, tr("msg.build_running_title"), tr("msg.build_running_body"),
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(10000)

        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait()
        if self._install_worker and self._install_worker.isRunning():
            self._install_worker.cancel()
            self._install_worker.wait()
        # Estos workers solo lanzan subprocesos cortos con timeout: se espera a que
        # terminen en lugar de usar terminate(), que puede dejar el proceso inestable.
        for th in (self._python_locator, self._pyinstaller_chk, *self._stale_checks):
            if th and th.isRunning() and not th.wait(5000):
                th.terminate()

        self.analysis_tab.shutdown()
        self.save_current_settings()
        event.accept()

