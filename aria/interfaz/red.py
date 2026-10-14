# Pestaña "Mi red": un grafo vivo (como la vista de grafo de Obsidian) con todo lo que forma Aria:
# su API y endpoints, tu API personal, los servicios conectados, tus datos y sus habilidades.
# Física sencilla: los nodos se repelen, las conexiones tiran como muelles y todo se centra solo.
import json
import math
import random
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from dataclasses import dataclass, field

import psutil
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from aria import config, gmail, google_cuenta, secretos
from aria.interfaz.estilo import ARENA, NARANJA, NARANJA_CLARO, NEGRO_BORDE, NEGRO_CLARO, NEGRO_MEDIO

GRIS_ETIQUETA = "#9C9486"

URL_API = f"http://{config.API_HOST}:{config.API_PUERTO}"
COLOR_TIPO = {"centro": ARENA, "hub": NARANJA, "api": NARANJA_CLARO, "endpoint": "#F7C99A", "servicio": "#9ED9A0",
              "apagado": "#7D7550", "datos": "#E8D48A", "habilidad": "#F5B38A", "mi_api": "#FFDFA8"}
GRUPOS_API = {  # se usa si la API está apagada (si está encendida se lee su documentación en vivo)
    "general": "Hablar con Aria, contexto y exportación", "memoria": "Lo que Aria sabe de ti",
    "diario": "Tu diario", "tareas": "Tareas", "proyectos": "Proyectos y kanban",
    "hábitos y plan": "Hábitos, bloques y plan del día", "salud": "Comidas, entrenos y perfil físico",
}


@dataclass
class Nodo:
    id: str
    etiqueta: str
    tipo: str
    info: str = ""
    radio: float = 10
    activo: bool = True
    x: float = field(default_factory=lambda: random.uniform(-200, 200))
    y: float = field(default_factory=lambda: random.uniform(-200, 200))
    vx: float = 0
    vy: float = 0
    fijo: bool = False


# ---------- La API como proceso aparte ----------

class ControlAPI:
    def __init__(self):
        self.proceso: subprocess.Popen | None = None

    @staticmethod
    def encendida() -> bool:
        try:
            with urllib.request.urlopen(f"{URL_API}/estado", timeout=1) as r:
                return r.status == 200
        except Exception:
            return False

    @staticmethod
    def documentacion() -> dict | None:
        try:
            with urllib.request.urlopen(f"{URL_API}/openapi.json", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def encender(self):
        if self.encendida():
            return
        ejecutable = sys.executable.replace("python.exe", "pythonw.exe")
        self.proceso = subprocess.Popen([ejecutable, str(config.RAIZ / "main.py"), "--api"], cwd=str(config.RAIZ),
                                        creationflags=subprocess.CREATE_NO_WINDOW)

    def apagar(self):
        """Cierra la API y sus procesos hijos (uvicorn crea uno para recargar mi_api)."""
        objetivos = []
        if self.proceso and self.proceso.poll() is None:
            objetivos.append(psutil.Process(self.proceso.pid))
        else:  # quizá se encendió desde fuera: buscamos quién escucha en el puerto
            for conexion in psutil.net_connections("tcp"):
                if conexion.laddr and conexion.laddr.port == config.API_PUERTO and conexion.pid:
                    objetivos.append(psutil.Process(conexion.pid))
        for proceso in objetivos:
            try:
                for hijo in proceso.children(recursive=True):
                    hijo.kill()
                proceso.kill()
            except psutil.Error:
                pass
        self.proceso = None


# ---------- Qué hay en la red ----------

def construir_red(ctx, registro, api_encendida: bool) -> tuple[list[Nodo], list[tuple[str, str]]]:
    nodos, aristas = [], []

    def nodo(id_, etiqueta, tipo, info="", radio=9, activo=True, padre=None):
        nodos.append(Nodo(id_, etiqueta, tipo, info, radio, activo))
        if padre:
            aristas.append((padre, id_))

    nodo("aria", config.NOMBRE_ASISTENTE, "centro", f"Tu asistente. Modelo: {config.MODELO}. Todo pasa por aquí.", 26)

    # API y endpoints
    nodo("api", "API", "hub", f"Puerta para otros programas: {URL_API}/docs\n"
                              + ("Encendida." if api_encendida else "Apagada: enciéndela con el botón."), 17,
         api_encendida, "aria")
    documentacion = ControlAPI.documentacion() if api_encendida else None
    if documentacion:
        for ruta, metodos in documentacion.get("paths", {}).items():
            for metodo, detalle in metodos.items():
                grupo = (detalle.get("tags") or ["general"])[0]
                id_grupo = f"api:{grupo}"
                if id_grupo not in {n.id for n in nodos}:
                    nodo(id_grupo, grupo, "api", GRUPOS_API.get(grupo, ""), 11, True, "api")
                nodo(f"ep:{metodo}:{ruta}", f"{metodo.upper()} {ruta}", "endpoint",
                     (detalle.get("summary") or "") + "\n" + (detalle.get("description") or "").strip(), 5, True, id_grupo)
    else:
        for grupo, descripcion in GRUPOS_API.items():
            nodo(f"api:{grupo}", grupo, "api", descripcion, 11, api_encendida, "api")

    # Tu API personal (mi_api)
    from aria.herramientas.mi_api import _rutas
    nodo("mi_api", "Mi API", "hub", "Lo que construyes tú en la carpeta mi_api/ (se publica en /mi/...).", 14,
         True, "api")
    for archivo in sorted(config.CARPETA_MI_API.glob("*.py")):
        if archivo.name == "__init__.py":
            continue
        try:
            rutas = _rutas(archivo.read_text(encoding="utf-8"))
        except SyntaxError:
            rutas = []
        nodo(f"mi:{archivo.name}", archivo.stem, "mi_api", f"mi_api/{archivo.name}", 8, True, "mi_api")
        for ruta in rutas:
            nodo(f"mi:{archivo.name}:{ruta}", ruta, "endpoint", f"Endpoint de tu API: {ruta}", 5, True,
                 f"mi:{archivo.name}")

    # Servicios conectados
    nodo("servicios", "Servicios", "hub", "Cuentas y programas a los que Aria está conectada.", 15, True, "aria")
    nodo("srv:ollama", f"Ollama · {config.MODELO}", "servicio", "El cerebro: el modelo de lenguaje en local.", 10, True,
         "servicios")
    cuentas = gmail.cuentas()
    nodo("srv:gmail", "Gmail", "servicio" if cuentas else "apagado",
         f"{len(cuentas)} cuentas: {gmail.describir_cuentas()}" if cuentas else "Sin conectar: /conectar gmail", 10,
         bool(cuentas), "servicios")
    for c in cuentas:
        nodo(f"srv:gmail:{c['correo']}", c["alias"] or c["correo"], "servicio", c["correo"], 6, True, "srv:gmail")
    proveedor = secretos.obtener("calendario_proveedor")
    servicios = [
        ("google", "Google (Calendar, Drive, Docs, Classroom)", google_cuenta.conectado(), "/conectar google"),
        ("icloud", "Apple Calendar", bool(secretos.obtener("icloud_usuario")), "/conectar icloud"),
        ("github", "GitHub", bool(secretos.obtener("github_token")), "/conectar github"),
        ("obs", "OBS Studio", secretos.obtener("obs_clave") is not None, "/conectar obs"),
    ]
    for id_, nombre, conectado, comando in servicios:
        extra = " · calendario activo" if proveedor == id_ else ""
        nodo(f"srv:{id_}", nombre.split(" (")[0], "servicio" if conectado else "apagado",
             (f"Conectado{extra}." if conectado else f"Sin conectar: {comando}") + f"\n{nombre}", 9, conectado,
             "servicios")

    # Tus datos
    nodo("datos", "Tus datos", "hub", "Bases de datos locales: todo se queda en tu PC.", 15, True, "aria")
    datos = [
        ("memoria", "Memoria", f"{ctx.memoria.contar()} recuerdos y tu diario"),
        ("tareas", "Tareas y proyectos", f"{len(ctx.tareas.listar())} tareas activas, "
                                         f"{len(ctx.tareas.proyectos())} proyectos, {len(ctx.planificacion.habitos())} hábitos"),
        ("salud", "Salud", "Comidas, entrenos y perfil físico"),
        ("apps", "Aplicaciones", f"{len(ctx.apps.todas())} aplicaciones y juegos"),
    ]
    for id_, nombre, info in datos:
        nodo(f"dat:{id_}", nombre, "datos", info, 10, True, "datos")
        aristas.append((f"dat:{id_}", "api"))  # la API expone tus datos

    # Habilidades (grupos de herramientas)
    nodo("habilidades", "Habilidades", "hub", "Lo que Aria sabe hacer: cada grupo son varias herramientas.", 15, True,
         "aria")
    por_grupo: dict[str, list[str]] = {}
    for h in registro._herramientas.values():
        por_grupo.setdefault(h.grupo, []).append(h.nombre)
    for grupo, herramientas in sorted(por_grupo.items()):
        nodo(f"hab:{grupo}", grupo.replace("_", " "), "habilidad",
             f"{len(herramientas)} herramientas: {', '.join(herramientas)}", 6 + min(5, len(herramientas)), True,
             "habilidades")
    for grupo, servicio in (("gmail", "srv:gmail"), ("google_drive", "srv:google"), ("classroom", "srv:google"),
                            ("calendario", "srv:google" if proveedor != "icloud" else "srv:icloud"),
                            ("github", "srv:github"), ("juegos", "srv:obs"), ("recuerdos", "dat:memoria"),
                            ("vida", "dat:memoria"), ("tareas", "dat:tareas"), ("proyectos", "dat:tareas"),
                            ("planificacion", "dat:tareas"), ("salud", "dat:salud"), ("aplicaciones", "dat:apps"),
                            ("mi_api", "mi_api")):
        if f"hab:{grupo}" in {n.id for n in nodos}:
            aristas.append((f"hab:{grupo}", servicio))
    return nodos, aristas


# ---------- El grafo ----------

class Grafo(QWidget):
    seleccionado = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(500, 400)
        self.nodos: dict[str, Nodo] = {}
        self.aristas: list[tuple[str, str]] = []
        self.vecinos: dict[str, set[str]] = {}
        self.zoom, self.desplazamiento = 1.0, QPointF(0, 0)
        self._encima: Nodo | None = None
        self._arrastrado: Nodo | None = None
        self._paneo: QPointF | None = None
        self._movido = False
        self._t = 0.0
        self._fases = {}
        self._reloj = QTimer(self, interval=33, timeout=self._paso)

    def cargar(self, nodos: list[Nodo], aristas: list[tuple[str, str]]):
        anteriores = self.nodos
        self.nodos = {}
        for n in nodos:
            if n.id in anteriores:  # conserva la posición de lo que ya estaba
                n.x, n.y = anteriores[n.id].x, anteriores[n.id].y
            self.nodos[n.id] = n
        self.aristas = [(a, b) for a, b in aristas if a in self.nodos and b in self.nodos]
        self.vecinos = {i: set() for i in self.nodos}
        for a, b in self.aristas:
            self.vecinos[a].add(b)
            self.vecinos[b].add(a)
            self._fases.setdefault((a, b), random.random())
        centro = self.nodos.get("aria")
        if centro:
            centro.x, centro.y, centro.fijo = 0, 0, True
        self._reloj.start()

    def showEvent(self, e):
        self._reloj.start()

    def hideEvent(self, e):
        self._reloj.stop()  # no gastar CPU si la pestaña no se ve

    # --- Física ---
    def _paso(self):
        self._t += 0.033
        nodos = list(self.nodos.values())
        for i, a in enumerate(nodos):
            for b in nodos[i + 1:]:
                dx, dy = a.x - b.x, a.y - b.y
                d2 = dx * dx + dy * dy + 0.01
                if d2 > 250000:
                    continue
                fuerza = 2200 / d2
                d = math.sqrt(d2)
                fx, fy = dx / d * fuerza, dy / d * fuerza
                a.vx += fx; a.vy += fy
                b.vx -= fx; b.vy -= fy
        for a_id, b_id in self.aristas:
            a, b = self.nodos[a_id], self.nodos[b_id]
            dx, dy = b.x - a.x, b.y - a.y
            d = math.hypot(dx, dy) + 0.01
            largo = 30 + (a.radio + b.radio) * 3.2
            fuerza = (d - largo) * 0.012
            a.vx += dx / d * fuerza; a.vy += dy / d * fuerza
            b.vx -= dx / d * fuerza; b.vy -= dy / d * fuerza
        for n in nodos:
            if n.fijo:
                n.vx = n.vy = 0
                continue
            n.vx = (n.vx - n.x * 0.0015) * 0.82
            n.vy = (n.vy - n.y * 0.0015) * 0.82
            velocidad = math.hypot(n.vx, n.vy)
            if velocidad > 12:
                n.vx, n.vy = n.vx / velocidad * 12, n.vy / velocidad * 12
            n.x += n.vx
            n.y += n.vy
        self.update()

    # --- Coordenadas ---
    def _a_pantalla(self, x: float, y: float) -> QPointF:
        return QPointF(self.width() / 2 + (x + self.desplazamiento.x()) * self.zoom,
                       self.height() / 2 + (y + self.desplazamiento.y()) * self.zoom)

    def _a_mundo(self, punto: QPointF) -> QPointF:
        return QPointF((punto.x() - self.width() / 2) / self.zoom - self.desplazamiento.x(),
                       (punto.y() - self.height() / 2) / self.zoom - self.desplazamiento.y())

    def _nodo_en(self, punto: QPointF) -> Nodo | None:
        mundo = self._a_mundo(punto)
        for n in sorted(self.nodos.values(), key=lambda n: -n.radio):
            if math.hypot(n.x - mundo.x(), n.y - mundo.y()) <= n.radio + 4 / self.zoom:
                return n
        return None

    # --- Dibujo ---
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fondo = QRadialGradient(QPointF(self.width() / 2, self.height() / 2), max(self.width(), self.height()) * 0.7)
        fondo.setColorAt(0, QColor(NEGRO_CLARO))
        fondo.setColorAt(1, QColor(NEGRO_MEDIO))
        p.fillRect(self.rect(), fondo)
        foco = self._encima.id if self._encima else None
        cercanos = (self.vecinos.get(foco, set()) | {foco}) if foco else None

        for a_id, b_id in self.aristas:
            a, b = self.nodos[a_id], self.nodos[b_id]
            pa, pb = self._a_pantalla(a.x, a.y), self._a_pantalla(b.x, b.y)
            resaltada = cercanos is not None and a_id in cercanos and b_id in cercanos
            activa = a.activo and b.activo
            alfa = 200 if resaltada else (35 if cercanos else (90 if activa else 40))
            color = QColor(NARANJA_CLARO if resaltada else ARENA)
            color.setAlpha(alfa)
            p.setPen(QPen(color, 2 if resaltada else 1, Qt.PenStyle.SolidLine if activa else Qt.PenStyle.DashLine))
            p.drawLine(pa, pb)
            if activa:  # pulso de luz que viaja por la conexión
                fase = (self._t * 0.35 + self._fases[(a_id, b_id)]) % 1
                punto = pa + (pb - pa) * fase
                brillo = QRadialGradient(punto, 5 * self.zoom + 2)
                brillo.setColorAt(0, QColor(255, 243, 220, 230 if resaltada or not cercanos else 60))
                brillo.setColorAt(1, QColor(255, 243, 220, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(brillo)
                p.drawEllipse(punto, 5 * self.zoom + 2, 5 * self.zoom + 2)

        for n in sorted(self.nodos.values(), key=lambda n: n.radio):
            centro = self._a_pantalla(n.x, n.y)
            radio = n.radio * self.zoom
            atenuado = cercanos is not None and n.id not in cercanos
            color = QColor(COLOR_TIPO.get(n.tipo, ARENA))
            if atenuado:
                color.setAlpha(70)
            if n.activo and not atenuado:
                latido = 1 + 0.15 * math.sin(self._t * 2 + hash(n.id) % 10)
                halo = QRadialGradient(centro, radio * 2.6 * latido)
                halo.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 110))
                halo.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(centro, radio * 2.6 * latido, radio * 2.6 * latido)
            p.setPen(QPen(QColor(NEGRO_MEDIO), 2 if n.tipo in ("centro", "hub") else 1))
            p.setBrush(color)
            p.drawEllipse(centro, radio, radio)
            importante = n.tipo in ("centro", "hub") or n is self._encima or (cercanos and n.id in cercanos)
            if importante or (self.zoom > 1.3 and not atenuado):
                p.setFont(QFont("Segoe UI", 10 if n.tipo in ("centro", "hub") else 8,
                                QFont.Weight.Bold if n.tipo in ("centro", "hub") else QFont.Weight.Normal))
                texto = QColor(ARENA if not atenuado else GRIS_ETIQUETA)
                p.setPen(texto)
                caja = QRectF(centro.x() - 90, centro.y() + radio + 2, 180, 18)
                p.drawText(caja, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, n.etiqueta)
        p.setPen(QColor(GRIS_ETIQUETA))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(10, self.height() - 10, "Arrastra los nodos · rueda: zoom · arrastra el fondo para moverte · clic: detalles")
        p.end()

    # --- Ratón ---
    def mousePressEvent(self, e):
        self._movido = False
        nodo = self._nodo_en(e.position())
        if nodo:
            self._arrastrado = nodo
            nodo.fijo = True
        else:
            self._paneo = e.position()

    def mouseMoveEvent(self, e):
        if self._arrastrado:
            mundo = self._a_mundo(e.position())
            self._arrastrado.x, self._arrastrado.y = mundo.x(), mundo.y()
            self._movido = True
        elif self._paneo is not None:
            delta = (e.position() - self._paneo) / self.zoom
            self.desplazamiento += delta
            self._paneo = e.position()
            self._movido = True
        else:
            encima = self._nodo_en(e.position())
            if encima is not self._encima:
                self._encima = encima
                self.setCursor(Qt.CursorShape.PointingHandCursor if encima else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._arrastrado:
            if not self._movido:
                self.seleccionado.emit(self._arrastrado)
            if self._arrastrado.id != "aria":
                self._arrastrado.fijo = False
        self._arrastrado = None
        self._paneo = None

    def wheelEvent(self, e):
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = max(0.3, min(3.5, self.zoom * factor))


class PestanaRed(QWidget):
    def __init__(self, ctx, registro):
        super().__init__()
        self.ctx, self.registro = ctx, registro
        self.api = ControlAPI()
        self.grafo = Grafo()
        self.grafo.seleccionado.connect(self._mostrar_detalle)
        lateral = QFrame()
        lateral.setFixedWidth(290)
        lateral.setStyleSheet(f"QFrame {{ background: {NEGRO_MEDIO}; border: 1px solid {NEGRO_BORDE}; border-radius: 14px; }} "
                              f"QLabel {{ color: {ARENA}; border: none; }}")
        caja_lateral = QVBoxLayout(lateral)
        self.estado_api = QLabel()
        self.boton_api = QPushButton()
        self.boton_api.clicked.connect(self._alternar_api)
        documentacion = QPushButton("Abrir documentación de la API")
        documentacion.clicked.connect(lambda: webbrowser.open(f"{URL_API}/docs"))
        recargar = QPushButton("Actualizar la red")
        recargar.clicked.connect(self.refrescar)
        self.titulo = QLabel("Toca un nodo", wordWrap=True)
        self.titulo.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {ARENA};")
        self.detalle = QLabel("Cada punto es una parte de Aria. Las líneas punteadas son cosas aún sin conectar.",
                              wordWrap=True)
        self.detalle.setAlignment(Qt.AlignmentFlag.AlignTop)
        leyenda = QLabel(" ".join(f'<span style="color:{color}">●</span> {nombre}' for nombre, color in (
            ("Aria", ARENA), ("API", NARANJA_CLARO), ("Servicio", "#9ED9A0"), ("Sin conectar", "#7D7550"),
            ("Datos", "#E8D48A"), ("Habilidad", "#F5B38A"), ("Mi API", "#FFDFA8"))), wordWrap=True)
        leyenda.setStyleSheet(f"background: {NEGRO_CLARO}; color: {ARENA}; border-radius: 10px; padding: 8px;")
        for w in (self.estado_api, self.boton_api, documentacion, recargar, QLabel(" "), self.titulo, self.detalle):
            caja_lateral.addWidget(w)
        caja_lateral.addStretch(1)
        caja_lateral.addWidget(leyenda)
        caja = QHBoxLayout(self)
        caja.addWidget(self.grafo, 1)
        caja.addWidget(lateral)
        self._vigia = QTimer(self, interval=5000, timeout=self._comprobar_api)
        self._encendida = None

    def refrescar(self):
        encendida = self.api.encendida()
        self._pintar_estado(encendida)
        nodos, aristas = construir_red(self.ctx, self.registro, encendida)
        self.grafo.cargar(nodos, aristas)
        self._vigia.start()

    def _pintar_estado(self, encendida: bool):
        self._encendida = encendida
        color = "#9ED9A0" if encendida else "#7D7550"
        self.estado_api.setText(f'<span style="color:{color}">●</span> API {"encendida" if encendida else "apagada"} '
                                f"<br><small>{URL_API}</small>")
        self.boton_api.setText("Apagar la API" if encendida else "Encender la API")

    def _comprobar_api(self):
        if not self.isVisible():
            self._vigia.stop()
            return
        def comprobar():
            encendida = self.api.encendida()
            if encendida != self._encendida:
                QTimer.singleShot(0, self.refrescar)
        threading.Thread(target=comprobar, daemon=True).start()

    def _alternar_api(self):
        if self._encendida:
            self.api.apagar()
            QTimer.singleShot(800, self.refrescar)
        else:
            self.api.encender()
            self.boton_api.setText("Encendiendo...")
            QTimer.singleShot(6000, self.refrescar)  # la API tarda unos segundos en arrancar

    def _mostrar_detalle(self, nodo: Nodo):
        self.titulo.setText(nodo.etiqueta)
        self.detalle.setText(nodo.info.replace("\n", "<br>") or "—")
