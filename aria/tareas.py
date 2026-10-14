# Tareas y proyectos (archivo datos/tareas.db), independientes de la memoria.
# Los estados de las tareas son las columnas del kanban: backlog -> pendiente -> en_curso -> bloqueada -> hecha.
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from aria.texto import normalizar

ESTADOS = ("backlog", "pendiente", "en_curso", "bloqueada", "hecha", "cancelada")
ACTIVOS = ("pendiente", "en_curso", "bloqueada")
PRIORIDADES = ("alta", "media", "baja")
HORIZONTES = ("corto", "medio", "largo")
ESTADOS_PROYECTO = ("activo", "en_pausa", "completado", "abandonado")
COLUMNAS_KANBAN = {"backlog": "Backlog", "pendiente": "Por hacer", "en_curso": "En curso",
                   "bloqueada": "Bloqueada", "hecha": "Hecho"}


def interpretar_fecha(texto: str) -> str | None:
    """'2026-10-03' o '2026-10-03 09:00' -> '2026-10-03 09:00'. Vacío -> None."""
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        momento = datetime.fromisoformat(texto.replace("T", " "))
    except ValueError:
        raise ValueError(f"fecha no válida '{texto}'. Usa AAAA-MM-DD o AAAA-MM-DD HH:MM")
    if len(texto) <= 10:  # solo fecha: vence al final del día
        momento = momento.replace(hour=23, minute=59)
    return momento.isoformat(sep=" ", timespec="minutes")


def tiene_hora(fecha_limite: str) -> bool:
    return not fecha_limite.endswith("23:59")


def tiempo_restante(fecha_limite: str, ahora: datetime) -> str:
    segundos = int((datetime.fromisoformat(fecha_limite) - ahora).total_seconds())
    dias, resto = divmod(abs(segundos), 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    partes = []
    if dias:
        partes.append(f"{dias} d")
    if horas:
        partes.append(f"{horas} h")
    if not dias and minutos:
        partes.append(f"{minutos} min")
    duracion = " ".join(partes) or "menos de 1 min"
    return f"venció hace {duracion}" if segundos < 0 else f"quedan {duracion}"


@dataclass
class Tarea:
    id: int
    titulo: str
    descripcion: str
    estado: str
    prioridad: str
    fecha_limite: str | None
    creada: str
    actualizada: str
    completada: str | None
    proyecto_id: int | None = None
    orden: int = 0
    evento_id: str | None = None
    origen: str = ""

    @property
    def activa(self) -> bool:
        return self.estado in ACTIVOS

    def describir(self, ahora: datetime, proyecto: str = "") -> str:
        texto = f"[{self.id}] {self.titulo} · {self.estado} · prioridad {self.prioridad}"
        if proyecto:
            texto += f" · proyecto {proyecto}"
        if self.fecha_limite:
            texto += f" · límite {self.fecha_limite}"
            if self.activa:
                texto += f" ({tiempo_restante(self.fecha_limite, ahora)})"
        if self.evento_id:
            texto += " · en calendario"
        if self.descripcion:
            texto += f"\n    {self.descripcion}"
        return texto


@dataclass
class Proyecto:
    id: int
    nombre: str
    descripcion: str
    horizonte: str
    resultado: str
    fecha_objetivo: str | None
    estado: str
    area: str
    creado: str
    actualizado: str


class Tareas:
    def __init__(self, ruta):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """CREATE TABLE IF NOT EXISTS tareas (
                id INTEGER PRIMARY KEY,
                titulo TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL DEFAULT 'pendiente',
                prioridad TEXT NOT NULL DEFAULT 'media',
                fecha_limite TEXT,
                creada TEXT NOT NULL,
                actualizada TEXT NOT NULL,
                completada TEXT
            );
            CREATE TABLE IF NOT EXISTS proyectos (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL DEFAULT '',
                horizonte TEXT NOT NULL DEFAULT 'corto',
                resultado TEXT NOT NULL DEFAULT '',
                fecha_objetivo TEXT,
                estado TEXT NOT NULL DEFAULT 'activo',
                area TEXT NOT NULL DEFAULT '',
                creado TEXT NOT NULL,
                actualizado TEXT NOT NULL
            );"""
        )
        columnas = {f[1] for f in self.db.execute("PRAGMA table_info(tareas)")}
        for columna, tipo in (("proyecto_id", "INTEGER"), ("orden", "INTEGER DEFAULT 0"),
                              ("evento_id", "TEXT"), ("origen", "TEXT DEFAULT ''")):
            if columna not in columnas:
                self.db.execute(f"ALTER TABLE tareas ADD COLUMN {columna} {tipo}")
        self.db.commit()

    @staticmethod
    def _ahora() -> str:
        return datetime.now().isoformat(sep=" ", timespec="seconds")

    @staticmethod
    def _validar(estado=None, prioridad=None):
        if estado is not None and estado not in ESTADOS:
            raise ValueError(f"estado no válido '{estado}'. Opciones: {', '.join(ESTADOS)}")
        if prioridad is not None and prioridad not in PRIORIDADES:
            raise ValueError(f"prioridad no válida '{prioridad}'. Opciones: {', '.join(PRIORIDADES)}")

    # ---------- Tareas ----------

    def crear(self, titulo, descripcion="", prioridad="media", fecha_limite=None, estado="pendiente",
              proyecto_id=None, origen="") -> Tarea:
        self._validar(estado, prioridad)
        ahora = self._ahora()
        orden = 0
        if proyecto_id:
            orden = self.db.execute("SELECT coalesce(max(orden), 0) + 1 FROM tareas WHERE proyecto_id = ?",
                                    (proyecto_id,)).fetchone()[0]
        cursor = self.db.execute(
            "INSERT INTO tareas (titulo, descripcion, estado, prioridad, fecha_limite, creada, actualizada, "
            "proyecto_id, orden, origen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (titulo.strip(), descripcion.strip(), estado, prioridad, fecha_limite, ahora, ahora,
             proyecto_id, orden, origen),
        )
        self.db.commit()
        return self.obtener(cursor.lastrowid)

    def obtener(self, id_tarea: int) -> Tarea | None:
        fila = self.db.execute("SELECT * FROM tareas WHERE id = ?", (id_tarea,)).fetchone()
        return Tarea(**fila) if fila else None

    def por_origen(self, origen: str) -> Tarea | None:
        fila = self.db.execute("SELECT * FROM tareas WHERE origen = ?", (origen,)).fetchone()
        return Tarea(**fila) if fila else None

    def listar(self, estados=ACTIVOS, proyecto_id: int | None = None) -> list[Tarea]:
        marcas = ",".join("?" * len(estados))
        filtro, parametros = "", list(estados)
        if proyecto_id is not None:
            filtro, parametros = " AND proyecto_id = ?", parametros + [proyecto_id]
        filas = self.db.execute(
            f"SELECT * FROM tareas WHERE estado IN ({marcas}){filtro} ORDER BY "
            "fecha_limite IS NULL, fecha_limite, "
            "CASE prioridad WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, orden, id",
            parametros,
        ).fetchall()
        return [Tarea(**f) for f in filas]

    def completadas_desde(self, desde: datetime) -> list[Tarea]:
        filas = self.db.execute("SELECT * FROM tareas WHERE estado = 'hecha' AND completada >= ? ORDER BY completada",
                                (desde.isoformat(sep=" ", timespec="seconds"),)).fetchall()
        return [Tarea(**f) for f in filas]

    def actualizar(self, id_tarea: int, **campos) -> Tarea | None:
        campos = {k: v for k, v in campos.items() if v is not None}
        self._validar(campos.get("estado"), campos.get("prioridad"))
        if not self.obtener(id_tarea):
            return None
        ahora = self._ahora()
        if "estado" in campos:
            campos["completada"] = ahora if campos["estado"] == "hecha" else None
        campos["actualizada"] = ahora
        asignaciones = ", ".join(f"{k} = ?" for k in campos)
        self.db.execute(f"UPDATE tareas SET {asignaciones} WHERE id = ?", (*campos.values(), id_tarea))
        self.db.commit()
        return self.obtener(id_tarea)

    def borrar(self, id_tarea: int) -> bool:
        cursor = self.db.execute("DELETE FROM tareas WHERE id = ?", (id_tarea,))
        self.db.commit()
        return cursor.rowcount > 0

    def urgentes(self, ahora: datetime) -> dict[str, list[Tarea]]:
        """Clasifica las tareas activas según lo que apremian."""
        fin_de_hoy = ahora.replace(hour=23, minute=59, second=59)
        manana = fin_de_hoy + timedelta(days=1)
        grupos = {"vencidas": [], "hoy": [], "manana": [], "en_curso": []}
        for tarea in self.listar():
            limite = datetime.fromisoformat(tarea.fecha_limite) if tarea.fecha_limite else None
            if limite and limite < ahora:
                grupos["vencidas"].append(tarea)
            elif limite and limite <= fin_de_hoy:
                grupos["hoy"].append(tarea)
            elif limite and limite <= manana:
                grupos["manana"].append(tarea)
            elif tarea.estado == "en_curso":
                grupos["en_curso"].append(tarea)
        return grupos

    # ---------- Proyectos ----------

    def crear_proyecto(self, nombre, descripcion="", horizonte="corto", resultado="", fecha_objetivo=None,
                       area="") -> Proyecto:
        if horizonte not in HORIZONTES:
            raise ValueError(f"horizonte no válido '{horizonte}'. Opciones: {', '.join(HORIZONTES)}")
        ahora = self._ahora()
        cursor = self.db.execute(
            "INSERT INTO proyectos (nombre, descripcion, horizonte, resultado, fecha_objetivo, area, creado, actualizado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nombre.strip(), descripcion.strip(), horizonte, resultado.strip(), fecha_objetivo, area.strip(), ahora, ahora),
        )
        self.db.commit()
        return self.proyecto(cursor.lastrowid)

    def proyecto(self, id_proyecto: int) -> Proyecto | None:
        fila = self.db.execute("SELECT * FROM proyectos WHERE id = ?", (id_proyecto,)).fetchone()
        return Proyecto(**fila) if fila else None

    def proyectos(self, estados=("activo", "en_pausa")) -> list[Proyecto]:
        marcas = ",".join("?" * len(estados))
        filas = self.db.execute(
            f"SELECT * FROM proyectos WHERE estado IN ({marcas}) ORDER BY "
            "CASE horizonte WHEN 'corto' THEN 0 WHEN 'medio' THEN 1 ELSE 2 END, fecha_objetivo IS NULL, fecha_objetivo, id",
            tuple(estados),
        ).fetchall()
        return [Proyecto(**f) for f in filas]

    def buscar_proyecto(self, nombre: str) -> Proyecto | None:
        """Por id o por nombre aproximado."""
        if str(nombre).strip().isdigit():
            return self.proyecto(int(nombre))
        buscado = normalizar(nombre)
        todos = self.proyectos(ESTADOS_PROYECTO)
        for p in todos:
            if normalizar(p.nombre) == buscado:
                return p
        candidatos = [p for p in todos if buscado in normalizar(p.nombre) or normalizar(p.nombre) in buscado]
        return candidatos[0] if len(candidatos) == 1 else None

    def actualizar_proyecto(self, id_proyecto: int, **campos) -> Proyecto | None:
        campos = {k: v for k, v in campos.items() if v not in (None, "")}
        if "horizonte" in campos and campos["horizonte"] not in HORIZONTES:
            raise ValueError(f"horizonte no válido. Opciones: {', '.join(HORIZONTES)}")
        if "estado" in campos and campos["estado"] not in ESTADOS_PROYECTO:
            raise ValueError(f"estado no válido. Opciones: {', '.join(ESTADOS_PROYECTO)}")
        campos["actualizado"] = self._ahora()
        asignaciones = ", ".join(f"{k} = ?" for k in campos)
        self.db.execute(f"UPDATE proyectos SET {asignaciones} WHERE id = ?", (*campos.values(), id_proyecto))
        self.db.commit()
        return self.proyecto(id_proyecto)

    def progreso(self, id_proyecto: int) -> tuple[int, int]:
        """(hechas, total) sin contar canceladas."""
        fila = self.db.execute(
            "SELECT sum(estado = 'hecha'), count(*) FROM tareas WHERE proyecto_id = ? AND estado != 'cancelada'",
            (id_proyecto,),
        ).fetchone()
        return fila[0] or 0, fila[1] or 0

    def ultima_actividad(self, id_proyecto: int) -> str:
        fila = self.db.execute(
            "SELECT max(actualizada) FROM tareas WHERE proyecto_id = ?", (id_proyecto,)).fetchone()
        return fila[0] or self.proyecto(id_proyecto).actualizado

    def nombre_proyecto(self, id_proyecto: int | None) -> str:
        if not id_proyecto:
            return ""
        p = self.proyecto(id_proyecto)
        return p.nombre if p else ""

    def cerrar(self):
        self.db.close()
