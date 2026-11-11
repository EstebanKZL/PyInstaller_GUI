## PyInstaller GUI - PRO Builder 5.2.0

Compilador visual para PyInstaller y Nuitka: análisis de dependencias e imports, entorno aislado,
instaladores (Inno Setup, NSIS, AppImage), firma de código, paquete de release y generador de GitHub Actions.
Interfaz con tema oscuro (Grafito) y claro (Papel), en español e inglés.

### Novedades

- **Íconos** del sistema de diseño en botones, menús, búsqueda del log y proyectos recientes.
- **Acerca de** nuevo, con un botón para copiar los datos del sistema al reportar un problema.
- **Registro a archivo** y captura de errores: un error inesperado se muestra y queda anotado, sin cerrar el programa.
- Corregido: el nombre de la pestaña activa se cortaba.
- Desde 5.1.0: **Nuitka** como segundo compilador, confirmación antes de ejecutar un Python del proyecto o de
  un perfil, y artefactos con nombres `<App>-<versión>-<sistema>-<arq>-<variante>.<ext>`.

### Descargas

| Sistema | Arquitectura | Instalable | Portable |
|---|---|---|---|
| Windows 10 / 11 | 64 bits | `PyInstallerGUI-5.2.0-win-x64-setup.exe` | `PyInstallerGUI-5.2.0-win-x64-portable.zip` |
| Windows 7 / 8 | 64 bits | `PyInstallerGUI-5.2.0-win7-x64-setup.exe` | `PyInstallerGUI-5.2.0-win7-x64-portable.zip` |
| Windows 7 / 8 / 10 / 11 | 32 bits | `PyInstallerGUI-5.2.0-win7-x86-setup.exe` | `PyInstallerGUI-5.2.0-win7-x86-portable.zip` |
| Linux | x86_64 | `PyInstallerGUI-5.2.0-linux-x86_64.AppImage` | — |

- **Instalable (Windows):** asistente de Inno Setup con accesos directos, entrada en «Agregar o quitar programas» y desinstalador.
- **Portable (Windows):** descomprimí y ejecutá `PyInstallerGUI.exe`. No instala nada.
- **AppImage (Linux):** `chmod +x PyInstallerGUI-5.2.0-linux-x86_64.AppImage` y ejecutalo.
- Verificá la descarga con `SHA256SUMS.txt` (`sha256sum -c SHA256SUMS.txt`).

### Notas de compatibilidad

- **Windows 10/11 de 64 bits** usa Qt 6 (PySide6). Qt 6 no existe para 32 bits, por eso el paquete
  de **32 bits** usa Qt 5 (PySide2) y sirve para Windows 7, 8, 10 y 11.
- **Windows 7/8** usa Python 3.8 + Qt 5, la última combinación que corre ahí. Windows 7 necesita el
  Service Pack 1 y las actualizaciones KB2533623 y KB2999226. PyInstaller soporta oficialmente desde
  Windows 8: en Windows 7 funciona, pero no está garantizado.
- **Linux:** compilado en Ubuntu 22.04 (glibc 2.35); corre en distribuciones de esa época o más nuevas.
  No hay versión de 32 bits porque Qt no publica PySide para Linux x86.
- **Nuitka** necesita un compilador de C: en Windows lo descarga solo la primera vez (MinGW64); en Linux
  usa `gcc` y para onefile `patchelf`.
- Los ejecutables no están firmados: Windows SmartScreen puede mostrar «Editor desconocido»
  (Más información → Ejecutar de todas formas).

Cada paquete se probó en GitHub Actions abriendo la ventana del programa antes de publicarlo.
