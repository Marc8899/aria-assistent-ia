# Copias de seguridad diarias de todas las bases de datos y exportación completa a JSON.
import json
import shutil
import sqlite3
from datetime import date, datetime

from aria import config

CARPETA_COPIAS = config.RAIZ / "datos" / "copias"
CARPETA_EXPORTACIONES = config.RAIZ / "datos" / "exportaciones"
DIAS_A_CONSERVAR = 14


def bases_de_datos() -> list:
    return [config.RUTA_DB, config.RUTA_TAREAS, config.RUTA_SALUD, config.RUTA_APLICACIONES]


def copia_diaria() -> str | None:
    """Una copia al día (la primera vez que se arranca Aria). Conserva las últimas DIAS_A_CONSERVAR."""
    destino = CARPETA_COPIAS / date.today().isoformat()
    if destino.exists():
        return None
    destino.mkdir(parents=True)
    for ruta in bases_de_datos():
        if ruta.exists():
            origen = sqlite3.connect(ruta)
            copia = sqlite3.connect(destino / ruta.name)
            origen.backup(copia)  # copia consistente aunque la base esté en uso
            copia.close()
            origen.close()
    antiguas = sorted(p for p in CARPETA_COPIAS.iterdir() if p.is_dir() and p.name[:4].isdigit())
    for vieja in antiguas[:-DIAS_A_CONSERVAR]:
        shutil.rmtree(vieja, ignore_errors=True)
    return str(destino)


def exportar(ctx) -> dict:
    """Todo lo que Aria sabe y registra, en un único diccionario legible."""
    def filas(db, sql):
        cursor = db.execute(sql)
        nombres = [c[0] for c in cursor.description]
        return [dict(zip(nombres, f)) for f in cursor.fetchall()]

    return {
        "exportado": datetime.now().isoformat(timespec="seconds"),
        "memorias": filas(ctx.memoria.db, "SELECT id, texto, categoria, importancia, sobre, fecha_evento, creado "
                                          "FROM memorias ORDER BY id"),
        "diario": filas(ctx.memoria.db, "SELECT * FROM diario ORDER BY fecha, id"),
        "proyectos": filas(ctx.tareas.db, "SELECT * FROM proyectos ORDER BY id"),
        "tareas": filas(ctx.tareas.db, "SELECT * FROM tareas ORDER BY id"),
        "habitos": filas(ctx.tareas.db, "SELECT * FROM habitos ORDER BY id"),
        "registros_habito": filas(ctx.tareas.db, "SELECT * FROM registros_habito ORDER BY fecha"),
        "bloques": filas(ctx.tareas.db, "SELECT * FROM bloques ORDER BY fecha, inicio"),
        "mejoras_kaizen": filas(ctx.tareas.db, "SELECT * FROM mejoras ORDER BY id"),
        "perfil_fisico": ctx.salud.perfil(),
        "pesos": filas(ctx.salud.db, "SELECT * FROM pesos ORDER BY fecha"),
        "comidas": filas(ctx.salud.db, "SELECT * FROM comidas ORDER BY fecha, id"),
        "entrenos": filas(ctx.salud.db, "SELECT * FROM entrenos ORDER BY fecha, id"),
    }


def exportar_a_archivo(ctx) -> str:
    CARPETA_EXPORTACIONES.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_EXPORTACIONES / f"aria-{datetime.now():%Y-%m-%d_%H%M}.json"
    ruta.write_text(json.dumps(exportar(ctx), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(ruta)
