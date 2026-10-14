# Proyectos (corto/medio/largo plazo), kanban, pasos accionables y kaizen.
from datetime import date, datetime, timedelta

from aria.tareas import COLUMNAS_KANBAN, ESTADOS_PROYECTO, HORIZONTES, interpretar_fecha

GRUPO = "proyectos"
PALABRAS_CLAVE = ("proyecto", "kanban", "objetivo", "meta", "pasos", "dividir", "divide", "desglosa", "kaizen",
                  "mejora", "mejorar", "revision", "repaso semanal", "backlog", "sprint", "largo plazo",
                  "corto plazo", "medio plazo", "progreso", "atascado", "siguiente paso", "accionable")


def registrar(registro, ctx):
    tareas, plan = ctx.tareas, ctx.planificacion

    def _proyecto(nombre: str):
        p = tareas.buscar_proyecto(nombre)
        if p is None:
            existentes = ", ".join(f"[{x.id}] {x.nombre}" for x in tareas.proyectos()) or "ninguno"
            raise ValueError(f"no encuentro el proyecto '{nombre}'. Proyectos: {existentes}")
        return p

    def _resumen(p) -> str:
        hechas, total = tareas.progreso(p.id)
        porcentaje = f"{100 * hechas // total} %" if total else "sin pasos"
        siguiente = next((t for t in tareas.listar(("en_curso", "pendiente"), p.id)), None)
        dias_quieto = (datetime.now() - datetime.fromisoformat(tareas.ultima_actividad(p.id))).days
        texto = (f"[{p.id}] {p.nombre} · {p.horizonte} plazo · {p.estado} · progreso {hechas}/{total} ({porcentaje})"
                 + (f" · objetivo {p.fecha_objetivo[:10]}" if p.fecha_objetivo else ""))
        if siguiente:
            texto += f"\n    siguiente paso: [{siguiente.id}] {siguiente.titulo}"
        elif p.estado == "activo" and total:
            texto += "\n    sin siguiente paso definido: hay que decidir el próximo paso accionable"
        if p.estado == "activo" and dias_quieto >= 14:
            texto += f"\n    ATENCIÓN: sin movimiento desde hace {dias_quieto} días"
        return texto

    @registro.herramienta(
        "Crea un proyecto: un resultado que requiere varios pasos. Define bien el resultado (cómo sabremos que "
        "está terminado). Después, divídelo en pasos con anadir_pasos.",
        nombre="Nombre corto del proyecto",
        horizonte=f"Plazo: {', '.join(HORIZONTES)} (corto: semanas; medio: meses; largo: un año o más)",
        resultado="Resultado esperado, concreto y medible",
        fecha_objetivo="Fecha objetivo 'AAAA-MM-DD' (opcional)",
        area="Área de la vida: trabajo, estudios, salud, personal, finanzas, ocio...",
        descripcion="Contexto y motivación (por qué importa)",
    )
    def crear_proyecto(nombre: str, horizonte: str = "corto", resultado: str = "", fecha_objetivo: str = "",
                       area: str = "", descripcion: str = "") -> str:
        p = tareas.crear_proyecto(nombre, descripcion, horizonte, resultado, interpretar_fecha(fecha_objetivo), area)
        return f"Proyecto creado: [{p.id}] {p.nombre} ({p.horizonte} plazo). Ahora conviene dividirlo en pasos accionables."

    @registro.herramienta(
        "Añade pasos accionables a un proyecto (cada uno es una tarea de su kanban). Cada paso debe empezar por un "
        "verbo, ser concreto y poder hacerse en una sentada (menos de ~2 h). El primero queda 'por hacer' y los "
        "demás en el backlog, salvo que se indique otra cosa.",
        proyecto="Nombre o id del proyecto",
        pasos="Un paso por línea, en orden. Opcional al final de la línea: ' | AAAA-MM-DD' como fecha límite",
        todos_por_hacer="true para poner todos los pasos en 'por hacer' en vez de en el backlog",
    )
    def anadir_pasos(proyecto: str, pasos: str, todos_por_hacer: bool = False) -> str:
        p = _proyecto(proyecto)
        hay_activos = bool(tareas.listar(("pendiente", "en_curso"), p.id))
        creadas = []
        for i, linea in enumerate(l.strip(" -•\t") for l in pasos.splitlines() if l.strip()):
            titulo, _, fecha = linea.partition("|")
            estado = "pendiente" if todos_por_hacer or (i == 0 and not hay_activos) else "backlog"
            t = tareas.crear(titulo.strip(), fecha_limite=interpretar_fecha(fecha), estado=estado, proyecto_id=p.id)
            creadas.append(f"[{t.id}] {t.titulo} ({COLUMNAS_KANBAN[estado]})")
        tareas.actualizar_proyecto(p.id)
        return f"{len(creadas)} pasos añadidos a '{p.nombre}':\n" + "\n".join(creadas)

    @registro.herramienta(
        "Muestra el tablero kanban de un proyecto: columnas Backlog, Por hacer, En curso, Bloqueada y Hecho.",
        proyecto="Nombre o id del proyecto",
    )
    def ver_proyecto(proyecto: str) -> str:
        p = _proyecto(proyecto)
        lineas = [_resumen(p)]
        if p.resultado:
            lineas.append(f"Resultado esperado: {p.resultado}")
        if p.descripcion:
            lineas.append(f"Por qué: {p.descripcion}")
        todas = tareas.listar(tuple(COLUMNAS_KANBAN), p.id)
        for estado, columna in COLUMNAS_KANBAN.items():
            de_columna = sorted((t for t in todas if t.estado == estado), key=lambda t: (t.orden, t.id))
            lineas.append(f"\n{columna.upper()} ({len(de_columna)})")
            lineas += [f"  [{t.id}] {t.titulo}" + (f" · {t.fecha_limite}" if t.fecha_limite else "") for t in de_columna]
        en_curso = sum(t.estado == "en_curso" for t in todas)
        if en_curso > 3:
            lineas.append(f"\nAviso: {en_curso} tareas en curso a la vez; el kanban recomienda no pasar de 3.")
        return "\n".join(lineas)

    @registro.herramienta(
        "Lista los proyectos con su progreso, siguiente paso y avisos (proyectos atascados o sin siguiente paso).",
        estado=f"Filtrar: {', '.join(ESTADOS_PROYECTO)} o 'todos' (vacío = activos y en pausa)",
    )
    def listar_proyectos(estado: str = "") -> str:
        estados = ESTADOS_PROYECTO if estado == "todos" else (estado,) if estado else ("activo", "en_pausa")
        proyectos = tareas.proyectos(estados)
        return "\n".join(_resumen(p) for p in proyectos) or "No hay proyectos con ese filtro."

    @registro.herramienta(
        "Modifica un proyecto: estado (activo, en_pausa, completado, abandonado), horizonte, resultado, fecha...",
        proyecto="Nombre o id del proyecto",
        estado=f"Nuevo estado: {', '.join(ESTADOS_PROYECTO)}",
        horizonte=f"Nuevo horizonte: {', '.join(HORIZONTES)}",
        resultado="Nuevo resultado esperado",
        fecha_objetivo="Nueva fecha objetivo 'AAAA-MM-DD'",
        nombre="Nuevo nombre",
    )
    def actualizar_proyecto(proyecto: str, estado: str = "", horizonte: str = "", resultado: str = "",
                            fecha_objetivo: str = "", nombre: str = "") -> str:
        p = _proyecto(proyecto)
        p = tareas.actualizar_proyecto(p.id, estado=estado, horizonte=horizonte, resultado=resultado,
                                       fecha_objetivo=interpretar_fecha(fecha_objetivo) if fecha_objetivo else None,
                                       nombre=nombre)
        return "Proyecto actualizado:\n" + _resumen(p)

    @registro.herramienta(
        "Revisión KAIZEN: reúne lo hecho en los últimos días, tareas vencidas, proyectos atascados, hábitos y las "
        "mejoras en marcha, para reflexionar con el usuario y proponer UNA mejora pequeña y concreta.",
        dias="Periodo a revisar en días (7 = revisión semanal)",
    )
    def revision_kaizen(dias: int = 7) -> str:
        hoy, desde = date.today(), datetime.now() - timedelta(days=dias)
        hechas = tareas.completadas_desde(desde)
        vencidas = tareas.urgentes(datetime.now())["vencidas"]
        lineas = [f"REVISIÓN DE LOS ÚLTIMOS {dias} DÍAS",
                  f"Tareas completadas: {len(hechas)}" + (": " + "; ".join(t.titulo for t in hechas[:15]) if hechas else ""),
                  f"Tareas vencidas sin hacer: {len(vencidas)}" + (": " + "; ".join(t.titulo for t in vencidas[:10]) if vencidas else "")]
        lineas.append("Proyectos:")
        lineas += ["  " + _resumen(p).replace("\n", "\n  ") for p in tareas.proyectos(("activo",))] or ["  (ninguno activo)"]
        lineas.append("Hábitos (cumplimiento en el periodo):")
        for h in plan.habitos():
            cumplidos, total = plan.cumplimiento(h, hoy, dias)
            lineas.append(f"  {h.nombre}: {cumplidos}/{total} · racha {plan.racha(h, hoy)}")
        mejoras = plan.mejoras()
        lineas.append("Mejoras kaizen en marcha:")
        lineas += [f"  [{m['id']}] ({m['estado']}) {m['mejora']} — porque: {m['observacion']}" for m in mejoras] \
            or ["  (ninguna)"]
        lineas.append("Preguntas guía: ¿Qué fue bien? ¿Qué costó o se repitió como problema? ¿Qué cambio "
                      "pequeño (1 %) probamos esta semana? ¿Las mejoras en marcha funcionan?")
        return "\n".join(lineas)

    @registro.herramienta(
        "Registra una mejora kaizen (un cambio pequeño para probar) o actualiza una existente.",
        mejora="El cambio pequeño y concreto a probar (para crear una nueva)",
        observacion="El problema o la observación que la motiva",
        area="Área: trabajo, estudios, salud, hogar...",
        id_mejora="Para actualizar una mejora existente (0 = crear nueva)",
        estado="Al actualizar: propuesta, probando, adoptada o descartada",
        resultado="Al actualizar: qué tal ha funcionado",
    )
    def registrar_mejora(mejora: str = "", observacion: str = "", area: str = "", id_mejora: int = 0,
                         estado: str = "", resultado: str = "") -> str:
        if id_mejora:
            ok = plan.actualizar_mejora(id_mejora, estado, resultado)
            return "Mejora actualizada." if ok else f"No existe la mejora {id_mejora}."
        if not mejora:
            return "Falta la mejora a registrar."
        id_nueva = plan.registrar_mejora(observacion, mejora, area)
        return f"Mejora kaizen [{id_nueva}] registrada como 'propuesta'. En la próxima revisión veremos si funciona."
