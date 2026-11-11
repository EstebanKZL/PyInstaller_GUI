import os
import shutil
import struct
import subprocess
import sys
import zipfile

import pytest

from pyinstaller_gui.core.builder import BuildRunner
from pyinstaller_gui.core.ci_workflow import generate_ci_files, workflow_paths, write_ci_files
from pyinstaller_gui.core.command import build_command, build_spec
from pyinstaller_gui.core.icons import build_icns, build_ico, read_ico_sizes, validate_icon_file
from pyinstaller_gui.core.installers import find_license, inno_script, nsis_script
from pyinstaller_gui.core.outputs import is_app_output
from pyinstaller_gui.core.naming import arch_label, artifact_name
from pyinstaller_gui.core.release import make_zip, sha256_file, write_checksums
from pyinstaller_gui.core.signing import find_signtool, redact, signtool_command
from pyinstaller_gui.core.version_info import generate_version_info, parse_version

# PNG mínimo válido de 1x1 (el contenedor ICO/ICNS no re-decodifica las imágenes)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000a49444154789c6300010000050001"
                    "0d0a2db40000000049454e44ae426082")


# ── Información de versión ───────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [("1.2", (1, 2, 0, 0)), ("1.2.3-beta", (1, 2, 3, 0)),
                                           ("v2.0.1.7.9", (2, 0, 1, 7)), ("", (0, 0, 0, 0))])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_version_info_lo_entiende_pyinstaller(tmp_path):
    versioninfo = pytest.importorskip("PyInstaller.utils.win32.versioninfo")
    text = generate_version_info("Mi App", "2.1.0", "ACME \"SA\"", "Producto", "Desc", "© 2026 ACME")
    p = tmp_path / "v.txt"
    p.write_text(text, encoding="utf-8")
    vs = versioninfo.load_version_info_from_text_file(str(p))
    assert vs.ffi.fileVersionMS == (2 << 16) | 1
    assert "ACME \"SA\"" in str(vs) and "Mi App.exe" in str(vs)


def test_version_info_en_comando_y_spec(cfg):
    cfg.version_info, cfg.app_version, cfg.company = True, "3.4.5", "ACME"
    cmd, notes = build_command(cfg)
    ver = next(c for c in cmd if c.startswith("--version-file="))
    path = ver.split("=", 1)[1]
    assert os.path.isfile(path) and "3.4.5" in open(path, encoding="utf-8").read()
    assert ".pyinstaller_gui" in path
    assert "version=" in build_spec(cfg)


# ── Íconos ───────────────────────────────────────────────────────────────
def test_build_ico_multi_tamano(tmp_path):
    data = build_ico({16: PNG, 32: PNG, 256: PNG})
    p = tmp_path / "x.ico"
    p.write_bytes(data)
    assert validate_icon_file(str(p), ".ico")
    assert read_ico_sizes(str(p)) == [16, 32, 256]
    # el offset de la primera imagen apunta justo después de las 3 entradas
    assert struct.unpack_from("<I", data, 6 + 12)[0] == 6 + 16 * 3


def test_build_icns():
    data = build_icns({16: PNG, 512: PNG, 999: PNG})
    assert data[:4] == b"icns" and struct.unpack(">I", data[4:8])[0] == len(data)
    assert b"icp4" in data and b"ic09" in data


# ── Firma ────────────────────────────────────────────────────────────────
def test_signtool_command_y_redaccion():
    cmd = signtool_command("signtool", "a.exe", "pfx", "c.pfx", "secreto", "http://ts")
    assert cmd[:4] == ["signtool", "sign", "/fd", "SHA256"] and "/f" in cmd and cmd[-1] == "a.exe"
    assert "secreto" not in " ".join(redact(cmd))
    assert "/a" in signtool_command("s", "a.exe")
    assert signtool_command("s", "a.exe", "thumbprint", "AB CD")[4:6] == ["/sha1", "ABCD"]


def _self_signed_pfx(tmp_path):
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("openssl no disponible")
    key, crt, pfx = tmp_path / "k.pem", tmp_path / "c.pem", tmp_path / "test.pfx"
    r = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
                        "-keyout", str(key), "-out", str(crt), "-subj", "/CN=PyInstaller GUI Test",
                        "-addext", "extendedKeyUsage=codeSigning"], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"openssl falló: {r.stderr[-300:]}")
    subprocess.run([openssl, "pkcs12", "-export", "-out", str(pfx), "-inkey", str(key), "-in", str(crt),
                    "-passout", "pass:clave123"], check=True, capture_output=True)
    return pfx


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="signtool es de Windows")
def test_firma_real_con_certificado_autofirmado(cfg, project, tmp_path, monkeypatch):
    """Compila, firma con un .pfx autofirmado (sin tocar el almacén de certificados de
    Windows) y verifica que el .exe tiene firma Authenticode."""
    pytest.importorskip("PyInstaller")
    if not find_signtool():
        pytest.skip("signtool no disponible (Windows SDK)")
    pfx = _self_signed_pfx(tmp_path)
    monkeypatch.setenv("PYI_GUI_SIGN_PASSWORD", "clave123")
    cfg.name, cfg.noconsole = "Firmada", False
    cfg.sign, cfg.sign_mode, cfg.sign_cert, cfg.sign_timestamp = True, "pfx", str(pfx), ""
    cfg.make_zip, cfg.make_checksums = True, True
    logs = []
    ok, msg = BuildRunner(cfg, build_command(cfg)[0], log=logs.append).run()
    assert ok, msg + "\n" + "\n".join(logs[-30:])
    assert "clave123" not in "\n".join(logs)
    exe = project / "dist" / "Firmada" / "Firmada.exe"
    # Sin el PSModulePath heredado: en los runners de GitHub apunta a los módulos de
    # PowerShell 7 y Windows PowerShell 5.1 no puede cargar Get-AuthenticodeSignature
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         f"(Get-AuthenticodeSignature -LiteralPath '{exe}').SignerCertificate.Subject"],
                        capture_output=True, text=True, env=env)
    assert "PyInstaller GUI Test" in ps.stdout, ps.stdout + ps.stderr
    # Release: ZIP + checksums verificables
    arch = arch_label("win", str(exe))
    z = project / "dist" / artifact_name("Firmada", cfg.app_version, "win", arch, "portable", "zip")
    sums = project / "dist" / "SHA256SUMS.txt"
    assert z.is_file() and sums.is_file()
    assert sums.read_text(encoding="utf-8").split()[0] == sha256_file(str(z))
    with zipfile.ZipFile(z) as zf:
        assert "Firmada/Firmada.exe" in zf.namelist()


# ── Release ──────────────────────────────────────────────────────────────
def test_zip_y_checksums(tmp_path):
    app = tmp_path / "App"
    (app / "_internal").mkdir(parents=True)
    (app / "App.exe").write_bytes(b"exe")
    (app / "_internal" / "x.dll").write_bytes(b"dll")
    z = make_zip(str(app), str(tmp_path / "App-1.0-win-x64-portable.zip"))
    with zipfile.ZipFile(z) as zf:
        assert sorted(zf.namelist()) == ["App/App.exe", "App/_internal/x.dll"]
    sums = write_checksums([z], str(tmp_path / "sums.txt"))
    line = open(sums, encoding="utf-8").read().strip()
    assert line == f"{sha256_file(z)}  {os.path.basename(z)}"


def test_salidas_de_release_reconocidas():
    for name in ("App-1.0-windows.zip", "App-SHA256SUMS.txt", "App_Setup_Inno.exe", "App_setup.iss",
                 "App-1.0.0-win-x64-setup.exe", "App-1.0.0-win7-x86-portable.zip", "App-1.0.0-win-x64-nsis-setup.exe",
                 "App-1.0.0-linux-x86_64.AppImage", "SHA256SUMS.txt"):
        assert is_app_output(name, "App"), name
    assert not is_app_output("Apple-1.0.zip", "App") and not is_app_output("App de fotos.zip", "App")
    # Los artefactos de "App-Lite" no son de "App"
    assert not is_app_output("App-Lite-1.0.0-win-x64-setup.exe", "App")
    assert is_app_output("MiApp-2.0-win-x64-setup.exe", "Mi App")


# ── Instaladores (scripts) ───────────────────────────────────────────────
def test_nsis_script(tmp_path):
    lic = tmp_path / "LICENSE"
    lic.write_text("MIT", encoding="utf-8")
    s = nsis_script('Mi "App"', "C:\\d\\Mi App", "Mi App.exe", "C:\\d\\out.exe", "1.2.3", "ACME", str(lic))
    assert '!define APP_NAME    "Mi \'App\'"' in s           # comillas neutralizadas
    assert "Page license" in s and "DisplayVersion" in s and "Uninstall\\Mi 'App'" in s
    assert 'IfFileExists "$INSTDIR\\${APP_EXE}" 0 +2' in s   # desinstalador seguro
    assert find_license(str(tmp_path)) == str(lic) and find_license("") == ""


def test_inno_script():
    s = inno_script("Mi App", "C:\\d\\Mi App", "Mi App.exe", "C:\\d", "Mi_App_Setup_Inno", "2.0", "ACME")
    assert s.count("AppId={{") == 1 and "AppVersion=2.0" in s
    assert 'Source: "C:\\d\\Mi App\\*"' in s and "{autopf}\\Mi App" in s
    # El AppId es estable (las actualizaciones reemplazan la versión instalada)
    assert s == inno_script("Mi App", "C:\\d\\Mi App", "Mi App.exe", "C:\\d", "Mi_App_Setup_Inno", "2.0", "ACME")


# ── GitHub Actions ───────────────────────────────────────────────────────
def test_ci_files(cfg, project, tmp_path):
    (project / "requirements.txt").write_text("requests\n", encoding="utf-8")
    (project / "icono.ico").write_bytes(build_ico({16: PNG}))
    (project / "icono.icns").write_bytes(build_icns({16: PNG}))
    (project / "assets").mkdir()
    cfg.icon = str(project / "icono.ico")
    cfg.add_data = [(str(project / "assets"), "assets"), (str(tmp_path / "fuera.txt"), ".")]
    cfg.version_info, cfg.name, cfg.extra_flags = True, "Mi App", "--log-level WARN"
    files, warnings = generate_ci_files(cfg, "3.12")
    paths = workflow_paths(cfg)
    assert set(files) == {paths["spec"], paths["workflow"], paths["version"]}
    spec = files[paths["spec"]]
    compile(spec, "ci.spec", "exec")
    assert "'main.py'" in spec and "('assets', 'assets')" in spec and "Cloud" not in spec
    assert "{'win32': 'icono.ico', 'darwin': 'icono.icns'}.get(sys.platform)" in spec
    assert str(project) not in spec                        # nada de rutas absolutas de esta máquina
    wf = files[paths["workflow"]]
    assert "pip install -r requirements.txt" in wf and 'python-version: "3.12"' in wf
    assert "windows-latest, ubuntu-latest, macos-latest" in wf and 'NAME="MiApp-${VER}-${OS}-${ARCH}-portable"' in wf
    assert "SHA256SUMS.txt" in wf and "softprops" not in wf
    assert any("fuera del proyecto" in w for w in warnings) and any("flags adicionales" in w for w in warnings)
    written = write_ci_files(str(project), files)
    assert all(os.path.isfile(p) for p in written)


def test_workflow_es_yaml_valido(cfg):
    yaml = pytest.importorskip("yaml")
    files, _ = generate_ci_files(cfg)
    doc = yaml.safe_load(files[workflow_paths(cfg)["workflow"]])
    assert doc["jobs"]["build"]["strategy"]["matrix"]["os"] == ["windows-latest", "ubuntu-latest", "macos-latest"]
    assert doc["jobs"]["release"]["needs"] == "build"


@pytest.mark.slow
def test_spec_de_ci_compila_de_verdad(cfg, project, tmp_path):
    """El .spec portable se puede compilar con PyInstaller desde la carpeta del proyecto."""
    pytest.importorskip("PyInstaller")
    cfg.name, cfg.noconsole = "CiApp", False
    files, _ = generate_ci_files(cfg)
    write_ci_files(str(project), files)
    spec = project / workflow_paths(cfg)["spec"]
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(tmp_path / "dist"),
                        "--workpath", str(tmp_path / "build"), str(spec)], cwd=str(tmp_path),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-3000:]
    exe = tmp_path / "dist" / "CiApp" / ("CiApp.exe" if sys.platform == "win32" else "CiApp")
    assert "HOLA-TEST" in subprocess.run([str(exe)], capture_output=True, text=True, timeout=120).stdout
