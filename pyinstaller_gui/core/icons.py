"""Validación de íconos y placeholder PNG."""

import os

MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


def validate_icon_file(path, expected_ext=None):
    if not path or not os.path.isfile(path):
        return False
    if expected_ext and not path.lower().endswith(expected_ext):
        return False
    if expected_ext == '.ico':
        try:
            with open(path, 'rb') as f:
                h = f.read(4)
                return len(h) == 4 and h[:2] == b'\x00\x00' and h[2:4] == b'\x01\x00'
        except Exception:
            return False
    return True


# ── Contenedores de íconos a partir de PNG (sin Pillow) ─────────────────
# ICO (Windows Vista+) y ICNS (macOS) admiten imágenes PNG embebidas, así que
# alcanza con armar el contenedor; el redimensionado lo hace quien llama (Qt).
ICO_SIZES  = (16, 24, 32, 48, 64, 128, 256)
ICNS_TYPES = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07", 256: b"ic08", 512: b"ic09", 1024: b"ic10"}


def build_ico(pngs):
    """pngs: {tamaño: bytes PNG} → bytes de un .ico multi-resolución."""
    import struct
    sizes = sorted(s for s in pngs if 1 <= s <= 256)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for s in sizes:
        data = pngs[s]
        dim = 0 if s == 256 else s   # 0 significa 256 en el formato ICO
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def build_icns(pngs):
    """pngs: {tamaño: bytes PNG} → bytes de un .icns."""
    import struct
    body = b""
    for s in sorted(pngs):
        if s in ICNS_TYPES:
            body += ICNS_TYPES[s] + struct.pack(">I", 8 + len(pngs[s])) + pngs[s]
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def read_ico_sizes(path):
    """Tamaños contenidos en un .ico (para verificar)."""
    import struct
    with open(path, "rb") as f:
        data = f.read()
    _, kind, count = struct.unpack_from("<HHH", data, 0)
    if kind != 1:
        return []
    return [(data[6 + 16 * i] or 256) for i in range(count)]
