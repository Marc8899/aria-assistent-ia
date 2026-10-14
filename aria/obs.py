# Control de OBS Studio a través de su servidor WebSocket (OBS 28 o superior).
import logging
import time

import obsws_python as obsws

from aria import config, secretos
from aria.aplicaciones import IndiceApps

logging.getLogger("obsws_python").setLevel(logging.CRITICAL)


class ErrorOBS(Exception):
    pass


class ControlOBS:
    def __init__(self, apps: IndiceApps):
        self.apps = apps

    def _cliente(self, clave=None):
        clave = secretos.obtener("obs_clave") if clave is None else clave
        try:
            return obsws.ReqClient(host=config.OBS_HOST, port=config.OBS_PUERTO, password=clave or "", timeout=3)
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            raise ErrorOBS(
                "No puedo conectar con OBS: o no está abierto, o el servidor WebSocket no está activado "
                "(Herramientas > Ajustes del servidor WebSocket)."
            ) from e
        except obsws.error.OBSSDKError as e:
            raise ErrorOBS(
                "OBS ha rechazado la conexión: la contraseña del WebSocket no coincide. "
                "El usuario debe escribir /conectar obs y poner la contraseña correcta."
            ) from e

    def probar(self, clave: str) -> str:
        cliente = self._cliente(clave)
        try:
            return cliente.get_version().obs_version
        finally:
            cliente.disconnect()

    def asegurar_abierto(self, espera_maxima=45):
        """Conecta con OBS; si no está abierto, lo abre y espera a que responda."""
        try:
            self._cliente().disconnect()
            return
        except ErrorOBS as e:
            if "contraseña" in str(e):
                raise
        app, _ = self.apps.buscar("OBS Studio")
        if app is None:
            raise ErrorOBS("OBS Studio no aparece entre las aplicaciones instaladas.")
        app.abrir()
        limite = time.time() + espera_maxima
        while time.time() < limite:
            time.sleep(2)
            try:
                self._cliente().disconnect()
                return
            except ErrorOBS as e:
                if "contraseña" in str(e):
                    raise
        raise ErrorOBS("He abierto OBS pero su servidor WebSocket no responde. ¿Está activado?")

    def estado(self) -> dict:
        cliente = self._cliente()
        try:
            return {
                "grabando": cliente.get_record_status().output_active,
                "escena_actual": cliente.get_current_program_scene().current_program_scene_name,
                "escenas": [e["sceneName"] for e in reversed(cliente.get_scene_list().scenes)],
            }
        finally:
            cliente.disconnect()

    def cambiar_escena(self, escena: str):
        cliente = self._cliente()
        try:
            escenas = [e["sceneName"] for e in cliente.get_scene_list().scenes]
            if escena not in escenas:
                raise ErrorOBS(f"No existe la escena '{escena}'. Escenas: {', '.join(escenas)}")
            cliente.set_current_program_scene(escena)
        finally:
            cliente.disconnect()

    def iniciar_grabacion(self) -> bool:
        """Devuelve False si ya estaba grabando."""
        cliente = self._cliente()
        try:
            if cliente.get_record_status().output_active:
                return False
            cliente.start_record()
            return True
        finally:
            cliente.disconnect()

    def detener_grabacion(self) -> str | None:
        """Devuelve la ruta del vídeo, o None si no estaba grabando."""
        cliente = self._cliente()
        try:
            if not cliente.get_record_status().output_active:
                return None
            return cliente.stop_record().output_path
        finally:
            cliente.disconnect()
