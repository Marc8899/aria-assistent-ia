from aria import config
from aria.texto import normalizar

GRUPO = "aplicaciones"
PALABRAS_CLAVE = ("abre", "abrir", "abreme", "aplicacion", "app", "programa", "instalad",
                  "ejecuta", "lanza", "inicia", "cierra", "cerrar", "pon", "arranca", "echar", "echa",
                  "abierto", "abiertas", "ventana")
ETIQUETAS = {"steam": "Steam", "epic": "Epic"}


def registrar(registro, ctx):
    apps = ctx.apps

    def describir(app) -> str:
        if not app.es_juego:
            return app.nombre
        etiqueta = ETIQUETAS.get(app.tipo, "juego")
        perfil = ctx.juegos.buscar_por_app(app.nombre)
        extra = f" · escena '{perfil.escena_obs}', espera {perfil.espera_segundos} s" if perfil else ""
        return f"{app.nombre} ({etiqueta}{extra})"

    @registro.herramienta(
        "Lista las aplicaciones y juegos del PC del usuario (menú Inicio, escritorio, Steam, Epic, "
        "carpetas de juegos y los añadidos a mano).",
        filtro="Texto para filtrar por nombre, o 'juegos' para ver solo juegos. Vacío = todas.",
    )
    def listar_aplicaciones(filtro: str = "") -> str:
        lista = apps.todas(refrescar=True)
        filtro = normalizar(filtro)
        if filtro in ("juegos", "juego"):
            lista = [a for a in lista if a.es_juego]
        elif filtro:
            lista = [a for a in lista if filtro in normalizar(a.nombre)]
        if not lista:
            return "No encuentro aplicaciones con ese filtro."
        lineas = [describir(a) for a in lista[:120]]
        extra = f"\n(... y {len(lista) - 120} más; usa un filtro)" if len(lista) > 120 else ""
        return f"{len(lista)} aplicaciones:\n" + "\n".join(lineas) + extra

    @registro.herramienta(
        "Abre una aplicación o juego del PC por su nombre. Al abrir un juego se graba la partida "
        "automáticamente con OBS (modo juego).",
        nombre="Nombre de la aplicación (no hace falta que sea exacto)",
    )
    def abrir_aplicacion(nombre: str) -> str:
        app, sugerencias = apps.buscar(nombre)
        if app is None:
            if sugerencias:
                return f"No sé cuál de estas es: {', '.join(sugerencias)}. Pregunta al usuario."
            return (f"No encuentro '{nombre}' entre las aplicaciones. Si es un juego o mod suelto, pregunta al "
                    "usuario dónde está el .exe o su carpeta y añádelo con anadir_juego.")
        if config.GRABAR_AL_ABRIR_JUEGOS and (app.es_juego or ctx.juegos.buscar_por_app(app.nombre)):
            return ctx.modo_juego.jugar(app)
        app.abrir()
        return f"Abriendo {app.nombre}."

    @registro.herramienta("Lista las aplicaciones/ventanas que el usuario tiene abiertas ahora mismo.")
    def aplicaciones_abiertas() -> str:
        from aria.ventanas import ventanas_abiertas
        por_programa: dict[str, list[str]] = {}
        for v in ventanas_abiertas():
            por_programa.setdefault(v.proceso, []).append(v.titulo)
        return "\n".join(f"- {programa}: {' | '.join(t[:70] for t in titulos[:4])}"
                         for programa, titulos in sorted(por_programa.items())) or "No hay ventanas abiertas."

    @registro.herramienta(
        "Cierra una aplicación abierta (todas sus ventanas). Primero lo intenta de forma amable, como pulsar la X, "
        "para que la app pueda pedir guardar; si se indica forzar, la cierra a la fuerza (se pierde lo no "
        "guardado). Nunca cierra procesos del sistema ni a Aria. El usuario lo aprobará.",
        confirmar=True,
        nombre="Nombre de la aplicación (p. ej. 'Chrome', 'Spotify', 'Bloc de notas', o un juego)",
        forzar="true para forzar el cierre si no se cierra por las buenas",
    )
    def cerrar_aplicacion(nombre: str, forzar: bool = False) -> str:
        from aria.ventanas import buscar_abiertas, cerrar
        app, _ = apps.buscar(nombre)
        ventanas = buscar_abiertas(nombre, app.carpeta if app and app.carpeta else "")
        if not ventanas and app:
            ventanas = buscar_abiertas(app.nombre, app.carpeta)
        if not ventanas:
            return f"No veo '{nombre}' abierto. Usa aplicaciones_abiertas para ver qué hay."
        cerradas, siguen = cerrar(ventanas, forzar)
        texto = f"Cerrado: {', '.join(cerradas)}." if cerradas else ""
        if siguen:
            texto += (f" Sigue abierto: {', '.join(siguen)}. Puede estar preguntando si guardar algo; "
                      "si el usuario quiere, se puede forzar (perderá lo no guardado).")
        return texto.strip()

    @registro.herramienta(
        "Añade al catálogo un programa que no aparece (un .exe suelto, una app portable...). Después se podrá "
        "abrir por su nombre. Para buscar el .exe puedes usar buscar_archivos.",
        ruta="Ruta completa del .exe o del acceso directo .lnk",
        nombre="Nombre con el que llamarlo",
        es_juego="true si es un juego (se grabará al abrirlo)",
    )
    def anadir_aplicacion(ruta: str, nombre: str = "", es_juego: bool = False) -> str:
        from aria.archivos import resolver
        archivo = resolver(ruta)
        if archivo.suffix.lower() not in (".exe", ".lnk") or not archivo.is_file():
            return f"No existe {archivo} o no es un .exe/.lnk."
        app = apps.anadir_exe(nombre.strip() or archivo.stem, archivo, es_juego)
        return f"Añadida '{app.nombre}'{' (juego)' if es_juego else ''}. Ya puedo abrirla por su nombre."
