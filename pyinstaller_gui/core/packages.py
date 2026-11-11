"""Consulta de paquetes instalados en el Python del proyecto."""

import json
import subprocess

from .process import sub_kwargs

# Paquetes que se usan para compilar y no forman parte del ejecutable
BUILD_TOOLS = frozenset({'pyinstaller', 'pyi-makespec', 'pyinstaller-hooks-contrib', 'pip', 'setuptools',
                         'wheel', 'build', 'twine', 'cx-freeze', 'cx_freeze', 'nuitka', 'py2exe'})

# Se ejecuta DENTRO del Python del proyecto (un solo proceso para todos los paquetes).
# Recibe [[paquete, especificador], ...] por argv (nunca interpolado en el código) y
# devuelve por cada paquete: versión instalada, módulos importables reales
# (Pillow → PIL, opencv-python → cv2, beautifulsoup4 → bs4...) y si cumple la versión.
_PKG_QUERY_SCRIPT = r"""
import sys, json, re, importlib.util
try:
    import importlib.metadata as md
except ImportError:
    md = None
try:
    from packaging.version import Version
    from packaging.specifiers import SpecifierSet
except Exception:
    Version = SpecifierSet = None
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def modules_of(dist):
    mods = []
    top = dist.read_text('top_level.txt') or ''
    for ln in top.splitlines():
        ln = ln.strip().replace('/', '.')
        if ln and ln not in mods:
            mods.append(ln)
    if not mods:
        for f in (dist.files or []):
            parts = str(f).replace('\\', '/').split('/')
            first = parts[0]
            if first.endswith(('.dist-info', '.egg-info', '.data', '.pth')) or first in ('..', '__pycache__'):
                continue
            if len(parts) == 1:
                if not first.endswith('.py'):
                    continue
                first = first[:-3]
            if IDENT.match(first) and first not in mods:
                mods.append(first)
    public = [m for m in mods if not m.startswith('_')]
    return public or mods

out = {}
for pkg, spec in json.loads(sys.argv[1]):
    info = {"version": "", "modules": [], "satisfies": None}
    if md is not None:
        try:
            dist = md.distribution(pkg)
            info["version"] = dist.version or ""
            info["modules"] = modules_of(dist)
        except Exception:
            pass
    if not info["version"]:
        guess = pkg.replace('-', '_')
        try:
            if importlib.util.find_spec(guess) is not None:
                info["modules"] = [guess]
        except Exception:
            pass
    if spec and info["version"] and Version is not None:
        try:
            info["satisfies"] = Version(info["version"]) in SpecifierSet(spec)
        except Exception:
            pass
    out[pkg] = info
print(json.dumps(out))
"""

def query_packages(python_exe, entries, timeout=60):
    """ entries: [(paquete, especificador), ...] → {paquete: {version, modules, satisfies}}.
    Devuelve {} si el Python del proyecto no responde. """
    if not entries:
        return {}
    try:
        r = subprocess.run([python_exe, "-c", _PKG_QUERY_SCRIPT, json.dumps([list(e) for e in entries])],
                           capture_output=True, text=True, timeout=timeout, **sub_kwargs())
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    except Exception:
        return {}

def pick_import_name(pkg, modules):
    """ Módulo principal de un paquete: el que coincide con el nombre normalizado,
    si no el primero público (sin '_' inicial, ej. PyYAML → yaml y no _yaml). """
    norm = pkg.replace('-', '_').replace('.', '_').lower()
    for m in modules:
        if m.lower() == norm:
            return m
    public = [m for m in modules if not m.startswith('_')]
    return (public or modules or [pkg.replace('-', '_')])[0]

def version_satisfies_fallback(req_spec, inst_ver):
    """ Comparación mínima cuando 'packaging' no está en el Python del proyecto. """
    for part in req_spec.split(','):
        part = part.strip()
        if part.startswith('==') and not part.endswith('*'):
            return inst_ver == part[2:].strip()
    return True


# Para módulos importados que NO están en requirements.txt: ¿se pueden importar y qué
# distribución de pip los provee? (cv2 → opencv-python). Se ejecuta en el Python del proyecto.
_MODULE_QUERY_SCRIPT = r"""
import sys, json, importlib.util
try:
    import importlib.metadata as md
except ImportError:
    md = None
mapping = {}
if md is not None:
    if hasattr(md, 'packages_distributions'):
        mapping = md.packages_distributions()
    else:
        for dist in md.distributions():
            name = dist.metadata.get('Name') or ''
            for ln in (dist.read_text('top_level.txt') or '').splitlines():
                if ln.strip():
                    mapping.setdefault(ln.strip(), []).append(name)
out = {}
for mod in json.loads(sys.argv[1]):
    try:
        ok = importlib.util.find_spec(mod) is not None
    except Exception:
        ok = False
    out[mod] = {"importable": ok, "dists": sorted(set(mapping.get(mod, [])))}
print(json.dumps(out))
"""

def query_modules(python_exe, modules, timeout=60):
    """ {módulo: {importable, dists}} en el Python del proyecto ({} si no responde). """
    if not modules:
        return {}
    try:
        r = subprocess.run([python_exe, "-c", _MODULE_QUERY_SCRIPT, json.dumps(sorted(modules))],
                           capture_output=True, text=True, timeout=timeout, **sub_kwargs())
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    except Exception:
        return {}
