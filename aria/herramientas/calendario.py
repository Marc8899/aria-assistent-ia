# Calendario (Apple iCloud o Google): ver agenda, crear, buscar y borrar eventos.
from datetime import date, datetime, timedelta

from aria.fechas import fecha_en_espanol

GRUPO = "calendario"
PALABRAS_CLAVE = ("calendario", "evento", "cita", "reunion", "agenda", "quedada", "quedado", "cumpleanos",
                  "medico", "dentista", "examen", "entrevista", "semana que viene", "esta semana", "manana tengo",
                  "que tengo", "libre")


def _fecha_hora(texto: str) -> tuple[datetime, bool]:
    texto = texto.strip().replace("T", " ")
    momento = datetime.fromisoformat(texto)
    return momento, len(texto) <= 10


def registrar(registro, ctx):
    cal = ctx.calendario

    @registro.herramienta(
        "Muestra los eventos del calendario del usuario en un periodo.",
        desde="Fecha de inicio 'AAAA-MM-DD' (vacío = hoy)",
        dias="Cuántos días mostrar (1 = solo ese día)",
    )
    def ver_agenda(desde: str = "", dias: int = 1) -> str:
        inicio = date.fromisoformat(desde) if desde else date.today()
        eventos = cal.eventos(datetime.combine(inicio, datetime.min.time()),
                              datetime.combine(inicio + timedelta(days=max(1, dias)), datetime.min.time()))
        cabecera = f"Agenda ({cal.nombre()}) desde el {fecha_en_espanol(datetime.combine(inicio, datetime.min.time()))}"
        return cabecera + ":\n" + ("\n".join(e.describir() for e in eventos) or "Sin eventos.")

    @registro.herramienta(
        "Crea un evento en el calendario. Antes comprueba que no exista ya uno igual.",
        titulo="Título del evento",
        inicio="'AAAA-MM-DD HH:MM', o 'AAAA-MM-DD' para un evento de todo el día",
        fin="'AAAA-MM-DD HH:MM' (vacío = 1 hora después)",
        descripcion="Notas opcionales",
    )
    def crear_evento(titulo: str, inicio: str, fin: str = "", descripcion: str = "") -> str:
        momento, todo_el_dia = _fecha_hora(inicio)
        existente = cal.buscar_parecido(titulo, momento.date(), margen_dias=0)
        if existente:
            return f"Ya existe un evento parecido: {existente.describir()}. No lo duplico."
        final = _fecha_hora(fin)[0] if fin else None
        id_evento = cal.crear(titulo, momento, final, todo_el_dia, descripcion)
        return f"Evento creado en {cal.nombre()}: {titulo} ({inicio}) · id {id_evento}"

    @registro.herramienta(
        "Busca eventos por texto en el calendario (próximos días o pasados recientes).",
        texto="Texto a buscar en el título",
        dias="Días hacia delante (y la mitad hacia atrás) en los que buscar",
    )
    def buscar_evento(texto: str, dias: int = 60) -> str:
        from aria.calendario import parecidos
        ahora = datetime.now()
        eventos = cal.eventos(ahora - timedelta(days=dias // 2), ahora + timedelta(days=dias))
        encontrados = [e for e in eventos if parecidos(texto, e.titulo)]
        return "\n".join(e.describir() for e in encontrados) or f"No hay eventos parecidos a '{texto}'."

    @registro.herramienta(
        "Borra un evento del calendario por su id (sale en ver_agenda o buscar_evento). El usuario lo aprobará.",
        confirmar=True,
        id_evento="Id del evento",
    )
    def borrar_evento(id_evento: str) -> str:
        return "Evento borrado." if cal.borrar(id_evento) else f"No he podido borrar el evento {id_evento}."
