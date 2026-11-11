"""Parseo de líneas de requirements.txt."""

import re


def parse_requirement_name(line):
    result = parse_requirement_full(line)
    return result[0] if result else None

def parse_requirement_full(line):
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('-'):
        return None
    line = line.split('#')[0].strip()
    if not line:
        return None
    m = re.match(r'^([A-Za-z0-9_\-\.]+)', line)
    if not m:
        return None
    pkg = m.group(1)
    rest = line[len(pkg):]
    rest_no_extras = re.sub(r'^\s*\[[^\]]*\]', '', rest).strip()
    ver_spec = rest_no_extras.split(';')[0].strip()
    full = f"{pkg}{ver_spec}" if ver_spec else pkg
    return (pkg, ver_spec, full)
