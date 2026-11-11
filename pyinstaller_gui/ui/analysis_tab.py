"""Pestaña Análisis: imports del proyecto (antes del build) y resultados del build
(módulos faltantes, diagnóstico del log, tamaño por paquete y prueba del ejecutable).

Las sugerencias se aplican sobre la ventana principal (owner) mediante:
add_hidden_import_name(), add_collect_entry() y add_requirement_lines().
"""

import os

from ..core.postbuild import diagnose_log, human_size
from ..i18n import tr
from ..qt_compat import (
    QColor, QGroupBox, QHBoxLayout, QListWidget, QListWidgetItem, QScrollArea, QSpinBox, QVBoxLayout, QWidget, Qt,
)
from .components import (
    make_badge, make_button, make_hint, make_label, make_section, set_badge, set_help,
    set_label_role,
)
from .theme import SP, THEME
from ..workers import ImportAnalysisWorker, PostBuildWorker, SmokeTestWorker

ACTIONS = Qt.UserRole          # lista de [tipo, valor] que aplica el ítem
CHECKABLE = Qt.UserRole + 2    # marcador de ítem aplicable (compatible PySide2/6)


def diagnostic_text(d):
    """Mensaje traducido de un diagnóstico del log (core.postbuild.diagnose_log)."""
    return tr(f"diag.{d['key']}", x=d["x"])


class AnalysisTab(QScrollArea):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self._import_worker = None
        self._post_worker = None
        self._smoke_worker = None
        self._last_exe = ""
        self.setObjectName("tabScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # las listas tienen su propio scroll
        content = QWidget()
        content.setObjectName("tabContent")
        v = QVBoxLayout(content)
        v.setContentsMargins(SP["lg"], SP["sm"], SP["lg"], SP["lg"])
        v.setSpacing(SP["sm"])
        v.addWidget(self._build_imports_group())
        v.addWidget(self._build_post_group())
        v.addStretch(1)
        self.setWidget(content)

    # ── Construcción ────────────────────────────────────────────────────
    def _build_imports_group(self):
        grp = QGroupBox(tr("an.imports_section"))
        gv = QVBoxLayout(grp)
        gv.setSpacing(SP["sm"])
        gv.addWidget(make_hint(tr("an.imports_hint")))
        self.imports_list = QListWidget()
        self.imports_list.setMinimumHeight(170)
        gv.addWidget(self.imports_list)
        row = QHBoxLayout()
        row.setSpacing(SP["sm"])
        self.imports_summary = make_hint("")
        row.addWidget(self.imports_summary, 1)
        row.addWidget(make_button(tr("an.apply"), None, lambda: self._apply_checked(self.imports_list), "an_apply"))
        self.btn_analyze = make_button(tr("an.analyze"), "btnPrimary", self.run_import_analysis, "an_analyze")
        row.addWidget(self.btn_analyze)
        gv.addLayout(row)
        return grp

    def _build_post_group(self):
        grp = QGroupBox(tr("an.post_section"))
        gv = QVBoxLayout(grp)
        gv.setSpacing(SP["sm"])
        head = QHBoxLayout()
        head.setSpacing(SP["sm"])
        self.post_badge = make_badge(tr("an.no_build_badge"), "neutral")
        set_help(self.post_badge, "an_post_badge")
        self.post_summary = make_label(tr("an.no_build"), "lblHint", wrap=True)
        head.addWidget(self.post_badge, 0, Qt.AlignTop)
        head.addWidget(self.post_summary, 1)
        gv.addLayout(head)

        gv.addSpacing(SP["xs"])
        gv.addWidget(make_section(tr("an.missing_section")))
        gv.addWidget(make_hint(tr("an.missing_hint")))
        self.missing_list = QListWidget()
        self.missing_list.setMinimumHeight(120)
        gv.addWidget(self.missing_list)

        gv.addWidget(make_section(tr("an.diag_section")))
        self.diag_list = QListWidget()
        self.diag_list.setMinimumHeight(70)
        gv.addWidget(self.diag_list)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(make_button(tr("an.apply"), None, lambda: (self._apply_checked(self.missing_list),
                                                                 self._apply_checked(self.diag_list)), "an_apply"))
        gv.addLayout(row)

        gv.addWidget(make_section(tr("an.size_section")))
        gv.addWidget(make_hint(tr("an.size_hint")))
        self.size_list = QListWidget()
        self.size_list.setMinimumHeight(120)
        gv.addWidget(self.size_list)

        gv.addWidget(make_section(tr("an.smoke_section")))
        smoke = QHBoxLayout()
        smoke.setSpacing(SP["sm"])
        self.btn_smoke = make_button(tr("an.smoke"), "btnSecondary", self.run_smoke_test, "an_smoke")
        self.btn_smoke.setEnabled(False)
        self.smoke_seconds = QSpinBox()
        self.smoke_seconds.setRange(2, 120)
        self.smoke_seconds.setValue(8)
        self.smoke_seconds.setSuffix(" s")
        set_help(self.smoke_seconds, "an_smoke_seconds")
        self.smoke_result = make_label("", "lblHint", wrap=True)
        smoke.addWidget(self.btn_smoke)
        smoke.addWidget(self.smoke_seconds)
        smoke.addWidget(self.smoke_result, 1)
        gv.addLayout(smoke)
        gv.addWidget(make_hint(tr("an.smoke_hint")))
        return grp

    # ── Ítems ───────────────────────────────────────────────────────────
    @staticmethod
    def _add_item(lst, text, color_key, tip="", actions=None, checked=False):
        it = QListWidgetItem(text)
        it.setForeground(QColor(THEME[color_key]))
        if tip:
            it.setToolTip(tip)
        if actions:
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            it.setData(ACTIONS, [list(a) for a in actions])
            it.setData(CHECKABLE, True)
        lst.addItem(it)
        return it

    def _apply_checked(self, lst):
        applied = []
        for i in range(lst.count()):
            it = lst.item(i)
            if not bool(it.data(CHECKABLE)) or it.checkState() != Qt.Checked:
                continue
            reqs = []
            for kind, value in it.data(ACTIONS) or []:
                if kind == "requirement":
                    reqs.append(value)
                elif kind == "hidden_import":
                    if self.owner.add_hidden_import_name(value):
                        applied.append(f"--hidden-import={value}")
                elif self.owner.add_collect_entry(kind.replace("_", "-"), value):
                    applied.append(f"--{kind.replace('_', '-')}={value}")
            if reqs:
                applied += self.owner.add_requirement_lines(reqs)
            it.setCheckState(Qt.Unchecked)
        if applied:
            self.owner.append_log(tr("log.applied", items=", ".join(applied)))
            self.owner._set_status(tr("status.applied", n=len(applied)))
        else:
            self.owner._set_status(tr("status.nothing_applied"))

    # ── Análisis de imports ─────────────────────────────────────────────
    def run_import_analysis(self):
        ws, py = self.owner.current_workspace, self.owner.project_python
        if not ws or not py:
            self.imports_summary.setText(tr("an.need_project"))
            return
        if self._import_worker and self._import_worker.isRunning():
            return
        self.imports_list.clear()
        self.imports_summary.setText(tr("an.analyzing"))
        self.btn_analyze.setEnabled(False)
        self._import_worker = ImportAnalysisWorker(ws, py)
        self._import_worker.finished_signal.connect(self._on_import_report)
        self._import_worker.start()

    def _on_import_report(self, rep):
        self.btn_analyze.setEnabled(True)
        if isinstance(rep, str):
            self.imports_summary.setText(rep)
            return
        L = self.imports_list
        for m in rep.missing:
            files = ", ".join(m["files"][:3]) + (" …" if len(m["files"]) > 3 else "")
            if m["dists"]:
                dist = m["dists"][0]
                self._add_item(L, tr("an.item_missing_dist", module=m["module"], dist=dist), "error",
                               tr("an.tip_missing_dist", files=files, dist=dist), [("requirement", dist)], checked=True)
            else:
                state = tr("an.installed_no_dist") if m["installed"] else tr("an.not_installed")
                self._add_item(L, tr("an.item_missing", module=m["module"], state=state), "error",
                               tr("an.tip_missing", files=files))
        for d in rep.dynamic:
            self._add_item(L, tr("an.item_dynamic", module=d["module"]), "counter",
                           tr("an.tip_dynamic", module=d["module"], files=", ".join(d["files"])),
                           [("hidden_import", d["module"])], checked=True)
        for h in rep.hints:
            actions = ([("hidden_import", x) for x in h["hidden"]] + [("collect_all", x) for x in h["collect_all"]]
                       + [("collect_data", x) for x in h["collect_data"]])
            flags = ", ".join([f"--hidden-import={x}" for x in h["hidden"]] + [f"--collect-all={x}" for x in h["collect_all"]]
                              + [f"--collect-data={x}" for x in h["collect_data"]])
            self._add_item(L, tr("an.item_hint", module=h["module"], note=tr(f"kb.{h['module']}")), "ip", flags,
                           actions, checked=True)
        for pkg in rep.unused:
            self._add_item(L, tr("an.item_unused", pkg=pkg), "text_secondary", tr("an.tip_unused"))
        for e in rep.errors:
            self._add_item(L, tr("an.item_syntax", error=e), "counter")
        if L.count() == 0:
            self._add_item(L, tr("an.item_all_ok"), "ok")
        self.imports_summary.setText(tr("an.summary", files=rep.files, third=len(rep.third_party),
                                        missing=len(rep.missing), dynamic=len(rep.dynamic), hints=len(rep.hints)))

    # ── Post-build ──────────────────────────────────────────────────────
    def start_post_build(self, cfg, log_text, success):
        set_badge(self.post_badge, tr("an.analyzing_badge"), "info")
        self.post_summary.setText(tr("an.analyzing_build"))
        self._post_worker = PostBuildWorker(cfg, log_text, success)
        self._post_worker.finished_signal.connect(self._on_post_build)
        self._post_worker.start()

    def _on_post_build(self, r):
        for lst in (self.missing_list, self.diag_list, self.size_list):
            lst.clear()
        important = [m for m in r["missing"] if m.important]
        for m in r["missing"]:
            who = ", ".join(f"{os.path.basename(w)} ({'/'.join(k)})" for w, k in m.importers[:3])
            if m.important:
                self._add_item(self.missing_list, tr("an.item_warn_important", module=m.module, who=who), "error",
                               tr("an.tip_warn_important"), [("hidden_import", m.module)], checked=True)
            elif m.from_project:
                self._add_item(self.missing_list, tr("an.item_warn", module=m.module, who=who), "counter",
                               tr("an.tip_warn_project"), [("hidden_import", m.module)])
            else:
                self._add_item(self.missing_list, tr("an.item_warn", module=m.module, who=who), "text_secondary",
                               tr("an.tip_warn_library"))
        for d in r["diagnostics"]:
            self._add_item(self.diag_list, diagnostic_text(d), "counter", d["line"],
                           [d["action"]] if d["action"] else None, checked=bool(d["action"]))
        if not r["diagnostics"]:
            self._add_item(self.diag_list, tr("an.no_diagnostics"), "ok")
        total = sum(s for _, s in r["sizes"])
        for name, size in r["sizes"][:30]:
            pct = f"{100 * size / total:5.1f}%" if total else ""
            self._add_item(self.size_list, f"{human_size(size):>10}  {pct}   {name}", "text")

        self._last_exe = r["exe"]
        self.btn_smoke.setEnabled(bool(r["exe"]))
        if not r["success"]:
            set_badge(self.post_badge, tr("an.badge_failed"), "error")
        elif important:
            set_badge(self.post_badge, tr("an.badge_warnings"), "warn")
        else:
            set_badge(self.post_badge, tr("an.badge_ok"), "ok")
        parts = []
        if r["target"]:
            parts.append(tr("an.result", target=r["target"], size=human_size(total)))
        if important:
            parts.append(tr("an.important_missing", n=len(important)))
        if r["error"]:
            parts.append(tr("an.analysis_error", error=r["error"]))
        self.post_summary.setText("  ·  ".join(parts))
        if important or r["diagnostics"]:
            self.owner.append_log(tr("log.analysis_summary", n=len(important), d=len(r["diagnostics"])))

    # ── Prueba del ejecutable ───────────────────────────────────────────
    def run_smoke_test(self):
        if not self._last_exe or (self._smoke_worker and self._smoke_worker.isRunning()):
            return
        self.btn_smoke.setEnabled(False)
        set_label_role(self.smoke_result, tr("an.smoke_running", exe=os.path.basename(self._last_exe)), "lblHint")
        self._smoke_worker = SmokeTestWorker(self._last_exe, self.smoke_seconds.value())
        self._smoke_worker.finished_signal.connect(self._on_smoke)
        self._smoke_worker.start()

    def _on_smoke(self, r):
        self.btn_smoke.setEnabled(True)
        if r["status"] == "running":
            text, role = tr("an.smoke_ok_running", s=r["elapsed"]), "lblOk"
        elif r["status"] == "exited":
            text, role = tr("an.smoke_ok_exited", s=r["elapsed"]), "lblOk"
        elif r["status"] == "crashed":
            text, role = tr("an.smoke_crashed", code=r["code"], s=r["elapsed"]), "lblError"
        else:
            text, role = tr("an.smoke_error", detail=r["output"]), "lblError"
        set_label_role(self.smoke_result, text, role)
        self.owner.append_log(tr("log.smoke", text=text) if role == "lblOk" else tr("log.smoke_failed", text=text))
        if r["output"].strip():
            self.owner.append_log(r["output"].rstrip())
        if r["status"] == "crashed":
            # Lo que imprimió el ejecutable al caerse también se diagnostica
            self.start_post_build_diagnostics(r["output"])

    def start_post_build_diagnostics(self, text):
        found = diagnose_log(text)
        if found:
            self.diag_list.clear()
        for d in found:
            self._add_item(self.diag_list, diagnostic_text(d), "error", d["line"],
                           [d["action"]] if d["action"] else None, checked=bool(d["action"]))

    def shutdown(self):
        if self._smoke_worker and self._smoke_worker.isRunning():
            self._smoke_worker.cancel()
            self._smoke_worker.wait(5000)
        for th in (self._import_worker, self._post_worker):
            if th and th.isRunning():
                th.wait(5000)
