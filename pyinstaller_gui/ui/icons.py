"""Íconos propios del sistema de diseño (v6.3): SVG de trazo fino que se colorean con el tema.

Grilla 24×24, trazo 1.75, puntas redondeadas, sin relleno salvo acentos. Se dibujan con
QSvgRenderer (QtSvg); si falta, los íconos quedan vacíos y el programa sigue funcionando.

Reglas de uso (sección 7 del diseño):
  - Sí: acciones universales en botones con texto (abrir, guardar, copiar, buscar, añadir,
    eliminar, actualizar, iniciar), menús comunes, campo de búsqueda y carpetas recientes.
  - No: títulos, labels, badges, pestañas principales ni el pie de los diálogos.
  - En una misma fila de botones, todos con ícono o ninguno (el primario puede llevarlo solo).
  - Nunca emojis, íconos del sistema (QStyle.SP_*) ni logos de marcas.
"""

from ..qt_compat import QByteArray, QGuiApplication, QIcon, QLabel, QPainter, QPixmap, QSize, QSvgRenderer, Qt
from .theme import THEME

ICON_SIZE = {"sm": 16, "md": 20, "lg": 24, "xl": 40}

_SVG_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
             'fill="none" stroke="{c}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">')

_FILE_BASE = ('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" '
              'fill="{c}" fill-opacity="0.12"/><path d="M14 3v5h5"/>')

_FOLDER_PATH = ("M3 7a1.5 1.5 0 0 1 1.5-1.5h4.6l2 2.2h8.4A1.5 1.5 0 0 1 21 9.2v8.3"
                "a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z")

_MONITOR = '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M9 20h6M12 16v4"/>'

_WINDOW = '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M6.5 6.5v.01M9 6.5v.01"/>'

_CLOUD = '<path d="M7 18.5a4.5 4.5 0 0 1-.5-9 6 6 0 0 1 11.5 1.5 3.75 3.75 0 0 1 0 7.5z"/>'

_SHIELD = '<path d="M12 3l8 3v6c0 4.5-3.4 7.8-8 9-4.6-1.2-8-4.5-8-9V6z"/>'

_TERM_FRAME = '<path d="M13 19.5H5a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5"/><path d="M7 9.5l2.5 2-2.5 2"/>'

_FOLDER_PART = ('<path d="M13 19H4.5A1.5 1.5 0 0 1 3 17.5v-10A1.5 1.5 0 0 1 4.5 6h4.6l2 2.2h8.4'
                'A1.5 1.5 0 0 1 21 9.7V12"/>')

_LOCK_BADGE = ('<rect x="15" y="16" width="6" height="4.5" rx="1" fill="{c}"/>'           # candado cerrado (relleno)
               '<path d="M16.5 16v-1.5a1.5 1.5 0 0 1 3 0V16"/>')

_OPEN_LOCK_BADGE = '<rect x="15" y="16" width="6" height="4.5" rx="1"/><path d="M16.5 16v-2.8a1.5 1.5 0 0 1 3 0"/>'

_PLUG = '<path d="M9 3v4M15 3v4"/><path d="M6.5 7h11v3a5.5 5.5 0 0 1-11 0z"/><path d="M12 15.5V21"/>'

ICON_SVG = {
    # ── Acciones generales ──
    "search":   '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    "refresh":  '<path d="M20 11a8 8 0 0 0-14.6-4.4L4 8"/><path d="M4 4v4h4"/>'
                '<path d="M4 13a8 8 0 0 0 14.6 4.4L20 16"/><path d="M20 20v-4h-4"/>',
    "settings": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
                '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "plus":     '<path d="M12 5v14M5 12h14"/>',
    "minus":    '<path d="M5 12h14"/>',
    "edit":     '<path d="M16.5 4.5a2.1 2.1 0 0 1 3 3L8 19l-4 1 1-4z"/><path d="M14.5 6.5l3 3"/>',
    "trash":    '<path d="M4 7h16"/><path d="M9 7V4.5h6V7"/><path d="M6 7l1 12.5h10L18 7"/><path d="M10 11v5M14 11v5"/>',
    "save":     '<path d="M5 4h11l3 3v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z"/><path d="M8 4v5h7V4"/><path d="M8 20v-6h8v6"/>',
    "open":     '<path d="M3 18V6a1 1 0 0 1 1-1h5l2 2h8a1 1 0 0 1 1 1v2"/>'
                '<path d="M3 18l2.6-7.2a1 1 0 0 1 1-.8H21l-2.7 7.3a1 1 0 0 1-.9.7H3z"/>',
    "export":   '<path d="M12 15V4"/><path d="M8 8l4-4 4 4"/><path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/>',
    "import":   '<path d="M12 4v11"/><path d="M8 11l4 4 4-4"/><path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/>',
    "copy":     '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    "close":    '<path d="M6 6l12 12M18 6L6 18"/>',
    "check":    '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "more":     '<circle cx="5" cy="12" r="1.3" fill="{c}"/><circle cx="12" cy="12" r="1.3" fill="{c}"/>'
                '<circle cx="19" cy="12" r="1.3" fill="{c}"/>',
    "filter":   '<path d="M4 5h16l-6 7.5V19l-4-2v-4.5z"/>',
    "play":     '<path d="M7 5v14l11-7z"/>',
    "stop":     '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "pause":    '<path d="M9 5v14M15 5v14"/>',
    "eye":      '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "external": '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "link":     '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/>'
                '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "lock":     '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "exit":     '<path d="M14 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4"/><path d="M10 16l-4-4 4-4"/><path d="M6 12h10"/>',
    "folder_plus": f'<path d="{_FOLDER_PATH}"/><path d="M12 10.5v5M9.5 13h5"/>',
    # ── Navegación ──
    "chevron_down":  '<path d="M6 9l6 6 6-6"/>',
    "chevron_up":    '<path d="M6 15l6-6 6 6"/>',
    "chevron_left":  '<path d="M15 6l-6 6 6 6"/>',
    "chevron_right": '<path d="M9 6l6 6-6 6"/>',
    "arrow_left":    '<path d="M19 12H5"/><path d="M11 6l-6 6 6 6"/>',
    "arrow_right":   '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
    "arrow_up":      '<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>',
    "home":          '<path d="M4 11l8-7 8 7"/><path d="M6 9.5V20h4.5v-5h3v5H18V9.5"/>',
    "list":          '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4.5 6v.01M4.5 12v.01M4.5 18v.01"/>',
    "grid":          '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/>'
                     '<rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>',
    # ── Estado / avisos ──
    "info":     '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.6v.01"/>',
    "warning":  '<path d="M12 3.5L2.8 19.5h18.4z"/><path d="M12 10v4.5"/><path d="M12 17.2v.01"/>',
    "error":    '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "success":  '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16.5 9.5"/>',
    "help":     '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.6v.6"/>'
                '<path d="M12 17v.01"/>',
    "dot":      '<circle cx="12" cy="12" r="4.5" fill="{c}" stroke="none"/>',
    "clock":    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    # ── Objetos / lugares ──
    "folder":   f'<path d="{_FOLDER_PATH}" fill="{{c}}" fill-opacity="0.18"/>',
    "file":     _FILE_BASE,
    "drive":    '<rect x="3" y="13" width="18" height="7" rx="2"/>'
                '<path d="M5 13l2.2-7.3A1 1 0 0 1 8.2 5h7.6a1 1 0 0 1 1 .7L19 13"/><path d="M7 16.5v.01M10 16.5v.01"/>',
    "monitor":  _MONITOR,
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2"/><path d="M7 9.5l3 2.5-3 2.5"/><path d="M12.5 15h4.5"/>',
    "network":  '<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/>'
                '<rect x="15" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M6 16v-2h12v2"/>',
    "server":   '<rect x="4" y="4" width="16" height="7" rx="1.5"/><rect x="4" y="13" width="16" height="7" rx="1.5"/>'
                '<path d="M8 7.5v.01M8 16.5v.01"/>',
    "user":     '<circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5"/>',
    "calendar": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "chip":     '<rect x="7" y="7" width="10" height="10" rx="1.5"/>'
                '<path d="M10 4v3M14 4v3M10 17v3M14 17v3M4 10h3M4 14h3M17 10h3M17 14h3"/>',
    "language": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
                '<path d="M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "moon":     '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "app":      '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M6.5 6.5v.01M9 6.5v.01"/>',
    # ── Red: protocolos y servicios (metáforas genéricas, sin logos de marcas) ──
    "mail":         '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/>',
    "ssh":          _TERM_FRAME + _LOCK_BADGE,
    "telnet":       _TERM_FRAME + _OPEN_LOCK_BADGE,          # candado abierto: sin cifrado
    "sftp":         _FOLDER_PART + _LOCK_BADGE,
    "ftp":          _FOLDER_PART + '<path d="M15.5 21v-6M13.8 16.7l1.7-1.7 1.7 1.7M19.5 15v6M17.8 19.3l1.7 1.7 1.7-1.7"/>',
    "vnc":          _MONITOR + '<path d="M10 7.5v5.5l1.6-1.4 1.2 2.4 1-.5-1.2-2.4h2.2z"/>',
    "rdp":          _MONITOR + '<path d="M9 12.5l5-5M10.5 7.5H14V11"/>',
    "wsl":          _WINDOW + '<path d="M7 12l2.5 2L7 16"/><path d="M11.5 16.5h4.5"/>',
    "web":          _WINDOW + '<circle cx="12" cy="14.5" r="3.2"/><path d="M8.8 14.5h6.4"/>',
    "https":        _WINDOW + '<rect x="9.5" y="13" width="5" height="4" rx="0.8"/><path d="M10.7 13v-1.2a1.3 1.3 0 0 1 2.6 0V13"/>',
    "websocket":    '<path d="M4 9h14"/><path d="M15 6l3 3-3 3"/><path d="M20 15H6"/><path d="M9 12l-3 3 3 3"/>',
    "cloud":        _CLOUD,
    "cloud_sync":   _CLOUD + '<path d="M9.8 14a2.3 2.3 0 0 1 4.1-1.2M14.2 15a2.3 2.3 0 0 1-4.1 1.2"/>'
                             '<path d="M14.2 11.6v1.4h-1.4M9.8 17.4V16h1.4"/>',
    "cloud_folder": _CLOUD + '<path d="M9.3 16.3v-3a.6.6 0 0 1 .6-.6h1.5l.8.8h2.2a.6.6 0 0 1 .6.6v2.2z"/>',
    "cloud_upload": _CLOUD + '<path d="M12 16.8v-4.6M10 14.2l2-2 2 2"/>',
    "share_folder": f'<path d="{_FOLDER_PATH}"/>' + '<circle cx="9.5" cy="14" r="1.2"/><circle cx="14.5" cy="11.8" r="1.2"/>'
                    '<circle cx="14.5" cy="16.2" r="1.2"/><path d="M10.6 13.5l2.8-1.2M10.6 14.5l2.8 1.2"/>',
    "dns":          '<path d="M12 3v18"/><path d="M12 5h6l2 2-2 2h-6"/><path d="M12 11H6l-2 2 2 2h6"/><path d="M9 21h6"/>',
    "tag":          '<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7L21 12.3a1 1 0 0 1 0 1.4l-7.3 7.3a1 1 0 0 1-1.4 0z"/>'
                    '<circle cx="8" cy="8" r="1.5"/>',
    # ── Red: equipos y conexión ──
    "router":       '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 16.5v.01M10 16.5v.01"/><path d="M14.5 16.5h3"/>'
                    '<path d="M16 13V9.5"/><path d="M13.2 7.2a4 4 0 0 1 5.6 0"/><path d="M11.2 5a6.8 6.8 0 0 1 9.6 0"/>',
    "switch":       '<rect x="2.5" y="7" width="19" height="10" rx="2"/>'
                    '<path d="M6 14v-2.5h2.2V14M10.9 14v-2.5h2.2V14M15.8 14v-2.5H18V14"/>',
    "wifi":         '<path d="M2.5 9a14 14 0 0 1 19 0"/><path d="M5.5 12.5a9.5 9.5 0 0 1 13 0"/><path d="M8.7 16a5 5 0 0 1 6.6 0"/>'
                    '<path d="M12 19.5v.01"/>',
    "ethernet":     '<path d="M4 5h16v10h-4v3.5H8V15H4z"/><path d="M8 8v3M10.7 8v3M13.3 8v3M16 8v3"/>',
    "camera":       '<rect x="3" y="7" width="13" height="10" rx="2"/><path d="M16 10.5l5-3v9l-5-3"/>',
    "printer":      '<path d="M7 9V4h10v5"/><rect x="3.5" y="9" width="17" height="7" rx="1.5"/><path d="M7 14h10v6H7z"/>',
    "database":     '<ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6"/>'
                    '<path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
    "container":    '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
    "laptop":       '<rect x="5" y="5" width="14" height="10" rx="1.2"/><path d="M3 19h18l-2-4H5z"/>',
    "phone":        '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 17.5h2"/>',
    "serial":       '<path d="M3 7h18l-2.5 10h-13z"/>'
                    '<path d="M7.5 10.5v.01M10.5 10.5v.01M13.5 10.5v.01M16.5 10.5v.01M9 13.5v.01M12 13.5v.01M15 13.5v.01"/>',
    "usb":          '<path d="M8 3h8v6H8z"/><path d="M10.5 5.5v1M13.5 5.5v1"/>'
                    '<path d="M6.5 9h11v6a3 3 0 0 1-3 3h-5a3 3 0 0 1-3-3z"/><path d="M12 18v3"/>',
    "plug":         _PLUG,
    "unplug":       _PLUG + '<path d="M3.5 3.5l17 17"/>',
    "power":        '<path d="M12 3v8"/><path d="M6.6 6.6a8 8 0 1 0 10.8 0"/>',
    # ── Red: seguridad y diagnóstico ──
    "shield":       _SHIELD,
    "vpn":          _SHIELD + '<rect x="9.25" y="11.5" width="5.5" height="4.5" rx="0.8"/>'
                              '<path d="M10.5 11.5v-1.3a1.5 1.5 0 0 1 3 0v1.3"/>',
    "firewall":     '<rect x="3" y="5" width="18" height="14" rx="1.5"/>'
                    '<path d="M3 9.7h18M3 14.3h18M9 5v4.7M15 5v4.7M6 9.7v4.6M12 9.7v4.6M18 9.7v4.6M9 14.3V19M15 14.3V19"/>',
    "key":          '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9"/><path d="M17 6l2.5 2.5M14.5 8.5l2 2"/>',
    "unlock":       '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/>',
    "certificate":  '<path d="M14 19H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5"/><path d="M7 8.5h10M7 12h5"/>'
                    '<circle cx="18" cy="15.5" r="2.5"/><path d="M16.8 17.7L16 21l2-1 2 1-.8-3.3"/>',
    "activity":     '<path d="M3 12h4l2.5-6 5 12 2.5-6h4"/>',
    "gauge":        '<path d="M4.5 18a9 9 0 1 1 15 0"/><path d="M12 13.5l4-4"/><circle cx="12" cy="13.5" r="1.2"/>',
    "route":        '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/>'
                    '<path d="M8 18h7.5a3 3 0 0 0 0-6h-7a3 3 0 0 1 0-6H16"/>',
    "radar":        '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l6-6"/>'
                    '<circle cx="12" cy="12" r="1" fill="{c}"/>',
    "broadcast":    '<circle cx="12" cy="12" r="2"/>'
                    '<path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8"/>',
    "transfer":     '<path d="M8 20V5M4 9l4-4 4 4"/><path d="M16 4v15M12 15l4 4 4-4"/>',
    # ── Varios ──
    "users":        '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.3 3.6-5 6.5-5s5.5 1.7 6.5 5"/>'
                    '<path d="M16 4.7a3.5 3.5 0 0 1 0 6.6"/><path d="M18 15.3c1.7.7 3 2.3 3.5 4.7"/>',
    "star":         '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    "pin":          '<path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z"/><path d="M12 14v7"/>',
    "bell":         '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    # ── Tipos de archivo extra ──
    "file_key":     _FILE_BASE + '<circle cx="10" cy="15.5" r="2"/><path d="M11.5 14l3.5-3.5M14 11.5l1.2 1.2"/>',
    "file_capture": _FILE_BASE + '<path d="M8 15h2l1.2-3 1.8 6 1.2-3H16"/>',
    "file_mail":    _FILE_BASE + '<rect x="8" y="12" width="8" height="6" rx="0.8"/><path d="M8.3 12.5l3.7 2.7 3.7-2.7"/>',
    # ── Tipos de archivo (página + glifo) ──
    "file_text":     _FILE_BASE + '<path d="M9 13h6M9 16.5h6M9 9.5h2"/>',
    "file_doc":      _FILE_BASE + '<path d="M8.5 12h7M8.5 15h7M8.5 18h4.5"/>',
    "file_sheet":    _FILE_BASE + '<rect x="8" y="11.5" width="8" height="6.5" rx="0.5"/><path d="M8 14.75h8M12 11.5v6.5"/>',
    "file_slides":   _FILE_BASE + '<rect x="8" y="11.5" width="8" height="5" rx="0.5"/><path d="M12 16.5v2"/>',
    "file_pdf":      _FILE_BASE + '<path d="M10 18.5v-7h2.25a2 2 0 0 1 0 4H10"/>',
    "file_archive":  _FILE_BASE + '<path d="M10 4.5v1.5M10 8v1.5M10 11.5v1.5"/><rect x="8.5" y="14.5" width="3" height="3.5" rx="0.6"/>',
    "file_image":    _FILE_BASE + '<circle cx="10" cy="12.5" r="1.25"/><path d="M8 18.5l3-3.5 2 2 1.5-1.5 1.5 3"/>',
    "file_audio":    _FILE_BASE + '<path d="M11 17V11l4.5-1.2v5.7"/><circle cx="9.5" cy="17" r="1.5"/><circle cx="14" cy="15.5" r="1.5"/>',
    "file_video":    _FILE_BASE + '<path d="M10 11.5v6l5-3z"/>',
    "file_code":     _FILE_BASE + '<path d="M10 12l-2.2 2.5 2.2 2.5M14 12l2.2 2.5-2.2 2.5"/>',
    "file_config":   _FILE_BASE + '<path d="M8.5 12.5h7M8.5 16.5h7"/>'
                                  '<circle cx="11" cy="12.5" r="1.1" fill="{c}"/><circle cx="13.5" cy="16.5" r="1.1" fill="{c}"/>',
    "file_exec":     _FILE_BASE + '<rect x="8" y="11" width="8" height="7" rx="1"/><path d="M8 13.3h8"/>',
    "file_disk":     _FILE_BASE + '<circle cx="12" cy="15" r="3.5"/><circle cx="12" cy="15" r="0.9"/>',
    "file_db":       _FILE_BASE + '<ellipse cx="12" cy="12" rx="3.5" ry="1.4"/>'
                                  '<path d="M8.5 12v5c0 .8 1.6 1.4 3.5 1.4s3.5-.6 3.5-1.4v-5"/>'
                                  '<path d="M8.5 14.5c0 .8 1.6 1.4 3.5 1.4s3.5-.6 3.5-1.4"/>',
    "file_firmware": _FILE_BASE + '<rect x="9.5" y="12.5" width="5" height="5" rx="0.8"/>'
                                  '<path d="M11 11v1.5M13 11v1.5M11 17.5V19M13 17.5V19M8 14h1.5M8 16h1.5M14.5 14H16M14.5 16H16"/>',
}

_ICON_PIXMAP_SIZES = (16, 20, 24, 32, 40, 48, 64)

_icon_cache = {}


def _svg_pixmap(name: str, color: str, px: int):
    """Renderiza un ícono a un QPixmap de px×px píxeles físicos."""
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    if QSvgRenderer is None or name not in ICON_SVG:
        return pm
    svg = (_SVG_HEAD + ICON_SVG[name] + "</svg>").replace("{c}", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    return pm


def _resolve_color(color: str) -> str:
    """Acepta una clave de THEME ('text_secondary', 'ok', 'ft_red'…) o un hex ya resuelto."""
    return THEME.get(color, color)


def icon(name: str, color: str = "text_secondary") -> "QIcon":
    """
    QIcon nítido en cualquier tamaño y DPI, con estado deshabilitado automático.
    color: clave de THEME. Ej.: icon("save"), icon("success", "ok"), icon("save", "text_on_accent").
    Debe llamarse desde el hilo principal (crea QPixmap).
    """
    key = (name, color)
    if key not in _icon_cache:
        ico = QIcon()
        normal, disabled = _resolve_color(color), THEME["disabled_text"]
        for px in _ICON_PIXMAP_SIZES:
            ico.addPixmap(_svg_pixmap(name, normal, px), QIcon.Normal, QIcon.Off)
            ico.addPixmap(_svg_pixmap(name, disabled, px), QIcon.Disabled, QIcon.Off)
        _icon_cache[key] = ico
    return _icon_cache[key]


def icon_pixmap(name: str, size: int = 16, color: str = "text_secondary"):
    """QPixmap HiDPI para QLabel (avisos, estados vacíos, diálogos)."""
    dpr = QGuiApplication.instance().devicePixelRatio() if QGuiApplication.instance() else 1.0
    pm = _svg_pixmap(name, _resolve_color(color), int(round(size * dpr)))
    pm.setDevicePixelRatio(dpr)
    return pm


def icon_label(name: str, size: int = 16, color: str = "text_secondary") -> "QLabel":
    lbl = QLabel()
    lbl.setPixmap(icon_pixmap(name, size, color))
    lbl.setFixedSize(size, size)
    return lbl


# Ícono de cada acción, por la misma clave de ayuda contextual que usan botones y menús:
# así un botón y su entrada de menú muestran siempre el mismo dibujo.
ACTION_ICONS = {
    # Proyecto y perfiles
    "open_project": "open", "select_folder": "open", "browse": "open", "browse_python": "open",
    "browse_pfx": "open", "recent": "clock", "detect_python": "search",
    "save_profile": "save", "load_profile": "open", "exit": "exit",
    # Compilación
    "build": "play", "cancel": "stop", "cancel_install": "stop", "rescan": "refresh",
    "show_command": "terminal", "show_spec": "file_code", "open_dist": "folder",
    # Listas
    "add": "plus", "add_file": "plus", "add_manual": "plus", "remove": "trash",
    "select_all": "check", "select_none": "minus",
    # pip
    "install_missing": "import", "install_selected": "import", "install_all": "import",
    "upgrade_all": "refresh",
    # Comando, log y análisis
    "copy": "copy", "save_spec": "save", "save_log": "save", "clear_log": "trash",
    "find_prev": "chevron_up", "find_next": "chevron_down", "find_log": "search",
    "an_apply": "check", "an_analyze": "search", "an_smoke": "play",
    # Ver / Ayuda
    "theme": "moon", "about": "info", "about_copy": "copy",
}

# Color del ícono según el tipo de botón
_BUTTON_ICON_COLORS = {
    "btnPrimary": "text_on_accent", "btnTable": "text_on_accent",
    "btnStart": "start_text", "btnStop": "stop_text", "btnSecondary": "accent_text",
}


def set_button_icon(btn, name, color=None):
    """Ícono de 16 px a la izquierda de un botón con texto; el color sigue al tipo de botón."""
    if name not in ICON_SVG:
        return
    if color is None:
        color = _BUTTON_ICON_COLORS.get(btn.objectName(), "text_secondary")
    btn.setIcon(icon(name, color))
    btn.setIconSize(QSize(ICON_SIZE["sm"], ICON_SIZE["sm"]))
    btn.setProperty("hasIcon", True)
