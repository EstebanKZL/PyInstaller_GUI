"""Generación de archivos .spec para PyInstaller 6.x."""

from .. import AUTHOR, VERSION


def _py_list(items, indent="        "):
    """ Lista Python válida (repr escapa comillas y backslashes de rutas Windows). """
    if not items:
        return "[]"
    return "[\n" + "".join(f"{indent}{item!r},\n" for item in items) + indent[:-4] + "]"

def generate_spec_content(app_name, script, imports, mode_onefile, noconsole,
                           icon_path, add_data_list, exclude_list, strip, noupx,
                           collect_all=(), debug=False, bootloader_ignore=False,
                           uac_admin=False, version_file="", runtime_tmpdir="",
                           optimize=False, collect_data=(), copy_metadata=(), icon_expr=None):
    """ Genera un .spec compatible con PyInstaller 6.x.
    add_data_list: lista de tuplas (origen, destino).
    collect_all / collect_data / copy_metadata: equivalentes a los flags --collect-all,
    --collect-data y --copy-metadata.
    onefile → un único EXE con binarios y datos; onedir → EXE + COLLECT. """
    datas = list(add_data_list)
    binaries = []
    hidden = list(imports)
    collect_lines = ""
    if collect_all or collect_data or copy_metadata:
        helpers = [h for h, used in (("collect_all", collect_all), ("collect_data_files", collect_data),
                                     ("copy_metadata", copy_metadata)) if used]
        collect_lines = f"\nfrom PyInstaller.utils.hooks import {', '.join(helpers)}\n\n"
        collect_lines += "datas, binaries, hiddenimports = {d}, [], {h}\n".format(
            d=_py_list(datas, "    "), h=_py_list(hidden, "    "))
        if collect_all:
            collect_lines += f"for _pkg in {list(collect_all)!r}:\n"
            collect_lines += "    _d, _b, _h = collect_all(_pkg)\n"
            collect_lines += "    datas += _d\n    binaries += _b\n    hiddenimports += _h\n"
        if collect_data:
            collect_lines += f"for _pkg in {list(collect_data)!r}:\n"
            collect_lines += "    datas += collect_data_files(_pkg)\n"
        if copy_metadata:
            collect_lines += f"for _pkg in {list(copy_metadata)!r}:\n"
            collect_lines += "    datas += copy_metadata(_pkg)\n"
        datas_expr, bins_expr, hidden_expr = "datas", "binaries", "hiddenimports"
    else:
        datas_expr = _py_list(datas)
        bins_expr = _py_list(binaries)
        hidden_expr = _py_list(hidden)

    upx = not noupx
    exe_opts = [
        f"name={app_name!r}",
        f"debug={bool(debug)}",
        f"bootloader_ignore_signals={bool(bootloader_ignore)}",
        f"strip={bool(strip)}",
        f"upx={upx}",
        f"console={not noconsole}",
    ]
    if icon_expr:   # expresión Python literal (ej. ícono distinto por plataforma en CI)
        exe_opts.append(f"icon={icon_expr}")
    elif icon_path:
        exe_opts.append(f"icon={icon_path!r}")
    if version_file:
        exe_opts.append(f"version={version_file!r}")
    if uac_admin:
        exe_opts.append("uac_admin=True")

    analysis_extra = "    optimize=1,\n" if optimize else ""

    if mode_onefile:
        if runtime_tmpdir:
            exe_opts.append(f"runtime_tmpdir={runtime_tmpdir!r}")
        exe_block = (
            "exe = EXE(\n"
            "    pyz,\n"
            "    a.scripts,\n"
            "    a.binaries,\n"
            "    a.datas,\n"
            "    [],\n"
            + "".join(f"    {o},\n" for o in exe_opts) +
            "    upx_exclude=[],\n"
            ")\n"
        )
    else:
        exe_block = (
            "exe = EXE(\n"
            "    pyz,\n"
            "    a.scripts,\n"
            "    [],\n"
            "    exclude_binaries=True,\n"
            + "".join(f"    {o},\n" for o in exe_opts) +
            ")\n\n"
            "coll = COLLECT(\n"
            "    exe,\n"
            "    a.binaries,\n"
            "    a.datas,\n"
            f"    strip={bool(strip)},\n"
            f"    upx={upx},\n"
            "    upx_exclude=[],\n"
            f"    name={app_name!r},\n"
            ")\n"
        )

    return (
        "# -*- mode: python ; coding: utf-8 -*-\n"
        f"# Generado por PyInstaller GUI PRO Builder {VERSION}\n"
        f"# Autor: {AUTHOR}\n"
        f"# Modo: {'onefile' if mode_onefile else 'onedir'}  |  Requiere PyInstaller 6.x\n"
        f"{collect_lines}\n"
        "a = Analysis(\n"
        f"    [{script!r}],\n"
        "    pathex=[],\n"
        f"    binaries={bins_expr},\n"
        f"    datas={datas_expr},\n"
        f"    hiddenimports={hidden_expr},\n"
        "    hookspath=[],\n"
        "    hooksconfig={},\n"
        "    runtime_hooks=[],\n"
        f"    excludes={_py_list(exclude_list)},\n"
        "    noarchive=False,\n"
        f"{analysis_extra}"
        ")\n\n"
        "pyz = PYZ(a.pure)\n\n"
        f"{exe_block}"
    )
