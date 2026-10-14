# Ventanas y procesos abiertos: saber qué está abierto y cerrar aplicaciones.
# Cerrar es "amable" (como pulsar la X: la app puede pedir guardar). Solo se fuerza si se pide.
import os
import time
from dataclasses import dataclass

import psutil

from aria.texto import normalizar

# Nunca se cierran: el sistema, el propio Aria (python) y su cerebro (Ollama).
PROTEGIDOS = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe", "sihost.exe",
    "taskhostw.exe", "ctfmon.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "runtimebroker.exe", "applicationframehost.exe", "securityhealthsystray.exe",
    "python.exe", "pythonw.exe", "ollama.exe", "ollama app.exe", "conhost.exe", "lockapp.exe", "audiodg.exe",
}


@dataclass
class VentanaAbierta:
    hwnd: int
    titulo: str
    pid: int
    proceso: str      # nombre del .exe
    ruta: str         # ruta del .exe


def ventanas_abiertas() -> list[VentanaAbierta]:
    """Ventanas visibles de verdad (las que se ven en la barra de tareas)."""
    import win32con
    import win32gui
    import win32process

    resultado = []

    def visitar(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd) or win32gui.GetWindow(hwnd, win32con.GW_OWNER):
            return True
        titulo = win32gui.GetWindowText(hwnd).strip()
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if not titulo or estilo & win32con.WS_EX_TOOLWINDOW:
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proceso = psutil.Process(pid)
            nombre, ruta = proceso.name(), proceso.exe()
        except psutil.Error:
            return True
        if nombre.lower() in PROTEGIDOS and nombre.lower() not in ("explorer.exe",):
            return True
        resultado.append(VentanaAbierta(hwnd, titulo, pid, nombre, ruta))
        return True

    win32gui.EnumWindows(visitar, None)
    return resultado


def buscar_abiertas(nombre: str, carpeta_app: str = "") -> list[VentanaAbierta]:
    """Ventanas que coinciden con un nombre (título, .exe o carpeta de la app del catálogo)."""
    buscado = normalizar(nombre).replace(" ", "")
    coincidencias = []
    for v in ventanas_abiertas():
        exe = normalizar(os.path.splitext(v.proceso)[0]).replace(" ", "")
        titulo = normalizar(v.titulo).replace(" ", "")
        en_carpeta = carpeta_app and os.path.normcase(v.ruta).startswith(os.path.normcase(carpeta_app) + os.sep)
        if en_carpeta or buscado in exe or (len(exe) >= 4 and exe in buscado) or (len(buscado) >= 3 and buscado in titulo):
            coincidencias.append(v)
    return coincidencias


def cerrar(ventanas: list[VentanaAbierta], forzar: bool = False, espera: float = 6.0) -> tuple[list[str], list[str]]:
    """Devuelve (cerradas, que_siguen_abiertas)."""
    import win32con
    import win32gui

    pids = {v.pid for v in ventanas if v.proceso.lower() not in PROTEGIDOS}
    for v in ventanas:
        if v.pid in pids:
            try:
                win32gui.PostMessage(v.hwnd, win32con.WM_CLOSE, 0, 0)  # como pulsar la X
            except Exception:
                pass
    limite = time.time() + espera
    while time.time() < limite and any(_ventana_viva(v) for v in ventanas if v.pid in pids):
        time.sleep(0.3)
    siguen = [v for v in ventanas if v.pid in pids and _ventana_viva(v)]
    if forzar:
        for pid in {v.pid for v in siguen}:
            try:
                proceso = psutil.Process(pid)
                for hijo in proceso.children(recursive=True):
                    hijo.kill()
                proceso.kill()
            except psutil.Error:
                pass
        time.sleep(0.5)
        siguen = [v for v in siguen if psutil.pid_exists(v.pid)]
    cerradas = [v.titulo for v in ventanas if v.pid in pids and v not in siguen]
    return cerradas, [v.titulo for v in siguen]


def _ventana_viva(v: VentanaAbierta) -> bool:
    import win32gui
    return psutil.pid_exists(v.pid) and win32gui.IsWindow(v.hwnd) and win32gui.IsWindowVisible(v.hwnd)
