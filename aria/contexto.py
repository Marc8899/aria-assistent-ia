# Lo que comparten las herramientas. Para un servicio nuevo, añádelo aquí y en construir().
from dataclasses import dataclass
from typing import Callable

from aria import config
from aria.aplicaciones import IndiceApps
from aria.calendario import Calendario
from aria.juegos import Juegos
from aria.memoria import Memoria
from aria.modo_juego import ModoJuego
from aria.obs import ControlOBS
from aria.planificacion import Planificacion
from aria.salud import Salud
from aria.tareas import Tareas


@dataclass
class Contexto:
    memoria: Memoria
    tareas: Tareas
    planificacion: Planificacion
    calendario: Calendario
    salud: Salud
    apps: IndiceApps
    obs: ControlOBS
    juegos: Juegos
    modo_juego: ModoJuego
    avisar: Callable[[str], None]  # para avisos que llegan en segundo plano (p. ej. "grabando")

    def cerrar(self):
        self.memoria.cerrar()
        self.tareas.cerrar()
        self.salud.cerrar()
        self.apps.cerrar()


def construir(avisar: Callable[[str], None] = print) -> Contexto:
    apps = IndiceApps(config.RUTA_APLICACIONES)
    obs = ControlOBS(apps)
    juegos = Juegos(config.RUTA_JUEGOS)
    tareas = Tareas(config.RUTA_TAREAS)
    return Contexto(
        memoria=Memoria(config.RUTA_DB),
        tareas=tareas,
        planificacion=Planificacion(tareas.db),
        calendario=Calendario(),
        salud=Salud(config.RUTA_SALUD),
        apps=apps,
        obs=obs,
        juegos=juegos,
        modo_juego=ModoJuego(obs, juegos, avisar),
        avisar=avisar,
    )
