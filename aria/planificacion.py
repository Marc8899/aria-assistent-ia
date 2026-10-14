# Hábitos (con rachas), bloques de tiempo (time blocking) y registro kaizen de mejoras.
# Comparte la base de datos de tareas (datos/tareas.db).
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from aria.texto import normalizar

DIAS_SEMANA = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
TIPOS_BLOQUE = ("trabajo profundo", "trabajo", "estudio", "reunion", "habito", "ejercicio", "descanso",
                "personal", "ocio", "tramites")
ESTADOS_MEJORA = ("propuesta", "probando", "adoptada", "descartada")


def interpretar_dias(texto: str) -> str:
    """'lunes, miércoles y viernes' -> '0,2,4'. 'diario'/'todos'/vacío -> '0,1,2,3,4,5,6'.
    'laborables' -> '0,1,2,3,4'. 'fines de semana' -> '5,6'."""
    t = normalizar(texto or "")
    if not t or any(p in t for p in ("diario", "todos", "cada dia")):
        return "0,1,2,3,4,5,6"
    if "laborable" in t or "entre semana" in t:
        return "0,1,2,3,4"
    if "fin de semana" in t or "fines de semana" in t:
        return "5,6"
    dias = [str(i) for i, nombre in enumerate(DIAS_SEMANA) if nombre in t]
    if not dias:
        raise ValueError("no entiendo los días. Usa p. ej. 'diario', 'laborables' o 'lunes, miércoles'")
    return ",".join(dias)


def describir_dias(dias: str) -> str:
    indices = [int(d) for d in dias.split(",")]
    if len(indices) == 7:
        return "a diario"
    if indices == [0, 1, 2, 3, 4]:
        return "los laborables"
    return "los " + ", ".join(DIAS_SEMANA[i] for i in indices)


@dataclass
class Habito:
    id: int
    nombre: str
    descripcion: str
    dias: str              # índices de días de la semana, '0,1,2'
    veces_semana: int      # >0: objetivo semanal flexible en vez de días fijos
    hora: str              # 'HH:MM' preferida, o ''
    activo: int
    creado: str

    def toca(self, dia: date) -> bool:
        if self.veces_semana:
            return True
        return str(dia.weekday()) in self.dias.split(",")

    def frecuencia(self) -> str:
        return f"{self.veces_semana} veces por semana" if self.veces_semana else describir_dias(self.dias)


@dataclass
class Bloque:
    id: int
    fecha: str
    inicio: str
    fin: str
    titulo: str
    tipo: str
    tarea_id: int | None
    evento_id: str | None


class Planificacion:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db.executescript(
            """CREATE TABLE IF NOT EXISTS habitos (
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, descripcion TEXT NOT NULL DEFAULT '',
                dias TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6', veces_semana INTEGER NOT NULL DEFAULT 0,
                hora TEXT NOT NULL DEFAULT '', activo INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS registros_habito (
                habito_id INTEGER NOT NULL, fecha TEXT NOT NULL, nota TEXT DEFAULT '',
                PRIMARY KEY (habito_id, fecha));
            CREATE TABLE IF NOT EXISTS bloques (
                id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, inicio TEXT NOT NULL, fin TEXT NOT NULL,
                titulo TEXT NOT NULL, tipo TEXT NOT NULL DEFAULT 'trabajo', tarea_id INTEGER, evento_id TEXT);
            CREATE TABLE IF NOT EXISTS mejoras (
                id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, area TEXT NOT NULL DEFAULT '',
                observacion TEXT NOT NULL, mejora TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'propuesta',
                resultado TEXT NOT NULL DEFAULT '', actualizada TEXT);"""
        )
        self.db.commit()

    # ---------- Hábitos ----------

    def crear_habito(self, nombre, descripcion="", dias="", veces_semana=0, hora="") -> Habito:
        if hora:
            datetime.strptime(hora, "%H:%M")
        cursor = self.db.execute(
            "INSERT INTO habitos (nombre, descripcion, dias, veces_semana, hora, creado) VALUES (?, ?, ?, ?, ?, ?)",
            (nombre.strip(), descripcion.strip(), interpretar_dias(dias), max(0, int(veces_semana)), hora,
             datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return self.habito(cursor.lastrowid)

    def habito(self, id_habito: int) -> Habito | None:
        fila = self.db.execute("SELECT * FROM habitos WHERE id = ?", (id_habito,)).fetchone()
        return Habito(**fila) if fila else None

    def habitos(self) -> list[Habito]:
        return [Habito(**f) for f in self.db.execute("SELECT * FROM habitos WHERE activo = 1 ORDER BY hora = '', hora, id")]

    def buscar_habito(self, nombre: str) -> Habito | None:
        if str(nombre).strip().isdigit():
            return self.habito(int(nombre))
        buscado = normalizar(nombre)
        candidatos = [h for h in self.habitos() if buscado in normalizar(h.nombre) or normalizar(h.nombre) in buscado]
        return candidatos[0] if len(candidatos) == 1 else None

    def archivar_habito(self, id_habito: int):
        self.db.execute("UPDATE habitos SET activo = 0 WHERE id = ?", (id_habito,))
        self.db.commit()

    def marcar(self, id_habito: int, dia: date, hecho: bool = True, nota: str = ""):
        if hecho:
            self.db.execute("INSERT OR REPLACE INTO registros_habito (habito_id, fecha, nota) VALUES (?, ?, ?)",
                            (id_habito, dia.isoformat(), nota))
        else:
            self.db.execute("DELETE FROM registros_habito WHERE habito_id = ? AND fecha = ?", (id_habito, dia.isoformat()))
        self.db.commit()

    def hecho(self, id_habito: int, dia: date) -> bool:
        return self.db.execute("SELECT 1 FROM registros_habito WHERE habito_id = ? AND fecha = ?",
                               (id_habito, dia.isoformat())).fetchone() is not None

    def _fechas_hechas(self, id_habito: int) -> set[str]:
        return {f[0] for f in self.db.execute("SELECT fecha FROM registros_habito WHERE habito_id = ?", (id_habito,))}

    def racha(self, habito: Habito, hoy: date) -> int:
        """Días (o semanas, si es semanal) seguidos cumpliendo. Hoy no rompe la racha si aún no se ha hecho."""
        hechas = self._fechas_hechas(habito.id)
        if habito.veces_semana:
            racha, lunes = 0, hoy - timedelta(days=hoy.weekday())
            semana_actual = sum((lunes + timedelta(d)).isoformat() in hechas for d in range(7))
            if semana_actual >= habito.veces_semana:
                racha += 1
            while True:
                lunes -= timedelta(days=7)
                if sum((lunes + timedelta(d)).isoformat() in hechas for d in range(7)) >= habito.veces_semana:
                    racha += 1
                else:
                    return racha
        racha, dia = 0, hoy
        if not habito.toca(dia) or dia.isoformat() not in hechas:
            dia -= timedelta(days=1)  # hoy todavía puede hacerse
        for _ in range(3650):
            if habito.toca(dia):
                if dia.isoformat() not in hechas:
                    break
                racha += 1
            dia -= timedelta(days=1)
            if dia.isoformat() < habito.creado[:10]:
                break
        return racha

    def cumplimiento(self, habito: Habito, hoy: date, dias: int = 30) -> tuple[int, int]:
        """(días cumplidos, días que tocaba) en el periodo."""
        hechas = self._fechas_hechas(habito.id)
        inicio = max(hoy - timedelta(days=dias - 1), date.fromisoformat(habito.creado[:10]))
        total = cumplidos = 0
        dia = inicio
        while dia <= hoy:
            if habito.veces_semana or habito.toca(dia):
                total += 1
                cumplidos += dia.isoformat() in hechas
            dia += timedelta(days=1)
        if habito.veces_semana:  # objetivo semanal: proporción respecto a lo esperado
            total = max(1, round(habito.veces_semana * (hoy - inicio).days / 7) or habito.veces_semana)
        return cumplidos, total

    def pendientes_hoy(self, hoy: date) -> list[Habito]:
        return [h for h in self.habitos() if h.toca(hoy) and not self.hecho(h.id, hoy)
                and not (h.veces_semana and self._semana_cumplida(h, hoy))]

    def _semana_cumplida(self, habito: Habito, hoy: date) -> bool:
        lunes = hoy - timedelta(days=hoy.weekday())
        hechas = self._fechas_hechas(habito.id)
        return sum((lunes + timedelta(d)).isoformat() in hechas for d in range(7)) >= habito.veces_semana

    # ---------- Bloques de tiempo ----------

    def crear_bloque(self, fecha: str, inicio: str, fin: str, titulo: str, tipo="trabajo", tarea_id=None) -> Bloque:
        date.fromisoformat(fecha)
        if datetime.strptime(fin, "%H:%M") <= datetime.strptime(inicio, "%H:%M"):
            raise ValueError("la hora de fin debe ser posterior a la de inicio")
        cursor = self.db.execute(
            "INSERT INTO bloques (fecha, inicio, fin, titulo, tipo, tarea_id) VALUES (?, ?, ?, ?, ?, ?)",
            (fecha, inicio, fin, titulo.strip(), tipo, tarea_id or None),
        )
        self.db.commit()
        return self.bloque(cursor.lastrowid)

    def bloque(self, id_bloque: int) -> Bloque | None:
        fila = self.db.execute("SELECT * FROM bloques WHERE id = ?", (id_bloque,)).fetchone()
        return Bloque(**fila) if fila else None

    def bloques(self, fecha: str) -> list[Bloque]:
        return [Bloque(**f) for f in self.db.execute("SELECT * FROM bloques WHERE fecha = ? ORDER BY inicio", (fecha,))]

    def solapes(self, fecha: str, inicio: str, fin: str, excluir: int = 0) -> list[Bloque]:
        return [b for b in self.bloques(fecha) if b.id != excluir and b.inicio < fin and inicio < b.fin]

    def asignar_evento(self, id_bloque: int, evento_id: str):
        self.db.execute("UPDATE bloques SET evento_id = ? WHERE id = ?", (evento_id, id_bloque))
        self.db.commit()

    def borrar_bloque(self, id_bloque: int) -> bool:
        cursor = self.db.execute("DELETE FROM bloques WHERE id = ?", (id_bloque,))
        self.db.commit()
        return cursor.rowcount > 0

    def bloque_actual_y_siguiente(self, ahora: datetime) -> tuple[Bloque | None, Bloque | None]:
        hora = ahora.strftime("%H:%M")
        actual = siguiente = None
        for b in self.bloques(ahora.date().isoformat()):
            if b.inicio <= hora < b.fin:
                actual = b
            elif b.inicio > hora and siguiente is None:
                siguiente = b
        return actual, siguiente

    # ---------- Kaizen ----------

    def registrar_mejora(self, observacion: str, mejora: str, area: str = "") -> int:
        cursor = self.db.execute(
            "INSERT INTO mejoras (fecha, area, observacion, mejora, actualizada) VALUES (?, ?, ?, ?, ?)",
            (date.today().isoformat(), area.strip(), observacion.strip(), mejora.strip(),
             datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return cursor.lastrowid

    def actualizar_mejora(self, id_mejora: int, estado: str = "", resultado: str = "") -> bool:
        if estado and estado not in ESTADOS_MEJORA:
            raise ValueError(f"estado no válido. Opciones: {', '.join(ESTADOS_MEJORA)}")
        cursor = self.db.execute(
            "UPDATE mejoras SET estado = coalesce(nullif(?, ''), estado), resultado = coalesce(nullif(?, ''), resultado), "
            "actualizada = ? WHERE id = ?",
            (estado, resultado, datetime.now().isoformat(timespec="seconds"), id_mejora),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def mejoras(self, estados=("propuesta", "probando")) -> list[sqlite3.Row]:
        marcas = ",".join("?" * len(estados))
        return self.db.execute(f"SELECT * FROM mejoras WHERE estado IN ({marcas}) ORDER BY id", tuple(estados)).fetchall()
