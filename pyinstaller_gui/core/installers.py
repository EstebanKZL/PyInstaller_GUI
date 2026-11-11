"""Empaquetado posterior al build: AppImage (Linux) e instalador NSIS (Windows).

Cada función recibe un callback log(str) para informar el progreso."""

import glob
import os
import re
import shutil
import subprocess
import sys

from .icons import MINIMAL_PNG, validate_icon_file
from .process import find_tool, sub_kwargs
from ..i18n import tr


def create_appimage(dist_dir, app_name, icon_png, log, temp_dirs, out_name="", arch="x86_64"):
    """Arma <app>.AppDir y lo convierte en AppImage. out_name: nombre del archivo final
    (por defecto el que elija appimagetool, <Name>-<arch>.AppImage)."""
    dist_path  = dist_dir
    appdir     = os.path.join(dist_path, f"{app_name}.AppDir")
    target     = os.path.join(dist_path, app_name)
    if not os.path.exists(target):
        log(tr("log.inst_no_result"))
        return False
        
    temp_dirs.append(appdir)
    usr_bin = os.path.join(appdir, "usr", "bin")
    os.makedirs(usr_bin, exist_ok=True)

    if os.path.isdir(target):
        for item in os.listdir(target):
            s, d2 = os.path.join(target, item), os.path.join(usr_bin, item)
            (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, d2)
    else:
        shutil.copy2(target, os.path.join(usr_bin, app_name))

    safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', app_name)
    old_bin = os.path.join(usr_bin, app_name)
    new_bin = os.path.join(usr_bin, safe_name)
    
    if safe_name != app_name and os.path.exists(old_bin):
        os.rename(old_bin, new_bin)
    if os.path.exists(new_bin):
        os.chmod(new_bin, 0o755)

    desktop_content = (
        f"[Desktop Entry]\nName={app_name}\nExec={safe_name}\n"
        f"Icon={safe_name}\nType=Application\nCategories=Development;\n"
    )
    with open(os.path.join(appdir, f"{app_name}.desktop"), 'w', encoding='utf-8') as f:
        f.write(desktop_content)

    icon_dst = os.path.join(appdir, f"{safe_name}.png")
    if icon_png and validate_icon_file(icon_png, '.png'):
        shutil.copy2(icon_png, icon_dst)
        log(tr("log.appimage_icon_ok"))
    else:
        with open(icon_dst, 'wb') as f:
            f.write(MINIMAL_PNG)
        log(tr("log.appimage_icon_placeholder"))

    run_path = os.path.join(appdir, "AppRun")
    with open(run_path, 'w') as f:
        f.write(f'#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/bin/{safe_name}" "$@"')
    os.chmod(run_path, 0o755)

    olds = glob.glob(os.path.join(dist_path, f"{app_name}*.AppImage"))
    if out_name:
        olds.append(os.path.join(dist_path, out_name))
    for old in olds:
        try: 
            os.remove(old)
        except Exception: 
            pass

    tool = find_tool("appimagetool")
    if not tool:
        log(tr("log.no_appimagetool_short"))
        return False

    env = {**os.environ, "ARCH": arch or "x86_64"}
    cmd = [tool, appdir] + ([os.path.join(dist_path, out_name)] if out_name else [])
    r = subprocess.run(cmd, cwd=dist_path,
                    capture_output=True, text=True, env=env, **sub_kwargs())
                    
    if r.returncode == 0:
        log(tr("log.appimage_ok"))
        return True
        
    log(tr("log.tool_error", tool="appimagetool", output=r.stderr))
    return False


# ── Instaladores de Windows (sobre la carpeta onedir) ────────────────────
def _onedir_exe(app_dir, app_name, log):
    exe = os.path.join(app_dir, f"{app_name}.exe")
    if os.path.isfile(exe):
        return exe
    exes = [f for f in os.listdir(app_dir) if f.lower().endswith('.exe')]
    if exes:
        return os.path.join(app_dir, exes[0])
    log(tr("log.inst_no_exe"))
    return ""


def _is_x64(x64):
    return sys.maxsize > 2**32 if x64 is None else bool(x64)


def _clean(text):
    """Valores para los scripts de instalador: sin comillas ni saltos de línea."""
    return str(text).replace('"', "'").replace("\r", " ").replace("\n", " ").strip()


def find_license(workspace):
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCIA.txt", "COPYING", "COPYING.txt"):
        p = os.path.join(workspace or "", name)
        if workspace and os.path.isfile(p):
            return p
    return ""


def nsis_script(app_name, app_dir, exe_name, installer_out, version="1.0.0", publisher="", license_file="",
                icon="", x64=None):
    """x64: el programa es de 64 bits (por defecto, el bitness de este Python)."""
    name = _clean(app_name)
    ver = _clean(version or "1.0.0")
    pub = _clean(publisher)
    pf = "$PROGRAMFILES64" if _is_x64(x64) else "$PROGRAMFILES"
    uninst_key = f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{name}"
    lines = [
        "; Instalador NSIS generado por PyInstaller GUI PRO Builder",
        "Unicode true",
        f'!define APP_NAME    "{name}"',
        f'!define APP_EXE     "{_clean(exe_name)}"',
        f'!define APP_VERSION "{ver}"',
        f'!define PUBLISHER   "{pub}"',
        f'!define UNINST_KEY  "{uninst_key}"',
        "",
        'Name "${APP_NAME} ${APP_VERSION}"',
        f'OutFile "{installer_out}"',
        f'InstallDir "{pf}\\${{APP_NAME}}"',
        'InstallDirRegKey HKLM "${UNINST_KEY}" "InstallLocation"',
        "RequestExecutionLevel admin",
        "SetCompressor /SOLID lzma",
    ]
    if icon and icon.lower().endswith(".ico") and os.path.isfile(icon):
        lines += [f'Icon "{icon}"', f'UninstallIcon "{icon}"']
    lines.append("")
    if license_file:
        lines += [f'LicenseData "{license_file}"', "Page license"]
    lines += [
        "Page directory",
        "Page instfiles",
        "UninstPage uninstConfirm",
        "UninstPage instfiles",
        "",
        'Section "Instalar"',
        "  SetShellVarContext all",
        '  SetOutPath "$INSTDIR"',
        f'  File /r "{app_dir}\\*.*"',
        '  WriteUninstaller "$INSTDIR\\Uninstall.exe"',
        '  CreateDirectory "$SMPROGRAMS\\${APP_NAME}"',
        '  CreateShortCut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"',
        '  CreateShortCut "$SMPROGRAMS\\${APP_NAME}\\Desinstalar ${APP_NAME}.lnk" "$INSTDIR\\Uninstall.exe"',
        '  CreateShortCut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"',
        "  ; Entrada en 'Agregar o quitar programas'",
        '  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP_NAME}"',
        '  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"',
        '  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${PUBLISHER}"',
        '  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\\${APP_EXE}"',
        '  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"',
        '  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" \'"$INSTDIR\\Uninstall.exe"\'',
        '  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1',
        '  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1',
        "SectionEnd",
        "",
        'Section "Uninstall"',
        "  SetShellVarContext all",
        "  ; Seguridad: solo borrar la carpeta si es realmente la de esta app",
        '  IfFileExists "$INSTDIR\\${APP_EXE}" 0 +2',
        '    RMDir /r "$INSTDIR"',
        '  Delete "$DESKTOP\\${APP_NAME}.lnk"',
        '  RMDir /r "$SMPROGRAMS\\${APP_NAME}"',
        '  DeleteRegKey HKLM "${UNINST_KEY}"',
        "SectionEnd",
    ]
    return "\n".join(lines) + "\n"


def create_nsis_installer(dist_dir, app_name, log, version="1.0.0", publisher="", license_file="", icon="",
                          output_base="", x64=None):
    """Genera un script .nsi y lo compila con makensis (Windows, --onedir). Devuelve la ruta o "".
    output_base: nombre del instalador sin .exe (por defecto <app>_Setup)."""
    app_dir = os.path.join(dist_dir, app_name)
    if not os.path.isdir(app_dir):
        log(tr("log.inst_no_onedir", app=app_name))
        return ""
    makensis = find_tool("makensis")
    if not makensis:
        log(tr("log.no_makensis"))
        return ""
    exe = _onedir_exe(app_dir, app_name, log)
    if not exe:
        return ""
    safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', app_name)
    nsi_path = os.path.join(dist_dir, f"{safe_name}_setup.nsi")
    out = os.path.join(dist_dir, f"{output_base or safe_name + '_Setup'}.exe")
    try:
        with open(nsi_path, 'w', encoding='utf-8') as f:
            f.write(nsis_script(app_name, app_dir, os.path.basename(exe), out, version, publisher, license_file, icon,
                                x64))
        log(tr("log.script_written", path=nsi_path))
    except Exception as e:
        log(tr("log.script_write_error", error=e))
        return ""
    r = subprocess.run([makensis, nsi_path], capture_output=True, text=True, **sub_kwargs())
    if r.returncode == 0:
        log(tr("log.installer_ok", label="NSIS", path=out))
        return out
    log(tr("log.tool_error", tool="makensis", output=f"{r.stdout}\n{r.stderr}"))
    return ""


def inno_script(app_name, app_dir, exe_name, output_dir, output_base, version="1.0.0", publisher="",
                license_file="", icon="", x64=None):
    import uuid
    name = _clean(app_name)
    exe = _clean(exe_name)
    app_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pyinstaller-gui://{name}/{_clean(publisher)}")).upper()
    lines = [
        "; Instalador Inno Setup generado por PyInstaller GUI PRO Builder",
        "[Setup]",
        "AppId={{" + app_id + "}",   # '{{' = llave literal en Inno Setup
        f"AppName={name}",
        f"AppVersion={_clean(version or '1.0.0')}",
        f"AppPublisher={_clean(publisher)}",
        "DefaultDirName={autopf}\\" + name,
        f"DefaultGroupName={name}",
        "UninstallDisplayIcon={app}\\" + exe,
        f"OutputDir={output_dir}",
        f"OutputBaseFilename={output_base}",
        "Compression=lzma2",
        "SolidCompression=yes",
        "WizardStyle=modern",
        "PrivilegesRequiredOverridesAllowed=dialog",
    ]
    if _is_x64(x64):
        lines += ["ArchitecturesAllowed=x64compatible", "ArchitecturesInstallIn64BitMode=x64compatible"]
    if license_file:
        lines.append(f"LicenseFile={license_file}")
    if icon and icon.lower().endswith(".ico") and os.path.isfile(icon):
        lines.append(f"SetupIconFile={icon}")
    lines += [
        "",
        "[Languages]",
        'Name: "spanish"; MessagesFile: "compiler:Languages\\Spanish.isl"',
        'Name: "english"; MessagesFile: "compiler:Default.isl"',
        "",
        "[Tasks]",
        'Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; '
        'Flags: unchecked',
        "",
        "[Files]",
        f'Source: "{app_dir}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs',
        "",
        "[Icons]",
        'Name: "{group}\\' + name + '"; Filename: "{app}\\' + exe + '"',
        'Name: "{group}\\{cm:UninstallProgram,' + name + '}"; Filename: "{uninstallexe}"',
        'Name: "{autodesktop}\\' + name + '"; Filename: "{app}\\' + exe + '"; Tasks: desktopicon',
        "",
        "[Run]",
        'Filename: "{app}\\' + exe + '"; Description: "{cm:LaunchProgram,' + name + '}"; '
        "Flags: nowait postinstall skipifsilent",
    ]
    return "\n".join(lines) + "\n"


def create_inno_installer(dist_dir, app_name, log, version="1.0.0", publisher="", license_file="", icon="",
                          output_base="", x64=None):
    """Genera un script .iss y lo compila con ISCC (Inno Setup 6). Devuelve la ruta o "".
    output_base: nombre del instalador sin .exe (por defecto <app>_Setup_Inno)."""
    app_dir = os.path.join(dist_dir, app_name)
    if not os.path.isdir(app_dir):
        log(tr("log.inst_no_onedir", app=app_name))
        return ""
    iscc = find_tool("ISCC")
    if not iscc:
        log(tr("log.no_iscc"))
        return ""
    exe = _onedir_exe(app_dir, app_name, log)
    if not exe:
        return ""
    safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', app_name)
    iss_path = os.path.join(dist_dir, f"{safe_name}_setup.iss")
    base = output_base or f"{safe_name}_Setup_Inno"
    with open(iss_path, "w", encoding="utf-8-sig") as f:   # BOM: Inno Setup lo necesita para UTF-8
        f.write(inno_script(app_name, app_dir, os.path.basename(exe), dist_dir, base, version, publisher,
                            license_file, icon, x64))
    log(tr("log.script_written", path=iss_path))
    r = subprocess.run([iscc, iss_path], capture_output=True, text=True, **sub_kwargs())
    out = os.path.join(dist_dir, base + ".exe")
    if r.returncode == 0 and os.path.isfile(out):
        log(tr("log.installer_ok", label="Inno Setup", path=out))
        return out
    log(tr("log.tool_error", tool="ISCC", output=f"{r.stdout}\n{r.stderr}"))
    return ""
