"""Compila PyInstaller GUI con su propio núcleo y arma los paquetes de release.

Uso (lo ejecuta .github/workflows/release.yml en cada sistema):
    python release/build_release.py --label win-x64
    python release/build_release.py --label linux-x86_64

Genera en release_out/, con la convención <App>-<versión>-<sistema>-<arq>-<variante>.<ext>
(los nombres los arma el propio núcleo del programa, core/naming.py):
    PyInstallerGUI-5.1.0-win-x64-setup.exe        PyInstallerGUI-5.1.0-win-x64-portable.zip
    PyInstallerGUI-5.1.0-win7-x64-setup.exe       PyInstallerGUI-5.1.0-win7-x64-portable.zip
    PyInstallerGUI-5.1.0-win7-x86-setup.exe       PyInstallerGUI-5.1.0-win7-x86-portable.zip
    PyInstallerGUI-5.1.0-linux-x86_64.AppImage

Antes de empaquetar ejecuta el binario con PYI_GUI_SELFTEST=1: la ventana tiene que
construirse y el programa cerrarse solo con código 0; si no, el script falla.
"""

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pyinstaller_gui import APP_VERSION  # noqa: E402
from pyinstaller_gui.core.builder import BuildRunner  # noqa: E402
from pyinstaller_gui.core.command import build_command  # noqa: E402
from pyinstaller_gui.core.config import BuildConfig  # noqa: E402
from pyinstaller_gui.core.naming import artifact_name  # noqa: E402
from pyinstaller_gui.core.postbuild import executable_path, smoke_test  # noqa: E402

APP = "PyInstallerGUI"

# label → (plataforma objetivo, sistema, arquitectura). Qt 6 no tiene versión x86:
# el paquete de 32 bits es de la línea Windows 7/8 (PySide2) y corre de Windows 7 a 11.
LABELS = {
    "win-x64": ("windows", "win", "x64"),
    "win7-x64": ("windows7", "win7", "x64"),
    "win7-x86": ("windows7", "win7", "x86"),
    "linux-x86_64": ("linux", "linux", "x86_64"),
}


def expected_artifacts(label, version):
    _platform, os_lbl, arch = LABELS[label]
    if os_lbl == "linux":
        return [artifact_name(APP, version, os_lbl, arch, ext="AppImage")]
    return [artifact_name(APP, version, os_lbl, arch, "setup", "exe"),
            artifact_name(APP, version, os_lbl, arch, "portable", "zip")]


def build_config(label):
    target_platform = LABELS[label][0]
    is_windows = target_platform.startswith("windows")
    cfg = BuildConfig(
        workspace=ROOT,
        script=os.path.join(ROOT, "PyInstaller_GUI.py"),
        name=APP,
        python_path=sys.executable,
        platform=target_platform,         # windows7 → artefactos "win7"
        onefile=False,                    # carpeta: arranca rápido y la necesitan Inno Setup y AppImage
        noconsole=True,
        clean=True,
        icon=os.path.join(ROOT, "icono.ico") if is_windows else "",
        appimage_icon=os.path.join(ROOT, "icono.png"),
        # resource_path() busca icono.ico / icono.png en la raíz del paquete
        add_data=[(os.path.join(ROOT, "icono.ico"), "."), (os.path.join(ROOT, "icono.png"), ".")],
        version_info=is_windows,
        app_version=APP_VERSION.lstrip("vV"),
        company="EstebanKZL",
        product="PyInstaller GUI - PRO Builder",
        description="Compilador visual para PyInstaller",
        copyright="© 2026 EstebanKZL",
        inno=is_windows,
        create_appimage=not is_windows,
        make_zip=is_windows,              # portable: <App>-<versión>-<sistema>-<arq>-portable.zip
    )
    return cfg


def self_test(cfg):
    exe = executable_path(cfg.dist_dir, cfg.app_name, cfg.onefile)
    os.environ["PYI_GUI_SELFTEST"] = "1"
    if not sys.platform.startswith("win"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = smoke_test(exe, seconds=90)
    print(f"[selftest] {result['status']} código={result['code']} en {result['elapsed']} s")
    if result["output"].strip():
        print(result["output"])
    if result["status"] != "exited":
        raise SystemExit(f"La autoprueba falló: el ejecutable no arrancó correctamente ({result['status']}).")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True, choices=sorted(LABELS))
    p.add_argument("--out", default=os.path.join(ROOT, "release_out"))
    args = p.parse_args()

    version = APP_VERSION.lstrip("vV")
    cfg = build_config(args.label)
    cmd, notes = build_command(cfg)
    for n in notes:
        print(n)
    ok, msg = BuildRunner(cfg, cmd, log=print, status=lambda m: print(f"[*] {m}")).run()
    print(msg)
    if not ok:
        raise SystemExit(1)

    self_test(cfg)

    os.makedirs(args.out, exist_ok=True)
    for name in expected_artifacts(args.label, version):
        src = os.path.join(cfg.dist_dir, name)
        if not os.path.isfile(src):
            raise SystemExit(f"No se generó {name}.")
        shutil.copy2(src, os.path.join(args.out, name))

    for f in sorted(os.listdir(args.out)):
        size = os.path.getsize(os.path.join(args.out, f)) / 1024 / 1024
        print(f"[release] {f}  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
