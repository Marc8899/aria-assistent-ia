# Conexión con la cuenta de Google (Calendar, Drive, Docs, Classroom) mediante OAuth.
# Requiere datos/google_credentials.json (lo explica la guía 'google'). El token se guarda en
# datos/google_token.json y se renueva solo.
from aria import config

ALCANCES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
]
RUTA_CREDENCIALES = config.RAIZ / "datos" / "google_credentials.json"
RUTA_TOKEN = config.RAIZ / "datos" / "google_token.json"


class ErrorGoogle(Exception):
    pass


def conectado() -> bool:
    return RUTA_TOKEN.exists()


def conectar_interactivo() -> str:
    """Abre el navegador para que el usuario autorice a Aria. Devuelve el correo de la cuenta."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not RUTA_CREDENCIALES.exists():
        raise ErrorGoogle(f"Falta {RUTA_CREDENCIALES}. Sigue la guía 'google' para descargarlo.")
    flujo = InstalledAppFlow.from_client_secrets_file(str(RUTA_CREDENCIALES), ALCANCES)
    credenciales = flujo.run_local_server(port=0, prompt="consent", open_browser=True,
                                          success_message="Aria ya está conectada a tu cuenta de Google. "
                                                          "Puedes cerrar esta pestaña.")
    RUTA_TOKEN.write_text(credenciales.to_json(), encoding="utf-8")
    perfil = servicio("drive", "v3").about().get(fields="user(emailAddress)").execute()
    return perfil["user"]["emailAddress"]


def _credenciales():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not RUTA_TOKEN.exists():
        raise ErrorGoogle(
            "La cuenta de Google no está conectada. Ofrece al usuario conectarla; si acepta, llama a "
            "consultar_guia('google') y síguela paso a paso. Al final escribirá /conectar google."
        )
    credenciales = Credentials.from_authorized_user_file(str(RUTA_TOKEN), ALCANCES)
    if not credenciales.valid:
        if credenciales.expired and credenciales.refresh_token:
            try:
                credenciales.refresh(Request())
            except Exception as e:
                raise ErrorGoogle(f"El permiso de Google ha caducado ({e}). Que el usuario repita /conectar google.")
            RUTA_TOKEN.write_text(credenciales.to_json(), encoding="utf-8")
        else:
            raise ErrorGoogle("El permiso de Google no es válido. Que el usuario repita /conectar google.")
    return credenciales


def comprobar_conexion():
    _credenciales()


def servicio(nombre: str, version: str):
    from googleapiclient.discovery import build

    return build(nombre, version, credentials=_credenciales(), cache_discovery=False)


def desconectar():
    RUTA_TOKEN.unlink(missing_ok=True)
