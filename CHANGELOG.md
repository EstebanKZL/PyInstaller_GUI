# Changelog

Todos los cambios importantes de este proyecto. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones siguen
[Semantic Versioning](https://semver.org/lang/es/).

## [5.1.0] - 2026-11-11

### Agregado
- **Nuitka como segundo compilador.** Se elige en *Principal → Compilador*. Traduce el Python a C y compila
  un binario nativo, sin `.py` ni `.pyc` legibles. Usa las mismas opciones del formulario (onedir/onefile,
  consola, ícono, información de versión, imports ocultos, exclusiones, datos, `--collect-*`), activa solo
  los plugins de Qt y tkinter, y deja el resultado en `dist/<app>/` para que instaladores, AppImage y
  análisis funcionen igual que con PyInstaller. El entorno aislado instala Nuitka en lugar de PyInstaller.
- Convención de nombres para los artefactos: `<App>-<versión>-<sistema>-<arq>-<variante>.<ext>`
  (por ejemplo `MiApp-1.0.0-win-x64-setup.exe`, `MiApp-1.0.0-win7-x86-portable.zip`,
  `MiApp-1.0.0-linux-x86_64.AppImage`) y `SHA256SUMS.txt`. La arquitectura se lee del ejecutable compilado.

### Seguridad
- Un intérprete Python que viene de afuera ya no se ejecuta sin preguntar: el venv que trae la carpeta del
  proyecto y el `python_path` de un perfil cargado piden confirmación. La respuesta se recuerda junto con la
  huella del ejecutable y de `pyvenv.cfg`: si cambian, se vuelve a preguntar.

### Cambiado
- Los instaladores Inno Setup y NSIS, el ZIP portable y el AppImage usan la nueva convención; la plataforma
  *Windows 7* genera artefactos `win7`. Los instaladores eligen 32 o 64 bits según el ejecutable, no según
  el Python que corre el programa.
- El workflow de GitHub Actions que genera el programa nombra los paquetes con la convención, publica un
  `SHA256SUMS.txt` y crea la release con la CLI oficial `gh`.
- Los paquetes de esta release siguen la convención (`PyInstallerGUI-5.1.0-win-x64-setup.exe`, etc.). El
  Linux portable `.tar.gz` se reemplaza por el AppImage.
- Las preferencias se guardan como `EstebanKZL` (hay que elegir tema e idioma otra vez una sola vez).

### Corregido
- Cambiar de compilador o de Python mientras se verificaba el anterior podía cerrar el programa de golpe.

## [5.0.0] - 2026-11-07

Versión mayor: el programa se reorganizó por completo y suma análisis, distribución y una interfaz nueva.

### Agregado
- **Interfaz rediseñada:** temas Grafito (oscuro) y Papel (claro), menús *Archivo / Compilación / Ver / Ayuda*,
  badges de estado, ayuda contextual en cada control, log monoespaciado con colores y búsqueda, atajos de
  teclado, cronómetro y aviso del sistema al terminar un build.
- **Español e inglés** en toda la interfaz y en los mensajes del log. El idioma inicial es el del sistema.
- **Entorno aislado:** compilación en un venv limpio creado desde `requirements.txt`, reutilizado mientras no cambie.
- **Análisis estático de imports:** paquetes faltantes en `requirements.txt`, requisitos sin uso, imports
  dinámicos y una base de conocimiento de librerías que necesitan opciones especiales.
- **Análisis después del build:** módulos que PyInstaller no encontró (`warn-*.txt`), tamaño por paquete,
  diagnóstico del log con soluciones aplicables y prueba del ejecutable generado.
- **Distribución:** información de versión de Windows, `.ico`/`.icns` desde un PNG, instalador Inno Setup,
  firma de código (`signtool` / `codesign`), ZIP y `SHA256SUMS`, generador de workflow de GitHub Actions.
- Opciones `--collect-all`, `--collect-data` y `--copy-metadata`.
- **Modo línea de comandos** (`--profile ... --build`) que funciona sin PySide instalado.
- Paquetes de release para Windows 10/11 x64, Windows 7/8 x64, Windows 7-11 x86 y Linux x86_64,
  portables e instalables.
- Tests automáticos (pytest) e integración continua en Windows, Linux y macOS.

### Cambiado
- El código pasó de un único archivo a un paquete (`pyinstaller_gui/`) con un núcleo sin Qt.
  `BuildConfig` es la única fuente de verdad para el comando, el `.spec`, los perfiles y el build.
- El instalador NSIS agrega la entrada en «Agregar o quitar programas», página de licencia y un
  desinstalador que solo borra la carpeta de la app.
- La tarjeta "Cross-compile (Wine + Docker)" pasa a ser "Multiplataforma (GitHub Actions)".
- Las preferencias se guardan en una ubicación nueva; las de 4.4.0 se migran solas al primer inicio.
- La ventana usa el tamaño mínimo de 1280×720.

### Corregido
- Se borraba con `rmtree` la carpeta dist/build entera elegida por el usuario: ahora solo se borra la
  salida de la app.
- El `.spec` generado no era válido para PyInstaller 6 (faltaba `COLLECT` en onedir y las rutas de
  Windows no estaban escapadas).
- Paquetes como Pillow, opencv-python o beautifulsoup4 figuraban como "no instalados".
- `--collect-all=PIL` se agregaba a todos los builds, aunque el proyecto no usara Pillow.
- AppImage y NSIS ignoraban la carpeta dist personalizada.
- Al re-escanear se pisaba el ícono cargado desde un perfil.
- El comando copiado se rompía con rutas que tienen espacios.
- La interfaz se congelaba al validar Python o verificar PyInstaller.
- Cancelar dejaba procesos de PyInstaller vivos.
- `python -I` ignoraba los paquetes instalados con `pip install --user`.
- `requirements.txt` instalaba PySide2 y PySide6 a la vez.
- El bloqueo del modo onedir/onefile fallaba con algunas combinaciones de opciones.

## [4.4.0]

Versión original: interfaz en un único archivo con PySide6/PySide2, detección de Python, escaneo de
`requirements.txt`, instalación con pip, instalador NSIS, AppImage y perfiles JSON.

[5.0.0]: https://github.com/EstebanKZL/PyInstaller_GUI/releases/tag/v5.0.0
