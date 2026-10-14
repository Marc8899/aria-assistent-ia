# Memoria a largo plazo en SQLite (memoria.db): recuerdos sobre el usuario y su diario.
# Pensada para crecer mucho: búsqueda de texto completo (FTS5) para recuperar solo lo relevante.
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

CATEGORIAS = ("perfil", "familia", "pareja", "amistades", "trabajo", "estudios", "salud", "gustos",
              "valores", "objetivos", "historia", "rutina", "dinero", "otros")
PALABRAS_VACIAS = {"que", "los", "las", "del", "con", "por", "para", "una", "uno", "unos", "unas", "como",
                   "pero", "mas", "muy", "este", "esta", "esto", "eso", "ese", "esa", "hay", "fue", "son",
                   "sus", "les", "nos", "mis", "tus", "algo", "cuando", "donde", "quien", "cual", "tengo",
                   "tiene", "estoy", "esta", "hoy", "ayer", "sobre", "porque", "the"}


@dataclass
class Recuerdo:
    id: int
    texto: str
    categoria: str
    importancia: int
    sobre: str
    fecha_evento: str | None

    def describir(self) -> str:
        extra = [self.categoria]
        if self.sobre:
            extra.append(f"sobre {self.sobre}")
        if self.fecha_evento:
            extra.append(self.fecha_evento)
        return f"[{self.id}] {self.texto} ({', '.join(extra)})"


def _consulta_fts(texto: str) -> str | None:
    """Convierte un texto libre en una consulta FTS5 segura: palabras útiles unidas con OR."""
    palabras = {p for p in re.findall(r"\w{3,}", texto.lower()) if p not in PALABRAS_VACIAS}
    return " OR ".join(f'"{p}"*' for p in sorted(palabras)[:20]) or None


class Memoria:
    def __init__(self, ruta):
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS memorias (id INTEGER PRIMARY KEY, texto TEXT)")
        # Migración suave desde versiones anteriores.
        columnas = {fila[1] for fila in self.db.execute("PRAGMA table_info(memorias)")}
        for columna, tipo in (("creado", "TEXT"), ("categoria", "TEXT DEFAULT 'otros'"),
                              ("importancia", "INTEGER DEFAULT 3"), ("sobre", "TEXT DEFAULT ''"),
                              ("fecha_evento", "TEXT"), ("actualizado", "TEXT")):
            if columna not in columnas:
                self.db.execute(f"ALTER TABLE memorias ADD COLUMN {columna} {tipo}")
        self.db.executescript(
            """
            UPDATE memorias SET categoria = 'otros' WHERE categoria IS NULL;
            UPDATE memorias SET importancia = 3 WHERE importancia IS NULL;
            UPDATE memorias SET sobre = '' WHERE sobre IS NULL;
            CREATE VIRTUAL TABLE IF NOT EXISTS memorias_fts USING fts5(
                texto, categoria, sobre, content='memorias', content_rowid='id',
                tokenize='unicode61 remove_diacritics 2');
            CREATE TRIGGER IF NOT EXISTS memorias_ai AFTER INSERT ON memorias BEGIN
                INSERT INTO memorias_fts(rowid, texto, categoria, sobre) VALUES (new.id, new.texto, new.categoria, new.sobre);
            END;
            CREATE TRIGGER IF NOT EXISTS memorias_ad AFTER DELETE ON memorias BEGIN
                INSERT INTO memorias_fts(memorias_fts, rowid, texto, categoria, sobre)
                VALUES ('delete', old.id, old.texto, old.categoria, old.sobre);
            END;
            CREATE TRIGGER IF NOT EXISTS memorias_au AFTER UPDATE ON memorias BEGIN
                INSERT INTO memorias_fts(memorias_fts, rowid, texto, categoria, sobre)
                VALUES ('delete', old.id, old.texto, old.categoria, old.sobre);
                INSERT INTO memorias_fts(rowid, texto, categoria, sobre) VALUES (new.id, new.texto, new.categoria, new.sobre);
            END;

            CREATE TABLE IF NOT EXISTS diario (
                id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, texto TEXT NOT NULL, animo TEXT DEFAULT '', creado TEXT);
            CREATE VIRTUAL TABLE IF NOT EXISTS diario_fts USING fts5(
                texto, content='diario', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
            CREATE TRIGGER IF NOT EXISTS diario_ai AFTER INSERT ON diario BEGIN
                INSERT INTO diario_fts(rowid, texto) VALUES (new.id, new.texto);
            END;
            CREATE TRIGGER IF NOT EXISTS diario_ad AFTER DELETE ON diario BEGIN
                INSERT INTO diario_fts(diario_fts, rowid, texto) VALUES ('delete', old.id, old.texto);
            END;
            """
        )
        # Si el índice está vacío pero hay recuerdos (venimos de una versión antigua), se reconstruye.
        if self.db.execute("SELECT count(*) FROM memorias_fts").fetchone()[0] == 0:
            self.db.execute("INSERT INTO memorias_fts(memorias_fts) VALUES ('rebuild')")
        self.db.commit()

    # ---------- Recuerdos ----------

    def _filas(self, sql: str, parametros=()) -> list[Recuerdo]:
        return [Recuerdo(*f) for f in self.db.execute(sql, parametros).fetchall()]

    CAMPOS = "id, texto, categoria, importancia, sobre, fecha_evento"

    def guardar(self, texto: str, categoria="otros", importancia=3, sobre="", fecha_evento=None) -> tuple[int, bool]:
        """Devuelve (id, es_nueva). No duplica recuerdos idénticos."""
        texto = texto.strip()
        categoria = categoria if categoria in CATEGORIAS else "otros"
        importancia = max(1, min(5, int(importancia)))
        existente = self.db.execute("SELECT id FROM memorias WHERE lower(texto) = lower(?)", (texto,)).fetchone()
        if existente:
            return existente[0], False
        ahora = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.execute(
            "INSERT INTO memorias (texto, categoria, importancia, sobre, fecha_evento, creado, actualizado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (texto, categoria, importancia, sobre.strip(), fecha_evento or None, ahora, ahora),
        )
        self.db.commit()
        return cursor.lastrowid, True

    def actualizar(self, id_memoria: int, **campos) -> bool:
        campos = {k: v for k, v in campos.items() if v not in (None, "")}
        if not campos:
            return False
        campos["actualizado"] = datetime.now().isoformat(timespec="seconds")
        asignaciones = ", ".join(f"{k} = ?" for k in campos)
        cursor = self.db.execute(f"UPDATE memorias SET {asignaciones} WHERE id = ?", (*campos.values(), id_memoria))
        self.db.commit()
        return cursor.rowcount > 0

    def listar(self) -> list[tuple[int, str]]:
        return self.db.execute("SELECT id, texto FROM memorias ORDER BY id").fetchall()

    def todos(self, categoria: str = "") -> list[Recuerdo]:
        if categoria:
            return self._filas(f"SELECT {self.CAMPOS} FROM memorias WHERE categoria = ? ORDER BY importancia DESC, id",
                               (categoria,))
        return self._filas(f"SELECT {self.CAMPOS} FROM memorias ORDER BY categoria, importancia DESC, id")

    def nucleo(self, limite: int = 30) -> list[Recuerdo]:
        """Lo esencial (importancia 4-5): va siempre en el system prompt."""
        return self._filas(f"SELECT {self.CAMPOS} FROM memorias WHERE importancia >= 4 "
                           f"ORDER BY importancia DESC, id LIMIT ?", (limite,))

    def buscar(self, texto: str, limite: int = 10, categoria: str = "") -> list[Recuerdo]:
        consulta = _consulta_fts(texto)
        if not consulta:
            return []
        filtro, parametros = ("AND m.categoria = ?", (consulta, categoria, limite)) if categoria \
            else ("", (consulta, limite))
        return self._filas(
            f"SELECT m.id, m.texto, m.categoria, m.importancia, m.sobre, m.fecha_evento "
            f"FROM memorias_fts f JOIN memorias m ON m.id = f.rowid WHERE memorias_fts MATCH ? {filtro} "
            f"ORDER BY bm25(memorias_fts) - m.importancia * 0.5 LIMIT ?",
            parametros,
        )

    def contar(self) -> int:
        return self.db.execute("SELECT count(*) FROM memorias").fetchone()[0]

    def olvidar(self, id_memoria: int) -> bool:
        cursor = self.db.execute("DELETE FROM memorias WHERE id = ?", (id_memoria,))
        self.db.commit()
        return cursor.rowcount > 0

    # ---------- Diario ----------

    def escribir_diario(self, texto: str, animo: str = "", fecha: str = "") -> int:
        cursor = self.db.execute(
            "INSERT INTO diario (fecha, texto, animo, creado) VALUES (?, ?, ?, ?)",
            (fecha or date.today().isoformat(), texto.strip(), animo.strip(),
             datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return cursor.lastrowid

    def leer_diario(self, desde: str, hasta: str) -> list[tuple]:
        return self.db.execute(
            "SELECT id, fecha, texto, animo FROM diario WHERE fecha BETWEEN ? AND ? ORDER BY fecha, id",
            (desde, hasta),
        ).fetchall()

    def buscar_diario(self, texto: str, limite: int = 10) -> list[tuple]:
        consulta = _consulta_fts(texto)
        if not consulta:
            return []
        return self.db.execute(
            "SELECT d.id, d.fecha, d.texto, d.animo FROM diario_fts f JOIN diario d ON d.id = f.rowid "
            "WHERE diario_fts MATCH ? ORDER BY bm25(diario_fts) LIMIT ?",
            (consulta, limite),
        ).fetchall()

    def cerrar(self):
        self.db.close()
