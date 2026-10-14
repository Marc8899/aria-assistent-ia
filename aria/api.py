# API HTTP de Aria: la puerta para que otros programas (el móvil, atajos, scripts, una web...) hablen con
# Aria y lean o guarden tus datos. Arranque: python main.py --api · Documentación: http://127.0.0.1:8765/docs
# Además publica en /mi/... los endpoints que el usuario cree en la carpeta mi_api/.
import importlib
import json
import pkgutil
import secrets
import threading
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from aria import config, copias
from aria import secretos as almacen
from aria.asistente import Asistente
from aria.contexto import construir
from aria.herramientas import crear_registro
from aria.memoria import CATEGORIAS
from aria.prompt import nota_de_contexto
from aria.salud import interpretar_ejercicios, interpretar_items
from aria.tareas import ACTIVOS, COLUMNAS_KANBAN, ESTADOS, interpretar_fecha

DESCRIPCION = """
Tu asistente, accesible desde cualquier programa. **Pulsa *Authorize* y pon tu clave** (comando `/api` en Aria).

* **general**: hablar con Aria (`/chat`), ver su contexto y exportar todo.
* **memoria** y **diario**: lo que Aria sabe de ti. Puedes volcar tu vida aquí desde otras apps.
* **tareas**, **proyectos**, **hábitos** y **plan**: tu sistema de productividad.
* **salud**: comidas, entrenos y perfil físico.
* **mi api**: los endpoints que construyas tú en la carpeta `mi_api/`.
"""


def clave_api() -> str:
    clave = almacen.obtener("api_clave")
    if not clave:
        clave = secrets.token_urlsafe(24)
        almacen.guardar("api_clave", clave)
    return clave


# ---------- Modelos de entrada ----------

class PeticionChat(BaseModel):
    mensaje: str
    sesion: str = Field("principal", description="Cada sesión es una conversación distinta")


class RecuerdoNuevo(BaseModel):
    texto: str
    categoria: str = Field("otros", description=", ".join(CATEGORIAS))
    importancia: int = Field(3, ge=1, le=5)
    sobre: str = ""
    fecha_evento: str = ""


class CambiosRecuerdo(BaseModel):
    texto: str | None = None
    categoria: str | None = None
    importancia: int | None = Field(None, ge=1, le=5)
    sobre: str | None = None


class EntradaDiario(BaseModel):
    texto: str
    animo: str = ""
    fecha: str = Field("", description="AAAA-MM-DD; vacío = hoy")


class TareaNueva(BaseModel):
    titulo: str
    descripcion: str = ""
    prioridad: str = "media"
    fecha_limite: str = ""
    estado: str = "pendiente"
    proyecto_id: int | None = None


class CambiosTarea(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    estado: str | None = None
    prioridad: str | None = None
    fecha_limite: str | None = None


class ProyectoNuevo(BaseModel):
    nombre: str
    horizonte: str = "corto"
    resultado: str = ""
    fecha_objetivo: str = ""
    area: str = ""
    descripcion: str = ""
    pasos: list[str] = Field(default_factory=list, description="Pasos accionables en orden")


class CambiosProyecto(BaseModel):
    nombre: str | None = None
    estado: str | None = None
    horizonte: str | None = None
    resultado: str | None = None
    fecha_objetivo: str | None = None


class HabitoNuevo(BaseModel):
    nombre: str
    dias: str = "diario"
    veces_semana: int = 0
    hora: str = ""
    descripcion: str = ""


class BloqueNuevo(BaseModel):
    fecha: str
    inicio: str
    fin: str
    titulo: str
    tipo: str = "trabajo"
    tarea_id: int | None = None


class ComidaNueva(BaseModel):
    alimentos: str = Field(..., description="'macarrones con tomate: 1 ración; pan: 40 g'")
    momento: str = ""
    fecha: str = ""


class EntrenoNuevo(BaseModel):
    tipo: str
    duracion_minutos: float
    ejercicios: str = Field("", description="'press banca: 4x8x60; sentadilla: 5x5x100'")
    intensidad: str = "media"
    distancia_km: float = 0
    notas: str = ""
    fecha: str = ""


class PerfilFisico(BaseModel):
    peso: float | None = None
    altura: float | None = None
    edad: int | None = None
    sexo: str | None = None
    actividad: str | None = None
    objetivo: str | None = None


def crear_app() -> FastAPI:
    clave = clave_api()
    try:
        copias.copia_diaria()
    except Exception as e:
        print(f"[aviso] Copia de seguridad diaria fallida: {e}")
    ctx = construir(avisar=lambda mensaje: print(f"[aviso] {mensaje}"))
    registro = crear_registro(ctx)
    sesiones: dict[str, Asistente] = {}
    candado = threading.RLock()  # el modelo y SQLite se usan de uno en uno
    cabecera = APIKeyHeader(name="X-API-Key", auto_error=False)

    def autorizar(valor: str | None = Security(cabecera)):
        if not valor or not secrets.compare_digest(valor, clave):
            raise HTTPException(401, "Falta la cabecera X-API-Key o no es correcta")

    app = FastAPI(title=f"API de {config.NOMBRE_ASISTENTE}", description=DESCRIPCION, version="2.0")
    protegido = [Depends(autorizar)]

    def ejecutar(funcion, *args, **kwargs):
        try:
            with candado:
                return funcion(*args, **kwargs)
        except ValueError as e:
            raise HTTPException(422, str(e))

    # ---------- General ----------

    @app.get("/estado", tags=["general"])
    def estado():
        """Comprueba que la API funciona (no necesita clave)."""
        return {"asistente": config.NOMBRE_ASISTENTE, "modelo": config.MODELO,
                "hora": datetime.now().isoformat(timespec="seconds")}

    @app.post("/chat", tags=["general"], dependencies=protegido)
    def chat(peticion: PeticionChat):
        """Habla con Aria como en la terminal. Devuelve la respuesta y las herramientas que ha usado.
        Las acciones que necesitan aprobación (enviar correos, mover archivos...) se rechazan desde la API."""
        usadas = []
        with candado:
            asistente = sesiones.setdefault(peticion.sesion, Asistente(registro, ctx))
            respuesta = asistente.responder(peticion.mensaje,
                                            al_usar_herramienta=lambda n, a: usadas.append({"herramienta": n, "argumentos": a}))
        return {"respuesta": respuesta, "herramientas": usadas}

    @app.get("/contexto", tags=["general"], dependencies=protegido)
    def contexto():
        """Lo que Aria tiene presente ahora mismo: hora, tareas urgentes, bloque actual, hábitos y calendario."""
        return {"contexto": ejecutar(nota_de_contexto, datetime.now(), ctx)}

    @app.get("/exportar", tags=["general"], dependencies=protegido)
    def exportar():
        """Todo lo que Aria sabe y registra, en un único JSON (copia de seguridad o para otra app)."""
        return ejecutar(copias.exportar, ctx)

    # ---------- Memoria y diario ----------

    @app.get("/memorias", tags=["memoria"], dependencies=protegido)
    def memorias(q: str = "", categoria: str = ""):
        """Todos los recuerdos, o los que coinciden con `q` (búsqueda de texto completo)."""
        resultado = ejecutar(ctx.memoria.buscar, q, 50, categoria) if q else ejecutar(ctx.memoria.todos, categoria)
        return [r.__dict__ for r in resultado]

    @app.get("/memorias/resumen", tags=["memoria"], dependencies=protegido)
    def resumen_memorias():
        """Cuántas cosas sabe Aria de ti en cada categoría."""
        with candado:
            todas = ctx.memoria.todos()
        return {"total": len(todas), "por_categoria": {c: sum(r.categoria == c for r in todas) for c in CATEGORIAS}}

    @app.post("/memorias", tags=["memoria"], dependencies=protegido, status_code=201)
    def nuevo_recuerdo(r: RecuerdoNuevo):
        id_memoria, nuevo = ejecutar(ctx.memoria.guardar, r.texto, r.categoria, r.importancia, r.sobre, r.fecha_evento)
        return {"id": id_memoria, "nuevo": nuevo}

    @app.patch("/memorias/{id_memoria}", tags=["memoria"], dependencies=protegido)
    def corregir_recuerdo(id_memoria: int, cambios: CambiosRecuerdo):
        if not ejecutar(ctx.memoria.actualizar, id_memoria, **cambios.model_dump(exclude_none=True)):
            raise HTTPException(404, "No existe ese recuerdo o no había cambios")
        return {"ok": True}

    @app.delete("/memorias/{id_memoria}", tags=["memoria"], dependencies=protegido, status_code=204)
    def olvidar_recuerdo(id_memoria: int):
        if not ejecutar(ctx.memoria.olvidar, id_memoria):
            raise HTTPException(404, "No existe ese recuerdo")

    @app.get("/diario", tags=["diario"], dependencies=protegido)
    def diario(desde: str = "", hasta: str = "", q: str = ""):
        if q:
            filas = ejecutar(ctx.memoria.buscar_diario, q, 50)
        else:
            filas = ejecutar(ctx.memoria.leer_diario, desde or (date.today() - timedelta(days=30)).isoformat(),
                             hasta or date.today().isoformat())
        return [{"id": i, "fecha": f, "texto": t, "animo": a} for i, f, t, a in filas]

    @app.post("/diario", tags=["diario"], dependencies=protegido, status_code=201)
    def escribir_diario(e: EntradaDiario):
        return {"id": ejecutar(ctx.memoria.escribir_diario, e.texto, e.animo, e.fecha)}

    # ---------- Tareas y proyectos ----------

    @app.get("/tareas", tags=["tareas"], dependencies=protegido)
    def listar_tareas(estado: str | None = None, proyecto_id: int | None = None):
        """Tareas activas, o las de un estado concreto (o `todas`)."""
        estados = ESTADOS if estado == "todas" else (estado,) if estado else ACTIVOS
        return ejecutar(ctx.tareas.listar, estados, proyecto_id)

    @app.post("/tareas", tags=["tareas"], dependencies=protegido, status_code=201)
    def crear_tarea(t: TareaNueva):
        return ejecutar(lambda: ctx.tareas.crear(t.titulo, t.descripcion, t.prioridad, interpretar_fecha(t.fecha_limite),
                                                 t.estado, t.proyecto_id))

    @app.patch("/tareas/{id_tarea}", tags=["tareas"], dependencies=protegido)
    def actualizar_tarea(id_tarea: int, cambios: CambiosTarea):
        datos = cambios.model_dump(exclude_none=True)
        if "fecha_limite" in datos:
            datos["fecha_limite"] = ejecutar(interpretar_fecha, datos["fecha_limite"])
        tarea = ejecutar(ctx.tareas.actualizar, id_tarea, **datos)
        if tarea is None:
            raise HTTPException(404, "No existe esa tarea")
        return tarea

    @app.delete("/tareas/{id_tarea}", tags=["tareas"], dependencies=protegido, status_code=204)
    def borrar_tarea(id_tarea: int):
        if not ejecutar(ctx.tareas.borrar, id_tarea):
            raise HTTPException(404, "No existe esa tarea")

    @app.get("/proyectos", tags=["proyectos"], dependencies=protegido)
    def proyectos(estado: str = ""):
        estados = (estado,) if estado else ("activo", "en_pausa")
        with candado:
            return [{**p.__dict__, "progreso": dict(zip(("hechas", "total"), ctx.tareas.progreso(p.id)))}
                    for p in ctx.tareas.proyectos(estados)]

    @app.post("/proyectos", tags=["proyectos"], dependencies=protegido, status_code=201)
    def crear_proyecto(p: ProyectoNuevo):
        def crear():
            proyecto = ctx.tareas.crear_proyecto(p.nombre, p.descripcion, p.horizonte, p.resultado,
                                                 interpretar_fecha(p.fecha_objetivo), p.area)
            for i, paso in enumerate(p.pasos):
                ctx.tareas.crear(paso, estado="pendiente" if i == 0 else "backlog", proyecto_id=proyecto.id)
            return proyecto
        return ejecutar(crear)

    @app.get("/proyectos/{id_proyecto}", tags=["proyectos"], dependencies=protegido)
    def ver_proyecto(id_proyecto: int):
        """El proyecto con su tablero kanban (tareas agrupadas por columna)."""
        with candado:
            p = ctx.tareas.proyecto(id_proyecto)
            if p is None:
                raise HTTPException(404, "No existe ese proyecto")
            tareas = ctx.tareas.listar(tuple(COLUMNAS_KANBAN), id_proyecto)
        return {**p.__dict__, "kanban": {columna: [t for t in tareas if t.estado == estado]
                                         for estado, columna in COLUMNAS_KANBAN.items()}}

    @app.patch("/proyectos/{id_proyecto}", tags=["proyectos"], dependencies=protegido)
    def actualizar_proyecto(id_proyecto: int, cambios: CambiosProyecto):
        datos = cambios.model_dump(exclude_none=True)
        if "fecha_objetivo" in datos:
            datos["fecha_objetivo"] = interpretar_fecha(datos["fecha_objetivo"])
        return ejecutar(ctx.tareas.actualizar_proyecto, id_proyecto, **datos)

    # ---------- Hábitos y plan ----------

    @app.get("/habitos", tags=["hábitos y plan"], dependencies=protegido)
    def habitos():
        hoy = date.today()
        with candado:
            plan = ctx.planificacion
            return [{**h.__dict__, "frecuencia": h.frecuencia(), "racha": plan.racha(h, hoy),
                     "hecho_hoy": plan.hecho(h.id, hoy), "toca_hoy": h.toca(hoy)} for h in plan.habitos()]

    @app.post("/habitos", tags=["hábitos y plan"], dependencies=protegido, status_code=201)
    def crear_habito(h: HabitoNuevo):
        return ejecutar(ctx.planificacion.crear_habito, h.nombre, h.descripcion, h.dias, h.veces_semana, h.hora)

    @app.post("/habitos/{id_habito}/marcar", tags=["hábitos y plan"], dependencies=protegido)
    def marcar_habito(id_habito: int, fecha: str = "", hecho: bool = True):
        with candado:
            h = ctx.planificacion.habito(id_habito)
            if h is None:
                raise HTTPException(404, "No existe ese hábito")
            ctx.planificacion.marcar(id_habito, date.fromisoformat(fecha) if fecha else date.today(), hecho)
            return {"racha": ctx.planificacion.racha(h, date.today())}

    @app.get("/plan", tags=["hábitos y plan"], dependencies=protegido)
    def plan_del_dia(fecha: str = ""):
        """Bloques de tiempo, eventos del calendario, tareas que vencen y hábitos de un día."""
        dia = date.fromisoformat(fecha) if fecha else date.today()
        with candado:
            eventos = []
            if ctx.calendario.conectado():
                try:
                    eventos = [e.__dict__ for e in ctx.calendario.eventos_del_dia(dia)]
                except Exception as e:
                    eventos = [{"error": str(e)}]
            return {
                "fecha": dia.isoformat(),
                "bloques": ctx.planificacion.bloques(dia.isoformat()),
                "eventos": eventos,
                "tareas": [t for t in ctx.tareas.listar() if t.fecha_limite and t.fecha_limite[:10] <= dia.isoformat()],
                "habitos": [{"nombre": h.nombre, "hora": h.hora, "hecho": ctx.planificacion.hecho(h.id, dia)}
                            for h in ctx.planificacion.habitos() if h.toca(dia)],
            }

    @app.post("/bloques", tags=["hábitos y plan"], dependencies=protegido, status_code=201)
    def crear_bloque(b: BloqueNuevo):
        return ejecutar(ctx.planificacion.crear_bloque, b.fecha, b.inicio, b.fin, b.titulo, b.tipo, b.tarea_id)

    @app.delete("/bloques/{id_bloque}", tags=["hábitos y plan"], dependencies=protegido, status_code=204)
    def borrar_bloque(id_bloque: int):
        if not ejecutar(ctx.planificacion.borrar_bloque, id_bloque):
            raise HTTPException(404, "No existe ese bloque")

    # ---------- Salud ----------

    @app.post("/comidas", tags=["salud"], dependencies=protegido, status_code=201)
    def registrar_comida(c: ComidaNueva):
        """Calcula calorías y macros aproximados con la base de datos de alimentos y lo guarda."""
        with candado:
            calculados, desconocidos = ctx.salud.calcular_items(interpretar_items(c.alimentos))
            if desconocidos:
                raise HTTPException(422, f"Alimentos desconocidos: {', '.join(desconocidos)}. "
                                         "Indica 'nombre: gramos: kcal' para estimarlos tú.")
            id_comida = ctx.salud.registrar_comida(calculados, c.momento, c.alimentos, c.fecha)
        return {"id": id_comida, "items": calculados, "kcal": sum(i["kcal"] for i in calculados)}

    @app.get("/nutricion", tags=["salud"], dependencies=protegido)
    def nutricion(fecha: str = ""):
        dia = fecha or date.today().isoformat()
        with candado:
            comidas = [dict(c) | {"items": json.loads(c["items"])} for c in ctx.salud.comidas(dia, dia)]
            entrenos = ctx.salud.entrenos(dia, dia)
            return {"fecha": dia, "comidas": comidas,
                    "totales": {k: round(sum(c[k] for c in comidas), 1) for k in ("kcal", "proteinas", "hidratos", "grasas")},
                    "quemadas_entrenando": sum(e["kcal"] for e in entrenos), "objetivos": ctx.salud.objetivos()}

    @app.post("/entrenos", tags=["salud"], dependencies=protegido, status_code=201)
    def registrar_entreno(e: EntrenoNuevo):
        id_entreno, kcal = ejecutar(ctx.salud.registrar_entreno, e.tipo, e.duracion_minutos, e.intensidad,
                                    e.distancia_km, interpretar_ejercicios(e.ejercicios), e.notas, e.fecha)
        return {"id": id_entreno, "kcal_estimadas": kcal}

    @app.get("/entrenos", tags=["salud"], dependencies=protegido)
    def entrenos(dias: int = 30):
        with candado:
            filas = ctx.salud.entrenos((date.today() - timedelta(days=dias)).isoformat(), date.today().isoformat())
        return [dict(f) | {"ejercicios": json.loads(f["ejercicios"])} for f in filas]

    @app.get("/perfil-fisico", tags=["salud"], dependencies=protegido)
    def ver_perfil():
        with candado:
            return {"perfil": ctx.salud.perfil(), "objetivos": ctx.salud.objetivos(),
                    "pesos": ctx.salud.historial_peso(30)}

    @app.patch("/perfil-fisico", tags=["salud"], dependencies=protegido)
    def cambiar_perfil(p: PerfilFisico):
        ejecutar(ctx.salud.actualizar_perfil, **p.model_dump(exclude_none=True))
        return ver_perfil()

    # ---------- La API del usuario: cada módulo de mi_api/ con un `router` se publica en /mi/... ----------
    import mi_api
    cargados = []
    for modulo in pkgutil.iter_modules(mi_api.__path__):
        try:
            cargado = importlib.import_module(f"mi_api.{modulo.name}")
        except Exception as e:
            print(f"[mi_api] No he podido cargar {modulo.name}.py: {type(e).__name__}: {e}")
            continue
        if hasattr(cargado, "router"):
            app.include_router(cargado.router, prefix="/mi", dependencies=protegido)
            cargados.append(modulo.name)
        else:
            print(f"[mi_api] {modulo.name}.py no define `router`; lo ignoro.")
    print(f"[mi_api] Cargados: {', '.join(cargados) or '(ninguno)'}", flush=True)

    return app


def arrancar():
    import uvicorn

    print(f"API de {config.NOMBRE_ASISTENTE} en http://{config.API_HOST}:{config.API_PUERTO}/docs")
    print(f"Clave (cabecera X-API-Key): {clave_api()}\n")
    # reload: si cambias algo en mi_api/, la API se recarga sola.
    uvicorn.run("aria.api:crear_app", factory=True, host=config.API_HOST, port=config.API_PUERTO,
                reload=True, reload_dirs=[str(config.CARPETA_MI_API)])
