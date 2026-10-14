# Interfaz de terminal. Solo entrada/salida: la lógica está en asistente.py.
import re
from datetime import datetime
from getpass import getpass

from aria import config, copias, gmail, google_cuenta, secretos
from aria.asistente import Asistente, ErrorModelo, comprobar_modelo
from aria.contexto import Contexto, construir
from aria.herramientas import crear_registro, github
from aria.obs import ErrorOBS
from aria.texto import parece_secreto

AYUDA = """Comandos:
  /tareas              ver las tareas activas
  /memorias            ver lo que recuerdo
  /olvidar N           borrar el recuerdo N
  /conectar SERVICIO   conectar gmail, github, obs, icloud (Apple Calendar) o google
                       (Calendar, Drive, Docs, Classroom). La contraseña no pasa por el chat.
  /desconectar SERVICIO   (para una cuenta de Gmail concreta: /desconectar gmail correo)
  /gmail               ver las cuentas de Gmail; /gmail principal CORREO para elegir la principal
  /calendario          ver o cambiar qué calendario se usa (icloud / google)
  /exportar            guardar TODO lo que sé y registro en un archivo JSON
  /api                 cómo arrancar y usar la API de Aria
  /reiniciar           empezar una conversación nueva (recuerdos y tareas se mantienen)
  /ayuda               esta ayuda
  salir                terminar"""

SECRETOS_POR_SERVICIO = {
    "github": ("github_token",),
    "obs": ("obs_clave",),
    "icloud": ("icloud_usuario", "icloud_clave"),
}


def _avisar(mensaje: str):
    # Llega desde otro hilo mientras se espera tu mensaje: se reimprime el "Tú: ".
    print(f"\n  {mensaje}\nTú: ", end="", flush=True)


def _mostrar_herramienta(nombre, argumentos):
    print(f"  [usando herramienta: {nombre} {argumentos}]")


def _confirmar(nombre, argumentos) -> bool:
    print(f"\n  [!] {config.NOMBRE_ASISTENTE} quiere ejecutar «{nombre}» con:")
    for clave, valor in argumentos.items():
        valor = str(valor).replace("\n", "\n      ")
        print(f"    {clave}: {valor}")
    return input("  ¿Lo hago? (s/n): ").strip().lower() in ("s", "si", "sí", "y", "yes")


def _limpiar_secreto(texto: str) -> str:
    """Al pegar, algunas terminales cuelan caracteres invisibles (marcas de pegado ESC[200~ / ESC[201~,
    un Ctrl+V literal...). Las claves de verdad nunca los llevan, así que se quitan."""
    texto = re.sub(r"\x1b\[20[01]~", "", texto)
    return "".join(c for c in texto if c.isprintable()).strip()


def _pedir_secreto(etiqueta: str) -> str:
    """Pide una clave sin mostrarla. Algunas terminales (p. ej. las integradas en otras apps)
    no dejan escribir a ciegas: en ese caso se ofrece escribirla a la vista y se borra de la pantalla."""
    print(f"  {etiqueta}")
    clave = _limpiar_secreto(getpass("  (escribe o pega y pulsa Enter; no se verá nada, es normal): "))
    if clave:
        return clave
    print("  No ha llegado nada. Si tu terminal no te deja escribir a ciegas, escríbela aquí a la vista\n"
          "  (no se envía al modelo y la borro de la pantalla al pulsar Enter). Enter vacío = cancelar.")
    clave = _limpiar_secreto(input("  Clave: "))
    print("\x1b[1A\x1b[2K  Clave: ********", flush=True)  # sobrescribe la línea con la clave
    return clave


def _conectar(servicio: str, ctx: Contexto):
    if servicio == "gmail":
        ya = gmail.cuentas()
        if ya:
            print(f"  Cuentas ya conectadas: {gmail.describir_cuentas()}. Vamos a añadir otra (o actualizar una).")
        usuario = input("  Dirección de Gmail: ").strip().lower()
        alias = input("  Alias para reconocerla (p. ej. personal, trabajo, uni; Enter = ninguno): ").strip()
        clave = _pedir_secreto("Contraseña de aplicación (16 letras).").replace(" ", "")
        if not clave:
            print("  Cancelado.")
            return
        try:
            gmail.probar(usuario, clave)
        except Exception as e:
            print(f"  No he podido entrar: {e}\n  Revisa la dirección y la contraseña de aplicación. No he guardado nada.")
            return
        gmail.guardar_cuenta(usuario, clave, alias)
        print(f"  Gmail conectado ({usuario}). Cuentas: {gmail.describir_cuentas()}")
    elif servicio == "github":
        token = _pedir_secreto("Token de GitHub (empieza por github_pat_).")
        if not token:
            print("  Cancelado.")
            return
        try:
            usuario = github.peticion("GET", "/user", token=token)["login"]
        except Exception as e:
            print(f"  GitHub no acepta el token: {e}")
            return
        secretos.guardar("github_token", token)
        print(f"  GitHub conectado como {usuario}.")
    elif servicio == "obs":
        # Primero comprobar que OBS responde: sin eso no se puede validar la contraseña.
        try:
            ctx.obs.probar("")
            print("  OBS responde y no tiene contraseña: conectado.")
            secretos.guardar("obs_clave", "")
            return
        except ErrorOBS as e:
            if "contraseña" not in str(e):
                print("  OBS no responde. Antes de /conectar obs:\n"
                      "   1) Abre OBS.\n"
                      "   2) Herramientas > Ajustes del servidor WebSocket > marca 'Activar servidor WebSocket'.\n"
                      "   3) Pulsa 'Mostrar información de conexión' y copia la contraseña.\n"
                      "  No he guardado nada.")
                return
        clave = _pedir_secreto("Contraseña del servidor WebSocket de OBS.")
        if not clave:
            print("  Cancelado.")
            return
        try:
            version = ctx.obs.probar(clave)
        except ErrorOBS as e:
            print(f"  {e}\n  He recibido {len(clave)} caracteres (las contraseñas que genera OBS suelen tener 16).\n"
                  f"  Si no cuadra, prueba a escribirla a mano en vez de pegarla. No he guardado nada.")
            return
        secretos.guardar("obs_clave", clave)
        print(f"  OBS {version} conectado.")
    elif servicio == "icloud":
        import caldav
        usuario = input("  Tu Apple ID (correo): ").strip()
        clave = _pedir_secreto("Contraseña específica de app de Apple (formato xxxx-xxxx-xxxx-xxxx).")
        if not clave:
            print("  Cancelado.")
            return
        try:
            calendarios = caldav.DAVClient(url="https://caldav.icloud.com", username=usuario,
                                           password=clave).principal().calendars()
        except Exception as e:
            print(f"  Apple rechaza la conexión: {e}\n  Revisa el Apple ID y la contraseña específica. No he guardado nada.")
            return
        secretos.guardar("icloud_usuario", usuario)
        secretos.guardar("icloud_clave", clave)
        secretos.guardar("calendario_proveedor", "icloud")
        ctx.calendario.reiniciar()
        print(f"  Apple Calendar conectado ({len(calendarios)} calendarios). Es ahora el calendario de Aria.")
    elif servicio == "google":
        print("  Se abrirá el navegador para que autorices a Aria en tu cuenta de Google...")
        try:
            correo = google_cuenta.conectar_interactivo()
        except Exception as e:
            print(f"  No se ha podido conectar: {e}")
            return
        if not secretos.obtener("calendario_proveedor"):
            secretos.guardar("calendario_proveedor", "google")
        ctx.calendario.reiniciar()
        proveedor = secretos.obtener("calendario_proveedor")
        print(f"  Google conectado ({correo}): Drive, Docs, Classroom y Calendar.\n"
              f"  Calendario activo: {proveedor} (cámbialo con /calendario google o /calendario icloud).")
    else:
        print("  Servicios: gmail, github, obs, icloud, google")


def _ejecutar_comando(entrada: str, asistente: Asistente, ctx: Contexto):
    comando, _, argumento = entrada.partition(" ")
    argumento = argumento.strip().lower()
    if comando == "/tareas":
        ahora = datetime.now()
        print("\n".join("  " + t.describir(ahora) for t in ctx.tareas.listar()) or "  (no hay tareas activas)")
    elif comando == "/memorias":
        filas = ctx.memoria.listar()
        print("\n".join(f"  [{i}] {t}" for i, t in filas) or "  (no recuerdo nada todavía)")
    elif comando == "/olvidar":
        if not argumento.isdigit():
            print("  Uso: /olvidar N   (mira los números con /memorias)")
        elif ctx.memoria.olvidar(int(argumento)):
            print("  Olvidado.")
        else:
            print(f"  No existe el recuerdo {argumento}.")
    elif comando == "/conectar":
        _conectar(argumento, ctx)
    elif comando == "/desconectar" and argumento.startswith("gmail"):
        correo = argumento.removeprefix("gmail").strip()
        lista = [c["correo"] for c in gmail.cuentas()]
        if not correo and len(lista) == 1:
            correo = lista[0]
        if not correo:
            print(f"  ¿Cuál? Escribe /desconectar gmail CORREO. Cuentas: {gmail.describir_cuentas() or 'ninguna'}")
        elif gmail.quitar_cuenta(correo):
            print(f"  {correo} desconectada. Quedan: {gmail.describir_cuentas() or 'ninguna'}")
        else:
            print(f"  No hay ninguna cuenta {correo}.")
    elif comando == "/gmail":
        partes = argumento.split()
        if len(partes) == 2 and partes[0] == "principal":
            if partes[1] in [c["correo"] for c in gmail.cuentas()]:
                gmail.poner_principal(partes[1])
                print(f"  Cuenta principal: {partes[1]}")
            else:
                print(f"  No hay ninguna cuenta {partes[1]}.")
        else:
            print(f"  Cuentas de Gmail: {gmail.describir_cuentas() or 'ninguna (usa /conectar gmail)'}\n"
                  f"  Añadir otra: /conectar gmail · Elegir la principal: /gmail principal CORREO")
    elif comando == "/desconectar":
        if argumento == "google":
            google_cuenta.desconectar()
        elif argumento in SECRETOS_POR_SERVICIO:
            for nombre in SECRETOS_POR_SERVICIO[argumento]:
                secretos.borrar(nombre)
        else:
            print("  Servicios: gmail, github, obs, icloud, google")
            print()
            return
        if secretos.obtener("calendario_proveedor") == argumento:
            secretos.borrar("calendario_proveedor")
        ctx.calendario.reiniciar()
        print(f"  {argumento} desconectado (credenciales borradas de este PC).")
    elif comando == "/calendario":
        if argumento in ("icloud", "google"):
            secretos.guardar("calendario_proveedor", argumento)
            ctx.calendario.reiniciar()
            print(f"  Calendario activo: {argumento}.")
        else:
            print(f"  Calendario activo: {secretos.obtener('calendario_proveedor') or 'ninguno'}. "
                  f"Usa /calendario icloud o /calendario google para cambiarlo.")
    elif comando == "/exportar":
        print(f"  Todo exportado a: {copias.exportar_a_archivo(ctx)}")
    elif comando == "/api":
        print(f"  Arranca la API en otra terminal con:  .venv\\Scripts\\python main.py --api\n"
              f"  Documentación interactiva:          http://{config.API_HOST}:{config.API_PUERTO}/docs\n"
              f"  Clave (cabecera X-API-Key):         {secretos.obtener('api_clave') or '(se crea al arrancarla)'}")
    elif comando == "/reiniciar":
        asistente.reiniciar()
        print("  Conversación reiniciada.")
    else:
        print(AYUDA)
    print()


def _responder(funcion, *args) -> str | None:
    try:
        return funcion(*args, al_usar_herramienta=_mostrar_herramienta, confirmar=_confirmar)
    except KeyboardInterrupt:
        print("\n  [cancelado]\n")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print("Copia este mensaje y pásamelo.\n")
    return None


def main():
    try:
        comprobar_modelo(config.MODELO)
    except ErrorModelo as e:
        print(f"\n{e}")
        return

    try:
        copias.copia_diaria()
    except Exception as e:
        print(f"  [aviso] No se ha podido hacer la copia de seguridad diaria: {e}")
    ctx = construir(avisar=_avisar)
    asistente = Asistente(crear_registro(ctx), ctx)
    print(f"{config.NOMBRE_ASISTENTE} lista. Escribe /ayuda para ver comandos o 'salir' para terminar.\n")

    try:
        saludo = _responder(asistente.saludar)
        if saludo:
            print(f"{config.NOMBRE_ASISTENTE}: {saludo}\n")
        while True:
            try:
                entrada = input("Tú: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not entrada:
                continue
            if entrada.lower() in ("salir", "exit"):
                break
            if entrada.startswith("/"):
                _ejecutar_comando(entrada, asistente, ctx)
                continue
            if parece_secreto(entrada):
                print("  [!] Parece que has escrito una contraseña o un token. Las claves no deben ir en el chat:\n"
                      "      usa /conectar gmail, /conectar github o /conectar obs.")
                if input("  ¿Enviar el mensaje igualmente? (s/n): ").strip().lower() not in ("s", "si", "sí"):
                    print("  No enviado.\n")
                    continue
            respuesta = _responder(asistente.responder, entrada)
            if respuesta is not None:
                print(f"{config.NOMBRE_ASISTENTE}: {respuesta}\n")
    finally:
        ctx.cerrar()
