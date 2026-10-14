# Masterclasses: guías paso a paso en aria/guias/*.md que Aria usa para enseñar.
# Para añadir una guía basta con crear otro .md en esa carpeta.
from pathlib import Path

from aria.texto import normalizar

GRUPO = "guias"
PALABRAS_CLAVE = None  # siempre disponible
CARPETA = Path(__file__).resolve().parent.parent / "guias"


def registrar(registro, ctx):
    temas = sorted(p.stem for p in CARPETA.glob("*.md"))

    @registro.herramienta(
        "Devuelve la guía paso a paso para ENSEÑAR al usuario un tema o ayudarle a conectar un servicio. "
        f"Temas disponibles: {', '.join(temas)}. Consúltala siempre antes de enseñar uno de estos temas "
        "o cuando una herramienta diga que un servicio no está conectado.",
        tema=f"Uno de: {', '.join(temas)}",
    )
    def consultar_guia(tema: str) -> str:
        buscado = normalizar(tema)
        for nombre in temas:
            if nombre in buscado or buscado in nombre:
                return ("(NOTA: el usuario NO ve esta guía. Escríbele tú el paso que toca con sus instrucciones "
                        "concretas: qué abrir, dónde pulsar, enlaces y comandos exactos. Nunca digas "
                        "'he explicado...' sin explicarlo.)\n\n"
                        + (CARPETA / f"{nombre}.md").read_text(encoding="utf-8"))
        return f"No hay guía sobre '{tema}'. Temas disponibles: {', '.join(temas)}."
