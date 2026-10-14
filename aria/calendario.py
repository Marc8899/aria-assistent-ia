# Calendario: Apple (iCloud, por CalDAV) o Google (API). Misma interfaz para los dos.
# El proveedor activo se guarda en el Administrador de credenciales ("calendario_proveedor").
import difflib
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from aria import google_cuenta, secretos
from aria.texto import normalizar

ICLOUD_URL = "https://caldav.icloud.com"
CACHE_SEGUNDOS = 600


class ErrorCalendario(Exception):
    pass


@dataclass
class Evento:
    id: str
    titulo: str
    inicio: datetime
    fin: datetime
    todo_el_dia: bool
    calendario: str = ""

    def describir(self) -> str:
        if self.todo_el_dia:
            cuando = f"{self.inicio:%Y-%m-%d} (todo el día)"
        else:
            cuando = f"{self.inicio:%Y-%m-%d %H:%M}–{self.fin:%H:%M}"
        return f"{cuando} · {self.titulo}" + (f" [{self.calendario}]" if self.calendario else "") + f" (id {self.id})"


def _a_datetime(valor) -> tuple[datetime, bool]:
    """Fecha de iCalendar/Google -> (datetime local sin zona, es_todo_el_dia)."""
    if isinstance(valor, datetime):
        if valor.tzinfo:
            valor = valor.astimezone().replace(tzinfo=None)
        return valor, False
    return datetime.combine(valor, datetime.min.time()), True


def parecidos(a: str, b: str) -> bool:
    a, b = normalizar(a), normalizar(b)
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.6


# ---------- Proveedores ----------

class _ICloud:
    nombre = "Apple Calendar (iCloud)"

    def __init__(self):
        import caldav
        usuario, clave = secretos.obtener("icloud_usuario"), secretos.obtener("icloud_clave")
        if not usuario or not clave:
            raise ErrorCalendario("iCloud no está conectado. Que el usuario escriba /conectar icloud.")
        self._cliente = caldav.DAVClient(url=ICLOUD_URL, username=usuario, password=clave)
        self._calendarios = None

    def calendarios(self):
        if self._calendarios is None:
            todos = self._cliente.principal().calendars()
            # Solo los calendarios que admiten eventos (no listas de recordatorios).
            self._calendarios = [c for c in todos if "VEVENT" in (c.get_supported_components() or ["VEVENT"])]
        return self._calendarios

    def eventos(self, desde: datetime, hasta: datetime) -> list[Evento]:
        eventos = []
        for cal in self.calendarios():
            for obj in cal.search(start=desde, end=hasta, event=True, expand=True):
                comp = obj.icalendar_component
                inicio, dia_entero = _a_datetime(comp.decoded("dtstart"))
                fin = _a_datetime(comp.decoded("dtend"))[0] if comp.get("dtend") else inicio + timedelta(hours=1)
                eventos.append(Evento(str(comp.get("uid")), str(comp.get("summary", "(sin título)")),
                                      inicio, fin, dia_entero, cal.name or ""))
        return eventos

    def crear(self, titulo, inicio: datetime, fin: datetime, todo_el_dia: bool, descripcion="") -> str:
        cal = self.calendarios()[0]
        if todo_el_dia:
            evento = cal.add_event(dtstart=inicio.date(), dtend=fin.date(), summary=titulo, description=descripcion)
        else:
            evento = cal.add_event(dtstart=inicio.astimezone(), dtend=fin.astimezone(), summary=titulo,
                                   description=descripcion)
        return str(evento.icalendar_component.get("uid"))

    def borrar(self, id_evento: str) -> bool:
        for cal in self.calendarios():
            try:
                cal.event_by_uid(id_evento).delete()
                return True
            except Exception:
                continue
        return False


class _Google:
    nombre = "Google Calendar"

    def __init__(self):
        self._api = google_cuenta.servicio("calendar", "v3")

    def eventos(self, desde: datetime, hasta: datetime) -> list[Evento]:
        respuesta = self._api.events().list(
            calendarId="primary", timeMin=desde.astimezone().isoformat(), timeMax=hasta.astimezone().isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=250,
        ).execute()
        eventos = []
        for e in respuesta.get("items", []):
            ini, fin = e["start"], e["end"]
            if "date" in ini:
                inicio, final, dia_entero = date.fromisoformat(ini["date"]), date.fromisoformat(fin["date"]), True
                inicio, final = _a_datetime(inicio)[0], _a_datetime(final)[0]
            else:
                inicio = _a_datetime(datetime.fromisoformat(ini["dateTime"]))[0]
                final = _a_datetime(datetime.fromisoformat(fin["dateTime"]))[0]
                dia_entero = False
            eventos.append(Evento(e["id"], e.get("summary", "(sin título)"), inicio, final, dia_entero))
        return eventos

    def crear(self, titulo, inicio: datetime, fin: datetime, todo_el_dia: bool, descripcion="") -> str:
        if todo_el_dia:
            cuerpo = {"start": {"date": inicio.date().isoformat()}, "end": {"date": fin.date().isoformat()}}
        else:
            cuerpo = {"start": {"dateTime": inicio.astimezone().isoformat()},
                      "end": {"dateTime": fin.astimezone().isoformat()}}
        cuerpo |= {"summary": titulo, "description": descripcion}
        return self._api.events().insert(calendarId="primary", body=cuerpo).execute()["id"]

    def borrar(self, id_evento: str) -> bool:
        try:
            self._api.events().delete(calendarId="primary", eventId=id_evento).execute()
            return True
        except Exception:
            return False


# ---------- Fachada ----------

class Calendario:
    def __init__(self):
        self._proveedor = None
        self._cache: dict[str, tuple[float, list[Evento]]] = {}

    @staticmethod
    def proveedor_configurado() -> str | None:
        return secretos.obtener("calendario_proveedor")

    def conectado(self) -> bool:
        return self.proveedor_configurado() is not None

    def _p(self):
        proveedor = self.proveedor_configurado()
        if proveedor is None:
            raise ErrorCalendario(
                "No hay ningún calendario conectado. Ofrece conectarlo: Apple Calendar (/conectar icloud, guía "
                "'calendario') o Google Calendar (/conectar google, guía 'google')."
            )
        if self._proveedor is None or getattr(self._proveedor, "clave", None) != proveedor:
            try:
                self._proveedor = _ICloud() if proveedor == "icloud" else _Google()
            except google_cuenta.ErrorGoogle as e:
                raise ErrorCalendario(str(e))
            self._proveedor.clave = proveedor
        return self._proveedor

    def nombre(self) -> str:
        return self._p().nombre

    def reiniciar(self):
        self._proveedor = None
        self._cache.clear()

    def eventos(self, desde: datetime, hasta: datetime, usar_cache=True) -> list[Evento]:
        clave = f"{desde:%Y%m%d%H%M}-{hasta:%Y%m%d%H%M}"
        if usar_cache and clave in self._cache and time.time() - self._cache[clave][0] < CACHE_SEGUNDOS:
            return self._cache[clave][1]
        eventos = sorted(self._p().eventos(desde, hasta), key=lambda e: e.inicio)
        self._cache[clave] = (time.time(), eventos)
        return eventos

    def eventos_del_dia(self, dia: date) -> list[Evento]:
        inicio = datetime.combine(dia, datetime.min.time())
        return self.eventos(inicio, inicio + timedelta(days=1))

    def crear(self, titulo, inicio: datetime, fin: datetime | None = None, todo_el_dia=False, descripcion="") -> str:
        if fin is None:
            fin = inicio + (timedelta(days=1) if todo_el_dia else timedelta(hours=1))
        id_evento = self._p().crear(titulo, inicio, fin, todo_el_dia, descripcion)
        self._cache.clear()
        return id_evento

    def borrar(self, id_evento: str) -> bool:
        ok = self._p().borrar(id_evento)
        self._cache.clear()
        return ok

    def buscar_parecido(self, titulo: str, dia: date, margen_dias: int = 1) -> Evento | None:
        """¿Hay ya un evento con un título parecido cerca de esa fecha?"""
        desde = datetime.combine(dia - timedelta(days=margen_dias), datetime.min.time())
        hasta = datetime.combine(dia + timedelta(days=margen_dias + 1), datetime.min.time())
        return next((e for e in self.eventos(desde, hasta, usar_cache=False) if parecidos(titulo, e.titulo)), None)
