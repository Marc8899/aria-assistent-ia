# Modo juego: abrir un juego, grabar la partida con OBS y parar al cerrarlo.
# Lo usan tanto "abre el Red Dead" como "quiero jugar al Red Dead".
import os
import threading
import time
from typing import Callable

import psutil

from aria import config
from aria.aplicaciones import App
from aria.juegos import Juegos, PerfilJuego
from aria.obs import ControlOBS, ErrorOBS

ESPERA_MAXIMA_ARRANQUE = 300  # segundos que esperamos a que arranque el juego
GRACIA_CIERRE = 10            # segundos sin procesos del juego para darlo por cerrado (launcher -> juego)


def _juego_abierto(perfil: PerfilJuego | None, app: App) -> bool:
    """¿Hay algún proceso del juego? Por el .exe del perfil o, si no, por su carpeta de instalación."""
    if perfil and perfil.proceso:
        nombre = perfil.proceso.lower()
        return any((p.info["name"] or "").lower() == nombre for p in psutil.process_iter(["name"]))
    carpeta = os.path.normcase(os.path.abspath(app.carpeta)) + os.sep
    return any(
        p.info["exe"] and os.path.normcase(p.info["exe"]).startswith(carpeta)
        for p in psutil.process_iter(["exe"])
    )


class ModoJuego:
    def __init__(self, obs: ControlOBS, juegos: Juegos, avisar: Callable[[str], None]):
        self.obs = obs
        self.juegos = juegos
        self.avisar = avisar
        self._en_marcha: set[str] = set()  # juegos con una grabación vigilada

    def jugar(self, app: App) -> str:
        """Abre el juego y prepara la grabación en segundo plano. Devuelve un texto para el usuario."""
        perfil = self.juegos.buscar_por_app(app.nombre)
        espera = perfil.espera_segundos if perfil else config.ESPERA_GRABACION_SEGUNDOS
        puede_vigilar = bool((perfil and perfil.proceso) or app.carpeta)
        try:
            self.obs.asegurar_abierto()
            if perfil and perfil.escena_obs:
                self.obs.cambiar_escena(perfil.escena_obs)
        except ErrorOBS as e:
            app.abrir()
            return f"Abriendo {app.nombre}, pero NO voy a grabar: {e}"
        app.abrir()
        if app.nombre in self._en_marcha:
            return f"Abriendo {app.nombre} (ya estaba preparada su grabación)."
        self._en_marcha.add(app.nombre)
        threading.Thread(target=self._grabar, args=(app, perfil, espera, puede_vigilar), daemon=True).start()
        if puede_vigilar:
            return (f"Abriendo {app.nombre}. Empezaré a grabar {espera} s después de que arranque "
                    f"y pararé cuando lo cierres.")
        return f"Abriendo {app.nombre}. Empezaré a grabar en {espera} s; dime 'para de grabar' cuando acabes."

    def _grabar(self, app: App, perfil: PerfilJuego | None, espera: int, puede_vigilar: bool):
        try:
            if puede_vigilar:
                limite = time.time() + ESPERA_MAXIMA_ARRANQUE
                while not _juego_abierto(perfil, app):
                    if time.time() > limite:
                        self.avisar(f"[OBS] {app.nombre} no ha arrancado en 5 min; no grabo.")
                        return
                    time.sleep(2)
            time.sleep(espera)
            if self.obs.iniciar_grabacion():
                self.avisar(f"[OBS] Grabando la partida de {app.nombre}.")
            else:
                self.avisar("[OBS] Ya estaba grabando.")
            if not puede_vigilar:
                return
            cerrado_desde = None
            while True:
                time.sleep(3)
                if _juego_abierto(perfil, app):
                    cerrado_desde = None
                elif cerrado_desde is None:
                    cerrado_desde = time.time()
                elif time.time() - cerrado_desde >= GRACIA_CIERRE:
                    break
            ruta = self.obs.detener_grabacion()
            if ruta:
                self.avisar(f"[OBS] Has cerrado {app.nombre}. Partida guardada en: {ruta}")
        except Exception as e:
            self.avisar(f"[OBS] Problema con la grabación de {app.nombre}: {e}")
        finally:
            self._en_marcha.discard(app.nombre)
