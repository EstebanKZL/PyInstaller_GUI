"""Generador de workflow de GitHub Actions: compila la app en Windows, Linux y macOS.

PyInstaller no hace cross-compile: cada sistema operativo tiene que compilar su propio
ejecutable. La forma práctica de obtener los tres es que GitHub los compile en sus
máquinas. Este módulo genera:
  - <app>.ci.spec: .spec portable (rutas relativas al proyecto, ícono según plataforma)
  - .github/workflows/build-<app>.yml: compila en los 3 sistemas y, al pushear un tag v*,
    publica un Release con los tres paquetes.
"""

import os

from .command import collect_all_packages
from .naming import artifact_app_name
from .outputs import safe_app_name
from .spec import generate_spec_content
from .version_info import generate_version_info
from ..i18n import tr

_WORKFLOW = """# Generado por PyInstaller GUI PRO Builder
# Compila __APP__ en Windows, Linux y macOS.
#   - Manual: pestaña Actions → "Build __APP__" → Run workflow
#   - Release: git tag v1.0.0 && git push --tags  → publica los 3 paquetes en GitHub Releases
#     con nombres <App>-<versión>-<sistema>-<arq>-portable y un SHA256SUMS.txt
name: Build __APP__

on:
  workflow_dispatch:
  push:
    tags: ["v*"]

jobs:
  build:
    name: Build (${{ matrix.os }})
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "__PYVER__"

      - name: Instalar dependencias
        run: |
          python -m pip install --upgrade pip
__REQS__          python -m pip install pyinstaller

      - name: Compilar con PyInstaller
        run: python -m PyInstaller --noconfirm --clean "__SPEC__"

      # Nombre: <App>-<versión>-<sistema>-<arq>-portable  (ej. MiApp-1.0.0-win-x64-portable.zip)
      - name: Empaquetar
        shell: bash
        run: |
          VER="dev"
          if [ "$GITHUB_REF_TYPE" = "tag" ]; then VER="${GITHUB_REF_NAME#v}"; fi
          case "$RUNNER_OS" in Windows) OS=win ;; Linux) OS=linux ;; *) OS=macos ;; esac
          case "$RUNNER_ARCH" in
            X86)   if [ "$OS" = win ]; then ARCH=x86; else ARCH=i686; fi ;;
            ARM64) if [ "$OS" = linux ]; then ARCH=aarch64; else ARCH=arm64; fi ;;
            *)     if [ "$OS" = win ]; then ARCH=x64; else ARCH=x86_64; fi ;;
          esac
          NAME="__ARTIFACT__-${VER}-${OS}-${ARCH}-portable"
          mkdir -p out
          if [ "$OS" = win ]; then
            7z a "out/${NAME}.zip" ./dist/* > /dev/null
          else
            tar -czf "out/${NAME}.tar.gz" -C dist .   # tar.gz conserva los permisos de ejecución
          fi
          ls -l out

      - uses: actions/upload-artifact@v4
        with:
          name: __ARTIFACT__-${{ runner.os }}
          path: out/*
          if-no-files-found: error

  release:
    if: startsWith(github.ref, 'refs/tags/')
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts
          merge-multiple: true

      - name: Checksums SHA256
        working-directory: artifacts
        run: sha256sum * > SHA256SUMS.txt && cat SHA256SUMS.txt

      # CLI oficial de GitHub: sin acciones de terceros con permiso de escritura
      - name: Crear la release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release create "$GITHUB_REF_NAME" artifacts/* --repo "$GITHUB_REPOSITORY" \
            --title "__APP__ $GITHUB_REF_NAME" --generate-notes --verify-tag
"""


def _rel(path, workspace):
    """Ruta relativa al proyecto con '/' (portable), o None si está fuera del proyecto."""
    if not path:
        return None
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(workspace))
    except ValueError:   # otra unidad en Windows
        return None
    if rel.startswith(".."):
        return None
    return rel.replace("\\", "/")


def workflow_paths(cfg):
    safe = safe_app_name(cfg.app_name)
    return {
        "spec": f"{safe}.ci.spec",
        "workflow": f".github/workflows/build-{safe}.yml",
        "version": f"{safe}_version_info.txt",
    }


def generate_ci_files(cfg, python_version="3.12"):
    """Devuelve (archivos, advertencias): archivos = {ruta relativa al proyecto: contenido}."""
    if not cfg.workspace:
        raise ValueError(tr("ci.need_project"))
    ws = cfg.workspace
    warnings = []
    paths = workflow_paths(cfg)
    files = {}

    script = _rel(cfg.script, ws)
    if not script:
        raise ValueError(tr("ci.script_outside"))

    datas = []
    for src, dst in cfg.add_data:
        rel = _rel(src, ws)
        if rel:
            datas.append((rel, dst))
        else:
            warnings.append(tr("ci.add_data_outside", path=src))

    icon_expr = None
    icon = cfg.icon.strip()
    if icon:
        rel = _rel(icon, ws)
        if not rel:
            warnings.append(tr("ci.icon_outside", path=icon))
        else:
            by_platform = {}
            base, ext = os.path.splitext(rel)
            if ext.lower() == ".ico":
                by_platform["win32"] = rel
                if os.path.isfile(os.path.join(ws, base + ".icns")):
                    by_platform["darwin"] = base + ".icns"
            elif ext.lower() == ".icns":
                by_platform["darwin"] = rel
                if os.path.isfile(os.path.join(ws, base + ".ico")):
                    by_platform["win32"] = base + ".ico"
            if by_platform:
                icon_expr = f"{by_platform!r}.get(sys.platform)"
                if "darwin" not in by_platform:
                    warnings.append(tr("ci.no_icns"))
            datas.append((rel, "."))

    version_file = ""
    if cfg.version_file.strip():
        version_file = _rel(cfg.version_file.strip(), ws) or ""
        if not version_file:
            warnings.append(tr("ci.version_outside"))
    elif cfg.version_info:
        version_file = paths["version"]
        files[version_file] = generate_version_info(cfg.app_name, cfg.app_version, cfg.company, cfg.product,
                                                    cfg.description, cfg.copyright)

    if cfg.is_nuitka:
        warnings.append(tr("ci.nuitka"))
    if cfg.runtime_tmpdir and cfg.onefile:
        warnings.append(tr("ci.tmpdir"))
    if cfg.extra_flags.strip():
        warnings.append(tr("ci.extra_flags", flags=cfg.extra_flags.strip()))

    imports = list(dict.fromkeys(cfg.hidden_imports))
    spec = generate_spec_content(
        cfg.app_name, script, imports, cfg.onefile, cfg.noconsole, "", datas, cfg.all_excludes,
        cfg.strip, cfg.noupx,
        collect_all=collect_all_packages(imports, cfg.collect_all),
        collect_data=list(dict.fromkeys(cfg.collect_data)),
        copy_metadata=list(dict.fromkeys(cfg.copy_metadata)),
        debug=cfg.debug, bootloader_ignore=cfg.bootloader_ignore, uac_admin=cfg.uac_admin,
        version_file=version_file, optimize=cfg.optimize, icon_expr=icon_expr,
    )
    header = "# -*- mode: python ; coding: utf-8 -*-\n"
    spec = spec.replace(header, header + "# .spec portable para GitHub Actions (rutas relativas a este archivo)\n"
                                         "import sys\n", 1)
    files[paths["spec"]] = spec

    has_req = os.path.isfile(os.path.join(ws, "requirements.txt"))
    reqs = "          python -m pip install -r requirements.txt\n" if has_req else ""
    if not has_req:
        warnings.append(tr("ci.no_requirements"))
    files[paths["workflow"]] = (_WORKFLOW.replace("__APP__", cfg.app_name)
                                .replace("__ARTIFACT__", artifact_app_name(cfg.app_name))
                                .replace("__SPEC__", paths["spec"])
                                .replace("__PYVER__", python_version)
                                .replace("__REQS__", reqs))
    return files, warnings


def write_ci_files(workspace, files):
    written = []
    for rel, content in files.items():
        path = os.path.join(workspace, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        written.append(path)
    return written
