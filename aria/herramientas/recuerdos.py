import re
from datetime import date

from aria.memoria import CATEGORIAS
from aria.texto import parece_secreto

GRUPO = "recuerdos"
PALABRAS_CLAVE = None  # siempre disponible


def registrar(registro, ctx):
    memoria = ctx.memoria

    @registro.herramienta(
        "Guarda un dato duradero sobre el usuario: quién es, su gente, su historia, gustos, salud, trabajo, "
        "objetivos... Un dato por llamada, en una frase autocontenida y en TERCERA persona (que se entienda sin "
        "contexto). NO la uses para tareas pendientes (crear_tarea) ni para el diario del día (escribir_diario).",
        texto="El dato en tercera persona, p. ej. 'Su hermana se llama Ana, tiene 25 años y vive en Valencia' "
              "(nunca 'mi hermana...')",
        categoria=f"Una de: {', '.join(CATEGORIAS)}",
        importancia="1-5. 5 = esencial (nombre, familia cercana, salud importante, valores); 3 = normal; 1 = anécdota",
        sobre="De quién o de qué trata, para encontrarlo luego (p. ej. 'Ana (hermana)', 'trabajo en Acme')",
        fecha_evento="SOLO si el dato es un suceso pasado con fecha conocida ('2019', '2021-09'). "
                     "Vacío para datos que no son sucesos. Nunca pongas la fecha de hoy",
    )
    def guardar_memoria(texto: str, categoria: str = "otros", importancia: int = 3, sobre: str = "",
                        fecha_evento: str = "") -> str:
        if parece_secreto(texto) or re.search(r"contrase[ñn]a|password|token|clave de", texto, re.I):
            return ("NO guardado: nunca se guardan contraseñas ni tokens en la memoria. Dile al usuario que use "
                    "el comando /conectar correspondiente y que, si la ha escrito en el chat, la anule y cree otra.")
        if fecha_evento.startswith(date.today().isoformat()):
            fecha_evento = ""  # el modelo a veces pone la fecha de hoy a datos que no son sucesos
        texto = re.sub(r"^(mi|mis)\s", lambda m: "Su " if m.group(1).lower() == "mi" else "Sus ", texto.strip(),
                       flags=re.I)
        id_memoria, es_nueva = memoria.guardar(texto, categoria, importancia, sobre, fecha_evento)
        return f"Guardado (id {id_memoria})." if es_nueva else f"Ya lo sabía (id {id_memoria})."

    @registro.herramienta(
        "Busca en la memoria a largo plazo y en el diario lo que se sabe sobre algo o alguien. Úsala antes de "
        "decir que no sabes algo del usuario.",
        consulta="Qué buscar (persona, tema, palabra clave)",
        categoria=f"Limitar a una categoría ({', '.join(CATEGORIAS)})",
    )
    def buscar_memoria(consulta: str, categoria: str = "") -> str:
        recuerdos = memoria.buscar(consulta, 15, categoria)
        diario = [] if categoria else memoria.buscar_diario(consulta, 5)
        lineas = [r.describir() for r in recuerdos]
        lineas += [f"(diario {f}) {t[:300]}" for _, f, t, _ in diario]
        return "\n".join(lineas) or f"No recuerdo nada sobre '{consulta}'."
