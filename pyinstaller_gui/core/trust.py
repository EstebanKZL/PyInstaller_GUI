"""Confianza en intérpretes Python antes de ejecutarlos.

Para verificar un intérprete el programa lo ejecuta (print('OK'), versión, paquetes).
Un python que viene de afuera puede ser cualquier ejecutable:
  - el venv que trae una carpeta de proyecto descargada de otro lado,
  - el python_path de un perfil JSON recibido de otra persona.
Esos se ejecutan solo después de que el usuario los confirme. Los que elige el usuario
con "Examinar" y los del sistema (PATH, py.exe, registro) se consideran confiables.

La confianza se guarda como "ruta|huella": la huella es el SHA-256 del ejecutable y del
pyvenv.cfg del venv (que decide qué Python base se carga). Si cualquiera de los dos
cambia, se vuelve a preguntar.
"""

import hashlib
import os

_SEP = "|"


def norm(path):
    return os.path.normcase(os.path.abspath(path)) if path else ""


def is_inside(path, folder):
    """True si 'path' está dentro de 'folder' (o es esa carpeta)."""
    if not path or not folder:
        return False
    p, f = norm(path), norm(folder)
    try:
        return os.path.commonpath([p, f]) == f
    except ValueError:   # otra unidad en Windows
        return False


def _venv_cfg(path):
    """pyvenv.cfg del venv al que pertenece el ejecutable (Scripts/ o bin/ → raíz del venv)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    cfg = os.path.join(root, "pyvenv.cfg")
    return cfg if os.path.isfile(cfg) else ""


def fingerprint(path):
    """SHA-256 del ejecutable + su pyvenv.cfg. "" si no se puede leer."""
    h = hashlib.sha256()
    try:
        for f in (path, _venv_cfg(path)):
            if not f:
                continue
            h.update(os.path.basename(f).encode())
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def is_trusted(path, trusted):
    """True si 'path' fue confirmado y no cambió desde entonces."""
    if not path:
        return False
    fp = fingerprint(path)
    return bool(fp) and f"{norm(path)}{_SEP}{fp}" in set(trusted)


def needs_confirmation(path, workspace="", from_profile=False, trusted=(), force=False):
    """True si hay que preguntar antes de ejecutar 'path'. force=True: siempre que no
    esté confirmado (entradas que el buscador marcó como no verificadas)."""
    if not path or is_trusted(path, trusted):
        return False
    return force or from_profile or is_inside(path, workspace)


def add_trusted(trusted, path):
    """Lista nueva con 'path' (y su huella actual) confiable; reemplaza huellas viejas."""
    key = norm(path)
    items = [t for t in trusted if t and t.split(_SEP, 1)[0] != key]
    fp = fingerprint(path) if path else ""
    if fp:
        items.append(f"{key}{_SEP}{fp}")
    return items
