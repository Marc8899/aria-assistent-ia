# Hábitos y time blocking (bloques de tiempo), y el plan del día que lo junta todo.
from datetime import date, datetime

from aria.calendario import ErrorCalendario
from aria.fechas import fecha_en_espanol
from aria.planificacion import TIPOS_BLOQUE

GRUPO = "planificacion"
PALABRAS_CLAVE = ("habito", "rutina", "racha", "bloque", "time block", "timeblock", "planifica", "planificar",
                  "organiza", "organizar", "horario", "plan del dia", "mi dia", "pomodoro", "hecho hoy",
                  "he meditado", "he leido", "he ido", "he hecho", "cada dia", "todos los dias")


def registrar(registro, ctx):
    plan, tareas = ctx.planificacion, ctx.tareas

    @registro.herramienta(
        "Crea un hábito a seguir. Puede ser en días concretos o un número de veces por semana.",
        nombre="Hábito, breve y concreto (p. ej. 'Leer 10 páginas')",
        dias="'diario', 'laborables', 'fines de semana' o días: 'lunes, miércoles, viernes'",
        veces_semana="Alternativa flexible: nº de veces por semana (0 = usar los días)",
        hora="Hora preferida 'HH:MM' (opcional)",
        descripcion="Detalles: disparador, versión mínima (regla de los 2 minutos)...",
    )
    def crear_habito(nombre: str, dias: str = "diario", veces_semana: int = 0, hora: str = "",
                     descripcion: str = "") -> str:
        h = plan.crear_habito(nombre, descripcion, dias, veces_semana, hora)
        return f"Hábito creado: [{h.id}] {h.nombre} · {h.frecuencia()}" + (f" a las {h.hora}" if h.hora else "")

    @registro.herramienta(
        "Marca un hábito como hecho (o deshecho) en un día. Devuelve la racha.",
        habito="Nombre o id del hábito",
        fecha="'AAAA-MM-DD' (vacío = hoy)",
        hecho="false para desmarcarlo",
    )
    def marcar_habito(habito: str, fecha: str = "", hecho: bool = True) -> str:
        h = plan.buscar_habito(habito)
        if h is None:
            nombres = ", ".join(f"[{x.id}] {x.nombre}" for x in plan.habitos()) or "ninguno"
            return f"No encuentro el hábito '{habito}'. Hábitos: {nombres}"
        dia = date.fromisoformat(fecha) if fecha else date.today()
        plan.marcar(h.id, dia, hecho)
        racha = plan.racha(h, date.today())
        unidad = "semanas" if h.veces_semana else "días"
        return f"'{h.nombre}' {'hecho' if hecho else 'desmarcado'} el {dia}. Racha: {racha} {unidad}."

    @registro.herramienta("Lista los hábitos con su racha, cumplimiento de los últimos 30 días y si toca hoy.")
    def ver_habitos() -> str:
        hoy = date.today()
        lineas = []
        for h in plan.habitos():
            cumplidos, total = plan.cumplimiento(h, hoy)
            estado = "hecho hoy" if plan.hecho(h.id, hoy) else ("toca hoy" if h.toca(hoy) else "hoy no toca")
            unidad = "sem" if h.veces_semana else "d"
            lineas.append(f"[{h.id}] {h.nombre} · {h.frecuencia()}{' a las ' + h.hora if h.hora else ''} · "
                          f"racha {plan.racha(h, hoy)} {unidad} · 30 días: {cumplidos}/{total} · {estado}")
        return "\n".join(lineas) or "No hay hábitos todavía."

    @registro.herramienta(
        "Reserva un bloque de tiempo (time blocking) para algo concreto. Avisa si se solapa con otro bloque o evento.",
        fecha="'AAAA-MM-DD'",
        inicio="'HH:MM'",
        fin="'HH:MM'",
        titulo="Qué se hará en el bloque",
        tipo=f"Uno de: {', '.join(TIPOS_BLOQUE)}",
        id_tarea="Id de la tarea asociada (0 = ninguna)",
        al_calendario="true para crearlo también como evento en el calendario",
    )
    def planificar_bloque(fecha: str, inicio: str, fin: str, titulo: str, tipo: str = "trabajo",
                          id_tarea: int = 0, al_calendario: bool = False) -> str:
        solapes = plan.solapes(fecha, inicio, fin)
        b = plan.crear_bloque(fecha, inicio, fin, titulo, tipo, id_tarea or None)
        texto = f"Bloque creado: [{b.id}] {fecha} {inicio}-{fin} {titulo} ({tipo})."
        if solapes:
            texto += " OJO, se solapa con: " + "; ".join(f"{s.inicio}-{s.fin} {s.titulo}" for s in solapes)
        if al_calendario:
            try:
                inicio_dt = datetime.fromisoformat(f"{fecha} {inicio}")
                evento = ctx.calendario.crear(titulo, inicio_dt, datetime.fromisoformat(f"{fecha} {fin}"))
                plan.asignar_evento(b.id, evento)
                texto += " Añadido también al calendario."
            except ErrorCalendario as e:
                texto += f" (No se ha podido añadir al calendario: {e})"
        return texto

    @registro.herramienta(
        "Borra un bloque de tiempo.",
        id_bloque="Id del bloque",
    )
    def borrar_bloque(id_bloque: int) -> str:
        b = plan.bloque(id_bloque)
        if b is None:
            return f"No existe el bloque {id_bloque}."
        plan.borrar_bloque(id_bloque)
        return f"Bloque borrado: {b.inicio}-{b.fin} {b.titulo}."

    @registro.herramienta(
        "Plan de un día: eventos del calendario, bloques de tiempo, tareas que vencen y hábitos que tocan. "
        "Úsalo para organizar el día o responder '¿qué tengo hoy?'.",
        fecha="'AAAA-MM-DD' (vacío = hoy)",
    )
    def ver_plan_dia(fecha: str = "") -> str:
        dia = date.fromisoformat(fecha) if fecha else date.today()
        momento = datetime.combine(dia, datetime.min.time())
        lineas = [f"Plan del {fecha_en_espanol(momento)}:"]
        agenda = [(b.inicio, f"{b.inicio}-{b.fin} [bloque {b.id}] {b.titulo} ({b.tipo})") for b in plan.bloques(dia.isoformat())]
        if ctx.calendario.conectado():
            try:
                for e in ctx.calendario.eventos_del_dia(dia):
                    hora = "00:00" if e.todo_el_dia else f"{e.inicio:%H:%M}"
                    texto = "todo el día" if e.todo_el_dia else f"{e.inicio:%H:%M}-{e.fin:%H:%M}"
                    agenda.append((hora, f"{texto} [calendario] {e.titulo}"))
            except Exception as error:
                lineas.append(f"(No he podido leer el calendario: {error})")
        lineas += [texto for _, texto in sorted(agenda)] or ["(sin bloques ni eventos)"]
        del_dia = [t for t in tareas.listar() if t.fecha_limite and t.fecha_limite[:10] <= dia.isoformat()]
        if del_dia:
            lineas.append("Tareas que vencen (o ya vencidas): " +
                          "; ".join(f"[{t.id}] {t.titulo} ({t.fecha_limite[11:]})" for t in del_dia))
        en_curso = [t for t in tareas.listar(("en_curso",)) if t not in del_dia]
        if en_curso:
            lineas.append("En curso: " + "; ".join(f"[{t.id}] {t.titulo}" for t in en_curso))
        habitos = [h for h in plan.habitos() if h.toca(dia)]
        if habitos:
            lineas.append("Hábitos: " + "; ".join(
                f"{h.nombre}{' ' + h.hora if h.hora else ''}{' (hecho)' if plan.hecho(h.id, dia) else ''}" for h in habitos))
        return "\n".join(lineas)
