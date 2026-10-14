# OBS + "modo juego". La lógica de abrir y grabar está en aria/modo_juego.py.
from pathlib import Path

from aria.juegos import PerfilJuego
from aria.obs import ErrorOBS

GRUPO = "juegos"
PALABRAS_CLAVE = ("obs", "grab", "jugar", "juego", "juega", "partida", "escena", "stream",
                  "directo", "video", "romhack", "mods", "emulador", "port")


def registrar(registro, ctx):
    obs, juegos, apps = ctx.obs, ctx.juegos, ctx.apps

    @registro.herramienta("Dice si OBS está abierto, si está grabando, la escena actual y las escenas que hay.")
    def obs_estado() -> str:
        try:
            e = obs.estado()
        except ErrorOBS as error:
            return str(error)
        return (f"OBS conectado. Grabando: {'sí' if e['grabando'] else 'no'}. "
                f"Escena actual: {e['escena_actual']}. Escenas: {', '.join(e['escenas'])}.")

    @registro.herramienta(
        "Controla OBS: empezar o parar de grabar, o cambiar de escena. Abre OBS si no lo está.",
        accion="Una de: iniciar_grabacion, detener_grabacion, cambiar_escena",
        escena="Nombre de la escena (solo para cambiar_escena)",
    )
    def obs_control(accion: str, escena: str = "") -> str:
        if accion == "iniciar_grabacion":
            obs.asegurar_abierto()
            return "Grabando." if obs.iniciar_grabacion() else "Ya estaba grabando."
        if accion == "detener_grabacion":
            ruta = obs.detener_grabacion()
            return f"Grabación detenida. Vídeo: {ruta}" if ruta else "No estaba grabando."
        if accion == "cambiar_escena":
            obs.asegurar_abierto()
            obs.cambiar_escena(escena)
            return f"Escena cambiada a {escena}."
        return "Acción no válida. Usa iniciar_grabacion, detener_grabacion o cambiar_escena."

    @registro.herramienta(
        "Marca una aplicación ya conocida como juego (o deja de considerarla juego). Los juegos se graban "
        "al abrirlos. Úsala cuando el usuario diga que algo es un juego, romhack o mod.",
        nombre="Nombre de la aplicación",
        es_juego="true para marcarla como juego, false para desmarcarla",
    )
    def marcar_como_juego(nombre: str, es_juego: bool = True) -> str:
        app, sugerencias = apps.buscar(nombre)
        if app is None:
            if sugerencias:
                return f"No sé cuál de estas es: {', '.join(sugerencias)}. Pregunta al usuario."
            return f"No encuentro '{nombre}'. Si es un .exe suelto, pide la ruta y usa anadir_juego."
        apps.marcar_juego(app, es_juego)
        if es_juego:
            return f"'{app.nombre}' marcado como juego: a partir de ahora se grabará al abrirlo."
        return f"'{app.nombre}' ya no se considera juego."

    @registro.herramienta(
        "Añade juegos que no detecta solo (romhacks, mods, ports, juegos sin instalador). Acepta la ruta de un "
        ".exe o de una carpeta: con una carpeta, se añaden todos los juegos que haya dentro y se vigila para "
        "detectar los nuevos que pongas en ella.",
        ruta="Ruta completa del .exe o de la carpeta",
        nombre="Cómo quiere llamarlo el usuario (solo para un .exe; vacío = nombre del archivo)",
    )
    def anadir_juego(ruta: str, nombre: str = "") -> str:
        destino = Path(ruta.strip().strip('"')).expanduser()
        if destino.is_dir():
            encontrados = apps.anadir_carpeta_juegos(destino)
            if not encontrados:
                return (f"He guardado la carpeta {destino}, pero no veo ningún .exe de juego dentro (miro hasta "
                        f"3 niveles). Si el juego necesita un emulador, añade el .exe concreto.")
            return (f"Carpeta añadida. Juegos encontrados: {', '.join(a.nombre for a in encontrados)}. "
                    "Si alguno tiene un nombre raro, puede renombrarse con anadir_juego pasando su .exe y un nombre.")
        if destino.suffix.lower() not in (".exe", ".lnk") or not destino.is_file():
            return f"No existe el archivo {destino} o no es un .exe/.lnk."
        app = apps.anadir_exe(nombre.strip() or destino.stem, destino)
        return f"Juego añadido: '{app.nombre}'. Se grabará al abrirlo y la grabación parará al cerrarlo."

    @registro.herramienta(
        "Personaliza el modo juego de un juego concreto (escena de OBS, segundos antes de grabar). No hace falta "
        "para grabar: los juegos ya se graban al abrirlos y paran al cerrarlos. Confirma antes la escena con obs_estado.",
        nombre="Cómo llama el usuario al juego",
        aplicacion="Nombre exacto del juego en la lista de aplicaciones",
        escena_obs="Escena de OBS a usar (vacío = no cambiar)",
        espera_segundos="Segundos a esperar antes de grabar (para saltar pantallas de carga)",
    )
    def configurar_juego(nombre: str, aplicacion: str, escena_obs: str = "", espera_segundos: int = 15) -> str:
        app, sugerencias = apps.buscar(aplicacion)
        if app is None:
            return f"No encuentro la aplicación '{aplicacion}'. Opciones parecidas: {', '.join(sugerencias) or 'ninguna'}."
        if not app.es_juego:
            apps.marcar_juego(app, True)
        juegos.configurar(PerfilJuego(nombre, app.nombre, escena_obs, espera_segundos))
        return f"Modo juego personalizado para '{nombre}' ({app.nombre})."

    @registro.herramienta(
        "MODO JUEGO: el usuario quiere jugar. Abre OBS si hace falta, abre el juego, graba la partida "
        "y para la grabación al cerrar el juego.",
        nombre="Juego al que quiere jugar",
    )
    def jugar(nombre: str) -> str:
        perfil = juegos.buscar(nombre)
        app, sugerencias = apps.buscar(perfil.aplicacion if perfil else nombre)
        if app is None:
            if sugerencias:
                return f"No sé cuál de estos es: {', '.join(sugerencias)}. Pregunta al usuario."
            return (f"No encuentro el juego '{nombre}'. Si es un romhack o mod suelto, pregunta al usuario dónde "
                    "está el .exe o su carpeta y añádelo con anadir_juego.")
        if not app.es_juego:
            apps.marcar_juego(app, True)  # si dice que quiere jugar a ello, es un juego
        return ctx.modo_juego.jugar(app)
