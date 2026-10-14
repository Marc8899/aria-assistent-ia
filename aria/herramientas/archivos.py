# Archivos: ver carpetas, buscar, mover, copiar, convertir formatos, comprimir y descomprimir.
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

from aria.archivos import (INICIO, buscar_indice_windows, buscar_recorriendo, comprobar_escritura, expandir,
                           resolver, ruta_libre, tamano_legible)
from aria.conversion import FORMATOS_SOPORTADOS, convertir

GRUPO = "archivos"
PALABRAS_CLAVE = ("archivo", "fichero", "carpeta", "mueve", "mover", "muevelo", "copia", "copiar", "renombra",
                  "comprim", "descomprim", "zip", "rar", "7z", "convierte", "convertir", "pasa a", "pasalo",
                  "formato", "descargas", "escritorio", "png", "jpg", "jpeg", "webp", "extrae", "organiza")


def _separar_rutas(texto: str) -> list[str]:
    return [r.strip() for r in texto.replace("\n", ";").split(";") if r.strip()]


def registrar(registro, ctx):
    @registro.herramienta(
        "Lista lo que hay en una carpeta (nombre, tamaño, fecha).",
        ruta="Carpeta. Admite alias: escritorio, descargas, documentos, imagenes, musica, videos",
        patron="Filtro opcional, p. ej. '*.pdf'",
    )
    def listar_carpeta(ruta: str = "escritorio", patron: str = "*") -> str:
        carpeta = resolver(ruta)
        if not carpeta.is_dir():
            return f"No existe la carpeta {carpeta}."
        elementos = sorted(carpeta.glob(patron or "*"), key=lambda p: (not p.is_dir(), p.name.lower()))
        lineas = []
        for p in elementos[:200]:
            try:
                info = p.stat()
            except OSError:
                continue
            fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(info.st_mtime))
            lineas.append(f"[carpeta] {p.name}" if p.is_dir() else f"{p.name} · {tamano_legible(info.st_size)} · {fecha}")
        extra = f"\n(... y {len(elementos) - 200} más)" if len(elementos) > 200 else ""
        return f"{carpeta} ({len(elementos)} elementos):\n" + ("\n".join(lineas) or "(vacía)") + extra

    @registro.herramienta(
        "Busca archivos en el PC por nombre y, opcionalmente, por su contenido (usa el índice de Windows: "
        "encuentra texto dentro de documentos Word, PDF, etc.).",
        texto="Parte del nombre o del contenido a buscar",
        carpeta="Dónde buscar (por defecto, toda la carpeta del usuario)",
        en_contenido="true para buscar también dentro de los archivos",
    )
    def buscar_archivos(texto: str, carpeta: str = "", en_contenido: bool = False) -> str:
        base = resolver(carpeta) if carpeta else INICIO
        try:
            resultados = buscar_indice_windows(texto, base, en_contenido)
            metodo = "índice de Windows"
        except Exception:
            resultados = []
        if not resultados:  # sin índice, o carpeta no indexada: se recorre a mano (solo nombres)
            resultados = buscar_recorriendo(texto, base)
            metodo = "recorrido de carpetas"
        if not resultados and not en_contenido:
            return f"No encuentro nada llamado '{texto}' en {base}. Puedo buscar dentro del contenido (en_contenido=true)."
        lineas = [f"{r} · {tamano_legible(t)} · {f}" for r, t, f in resultados]
        return f"{len(resultados)} resultados ({metodo}):\n" + ("\n".join(lineas) or "ninguno")

    @registro.herramienta(
        "Mueve o renombra archivos o carpetas. Admite comodines ('descargas/*.pdf'). Si el destino es una carpeta "
        "(o no existe y hay varios archivos), los mete dentro, creándola si hace falta. Nunca sobrescribe.",
        confirmar=True,
        origen="Ruta o comodín; varias separadas por ';'",
        destino="Carpeta de destino, o nuevo nombre/ruta si es un solo archivo",
    )
    def mover_archivos(origen: str, destino: str) -> str:
        return _mover_o_copiar(origen, destino, mover=True)

    @registro.herramienta(
        "Copia archivos o carpetas. Admite comodines. Nunca sobrescribe: si existe, añade (1), (2)...",
        origen="Ruta o comodín; varias separadas por ';'",
        destino="Carpeta de destino o ruta del nuevo archivo",
    )
    def copiar_archivos(origen: str, destino: str) -> str:
        return _mover_o_copiar(origen, destino, mover=False)

    def _mover_o_copiar(origen: str, destino: str, mover: bool) -> str:
        fuentes = [p for patron in _separar_rutas(origen) for p in expandir(patron)]
        if not fuentes:
            return f"No encuentro nada en '{origen}'."
        objetivo = resolver(destino)
        comprobar_escritura(objetivo)
        # "mueve foto.jpg a imagenes": si el destino no existe y no tiene extensión, es una carpeta nueva.
        a_carpeta = (objetivo.is_dir() or len(fuentes) > 1 or destino.rstrip().endswith(("/", "\\"))
                     or (not objetivo.exists() and not objetivo.suffix and bool(fuentes[0].suffix)))
        if a_carpeta:
            objetivo.mkdir(parents=True, exist_ok=True)
        hechos = []
        for fuente in fuentes:
            if mover:
                comprobar_escritura(fuente)
            final = ruta_libre(objetivo / fuente.name if a_carpeta else objetivo)
            final.parent.mkdir(parents=True, exist_ok=True)
            if mover:
                shutil.move(str(fuente), str(final))
            elif fuente.is_dir():
                shutil.copytree(fuente, final)
            else:
                shutil.copy2(fuente, final)
            hechos.append(f"{fuente.name} -> {final}")
        verbo = "Movidos" if mover else "Copiados"
        return f"{verbo} {len(hechos)}:\n" + "\n".join(hechos[:50]) + ("\n..." if len(hechos) > 50 else "")

    @registro.herramienta(
        "Convierte un archivo a otro formato. " + FORMATOS_SOPORTADOS + " El resultado se guarda junto al original.",
        origen="Archivo a convertir (o comodín para varios, p. ej. 'descargas/*.png')",
        formato="Formato de destino: pdf, docx, txt, md, xlsx, csv, png, jpg, webp...",
    )
    def convertir_archivo(origen: str, formato: str) -> str:
        fuentes = [p for patron in _separar_rutas(origen) for p in expandir(patron) if p.is_file()]
        if not fuentes:
            return f"No encuentro el archivo '{origen}'."
        resultados = []
        for fuente in fuentes[:30]:
            try:
                resultados.append(f"{fuente.name} -> {convertir(fuente, formato.strip('. ').lower())}")
            except Exception as e:
                resultados.append(f"{fuente.name}: no se pudo ({e})")
        return "\n".join(resultados)

    @registro.herramienta(
        "Comprime archivos y carpetas en un .zip.",
        origen="Rutas o comodines separados por ';'",
        destino="Ruta del .zip (por defecto, junto al primer archivo)",
    )
    def comprimir(origen: str, destino: str = "") -> str:
        fuentes = [p for patron in _separar_rutas(origen) for p in expandir(patron)]
        if not fuentes:
            return f"No encuentro nada en '{origen}'."
        zip_destino = resolver(destino) if destino else fuentes[0].with_suffix(".zip")
        if zip_destino.suffix.lower() != ".zip":
            zip_destino = zip_destino.with_suffix(".zip")
        zip_destino = ruta_libre(zip_destino)
        comprobar_escritura(zip_destino)
        total = 0
        with zipfile.ZipFile(zip_destino, "w", zipfile.ZIP_DEFLATED) as z:
            for fuente in fuentes:
                if fuente.is_dir():
                    for archivo in fuente.rglob("*"):
                        if archivo.is_file():
                            z.write(archivo, archivo.relative_to(fuente.parent))
                            total += 1
                else:
                    z.write(fuente, fuente.name)
                    total += 1
        return f"Creado {zip_destino} ({total} archivos, {tamano_legible(zip_destino.stat().st_size)})."

    @registro.herramienta(
        "Descomprime un .zip, .rar, .7z, .tar o .tar.gz.",
        archivo="Ruta del archivo comprimido",
        destino="Carpeta donde extraer (por defecto, una carpeta con su nombre al lado)",
    )
    def descomprimir(archivo: str, destino: str = "") -> str:
        comprimido = resolver(archivo)
        if not comprimido.is_file():
            return f"No existe {comprimido}."
        nombre_base = comprimido.name.removesuffix(".gz").removesuffix(".tar") if comprimido.suffix == ".gz" \
            else comprimido.stem
        carpeta = resolver(destino) if destino else ruta_libre(comprimido.parent / nombre_base)
        comprobar_escritura(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        sufijo = comprimido.suffix.lower()
        if sufijo == ".zip":
            with zipfile.ZipFile(comprimido) as z:
                for miembro in z.namelist():  # evita rutas que se salgan de la carpeta destino
                    if not (carpeta / miembro).resolve().is_relative_to(carpeta.resolve()):
                        return f"El zip contiene una ruta peligrosa ({miembro}); no lo extraigo."
                z.extractall(carpeta)
        elif sufijo in (".tar", ".gz", ".tgz", ".bz2", ".xz"):
            with tarfile.open(comprimido) as t:
                t.extractall(carpeta, filter="data")
        elif sufijo in (".rar", ".7z"):
            # El tar de Windows 11 (libarchive) sabe extraer RAR y 7z.
            r = subprocess.run(["tar", "-xf", str(comprimido), "-C", str(carpeta)], capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode != 0:
                return f"No he podido extraerlo: {r.stderr.strip()[:300]}"
        else:
            return f"No sé descomprimir archivos {sufijo}."
        cuantos = sum(1 for _ in carpeta.rglob("*"))
        return f"Extraído en {carpeta} ({cuantos} elementos)."
