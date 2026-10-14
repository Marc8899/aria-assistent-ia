from datetime import datetime, timedelta

from aria.calendario import ErrorCalendario
from aria.tareas import ACTIVOS, ESTADOS, PRIORIDADES, interpretar_fecha, tiene_hora

GRUPO = "tareas"
PALABRAS_CLAVE = None  # siempre disponible


def registrar(registro, ctx):
    tareas, calendario = ctx.tareas, ctx.calendario

    def sincronizar_calendario(tarea) -> str:
        """Mira si la tarea ya está en el calendario y, si no, la añade."""
        if not tarea.fecha_limite or not calendario.conectado():
            return ""
        momento = datetime.fromisoformat(tarea.fecha_limite)
        try:
            existente = calendario.buscar_parecido(tarea.titulo, momento.date())
            if existente:
                tareas.actualizar(tarea.id, evento_id=existente.id)
                return f" Ya estaba en tu calendario: {existente.describir()}."
            if tiene_hora(tarea.fecha_limite):
                id_evento = calendario.crear(tarea.titulo, momento, momento + timedelta(hours=1), False, tarea.descripcion)
            else:
                id_evento = calendario.crear(tarea.titulo, momento.replace(hour=0, minute=0), None, True, tarea.descripcion)
            tareas.actualizar(tarea.id, evento_id=id_evento)
            return f" No estaba en el calendario: la he añadido a {calendario.nombre()}."
        except ErrorCalendario as e:
            return f" (No he podido revisar el calendario: {e})"
        except Exception as e:
            return f" (Error con el calendario: {e})"

    @registro.herramienta(
        "Crea una tarea pendiente del usuario (algo que tiene que hacer). Si tiene fecha y hay calendario "
        "conectado, comprueba si ya está en el calendario y si no, la añade.",
        titulo="Qué hay que hacer, breve y empezando por un verbo",
        fecha_limite="Cuándo vence: 'AAAA-MM-DD HH:MM' o 'AAAA-MM-DD'. Calcúlala a partir de la fecha "
                     "actual del contexto. Vacío si no tiene fecha.",
        prioridad=f"Una de: {', '.join(PRIORIDADES)}",
        descripcion="Detalles opcionales",
        proyecto="Nombre o id del proyecto al que pertenece (opcional)",
    )
    def crear_tarea(titulo: str, fecha_limite: str = "", prioridad: str = "media", descripcion: str = "",
                    proyecto: str = "") -> str:
        id_proyecto = None
        if proyecto:
            p = tareas.buscar_proyecto(proyecto)
            if p is None:
                return f"No encuentro el proyecto '{proyecto}'. No he creado la tarea."
            id_proyecto = p.id
        tarea = tareas.crear(titulo, descripcion, prioridad, interpretar_fecha(fecha_limite), proyecto_id=id_proyecto)
        return "Tarea creada: " + tarea.describir(datetime.now(), tareas.nombre_proyecto(id_proyecto)) \
            + sincronizar_calendario(tarea)

    @registro.herramienta(
        "Lista las tareas del usuario con su estado y el tiempo que les queda.",
        estado=f"Filtrar por estado ({', '.join(ESTADOS)}), 'todas', o vacío para las activas",
        proyecto="Solo las de este proyecto (nombre o id)",
    )
    def listar_tareas(estado: str = "", proyecto: str = "") -> str:
        if estado == "todas":
            estados = ESTADOS
        elif estado:
            estados = (estado,)
        else:
            estados = ACTIVOS
        id_proyecto = None
        if proyecto:
            p = tareas.buscar_proyecto(proyecto)
            if p is None:
                return f"No encuentro el proyecto '{proyecto}'."
            id_proyecto = p.id
        lista = tareas.listar(estados, id_proyecto)
        ahora = datetime.now()
        return "\n".join(t.describir(ahora, tareas.nombre_proyecto(t.proyecto_id)) for t in lista) \
            or "No hay tareas con ese filtro."

    @registro.herramienta(
        "Modifica una tarea: cambiar estado/columna del kanban (backlog, pendiente, en_curso, bloqueada, hecha, "
        "cancelada), título, fecha, prioridad o descripción. Deja vacíos los campos que no cambian.",
        id_tarea="Id numérico de la tarea",
        estado=f"Nuevo estado: {', '.join(ESTADOS)}",
        titulo="Nuevo título",
        fecha_limite="Nueva fecha 'AAAA-MM-DD HH:MM' o 'AAAA-MM-DD'",
        prioridad=f"Nueva prioridad: {', '.join(PRIORIDADES)}",
        descripcion="Nueva descripción",
    )
    def actualizar_tarea(id_tarea: int, estado: str = "", titulo: str = "", fecha_limite: str = "",
                         prioridad: str = "", descripcion: str = "") -> str:
        tarea = tareas.actualizar(
            id_tarea,
            estado=estado or None,
            titulo=titulo or None,
            fecha_limite=interpretar_fecha(fecha_limite) if fecha_limite else None,
            prioridad=prioridad or None,
            descripcion=descripcion or None,
        )
        if tarea is None:
            return f"No existe la tarea {id_tarea}."
        texto = "Tarea actualizada: " + tarea.describir(datetime.now(), tareas.nombre_proyecto(tarea.proyecto_id))
        if fecha_limite and not tarea.evento_id:
            texto += sincronizar_calendario(tarea)
        if estado == "hecha" and tarea.proyecto_id:
            siguiente = next(iter(tareas.listar(("pendiente", "en_curso"), tarea.proyecto_id)), None)
            backlog = next(iter(tareas.listar(("backlog",), tarea.proyecto_id)), None)
            if siguiente is None and backlog:
                tareas.actualizar(backlog.id, estado="pendiente")
                texto += f" Siguiente paso del proyecto movido a 'por hacer': [{backlog.id}] {backlog.titulo}."
            elif siguiente is None:
                texto += " El proyecto no tiene más pasos: ¿está terminado o falta definir el siguiente?"
        return texto

    @registro.herramienta(
        "Borra una tarea para siempre. Si solo está terminada, mejor marcarla como 'hecha'.",
        confirmar=True,
        id_tarea="Id numérico de la tarea",
    )
    def borrar_tarea(id_tarea: int) -> str:
        return "Tarea borrada." if tareas.borrar(id_tarea) else f"No existe la tarea {id_tarea}."
