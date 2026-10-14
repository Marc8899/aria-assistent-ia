# Registro de herramientas: el esquema para el modelo se genera a partir de la
# firma de la función, así que añadir una herramienta es escribir una función.
#
# Las herramientas van en grupos. Un grupo con palabras clave solo se ofrece al
# modelo cuando el usuario habla de ese tema: con muchas herramientas a la vez,
# un modelo de 14B elige peor.
import inspect
import re
from dataclasses import dataclass
from typing import Callable

from aria.texto import normalizar

TIPOS_JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    funcion: Callable
    parametros: dict[str, str]  # nombre del parámetro -> descripción
    grupo: str
    confirmar: bool  # True = el usuario tiene que aprobarla antes de ejecutarse
    requisito: Callable | None  # se comprueba ANTES de pedir aprobación (p. ej. "¿está conectado?")

    def esquema(self) -> dict:
        propiedades, requeridos = {}, []
        for nombre, param in inspect.signature(self.funcion).parameters.items():
            propiedades[nombre] = {
                "type": TIPOS_JSON.get(param.annotation, "string"),
                "description": self.parametros.get(nombre, ""),
            }
            if param.default is inspect.Parameter.empty:
                requeridos.append(nombre)
        return {
            "type": "function",
            "function": {
                "name": self.nombre,
                "description": self.descripcion,
                "parameters": {"type": "object", "properties": propiedades, "required": requeridos},
            },
        }

    def ejecutar(self, argumentos: dict) -> str:
        firma = inspect.signature(self.funcion).parameters
        convertidos = {}
        for nombre, valor in (argumentos or {}).items():
            if nombre not in firma:
                continue  # el modelo a veces inventa parámetros
            tipo = firma[nombre].annotation
            # Los modelos a veces mandan "3" en vez de 3.
            if tipo in (int, float) and isinstance(valor, str):
                valor = tipo(valor)
            convertidos[nombre] = valor
        return str(self.funcion(**convertidos))


class Registro:
    def __init__(self):
        self._herramientas: dict[str, Herramienta] = {}
        self._palabras: dict[str, tuple[str, ...] | None] = {}
        self._grupo = "base"

    def modulo(self, grupo: str, palabras_clave: tuple[str, ...] | None):
        """Las herramientas que se registren a continuación pertenecen a este grupo.
        palabras_clave=None significa que el grupo se ofrece siempre."""
        self._grupo = grupo
        self._palabras[grupo] = palabras_clave

    def herramienta(self, descripcion: str, /, confirmar: bool = False, requisito: Callable | None = None,
                    **parametros: str):
        """Decorador: @registro.herramienta("Qué hace", param="qué es")."""
        def decorador(funcion):
            self._herramientas[funcion.__name__] = Herramienta(
                funcion.__name__, descripcion, funcion, parametros, self._grupo, confirmar, requisito
            )
            return funcion
        return decorador

    def grupos_para(self, textos: list[str]) -> set[str]:
        texto = normalizar(" ".join(textos))
        return {
            grupo for grupo, palabras in self._palabras.items()
            if palabras is None or any(re.search(r"\b" + re.escape(p), texto) for p in palabras)
        }

    def esquemas(self, grupos: set[str] | None = None) -> list[dict]:
        return [h.esquema() for h in self._herramientas.values() if grupos is None or h.grupo in grupos]

    def ejecutar(self, nombre: str, argumentos: dict, confirmar: Callable | None = None) -> str:
        herramienta = self._herramientas.get(nombre)
        if herramienta is None:
            return f"Herramienta desconocida: {nombre}"
        if herramienta.requisito:
            try:
                herramienta.requisito()
            except Exception as e:
                return str(e)
        if herramienta.confirmar:
            if confirmar is None:
                return ("Esta acción necesita que el usuario la apruebe y desde aquí no se puede pedir. "
                        "Dile que la haga desde la terminal de Aria.")
            if not confirmar(nombre, argumentos):
                return ("El usuario ha RECHAZADO la acción en la ventana de aprobación, así que no se ha hecho. "
                        "No le pidas que confirme en el chat; pregúntale si quiere cambiar algo.")
        try:
            return herramienta.ejecutar(argumentos)
        except Exception as e:
            return f"Error en la herramienta {nombre}: {e}"
