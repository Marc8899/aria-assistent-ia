# Utilidades de archivos: rutas con alias ("escritorio", "descargas"...), protección de carpetas del
# sistema, nombres libres (nunca se sobrescribe nada) y búsqueda con el índice de Windows.
import os
import re
import time
import urllib.parse
import winreg
from datetime import datetime, timezone
from pathlib import Path

from aria.texto import normalizar

INICIO = Path.home()
_CLAVES_CARPETAS = {
    "escritorio": "Desktop", "documentos": "Personal", "descargas": "{374DE290-123F-4565-9164-39C4925E467B}",
    "imagenes": "My Pictures", "fotos": "My Pictures", "musica": "My Music", "videos": "My Video",
}
CARPETAS_IGNORADAS = {"appdata", "node_modules", ".git", ".venv", "venv", "__pycache__", "$recycle.bin",
                      ".cache", "site-packages"}


def carpeta_especial(nombre: str) -> Path | None:
    nombre = normalizar(nombre)
    if nombre in ("inicio", "usuario", "home", "mi carpeta"):
        return INICIO
    clave = _CLAVES_CARPETAS.get(nombre)
    if not clave:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return Path(os.path.expandvars(winreg.QueryValueEx(k, clave)[0]))
    except OSError:
        return None


def resolver(ruta: str) -> Path:
    """'descargas/fotos', '~/x', '%USERPROFILE%\\x', 'C:\\x' -> Path absoluta."""
    texto = os.path.expandvars(os.path.expanduser(ruta.strip().strip('"').strip("'")))
    partes = re.split(r"[\\/]", texto, maxsplit=1)
    especial = carpeta_especial(partes[0])
    if especial:
        return especial / partes[1] if len(partes) > 1 and partes[1] else especial
    camino = Path(texto)
    return camino if camino.is_absolute() else INICIO / camino


def _protegidas() -> list[Path]:
    entorno = os.environ
    return [Path(p) for p in (
        entorno.get("SystemRoot", r"C:\Windows"), entorno.get("ProgramW6432", r"C:\Program Files"),
        entorno.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), entorno.get("ProgramData", r"C:\ProgramData"),
        str(INICIO / "AppData"),
    )]


def comprobar_escritura(ruta: Path):
    """Impide mover o escribir dentro de carpetas del sistema o de programas."""
    absoluta = ruta.resolve()
    for protegida in _protegidas():
        if absoluta == protegida or protegida in absoluta.parents:
            raise PermissionError(f"Por seguridad no modifico nada dentro de {protegida} (carpeta del sistema o de programas).")
    if absoluta.parent == absoluta:
        raise PermissionError("Por seguridad no modifico la raíz de una unidad.")


def ruta_libre(ruta: Path) -> Path:
    """Si ya existe, añade ' (1)', ' (2)'... para no sobrescribir nunca."""
    if not ruta.exists():
        return ruta
    for i in range(1, 1000):
        candidata = ruta.with_name(f"{ruta.stem} ({i}){ruta.suffix}")
        if not candidata.exists():
            return candidata
    raise FileExistsError(f"Demasiadas copias de {ruta.name}")


def expandir(patron: str) -> list[Path]:
    """Una ruta o un comodín ('descargas/*.pdf') -> lista de rutas existentes."""
    ruta = resolver(patron)
    if any(c in ruta.name for c in "*?["):
        return sorted(ruta.parent.glob(ruta.name))
    return [ruta] if ruta.exists() else []


def tamano_legible(bytes_: float) -> str:
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if bytes_ < 1024:
            return f"{bytes_:.0f} {unidad}" if unidad == "B" else f"{bytes_:.1f} {unidad}"
        bytes_ /= 1024
    return f"{bytes_:.1f} PB"


# ---------- Búsqueda ----------

def buscar_indice_windows(texto: str, carpeta: Path, contenido: bool, limite: int = 30) -> list[tuple[str, int, str]]:
    """Usa el índice de búsqueda de Windows (instantáneo y mira dentro de documentos)."""
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    seguro = texto.replace("'", "''").replace('"', "")
    condicion = f"System.FileName LIKE '%{seguro}%'"
    if contenido:
        condicion = f"({condicion} OR CONTAINS(*, '\"{seguro}*\"'))"
    ambito = carpeta.as_posix().replace("'", "''")
    condicion += "".join(f" AND System.ItemUrl NOT LIKE '%/{c}/%'" for c in sorted(CARPETAS_IGNORADAS)
                         if not c.startswith("$"))
    # System.ItemUrl da la ruta real (ItemPathDisplay la traduce: "C:\Usuarios\...\Documentos").
    sql = (f"SELECT TOP {limite * 4} System.ItemUrl, System.Size, System.DateModified FROM SYSTEMINDEX "
           f"WHERE SCOPE='file:{ambito}' AND {condicion} ORDER BY System.DateModified DESC")
    conexion = win32com.client.Dispatch("ADODB.Connection")
    conexion.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
    registros = win32com.client.Dispatch("ADODB.Recordset")
    resultados = []
    try:
        registros.Open(sql, conexion)
        while not registros.EOF:
            campos = registros.Fields
            fecha = campos.Item("System.DateModified").Value
            url = campos.Item("System.ItemUrl").Value or ""
            tamano = int(campos.Item("System.Size").Value or 0)
            ruta = str(Path(urllib.parse.unquote(url.removeprefix("file:").lstrip("/"))))
            registros.MoveNext()
            if any(parte.lower() in CARPETAS_IGNORADAS for parte in Path(ruta).parts[:-1]):
                continue  # entornos virtuales, cachés, AppData...: ruido
            if fecha:  # el índice guarda las fechas en UTC
                fecha = datetime(fecha.year, fecha.month, fecha.day, fecha.hour, fecha.minute,
                                 tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
            resultados.append((ruta, tamano, fecha or ""))
            if len(resultados) >= limite:
                break
    finally:
        try:
            registros.Close()
        except Exception:
            pass
        conexion.Close()
    return resultados


def buscar_recorriendo(texto: str, carpeta: Path, limite: int = 30, segundos: float = 15) -> list[tuple[str, int, str]]:
    """Plan B sin índice: recorre carpetas comparando nombres (sin tildes ni mayúsculas)."""
    buscado = normalizar(texto)
    limite_tiempo = time.time() + segundos
    resultados = []
    for raiz, carpetas, archivos in os.walk(carpeta):
        carpetas[:] = [c for c in carpetas if c.lower() not in CARPETAS_IGNORADAS and not c.startswith(".")]
        for nombre in archivos + carpetas:
            if buscado in normalizar(nombre):
                ruta = Path(raiz) / nombre
                try:
                    info = ruta.stat()
                    resultados.append((str(ruta), info.st_size, time.strftime("%Y-%m-%d %H:%M",
                                                                              time.localtime(info.st_mtime))))
                except OSError:
                    continue
                if len(resultados) >= limite:
                    return resultados
        if time.time() > limite_tiempo:
            break
    return resultados
