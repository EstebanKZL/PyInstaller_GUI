"""Base de conocimiento: librerías que PyInstaller no empaqueta bien por sí solo.

Cada entrada se activa cuando el proyecto importa el módulo de la clave (nombre de
nivel superior o con puntos) y sugiere hidden-imports, --collect-all o --collect-data.
Solo se incluyen casos conocidos que los hooks oficiales no resuelven siempre.
"""

KNOWLEDGE = {
    "uvicorn": {
        "hidden": ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                   "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"],
        "note": "uvicorn carga loops/protocolos por nombre en runtime.",
    },
    "passlib": {
        "hidden": ["passlib.handlers.bcrypt"],
        "note": "passlib importa los handlers de hash dinámicamente.",
    },
    "tkcalendar": {
        "hidden": ["babel.numbers"],
        "note": "tkcalendar usa babel.numbers sin import estático.",
    },
    "pyttsx3": {
        "hidden": ["pyttsx3.drivers", "pyttsx3.drivers.sapi5", "pyttsx3.drivers.espeak", "pyttsx3.drivers.nsss"],
        "note": "pyttsx3 elige el driver de voz por nombre en runtime.",
    },
    "win32serviceutil": {
        "hidden": ["win32timezone"],
        "note": "Los servicios de Windows con pywin32 necesitan win32timezone.",
    },
    "plyer": {
        "collect_all": ["plyer"],
        "note": "plyer carga la implementación de cada plataforma dinámicamente.",
    },
    "engineio": {
        "hidden": ["engineio.async_drivers.threading"],
        "note": "python-engineio/socketio elige el async driver por nombre.",
    },
    "socketio": {
        "hidden": ["engineio.async_drivers.threading"],
        "note": "python-socketio elige el async driver de engineio por nombre.",
    },
    "customtkinter": {
        "collect_data": ["customtkinter"],
        "note": "customtkinter necesita sus temas .json y assets.",
    },
    "ttkbootstrap": {
        "collect_data": ["ttkbootstrap"],
        "note": "ttkbootstrap necesita sus temas y assets.",
    },
    "PIL": {
        "hidden": ["PIL._tkinter_finder"],
        "note": "Pillow + tkinter (ImageTk) necesita PIL._tkinter_finder.",
    },
    "PySide6": {"collect_all": ["PySide6"], "note": "Plugins de plataforma Qt (X11/Wayland/Windows)."},
    "PySide2": {"collect_all": ["PySide2"], "note": "Plugins de plataforma Qt (X11/Wayland/Windows)."},
    "PyQt5":   {"collect_all": ["PyQt5"],   "note": "Plugins de plataforma Qt (X11/Wayland/Windows)."},
    "PyQt6":   {"collect_all": ["PyQt6"],   "note": "Plugins de plataforma Qt (X11/Wayland/Windows)."},
}


def hints_for(imported_modules):
    """imported_modules: nombres importados (con o sin puntos). Devuelve [(clave, entrada)]."""
    names = set(imported_modules)
    tops = {n.split(".")[0] for n in names}
    return [(key, KNOWLEDGE[key]) for key in KNOWLEDGE if key in names or key in tops]
