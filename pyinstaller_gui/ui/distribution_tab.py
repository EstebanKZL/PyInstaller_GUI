"""Pestaña Distribución: información de versión, íconos, instaladores, firma de código,
paquete de release y generador de workflow de GitHub Actions.

Lee y escribe su parte del BuildConfig con fill_config() / apply_config().
"""

import os
import sys
import tempfile

from ..core.ci_workflow import generate_ci_files, workflow_paths, write_ci_files
from ..core.config import BuildConfig
from ..core.icons import ICNS_TYPES, ICO_SIZES, build_icns, build_ico
from ..core.installers import find_license
from ..core.process import find_tool
from ..core.signing import DEFAULT_PASSWORD_ENV, find_signtool
from ..i18n import tr
from ..qt_compat import (
    QCheckBox, QColor, QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QImage, QLabel, QLineEdit,
    QMessageBox, QPainter, QScrollArea, QVBoxLayout, QWidget, Qt,
)
from .components import make_badge, make_button, make_hint, make_label, set_help, set_label_role
from .theme import SP

SIGN_MODES = ("auto", "thumbprint", "pfx")


def _form(rows, label_width=150):
    """Formulario con labels alineados a la derecha (regla de layout de la guía)."""
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


def _tool_status(found, name, url):
    """Fila con badge de estado de una herramienta externa (instalada / no instalada)."""
    row = QHBoxLayout()
    row.setSpacing(SP["sm"])
    row.addWidget(make_badge(tr("dist.tool_found", tool=name) if found else tr("dist.tool_missing", tool=name),
                             "ok" if found else "warn"))
    if not found:
        link = make_label(url, "lblHint")
        link.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(link)
    row.addStretch(1)
    return row


def _line(placeholder_key, help_key):
    le = QLineEdit()
    le.setPlaceholderText(tr(placeholder_key))
    set_help(le, help_key)
    return le


class DistributionTab(QScrollArea):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setObjectName("tabScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        w = QWidget()
        w.setObjectName("tabContent")
        v = QVBoxLayout(w)
        v.setContentsMargins(SP["lg"], SP["sm"], SP["lg"], SP["lg"])
        v.setSpacing(SP["sm"])
        v.addWidget(self._build_version_group())
        v.addWidget(self._build_icons_group())
        v.addWidget(self._build_installers_group())
        v.addWidget(self._build_signing_group())
        v.addWidget(self._build_release_group())
        v.addWidget(self._build_ci_group())
        v.addStretch(1)
        self.setWidget(w)
        self.reset()

    # ── Secciones ───────────────────────────────────────────────────────
    def _build_version_group(self):
        grp = QGroupBox(tr("dist.version_section"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        self.vi_cb = QCheckBox(tr("dist.vi_enable"))
        set_help(self.vi_cb, "vi_enable")
        g.addWidget(self.vi_cb)
        self.app_version = _line("dist.ph_version", "vi_version")
        self.company = _line("dist.ph_company", "vi_company")
        self.product = _line("dist.ph_product", "vi_product")
        self.description = _line("dist.ph_description", "vi_description")
        self.copyright = _line("dist.ph_copyright", "vi_copyright")
        g.addLayout(_form([(tr("dist.version"), self.app_version), (tr("dist.company"), self.company),
                           (tr("dist.product"), self.product), (tr("dist.description"), self.description),
                           (tr("dist.copyright"), self.copyright)]))
        g.addWidget(make_hint(tr("dist.version_hint")))
        return grp

    def _build_icons_group(self):
        grp = QGroupBox(tr("dist.icons_section"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        g.addWidget(make_hint(tr("dist.icons_hint", sizes=", ".join(map(str, ICO_SIZES)))))
        row = QHBoxLayout()
        row.setSpacing(SP["sm"])
        row.addWidget(make_button(tr("dist.make_icons"), "btnSecondary", lambda: self.convert_icon(), "make_icons"))
        self.icon_result = make_label("", "lblHint", wrap=True)
        row.addWidget(self.icon_result, 1)
        g.addLayout(row)
        return grp

    def _build_installers_group(self):
        grp = QGroupBox(tr("dist.installers_section"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        self.inno_cb = QCheckBox(tr("dist.inno"))
        set_help(self.inno_cb, "inno")
        g.addWidget(self.inno_cb)
        g.addLayout(_tool_status(bool(find_tool("ISCC")), "Inno Setup 6", "https://jrsoftware.org/isdl.php"))
        g.addLayout(_tool_status(bool(find_tool("makensis")), "NSIS", "https://nsis.sourceforge.io/Download"))
        g.addWidget(make_hint(tr("dist.installers_hint")))
        self.license_label = make_hint("")
        g.addWidget(self.license_label)
        return grp

    def _build_signing_group(self):
        grp = QGroupBox(tr("dist.signing_section"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        self.sign_cb = QCheckBox(tr("dist.sign"))
        set_help(self.sign_cb, "sign")
        g.addWidget(self.sign_cb)
        self.sign_mode = QComboBox()
        for key in SIGN_MODES:
            self.sign_mode.addItem(tr(f"dist.sign_mode_{key}"), key)
        set_help(self.sign_mode, "sign_mode")
        self.sign_cert = _line("dist.ph_cert", "sign_cert")
        cert_row = QHBoxLayout()
        cert_row.setSpacing(SP["sm"])
        cert_row.addWidget(self.sign_cert, 1)
        cert_row.addWidget(make_button(tr("btn.browse"), None, self._browse_pfx, "browse_pfx"))
        self.sign_password_env = _line("dist.ph_password_env", "sign_password_env")
        self.sign_timestamp = _line("dist.ph_timestamp", "sign_timestamp")
        g.addLayout(_form([(tr("dist.certificate"), self.sign_mode), (tr("dist.cert_value"), cert_row),
                           (tr("dist.password_env"), self.sign_password_env),
                           (tr("dist.timestamp"), self.sign_timestamp)]))
        g.addWidget(make_hint(tr("dist.signing_hint")))
        if sys.platform == "win32":
            g.addLayout(_tool_status(bool(find_signtool()), "signtool",
                                     "https://developer.microsoft.com/windows/downloads/windows-sdk/"))
        elif sys.platform == "darwin":
            g.addLayout(_tool_status(bool(find_tool("codesign")), "codesign", "Xcode Command Line Tools"))
        return grp

    def _build_release_group(self):
        grp = QGroupBox(tr("dist.release_section"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        self.zip_cb = QCheckBox(tr("dist.zip"))
        set_help(self.zip_cb, "zip")
        self.sums_cb = QCheckBox(tr("dist.sums"))
        set_help(self.sums_cb, "sums")
        g.addWidget(self.zip_cb)
        g.addWidget(self.sums_cb)
        return grp

    def _build_ci_group(self):
        grp = QGroupBox(tr("dist.ci_section"))
        g = QVBoxLayout(grp)
        g.setSpacing(SP["sm"])
        g.addWidget(make_hint(tr("dist.ci_hint")))
        row = QHBoxLayout()
        row.setSpacing(SP["sm"])
        self.ci_python = QComboBox()
        self.ci_python.addItems(["3.10", "3.11", "3.12", "3.13"])
        self.ci_python.setCurrentText("3.12")
        set_help(self.ci_python, "ci_python")
        row.addWidget(QLabel(tr("dist.ci_python")))
        row.addWidget(self.ci_python)
        row.addStretch(1)
        row.addWidget(make_button(tr("dist.generate_workflow"), "btnPrimary", self.generate_workflow, "generate_workflow"))
        g.addLayout(row)
        self.ci_result = make_label("", "lblHint", wrap=True)
        self.ci_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        g.addWidget(self.ci_result)
        return grp

    # ── BuildConfig ─────────────────────────────────────────────────────
    def fill_config(self, cfg):
        cfg.version_info = self.vi_cb.isChecked()
        cfg.app_version = self.app_version.text().strip() or "1.0.0"
        cfg.company = self.company.text().strip()
        cfg.product = self.product.text().strip()
        cfg.description = self.description.text().strip()
        cfg.copyright = self.copyright.text().strip()
        cfg.inno = self.inno_cb.isChecked()
        cfg.sign = self.sign_cb.isChecked()
        cfg.sign_mode = self.sign_mode.currentData() or "auto"
        cfg.sign_cert = self.sign_cert.text().strip()
        cfg.sign_password_env = self.sign_password_env.text().strip() or DEFAULT_PASSWORD_ENV
        cfg.sign_timestamp = self.sign_timestamp.text().strip()
        cfg.make_zip = self.zip_cb.isChecked()
        cfg.make_checksums = self.sums_cb.isChecked()
        return cfg

    def apply_config(self, cfg):
        self.vi_cb.setChecked(cfg.version_info)
        self.app_version.setText(cfg.app_version)
        self.company.setText(cfg.company)
        self.product.setText(cfg.product)
        self.description.setText(cfg.description)
        self.copyright.setText(cfg.copyright)
        self.inno_cb.setChecked(cfg.inno and self.inno_cb.isEnabled())
        self.sign_cb.setChecked(cfg.sign)
        idx = self.sign_mode.findData(cfg.sign_mode)
        self.sign_mode.setCurrentIndex(max(idx, 0))
        self.sign_cert.setText(cfg.sign_cert)
        self.sign_password_env.setText(cfg.sign_password_env)
        self.sign_timestamp.setText(cfg.sign_timestamp)
        self.zip_cb.setChecked(cfg.make_zip)
        self.sums_cb.setChecked(cfg.make_checksums)
        self.refresh_project_info()

    def reset(self):
        self.apply_config(BuildConfig())
        self.ci_result.setText("")
        self.icon_result.setText("")

    def refresh_project_info(self):
        lic = find_license(self.owner.current_workspace) if hasattr(self.owner, "current_workspace") else ""
        self.license_label.setText(tr("dist.license_found", path=lic) if lic else tr("dist.license_missing"))

    # ── Acciones ────────────────────────────────────────────────────────
    def _browse_pfx(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dist.certificate"), "", tr("filter.certificates"))
        if path:
            self.sign_cert.setText(path)
            self.sign_mode.setCurrentIndex(self.sign_mode.findData("pfx"))

    @staticmethod
    def _png_sizes(src, sizes):
        """Redimensiona src (QImage) a cada tamaño (cuadrado, centrado) y devuelve {tamaño: bytes PNG}."""
        out = {}
        tmp = tempfile.mkdtemp(prefix="pyi_gui_icon_")
        for s in sizes:
            scaled = src.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            canvas = QImage(s, s, QImage.Format_ARGB32)
            canvas.fill(QColor(0, 0, 0, 0))   # fondo transparente
            p = QPainter(canvas)
            p.drawImage((s - scaled.width()) // 2, (s - scaled.height()) // 2, scaled)
            p.end()
            path = os.path.join(tmp, f"{s}.png")
            canvas.save(path, "PNG")
            with open(path, "rb") as f:
                out[s] = f.read()
        return out

    def convert_icon(self, png_path=None):
        start = self.owner.current_workspace or ""
        if not png_path:
            png_path, _ = QFileDialog.getOpenFileName(self, tr("dist.png_source"), start, tr("filter.png"))
        if not png_path:
            return None
        src = QImage(png_path)
        if src.isNull():
            QMessageBox.warning(self, tr("dist.icons_section"), tr("dist.png_unreadable"))
            return None
        base = os.path.splitext(png_path)[0]
        ico, icns = base + ".ico", base + ".icns"
        existing = [p for p in (ico, icns) if os.path.exists(p)]
        if existing:
            r = QMessageBox.question(self, tr("dist.replace_title"), tr("dist.replace_body", files="\n".join(existing)),
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return None
        pngs = self._png_sizes(src, sorted(set(ICO_SIZES) | set(ICNS_TYPES)))
        with open(ico, "wb") as f:
            f.write(build_ico({s: pngs[s] for s in ICO_SIZES}))
        with open(icns, "wb") as f:
            f.write(build_icns({s: pngs[s] for s in ICNS_TYPES}))
        self.owner.icon_input.setText(ico)
        if not self.owner.appimage_icon_input.text().strip():
            self.owner.appimage_icon_input.setText(png_path)
        text = tr("dist.icons_done", ico=os.path.basename(ico), icns=os.path.basename(icns))
        if src.width() < 256:
            set_label_role(self.icon_result, text + " " + tr("dist.icons_small"), "lblWarn")
        else:
            set_label_role(self.icon_result, text, "lblOk")
        return ico, icns

    def generate_workflow(self):
        cfg = self.owner.collect_config()
        try:
            files, warnings = generate_ci_files(cfg, self.ci_python.currentText())
        except ValueError as e:
            QMessageBox.warning(self, "GitHub Actions", str(e))
            return None
        existing = [rel for rel in files if os.path.exists(os.path.join(cfg.workspace, rel))]
        if existing:
            r = QMessageBox.question(self, tr("dist.replace_title"), tr("dist.replace_body", files="\n".join(existing)),
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return None
        written = write_ci_files(cfg.workspace, files)
        paths = workflow_paths(cfg)
        text = tr("dist.ci_done", files="\n  ".join(sorted(files)), version=cfg.app_version)
        if warnings:
            text += "\n\n" + tr("dist.ci_warnings", items="\n  • ".join(warnings))
        set_label_role(self.ci_result, text, "lblWarn" if warnings else "lblOk")
        self.owner.append_log(tr("log.ci_generated", path=paths["workflow"]))
        for w in warnings:
            self.owner.append_log(tr("log.ci_warning", text=w))
        return written
