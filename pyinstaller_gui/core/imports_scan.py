"""Análisis estático (AST) de los imports reales del proyecto.

Compara lo que el código importa con lo que declara requirements.txt y detecta
imports dinámicos (importlib.import_module("x")), que PyInstaller no ve.
"""

import ast
import os
import sys
import sysconfig
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .knowledge import hints_for
from .packages import BUILD_TOOLS, pick_import_name

SKIP_DIRS = {"venv", ".venv", "env", ".env", "virtualenv", ".pipenv", "build", "dist", "__pycache__",
             ".git", ".hg", ".svn", "node_modules", "site-packages", ".tox", ".nox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", ".pyinstaller_gui", ".idea", ".vscode"}


def stdlib_modules():
    names = set(sys.builtin_module_names)
    if hasattr(sys, "stdlib_module_names"):   # Python 3.10+
        return names | set(sys.stdlib_module_names)
    stdlib = sysconfig.get_paths().get("stdlib", "")
    for entry in (os.listdir(stdlib) if stdlib and os.path.isdir(stdlib) else []):
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isdir(os.path.join(stdlib, entry)) and entry != "site-packages":
            names.add(entry)
    return names


# Los tests no forman parte del ejecutable: sus imports (pytest...) no son dependencias de runtime
TEST_DIRS = {"tests", "test", "testing"}


def _is_test_file(name):
    return name == "conftest.py" or name.startswith("test_") or name.endswith("_test.py")


def iter_py_files(root, include_tests=False):
    for dirpath, dirnames, filenames in os.walk(root):
        # No entrar en entornos virtuales ni carpetas de build/caché
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")
                       and (include_tests or d not in TEST_DIRS)
                       and not os.path.isfile(os.path.join(dirpath, d, "pyvenv.cfg"))]
        for f in filenames:
            if f.endswith((".py", ".pyw")) and (include_tests or not _is_test_file(f)):
                yield os.path.join(dirpath, f)


@dataclass
class ImportScan:
    imports: Dict[str, Set[str]] = field(default_factory=dict)    # módulo (con puntos) → archivos
    dynamic: Dict[str, Set[str]] = field(default_factory=dict)    # import_module("x") → archivos
    local_modules: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    files: int = 0

    @property
    def top_level(self):
        return {m.split(".")[0] for m in self.imports}


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def scan_imports(root):
    scan = ImportScan()
    for path in iter_py_files(root):
        rel = os.path.relpath(path, root)
        parts = rel.replace("\\", "/").split("/")
        scan.local_modules.add(os.path.splitext(parts[-1])[0])
        for d in parts[:-1]:
            scan.local_modules.add(d)
        scan.files += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                tree = ast.parse(f.read(), filename=rel)
        except (SyntaxError, ValueError) as e:
            scan.errors.append(f"{rel}: {e}")
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names if a.name != "*"]
            elif isinstance(node, ast.Call) and node.args:
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
                if fname in ("import_module", "__import__"):
                    target = _const_str(node.args[0])
                    if target and not target.startswith("."):
                        scan.dynamic.setdefault(target, set()).add(rel)
            for n in names:
                scan.imports.setdefault(n, set()).add(rel)
    return scan


@dataclass
class ImportReport:
    missing: List[dict] = field(default_factory=list)     # {module, files, dists, installed}
    unused: List[str] = field(default_factory=list)       # paquetes de requirements sin import visible
    dynamic: List[dict] = field(default_factory=list)     # {module, files}
    hints: List[dict] = field(default_factory=list)       # {module, hidden, collect_all, collect_data, note}
    errors: List[str] = field(default_factory=list)
    files: int = 0
    third_party: List[str] = field(default_factory=list)


def analyze(scan, requirements, pkg_info, module_info):
    """requirements: [(paquete, spec, línea)] ; pkg_info: resultado de query_packages ;
    module_info: resultado de query_modules → {módulo: {importable, dists}}."""
    std = stdlib_modules()
    ignore = std | scan.local_modules | {"__future__", "__main__"}
    third = sorted(m for m in scan.top_level if m not in ignore)

    provided = {}   # módulo → paquete de requirements que lo provee
    for pkg, _spec, _line in requirements:
        mods = (pkg_info.get(pkg) or {}).get("modules") or [pick_import_name(pkg, [])]
        for m in mods:
            provided[m] = pkg

    report = ImportReport(errors=list(scan.errors), files=scan.files, third_party=third)
    for mod in third:
        if mod in provided:
            continue
        info = module_info.get(mod) or {}
        files = sorted(set().union(*(scan.imports[n] for n in scan.imports if n.split(".")[0] == mod)))
        report.missing.append({"module": mod, "files": files, "dists": info.get("dists") or [],
                               "installed": bool(info.get("importable"))})

    used_pkgs = {provided[m] for m in third if m in provided}
    for pkg, _spec, _line in requirements:
        if pkg not in used_pkgs and pkg.lower() not in BUILD_TOOLS and not pkg.lower().startswith("pyinstaller"):
            report.unused.append(pkg)

    for mod, files in sorted(scan.dynamic.items()):
        if mod.split(".")[0] not in std:
            report.dynamic.append({"module": mod, "files": sorted(files)})

    for key, entry in hints_for(list(scan.imports) + list(scan.dynamic)):
        report.hints.append({"module": key, "hidden": entry.get("hidden", []),
                             "collect_all": entry.get("collect_all", []),
                             "collect_data": entry.get("collect_data", []), "note": entry.get("note", "")})
    return report
