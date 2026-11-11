"""Paquete de release: ZIP del resultado y SHA256SUMS.txt para publicar.

Los nombres de los archivos siguen la convención de core/naming.py."""

import hashlib
import os
import zipfile


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_zip(target, zip_path):
    """Comprime una carpeta (conservando su nombre como raíz) o un archivo suelto."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        if os.path.isdir(target):
            base = os.path.dirname(os.path.abspath(target))
            for dp, _dn, fn in os.walk(target):
                for f in fn:
                    full = os.path.join(dp, f)
                    z.write(full, os.path.relpath(full, base))
        else:
            z.write(target, os.path.basename(target))
    return zip_path


def write_checksums(files, out_path):
    """Formato de sha256sum: '<hash>  <nombre>' (verificable con sha256sum -c)."""
    lines = [f"{sha256_file(p)}  {os.path.basename(p)}" for p in files if os.path.isfile(p)]
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
