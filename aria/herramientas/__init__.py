# Para añadir un grupo de herramientas: crea un módulo con GRUPO, PALABRAS_CLAVE
# (None = siempre disponible) y una función registrar(registro, ctx), y añádelo a MODULOS.
import sys

from aria.contexto import Contexto
from aria.herramientas import (
    aplicaciones, archivos, calculo, calendario, classroom, documentos, github, gmail, google_drive, guias, juegos,
    mi_api, planificacion, proyectos, recuerdos, salud, sistema, tareas, vida, web,
)
from aria.herramientas.base import Registro

MODULOS = (
    # Siempre disponibles
    tareas, recuerdos, calculo, web, guias,
    # Por tema
    vida, calendario, planificacion, proyectos, salud, archivos, documentos, sistema, aplicaciones, juegos,
    gmail, google_drive, classroom, github, mi_api,
)


SOLO_WINDOWS = (aplicaciones, juegos)


def crear_registro(ctx: Contexto) -> Registro:
    registro = Registro()
    for modulo in MODULOS:
        if sys.platform == "darwin" and modulo in SOLO_WINDOWS:
            continue
        registro.modulo(modulo.GRUPO, modulo.PALABRAS_CLAVE)
        modulo.registrar(registro, ctx)
    return registro
