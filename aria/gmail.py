# Gmail por IMAP (leer y organizar) y SMTP (enviar), con varias cuentas.
# Cada cuenta usa una contraseña de aplicación guardada en el Administrador de credenciales.
#
# Trabajamos siempre sobre "Todos los mensajes" ([Gmail]/All Mail): ahí el buscador de Gmail (X-GM-RAW)
# ve todo, y los uid son estables. Las carpetas de Gmail son etiquetas (X-GM-LABELS).
# Eliminar = mover a la Papelera (recuperable 30 días). Nunca se borra nada para siempre.
import base64
import email
import imaplib
import json
import re
import smtplib
from contextlib import contextmanager
from email.message import EmailMessage
from email.policy import default as politica

from aria import secretos
from aria.texto import html_a_texto, normalizar

IMAP_HOST, SMTP_HOST = "imap.gmail.com", "smtp.gmail.com"


class ErrorGmail(Exception):
    pass


# ---------- Nombres de carpeta (UTF-7 modificado, el formato de IMAP) ----------

def utf7_decodificar(texto: str) -> str:
    partes = re.split(r"&([^-]*)-", texto)
    salida = []
    for i, parte in enumerate(partes):
        if i % 2 == 0:
            salida.append(parte)
        elif parte == "":
            salida.append("&")
        else:
            b64 = parte.replace(",", "/")
            salida.append(base64.b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-16-be"))
    return "".join(salida)


def utf7_codificar(texto: str) -> str:
    salida, pendiente = [], ""

    def volcar():
        nonlocal pendiente
        if pendiente:
            b64 = base64.b64encode(pendiente.encode("utf-16-be")).decode().rstrip("=").replace("/", ",")
            salida.append(f"&{b64}-")
            pendiente = ""

    for c in texto:
        if 0x20 <= ord(c) <= 0x7E:
            volcar()
            salida.append("&-" if c == "&" else c)
        else:
            pendiente += c
    volcar()
    return "".join(salida)


def _entrecomillar(nombre: str) -> str:
    return '"' + utf7_codificar(nombre).replace("\\", "\\\\").replace('"', '\\"') + '"'


# ---------- Cuentas ----------

def cuentas() -> list[dict]:
    """[{'correo': ..., 'alias': ...}]. Migra la configuración antigua de una sola cuenta."""
    datos = secretos.obtener("gmail_cuentas")
    if datos:
        return json.loads(datos)
    antiguo_usuario, antigua_clave = secretos.obtener("gmail_usuario"), secretos.obtener("gmail_clave")
    if antiguo_usuario and antigua_clave:
        guardar_cuenta(antiguo_usuario.lower(), antigua_clave, "")
        secretos.borrar("gmail_usuario")
        secretos.borrar("gmail_clave")
        return cuentas()
    return []


def principal() -> str | None:
    lista = cuentas()
    elegida = secretos.obtener("gmail_principal")
    if elegida and any(c["correo"] == elegida for c in lista):
        return elegida
    return lista[0]["correo"] if lista else None


def guardar_cuenta(correo: str, clave: str, alias: str = ""):
    lista = [c for c in json.loads(secretos.obtener("gmail_cuentas") or "[]") if c["correo"] != correo]
    lista.append({"correo": correo, "alias": alias.strip()})
    secretos.guardar("gmail_cuentas", json.dumps(lista, ensure_ascii=False))
    secretos.guardar(f"gmail_clave:{correo}", clave)
    if len(lista) == 1:
        secretos.guardar("gmail_principal", correo)


def quitar_cuenta(correo: str) -> bool:
    lista = cuentas()
    restantes = [c for c in lista if c["correo"] != correo]
    if len(restantes) == len(lista):
        return False
    secretos.guardar("gmail_cuentas", json.dumps(restantes, ensure_ascii=False))
    secretos.borrar(f"gmail_clave:{correo}")
    if secretos.obtener("gmail_principal") == correo:
        secretos.borrar("gmail_principal")
    return True


def poner_principal(correo: str):
    secretos.guardar("gmail_principal", correo)


def describir_cuentas() -> str:
    p = principal()
    return ", ".join(f"{c['correo']}" + (f" ({c['alias']})" if c["alias"] else "") + (" [principal]" if c["correo"] == p else "")
                     for c in cuentas())


def resolver_cuenta(texto: str = "") -> str:
    """'' -> principal; correo o alias (aproximado) -> esa cuenta."""
    lista = cuentas()
    if not lista:
        raise ErrorGmail(
            "Gmail no está conectado. Ofrece al usuario enseñarle a conectarlo paso a paso; si acepta, llama a "
            "consultar_guia('gmail'). No des instrucciones de memoria. Al final tendrá que escribir /conectar gmail."
        )
    if not texto.strip():
        return principal()
    buscado = normalizar(texto)
    for c in lista:
        if buscado in (normalizar(c["correo"]), normalizar(c["alias"])):
            return c["correo"]
    candidatas = [c for c in lista if buscado in normalizar(c["correo"]) or (c["alias"] and buscado in normalizar(c["alias"]))]
    if len(candidatas) == 1:
        return candidatas[0]["correo"]
    raise ErrorGmail(f"No sé qué cuenta es '{texto}'. Cuentas conectadas: {describir_cuentas()}")


def resolver_cuentas(texto: str = "") -> list[str]:
    """Para leer: '' o 'todas' = todas las cuentas."""
    if not texto.strip() or normalizar(texto) in ("todas", "todos", "all"):
        resolver_cuenta()  # lanza el error de "no conectado" si no hay ninguna
        return [c["correo"] for c in cuentas()]
    return [resolver_cuenta(texto)]


def _clave(correo: str) -> str:
    clave = secretos.obtener(f"gmail_clave:{correo}")
    if not clave:
        raise ErrorGmail(f"Falta la contraseña de {correo}. Que el usuario repita /conectar gmail.")
    return clave


def probar(correo: str, clave: str):
    conexion = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        conexion.login(correo, clave)
    finally:
        try:
            conexion.logout()
        except Exception:
            pass


# ---------- Conexión IMAP ----------

class Buzon:
    """Una sesión IMAP sobre 'Todos los mensajes' de una cuenta."""

    def __init__(self, conexion: imaplib.IMAP4_SSL, correo: str):
        self.c = conexion
        self.correo = correo
        self._carpetas = None

    def carpetas(self) -> list[tuple[str, str]]:
        """[(nombre, uso_especial)], p. ej. ('[Gmail]/Papelera', '\\Trash')."""
        if self._carpetas is None:
            _, filas = self.c.list()
            self._carpetas = []
            for fila in filas or []:
                if not isinstance(fila, bytes):
                    continue
                m = re.match(rb'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<nombre>.+)', fila)
                if not m:
                    continue
                nombre = m.group("nombre").decode(errors="replace").strip()
                if nombre.startswith('"'):
                    nombre = nombre[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                especial = next((f for f in m.group("flags").decode().split()
                                 if f in ("\\All", "\\Trash", "\\Sent", "\\Drafts", "\\Junk", "\\Flagged", "\\Important")), "")
                self._carpetas.append((utf7_decodificar(nombre), especial))
        return self._carpetas

    def especial(self, uso: str) -> str:
        nombre = next((n for n, e in self.carpetas() if e == uso), None)
        if nombre is None:
            raise ErrorGmail(f"No encuentro la carpeta especial {uso} en Gmail. ¿Está activado IMAP?")
        return nombre

    def buscar(self, consulta: str, limite: int) -> list[bytes]:
        self.c.literal = consulta.encode("utf-8")
        _, datos = self.c.uid("SEARCH", "CHARSET", "UTF-8", "X-GM-RAW")
        uids = datos[0].split() if datos and datos[0] else []
        return uids[-limite:][::-1]  # los más recientes primero

    def resumen(self, uid: bytes) -> dict | None:
        _, datos = self.c.uid("FETCH", uid, "(FLAGS X-GM-LABELS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if not datos or not isinstance(datos[0], tuple):
            return None
        meta = (datos[0][0] + b"".join(d for d in datos[1:] if isinstance(d, bytes))).decode(errors="replace")
        cabecera = email.message_from_bytes(datos[0][1], policy=politica)
        etiquetas = re.search(r"X-GM-LABELS \((.*?)\)(?: |$|\))", meta)
        lista = []
        if etiquetas:
            for e in re.findall(r'"((?:[^"\\]|\\.)*)"|(\S+)', etiquetas.group(1)):
                nombre = utf7_decodificar((e[0] or e[1]).replace('\\"', '"').replace("\\\\", "\\"))
                lista.append({"\\Inbox": "Recibidos", "\\Important": "", "\\Sent": "Enviados", "\\Draft": "Borradores",
                              "\\Starred": "Destacados"}.get(nombre, nombre))
        return {"uid": uid.decode(), "fecha": str(cabecera["date"] or ""), "de": str(cabecera["from"] or ""),
                "asunto": str(cabecera["subject"] or "(sin asunto)"), "leido": "\\Seen" in meta,
                "etiquetas": [e for e in lista if e]}

    def mensaje(self, uid: str):
        _, datos = self.c.uid("FETCH", uid, "(BODY.PEEK[])")
        if not datos or not isinstance(datos[0], tuple):
            raise ErrorGmail(f"No encuentro el correo {uid} en {self.correo}.")
        return email.message_from_bytes(datos[0][1], policy=politica)

    def asegurar_etiqueta(self, nombre: str):
        if not any(n.lower() == nombre.lower() for n, _ in self.carpetas()):
            self.c.create(_entrecomillar(nombre))
            self._carpetas = None

    def etiquetas(self, uids: str, nombre: str, quitar: bool = False):
        etiqueta = "\\Inbox" if nombre == "\\Inbox" else _entrecomillar(nombre)
        tipo, respuesta = self.c.uid("STORE", uids, ("-" if quitar else "+") + "X-GM-LABELS", f"({etiqueta})")
        if tipo != "OK":
            raise ErrorGmail(f"Gmail no ha aceptado el cambio de etiqueta: {respuesta}")

    def banderas(self, uids: str, bandera: str, quitar: bool = False):
        self.c.uid("STORE", uids, ("-" if quitar else "+") + "FLAGS", f"({bandera})")

    def a_papelera(self, uids: str):
        tipo, respuesta = self.c.uid("MOVE", uids, _entrecomillar(self.especial("\\Trash")))
        if tipo != "OK":
            raise ErrorGmail(f"Gmail no ha movido los correos a la papelera: {respuesta}")


@contextmanager
def buzon(correo: str, escritura: bool = False):
    conexion = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        try:
            conexion.login(correo, _clave(correo))
        except imaplib.IMAP4.error as e:
            raise ErrorGmail(f"Gmail rechaza las credenciales de {correo} ({e}). Que el usuario repita /conectar gmail.")
        b = Buzon(conexion, correo)
        conexion.select(_entrecomillar(b.especial("\\All")), readonly=not escritura)
        yield b
    finally:
        try:
            conexion.logout()
        except Exception:
            pass


def cuerpo_texto(mensaje) -> str:
    parte = mensaje.get_body(preferencelist=("plain", "html"))
    if parte is None:
        return "(sin texto)"
    contenido = parte.get_content()
    return html_a_texto(contenido) if parte.get_content_type() == "text/html" else contenido


# ---------- Enviar ----------

def enviar(correo: str, para: str, asunto: str, cuerpo: str, cc: str = "", responder_a: str = "") -> str:
    mensaje = EmailMessage()
    if responder_a:
        with buzon(correo) as b:
            original = b.mensaje(responder_a)
        para = para or str(original["reply-to"] or original["from"])
        asunto_original = str(original["subject"] or "")
        asunto = asunto or (asunto_original if asunto_original.lower().startswith("re:") else f"Re: {asunto_original}")
        if original["message-id"]:
            mensaje["In-Reply-To"] = original["message-id"]
            mensaje["References"] = f"{original['references'] or ''} {original['message-id']}".strip()
    if not para:
        raise ErrorGmail("Falta el destinatario.")
    mensaje["From"], mensaje["To"], mensaje["Subject"] = correo, para, asunto
    if cc:
        mensaje["Cc"] = cc
    mensaje.set_content(cuerpo)
    with smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=30) as smtp:
        smtp.login(correo, _clave(correo))
        smtp.send_message(mensaje)
    return para
