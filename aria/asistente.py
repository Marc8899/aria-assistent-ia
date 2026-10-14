# El "cerebro": conversación + bucle de herramientas. No sabe nada de la terminal,
# así que lo usan igual la CLI, la API y, más adelante, un programador de tareas.
import re
from datetime import datetime

import ollama

from aria import config
from aria.contexto import Contexto
from aria.herramientas.base import Registro
from aria.prompt import crear_system_prompt, nota_de_contexto

MENSAJE_INICIO = ("[Evento: el usuario acaba de abrir Aria. Salúdale según el momento del día y, si hay "
                  "tareas vencidas, para hoy o en curso, recuérdaselas en pocas palabras. Sé breve.]")


class ErrorModelo(Exception):
    pass


def comprobar_modelo(modelo: str):
    try:
        ollama.show(modelo)
    except Exception as e:
        raise ErrorModelo(
            f"No puedo usar el modelo '{modelo}'.\n"
            f"1) ¿Está abierto Ollama?  2) Ejecuta 'ollama list' y copia el nombre exacto en aria/config.py.\n"
            f"Detalle técnico: {e}"
        ) from e


def _rol(mensaje) -> str:
    return mensaje["role"] if isinstance(mensaje, dict) else mensaje.role


def _limpiar(texto: str) -> str:
    # Por si el modelo cuela su razonamiento en la respuesta.
    return re.sub(r"<think>.*?</think>", "", texto or "", flags=re.DOTALL).strip()


class Asistente:
    def __init__(self, registro: Registro, ctx: Contexto):
        self.registro = registro
        self.ctx = ctx
        self.reiniciar()

    def reiniciar(self):
        self.mensajes = [self._mensaje_sistema()]
        self._textos_recientes: list[str] = []

    def _mensaje_sistema(self) -> dict:
        memoria = self.ctx.memoria
        contenido = crear_system_prompt(config.NOMBRE_ASISTENTE, config.MODELO, memoria.nucleo(), memoria.contar())
        return {"role": "system", "content": contenido}

    def _recortar_historial(self):
        exceso = len(self.mensajes) - 1 - config.MAX_MENSAJES_HISTORIAL
        if exceso <= 0:
            return
        # Cortar siempre en un mensaje del usuario para no partir una ronda de herramientas.
        corte = 1 + exceso
        while corte < len(self.mensajes) and _rol(self.mensajes[corte]) != "user":
            corte += 1
        del self.mensajes[1:corte]

    def _llamar_modelo(self, herramientas: list[dict] | None):
        respuesta = ollama.chat(
            model=config.MODELO,
            messages=self.mensajes,
            tools=herramientas or None,
            think=config.PENSAR,
            options={"num_ctx": config.CONTEXTO_TOKENS},
        )
        self.mensajes.append(respuesta.message)
        return respuesta.message

    def responder(self, texto: str, al_usar_herramienta=None, confirmar=None) -> str:
        """Procesa un mensaje del usuario y devuelve la respuesta final.

        confirmar(nombre, argumentos) -> bool se llama antes de las acciones que
        necesitan aprobación; sin ella, esas acciones se rechazan.
        Si algo falla (o se interrumpe), la conversación vuelve exactamente al
        estado anterior a este mensaje y se relanza la excepción.
        """
        self._recortar_historial()
        self.mensajes[0] = self._mensaje_sistema()  # recoge recuerdos nuevos
        inicio, recientes_antes = len(self.mensajes), self._textos_recientes
        # Los grupos de herramientas se eligen por el tema de los últimos mensajes.
        self._textos_recientes = (self._textos_recientes + [texto])[-3:]
        herramientas = self.registro.esquemas(self.registro.grupos_para(self._textos_recientes))
        nota = nota_de_contexto(datetime.now(), self.ctx, "" if texto.startswith("[Evento") else texto)
        self.mensajes.append({"role": "user", "content": f"{nota}\n\n{texto}"})
        try:
            for _ in range(config.MAX_PASOS_HERRAMIENTAS):
                mensaje = self._llamar_modelo(herramientas)
                if not mensaje.tool_calls:
                    return _limpiar(mensaje.content)
                for llamada in mensaje.tool_calls:
                    nombre, argumentos = llamada.function.name, llamada.function.arguments
                    if al_usar_herramienta:
                        al_usar_herramienta(nombre, argumentos)
                    resultado = self.registro.ejecutar(nombre, argumentos, confirmar)
                    self.mensajes.append({"role": "tool", "content": resultado, "tool_name": nombre})
            # Demasiadas rondas: forzar una respuesta con lo que ya tiene.
            return _limpiar(self._llamar_modelo(None).content)
        except BaseException:
            del self.mensajes[inicio:]
            self._textos_recientes = recientes_antes
            raise

    def saludar(self, **opciones) -> str:
        return self.responder(MENSAJE_INICIO, **opciones)
