# Catálogo de aplicaciones del PC, guardado en datos/aplicaciones.db.
# Fuentes: menú Inicio, accesos directos del escritorio, Steam, Epic, las carpetas de juegos
# que indique el usuario (romhacks, mods...) y los .exe añadidos a mano.
# Lo que decide el usuario (qué es un juego, entradas manuales) se conserva al refrescar.
import difflib
import json
import os
import re
import sqlite3
import subprocess
import time
import winreg
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from aria.texto import normalizar

CADUCIDAD_SEGUNDOS = 600
NO_SON_JUEGOS = re.compile(r"redistributable|runtime|proton|steamworks|dedicated server", re.I)
# .exe que no son el juego en sí (al escanear carpetas de juegos)
EXE_AUXILIARES = re.compile(
    r"unins|setup|install|crash|report|update|redist|vcredist|dxsetup|prereq|helper|notification|"
    r"elevate|cleanup|uninstall|config(urator)?$|7z|winrar", re.I)
PRIORIDAD_ORIGEN = {"manual": 0, "steam": 1, "epic": 2, "carpeta": 3, "escritorio": 4, "inicio": 5}

# Carpetas especiales que usa Windows en los AppID del menú Inicio
CARPETAS_CONOCIDAS = {
    "{6D809377-6AF0-444B-8957-A3773F02200E}": os.environ.get("ProgramW6432", r"C:\Program Files"),
    "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}": os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    "{F38BF404-1D43-42F2-9305-67DE0B28FC23}": os.environ.get("SystemRoot", r"C:\Windows"),
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}": os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
}


def _clave(nombre: str) -> str:
    """'The Witcher 2: Assassins…' y 'The Witcher 2 Assassins…' dan la misma clave."""
    return re.sub(r"[^a-z0-9]", "", normalizar(nombre))


@dataclass
class App:
    nombre: str
    tipo: str          # "windows", "steam", "epic" o "exe"
    destino: str       # AppID de Windows, id de Steam, URI de Epic o ruta del .exe/.lnk
    carpeta: str = ""  # carpeta de instalación: sirve para saber si el juego sigue abierto
    origen: str = ""   # de dónde salió (ver PRIORIDAD_ORIGEN)
    marcado_juego: bool | None = None  # decisión del usuario; None = automático

    @property
    def es_juego(self) -> bool:
        if self.marcado_juego is not None:
            return self.marcado_juego
        return self.tipo in ("steam", "epic") or self.origen == "carpeta"

    def abrir(self):
        if self.tipo == "windows":
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{self.destino}"])
        elif self.tipo == "steam":
            os.startfile(f"steam://rungameid/{self.destino}")
        elif self.tipo == "epic":
            os.startfile(self.destino)
        elif self.destino.lower().endswith(".lnk"):
            os.startfile(self.destino)  # el acceso directo ya trae su carpeta de trabajo
        else:
            # Muchos juegos y mods necesitan arrancar desde su propia carpeta.
            os.startfile(self.destino, cwd=self.carpeta or None)


# ---------- Detección ----------

def _powershell_json(comando: str):
    salida = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + comando],
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout.decode("utf-8", errors="replace").strip()
    datos = json.loads(salida or "[]")
    return [datos] if isinstance(datos, dict) else datos


def _ruta_de_appid(app_id: str) -> str:
    """'{GUID}\\obs-studio\\bin\\64bit\\obs64.exe' -> ruta real, si es un programa de escritorio."""
    for guid, base in CARPETAS_CONOCIDAS.items():
        if app_id.upper().startswith(guid):
            app_id = base + app_id[len(guid):]
            break
    return app_id if app_id.lower().endswith(".exe") and os.path.isfile(app_id) else ""


def _apps_menu_inicio() -> list[App]:
    apps = []
    for d in _powershell_json("Get-StartApps | ConvertTo-Json -Compress"):
        nombre, app_id = d.get("Name") or "", d.get("AppID") or ""
        if not nombre or app_id.startswith("http") or re.search(r"uninstall|desinstalar", nombre, re.I):
            continue
        ruta = _ruta_de_appid(app_id)
        apps.append(App(nombre, "windows", app_id, os.path.dirname(ruta), "inicio"))
    return apps


def _accesos_escritorio() -> list[App]:
    comando = (
        "$sh = New-Object -ComObject WScript.Shell; "
        "$dirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory')); "
        "Get-ChildItem -Path $dirs -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object { "
        "$l = $sh.CreateShortcut($_.FullName); "
        "[pscustomobject]@{ nombre = $_.BaseName; lnk = $_.FullName; destino = $l.TargetPath } } "
        "| ConvertTo-Json -Compress"
    )
    apps = []
    for d in _powershell_json(comando):
        destino = d.get("destino") or ""
        if not destino.lower().endswith(".exe") or not os.path.isfile(destino):
            continue
        nombre = re.sub(r"(\.exe)?\s*-\s*(acceso directo|shortcut)$", "", d["nombre"], flags=re.I)
        nombre = re.sub(r"\.exe$", "", nombre, flags=re.I)
        apps.append(App(nombre, "exe", d["lnk"], os.path.dirname(destino), "escritorio"))
    return apps


def _juegos_steam() -> list[App]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as clave:
            ruta_steam = Path(winreg.QueryValueEx(clave, "SteamPath")[0])
    except OSError:
        return []
    bibliotecas = {ruta_steam}
    vdf = ruta_steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for ruta in re.findall(r'"path"\s+"(.+?)"', vdf.read_text(encoding="utf-8", errors="replace")):
            bibliotecas.add(Path(ruta.replace("\\\\", "\\")))
    juegos = []
    for biblioteca in bibliotecas:
        for manifiesto in (biblioteca / "steamapps").glob("appmanifest_*.acf"):
            texto = manifiesto.read_text(encoding="utf-8", errors="replace")
            app_id = re.search(r'"appid"\s+"(\d+)"', texto)
            nombre = re.search(r'"name"\s+"(.+?)"', texto)
            carpeta = re.search(r'"installdir"\s+"(.+?)"', texto)
            if app_id and nombre and not NO_SON_JUEGOS.search(nombre.group(1)):
                ruta = str(biblioteca / "steamapps" / "common" / carpeta.group(1)) if carpeta else ""
                juegos.append(App(nombre.group(1), "steam", app_id.group(1), ruta, "steam"))
    return juegos


def _juegos_epic() -> list[App]:
    carpeta = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    juegos = []
    for item in carpeta.glob("*.item"):
        try:
            d = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("bIsApplication") is False or (d.get("MainGameAppName") or d.get("AppName")) != d.get("AppName"):
            continue  # DLC o complementos
        uri = (f"com.epicgames.launcher://apps/{d['CatalogNamespace']}%3A{d['CatalogItemId']}"
               f"%3A{d['AppName']}?action=launch&silent=true")
        juegos.append(App(d["DisplayName"], "epic", uri, d.get("InstallLocation", ""), "epic"))
    return juegos


def ejecutables_de_juego(carpeta: Path) -> list[Path]:
    """Los .exe que parecen juegos en una carpeta y sus subcarpetas (hasta 2 niveles)."""
    encontrados = list(carpeta.glob("*.exe")) + list(carpeta.glob("*/*.exe")) + list(carpeta.glob("*/*/*.exe"))
    return [e for e in encontrados if not EXE_AUXILIARES.search(e.stem)]


def _juegos_en_carpetas(carpetas: list[str]) -> list[App]:
    juegos = []
    for carpeta in carpetas:
        for exe in ejecutables_de_juego(Path(carpeta)):
            juegos.append(App(exe.stem, "exe", str(exe), str(exe.parent), "carpeta"))
    return juegos


# ---------- Catálogo ----------

class IndiceApps:
    def __init__(self, ruta):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.db.executescript(
            """CREATE TABLE IF NOT EXISTS aplicaciones (
                clave TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                destino TEXT NOT NULL,
                carpeta TEXT NOT NULL DEFAULT '',
                origen TEXT NOT NULL,
                es_juego INTEGER,   -- NULL = automático, 1 = sí, 0 = no (lo decide el usuario)
                visto TEXT
            );
            CREATE TABLE IF NOT EXISTS carpetas_juegos (ruta TEXT PRIMARY KEY);"""
        )
        self.db.commit()
        self._apps: list[App] = []
        self._cargado = 0.0

    def carpetas_juegos(self) -> list[str]:
        return [f[0] for f in self.db.execute("SELECT ruta FROM carpetas_juegos ORDER BY ruta")]

    def _sincronizar(self):
        """Vuelve a detectar todo y actualiza la base de datos sin perder lo que decidió el usuario."""
        detectadas = (_juegos_steam() + _juegos_epic() + _juegos_en_carpetas(self.carpetas_juegos())
                      + _accesos_escritorio() + _apps_menu_inicio())
        manuales = {f[0] for f in self.db.execute("SELECT destino FROM aplicaciones WHERE origen = 'manual'")}
        mejores: dict[str, App] = {}
        for app in detectadas:
            clave = _clave(app.nombre)
            if not clave or app.destino in manuales:
                continue
            actual = mejores.get(clave)
            if actual is None or PRIORIDAD_ORIGEN[app.origen] < PRIORIDAD_ORIGEN[actual.origen]:
                mejores[clave] = app
        ahora = datetime.now().isoformat(timespec="seconds")
        for clave, app in mejores.items():
            self.db.execute(
                "INSERT INTO aplicaciones (clave, nombre, tipo, destino, carpeta, origen, visto) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(clave) DO UPDATE SET "
                "nombre = excluded.nombre, tipo = excluded.tipo, destino = excluded.destino, "
                "carpeta = excluded.carpeta, origen = excluded.origen, visto = excluded.visto "
                "WHERE aplicaciones.origen != 'manual'",
                (clave, app.nombre, app.tipo, app.destino, app.carpeta, app.origen, ahora),
            )
        # Lo que ya no está instalado desaparece (salvo lo añadido a mano, mientras exista el archivo).
        self.db.execute("DELETE FROM aplicaciones WHERE origen != 'manual' AND (visto IS NULL OR visto != ?)", (ahora,))
        for clave, destino in self.db.execute("SELECT clave, destino FROM aplicaciones WHERE origen = 'manual'").fetchall():
            if not os.path.exists(destino):
                self.db.execute("DELETE FROM aplicaciones WHERE clave = ?", (clave,))
        self.db.commit()

    def todas(self, refrescar=False) -> list[App]:
        if refrescar or time.time() - self._cargado > CADUCIDAD_SEGUNDOS:
            self._sincronizar()
            self._cargado = time.time()
        filas = self.db.execute(
            "SELECT nombre, tipo, destino, carpeta, origen, es_juego FROM aplicaciones ORDER BY clave"
        ).fetchall()
        self._apps = [App(n, t, d, c, o, None if j is None else bool(j)) for n, t, d, c, o, j in filas]
        return self._apps

    def buscar(self, nombre: str) -> tuple[App | None, list[str]]:
        """Devuelve (app, sugerencias). app es None si no hay coincidencia clara."""
        apps = self.todas()
        # "el Silent Hill 2", "al Red Dead" -> sin artículo
        nombre = re.sub(r"^(el|la|los|las|al|del|un|una)\s+", "", nombre.strip(), flags=re.I)
        buscado = normalizar(nombre)
        por_clave = {_clave(a.nombre): a for a in apps}
        if _clave(nombre) in por_clave:
            return por_clave[_clave(nombre)], []
        por_nombre = {normalizar(a.nombre): a for a in apps}
        # Primero coincidencias al principio de una palabra ("obs" -> "OBS Studio", no "DirectVobSub").
        patron = re.compile(r"\b" + re.escape(buscado))
        for candidatos in ([a for a in apps if patron.search(normalizar(a.nombre))],
                           [a for a in apps if buscado in normalizar(a.nombre)]):
            candidatos.sort(key=lambda a: len(a.nombre))
            if len(candidatos) == 1:
                return candidatos[0], []
            if candidatos:
                return None, [a.nombre for a in candidatos[:8]]
        parecidos = difflib.get_close_matches(buscado, por_nombre, n=5, cutoff=0.6)
        if len(parecidos) == 1:
            return por_nombre[parecidos[0]], []
        return None, [por_nombre[p].nombre for p in parecidos]

    # ---------- Lo que decide el usuario ----------

    def marcar_juego(self, app: App, es_juego: bool):
        self.db.execute("UPDATE aplicaciones SET es_juego = ? WHERE clave = ?", (int(es_juego), _clave(app.nombre)))
        self.db.commit()

    def anadir_exe(self, nombre: str, ruta: Path, es_juego: bool = True) -> App:
        """Añade a mano un .exe (o .lnk). Si ya estaba con otro nombre, lo renombra."""
        carpeta = str(ruta.parent)
        self.db.execute("DELETE FROM aplicaciones WHERE destino = ? OR clave = ?", (str(ruta), _clave(nombre)))
        self.db.execute(
            "INSERT INTO aplicaciones (clave, nombre, tipo, destino, carpeta, origen, es_juego, visto) "
            "VALUES (?, ?, 'exe', ?, ?, 'manual', ?, ?)",
            (_clave(nombre), nombre, str(ruta), carpeta, int(es_juego), datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return App(nombre, "exe", str(ruta), carpeta, "manual", es_juego)

    def anadir_carpeta_juegos(self, carpeta: Path) -> list[App]:
        self.db.execute("INSERT OR IGNORE INTO carpetas_juegos (ruta) VALUES (?)", (str(carpeta),))
        self.db.commit()
        self.todas(refrescar=True)
        rutas = {str(e) for e in ejecutables_de_juego(carpeta)}
        return [a for a in self._apps if a.destino in rutas]

    def cerrar(self):
        self.db.close()
