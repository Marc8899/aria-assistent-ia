# Contraseñas y tokens: se guardan en el Administrador de credenciales de Windows,
# nunca en archivos del proyecto ni en la conversación con el modelo.
import keyring
from keyring.errors import PasswordDeleteError

SERVICIO = "aria-asistente"


def guardar(nombre: str, valor: str):
    keyring.set_password(SERVICIO, nombre, valor)


def obtener(nombre: str) -> str | None:
    return keyring.get_password(SERVICIO, nombre)


def borrar(nombre: str):
    try:
        keyring.delete_password(SERVICIO, nombre)
    except PasswordDeleteError:
        pass
