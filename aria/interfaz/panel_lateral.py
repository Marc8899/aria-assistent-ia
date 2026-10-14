# Panel lateral: al empujar el ratón contra el borde derecho de la pantalla aparece una versión sencilla de Aria
# (como el Centro de control del iPhone). Las secciones se eligen en config.PANEL_SECCIONES.
#
# Para que sea fluido: aparece con un fundido y un desplazamiento corto (Windows los compone sin tirones) y
# nada lento (como el calendario, que va por internet) se hace en el hilo de la interfaz.
import threading
from datetime import date, datetime

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRectF, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from aria import config
from aria.fechas import fecha_en_espanol
from aria.interfaz.estilo import ARENA, COLORES_ESTADO, NARANJA, NEGRO_BORDE, NEGRO_CLARO, NEGRO_MEDIO, TEXTO_ESTADO
from aria.tareas import tiempo_restante
from aria.voz.tecla import nombre_tecla

ANCHO = 370
DESLIZ = 36               # píxeles de desplazamiento al aparecer (corto = fluido)
ESPERA_BORDE_MS = 180     # cuánto hay que empujar contra el borde
ESPERA_SALIDA_MS = 350    # cuánto tarda en irse al sacar el ratón
BOTON = "#3A3A40"
BOTON_ENCIMA = "#4A4A52"


def app_a_pantalla_completa() -> bool:
    """¿Hay un juego o vídeo a pantalla completa? Entonces el panel no debe salir."""
    try:
        import win32api
        import win32gui
        ventana = win32gui.GetForegroundWindow()
        if not ventana or win32gui.GetClassName(ventana) in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False
        izquierda, arriba, derecha, abajo = win32gui.GetWindowRect(ventana)
        m_izq, m_arr, m_der, m_aba = win32api.GetMonitorInfo(win32api.MonitorFromWindow(ventana, 2))["Monitor"]
        return izquierda <= m_izq and arriba <= m_arr and derecha >= m_der and abajo >= m_aba
    except Exception:
        return False


ESTILO = f"""
QWidget {{ background: transparent; color: {ARENA}; font-family: 'Segoe UI'; }}
QLabel#hora {{ font-size: 36pt; font-weight: 300; }}
QLabel#fecha {{ font-size: 11pt; }}
QLabel#seccion {{ font-weight: 700; font-size: 9pt; letter-spacing: 1px; margin-top: 8px; }}
QLabel#caja {{ background: {NEGRO_MEDIO}; border: 1px solid {NEGRO_BORDE}; border-radius: 12px; padding: 9px;
               font-size: 10pt; }}
QLineEdit {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; border-radius: 12px;
             padding: 8px; font-size: 10.5pt; selection-background-color: {NARANJA}; }}
QLineEdit:focus {{ border-color: {ARENA}; }}
QListWidget {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; border-radius: 12px;
               padding: 4px; font-size: 10pt; outline: none; }}
QListWidget::item {{ padding: 6px; border-radius: 7px; }}
QListWidget::item:hover {{ background: {NEGRO_CLARO}; }}
QListWidget::item:selected {{ background: {BOTON}; color: {ARENA}; }}
QListWidget::indicator {{ width: 15px; height: 15px; border-radius: 5px; border: 2px solid {ARENA}; }}
QListWidget::indicator:checked {{ background: {NARANJA}; border-color: {NARANJA}; }}
QPushButton {{ background: {BOTON}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; border-radius: 12px;
               padding: 10px 6px; font-weight: 600; font-size: 9.5pt; }}
QPushButton:hover {{ background: {BOTON_ENCIMA}; border-color: {ARENA}; }}
QPushButton:pressed {{ background: {NEGRO_MEDIO}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BOTON_ENCIMA}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


class PanelLateral(QWidget):
    _proximo_listo = Signal(str)

    def __init__(self, ctx, motor, abrir_ventana, robot, abrir_red):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.ctx, self.motor, self.robot = ctx, motor, robot
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(ESTILO)
        self.activado = True
        self._en_borde_desde = None
        self._fuera_desde = None
        self._cargando = False
        self._saliendo = False
        self._posicion_dentro = QPoint()
        caja = QVBoxLayout(self)
        caja.setContentsMargins(22, 20, 22, 20)
        caja.setSpacing(7)
        secciones = {"reloj": self._reloj, "preguntar": self._preguntar, "hoy": self._hoy,
                     "proximo": self._proximo, "accesos": lambda: self._accesos(abrir_ventana, abrir_red)}
        for nombre in config.PANEL_SECCIONES:
            if nombre in secciones:
                caja.addWidget(secciones[nombre]())
        caja.addStretch(1)

        self._mover = QPropertyAnimation(self, b"pos", self)
        self._opacidad = QPropertyAnimation(self, b"windowOpacity", self)
        self._animacion = QParallelAnimationGroup(self)
        self._animacion.addAnimation(self._mover)
        self._animacion.addAnimation(self._opacidad)
        self._animacion.finished.connect(self._fin_animacion)

        self._vigia = QTimer(self, interval=50, timeout=self._vigilar)
        self._vigia.start()
        self._segundero = QTimer(self, interval=1000, timeout=self._actualizar_hora)
        self._proximo_listo.connect(lambda texto: hasattr(self, "proximo") and self.proximo.setText(texto))
        motor.respuesta.connect(self._nueva_respuesta)
        motor.estado_cambiado.connect(self._estado)

    # ---------- Secciones ----------

    def _seccion(self, titulo: str) -> QLabel:
        return QLabel(titulo.upper(), objectName="seccion")

    def _reloj(self):
        w = QWidget()
        c = QVBoxLayout(w)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(0)
        self.hora = QLabel(objectName="hora")
        self.fecha = QLabel(objectName="fecha")
        self.estado = QLabel(objectName="fecha")
        for etiqueta in (self.hora, self.fecha, self.estado):
            c.addWidget(etiqueta)
        self._actualizar_hora()
        self._estado("inactivo")
        return w

    def _preguntar(self):
        w = QWidget()
        c = QVBoxLayout(w)
        c.setContentsMargins(0, 0, 0, 0)
        c.addWidget(self._seccion("Pregúntale a Aria"))
        fila = QHBoxLayout()
        self.entrada = QLineEdit(placeholderText="Escribe y pulsa Enter...")
        self.entrada.returnPressed.connect(self._enviar)
        microfono = QPushButton("Hablar")
        microfono.setFixedWidth(72)
        microfono.setToolTip(f"Mantén pulsado para hablar (o {nombre_tecla(config.TECLA_HABLAR)})")
        microfono.pressed.connect(self.motor.tecla_pulsada)
        microfono.released.connect(self.motor.tecla_soltada)
        fila.addWidget(self.entrada)
        fila.addWidget(microfono)
        c.addLayout(fila)
        self.respuesta = QLabel(objectName="caja", wordWrap=True)
        self.respuesta.hide()
        c.addWidget(self.respuesta)
        return w

    def _hoy(self):
        w = QWidget()
        c = QVBoxLayout(w)
        c.setContentsMargins(0, 0, 0, 0)
        c.addWidget(self._seccion("Tareas"))
        self.tareas = QListWidget()
        self.tareas.setMaximumHeight(175)
        self.tareas.itemChanged.connect(self._tarea_marcada)
        c.addWidget(self.tareas)
        c.addWidget(self._seccion("Hábitos de hoy"))
        self.habitos = QListWidget()
        self.habitos.setMaximumHeight(120)
        self.habitos.itemChanged.connect(self._habito_marcado)
        c.addWidget(self.habitos)
        for lista in (self.tareas, self.habitos):
            lista.setWordWrap(True)
            lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return w

    def _proximo(self):
        w = QWidget()
        c = QVBoxLayout(w)
        c.setContentsMargins(0, 0, 0, 0)
        c.addWidget(self._seccion("Ahora y luego"))
        self.proximo = QLabel(objectName="caja", wordWrap=True)
        c.addWidget(self.proximo)
        return w

    def _accesos(self, abrir_ventana, abrir_red):
        w = QWidget()
        c = QVBoxLayout(w)
        c.setContentsMargins(0, 0, 0, 0)
        c.addWidget(self._seccion("Accesos rápidos"))
        rejilla = QGridLayout()
        rejilla.setSpacing(7)
        self.boton_voz = QPushButton()
        self.boton_voz.clicked.connect(self._alternar_voz)
        botones = [("Abrir Aria", lambda: (self.ocultar(), abrir_ventana())), (None, self.boton_voz),
                   ("Mascota", lambda: self.robot.setVisible(not self.robot.isVisible())),
                   ("Mi red", lambda: (self.ocultar(), abrir_red())),
                   ("Nueva charla", self.motor.reiniciar),
                   ("Plan del día", lambda: self._preguntar_rapido("¿Qué tengo hoy? Resúmeme el plan del día en pocas líneas."))]
        for i, (texto, accion) in enumerate(botones):
            boton = accion if texto is None else QPushButton(texto)
            if texto is not None:
                boton.clicked.connect(accion)
            rejilla.addWidget(boton, i // 2, i % 2)
        self._pintar_voz()
        c.addLayout(rejilla)
        return w

    # ---------- Aparecer y desaparecer ----------

    def _vigilar(self):
        if not self.activado:
            return
        raton = QCursor.pos()
        borde_derecho = QGuiApplication.primaryScreen().virtualGeometry().right()
        ahora = datetime.now()
        if not self.isVisible() or self._saliendo:
            if raton.x() >= borde_derecho - 1:
                self._en_borde_desde = self._en_borde_desde or ahora
                if (ahora - self._en_borde_desde).total_seconds() * 1000 >= ESPERA_BORDE_MS \
                        and not app_a_pantalla_completa():
                    self._en_borde_desde = None
                    self.mostrar(QGuiApplication.screenAt(raton))
            else:
                self._en_borde_desde = None
            return
        # Visible: se queda mientras el ratón esté encima (o pegado al borde, a la altura del panel).
        zona = self.frameGeometry().adjusted(-12, -12, 12, 12)
        pegado_al_borde = raton.x() >= borde_derecho - 2 and zona.top() <= raton.y() <= zona.bottom()
        if zona.contains(raton) or pegado_al_borde:
            self._fuera_desde = None
            return
        self._fuera_desde = self._fuera_desde or ahora
        escribiendo = hasattr(self, "entrada") and self.entrada.hasFocus() and self.entrada.text()
        espera = ESPERA_SALIDA_MS * (4 if escribiendo else 1)
        if (ahora - self._fuera_desde).total_seconds() * 1000 >= espera:
            self.ocultar()

    def mostrar(self, pantalla=None):
        pantalla = pantalla or QGuiApplication.primaryScreen()
        zona = pantalla.availableGeometry()
        self.setFixedSize(ANCHO, zona.height() - 24)
        self._posicion_dentro = QPoint(zona.right() - ANCHO - 8, zona.top() + 12)
        self._saliendo = False
        self._fuera_desde = None
        self._animacion.stop()
        self.setWindowOpacity(0.0)
        self.move(self._posicion_dentro + QPoint(DESLIZ, 0))
        self.show()
        self.raise_()
        self._animar(self._posicion_dentro + QPoint(DESLIZ, 0), self._posicion_dentro, 0.0, 1.0, 170,
                     QEasingCurve.Type.OutCubic)
        self._actualizar_hora()
        self._segundero.start()
        QTimer.singleShot(190, self.refrescar)  # los datos, cuando la animación ya ha terminado

    def ocultar(self):
        if not self.isVisible() or self._saliendo:
            return
        self._saliendo = True
        self._segundero.stop()
        self._animacion.stop()
        self._animar(self.pos(), self._posicion_dentro + QPoint(DESLIZ, 0), self.windowOpacity(), 0.0, 140,
                     QEasingCurve.Type.InCubic)

    def _animar(self, desde, hasta, opacidad_desde, opacidad_hasta, ms, curva):
        for animacion, inicio, fin in ((self._mover, desde, hasta), (self._opacidad, opacidad_desde, opacidad_hasta)):
            animacion.setDuration(ms)
            animacion.setEasingCurve(curva)
            animacion.setStartValue(inicio)
            animacion.setEndValue(fin)
        self._animacion.start()

    def _fin_animacion(self):
        if self._saliendo:
            self.hide()
            self._saliendo = False

    def changeEvent(self, e):
        # Clic fuera del panel (pierde el foco) = cerrarlo.
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow() and self.isVisible():
            QTimer.singleShot(120, lambda: None if self.frameGeometry().contains(QCursor.pos()) else self.ocultar())
        super().changeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.ocultar()
        super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        camino = QPainterPath()
        camino.addRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 24, 24)
        p.setPen(QPen(QColor(NEGRO_BORDE), 1.5))
        p.setBrush(QColor(NEGRO_CLARO))
        p.drawPath(camino)
        p.end()

    # ---------- Datos ----------

    def refrescar(self):
        self._actualizar_proximo()
        if self.motor.ocupado or not hasattr(self, "tareas"):
            return
        self._cargando = True
        ahora = datetime.now()
        self.tareas.clear()
        for t in self.ctx.tareas.listar()[:8]:
            vencida = t.fecha_limite and datetime.fromisoformat(t.fecha_limite) < ahora
            texto = ("VENCIDA · " if vencida else "") + t.titulo
            if t.fecha_limite:
                texto += f"  ·  {tiempo_restante(t.fecha_limite, ahora)}"
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.tareas.addItem(item)
        if not self.tareas.count():
            self.tareas.addItem("Nada pendiente")
        self.habitos.clear()
        plan = self.ctx.planificacion
        for h in plan.habitos():
            if h.toca(ahora.date()):
                item = QListWidgetItem(h.nombre + (f"  ·  {h.hora}" if h.hora else ""))
                item.setData(Qt.ItemDataRole.UserRole, h.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if plan.hecho(h.id, ahora.date()) else Qt.CheckState.Unchecked)
                self.habitos.addItem(item)
        if not self.habitos.count():
            self.habitos.addItem("Hoy no toca ningún hábito")
        self._cargando = False

    def _actualizar_proximo(self):
        if not hasattr(self, "proximo"):
            return
        ahora = datetime.now()
        lineas = []
        actual, siguiente = self.ctx.planificacion.bloque_actual_y_siguiente(ahora)
        if actual:
            lineas.append(f"<b>Ahora:</b> {actual.titulo} (hasta las {actual.fin})")
        if siguiente:
            lineas.append(f"<b>Luego:</b> {siguiente.inicio} {siguiente.titulo}")
        base = "<br>".join(lineas)
        self.proximo.setText(base or "Nada planificado para lo que queda de día.")
        if self.ctx.calendario.conectado():
            def consultar():  # va por internet: en otro hilo para no congelar el panel
                try:
                    proximos = [e for e in self.ctx.calendario.eventos_del_dia(ahora.date())
                                if not e.todo_el_dia and e.inicio > ahora]
                except Exception:
                    return
                if proximos:
                    extra = f"<b>Calendario:</b> {proximos[0].inicio:%H:%M} {proximos[0].titulo}"
                    self._proximo_listo.emit(f"{base}<br>{extra}" if base else extra)
            threading.Thread(target=consultar, daemon=True).start()

    def _actualizar_hora(self):
        if hasattr(self, "hora"):
            ahora = datetime.now()
            self.hora.setText(f"{ahora:%H:%M}")
            self.fecha.setText(fecha_en_espanol(ahora).capitalize())

    def _estado(self, estado: str):
        if hasattr(self, "estado"):
            self.estado.setText(f'<span style="color:{COLORES_ESTADO[estado]}">●</span> Aria: {TEXTO_ESTADO[estado]}')

    def _tarea_marcada(self, item):
        if self._cargando or item.data(Qt.ItemDataRole.UserRole) is None or self.motor.ocupado:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self.ctx.tareas.actualizar(item.data(Qt.ItemDataRole.UserRole), estado="hecha")
            QTimer.singleShot(450, self.refrescar)

    def _habito_marcado(self, item):
        if self._cargando or item.data(Qt.ItemDataRole.UserRole) is None or self.motor.ocupado:
            return
        self.ctx.planificacion.marcar(item.data(Qt.ItemDataRole.UserRole), date.today(),
                                      item.checkState() == Qt.CheckState.Checked)

    def _enviar(self):
        texto = self.entrada.text().strip()
        if texto and not self.motor.ocupado:
            self.entrada.clear()
            self._preguntar_rapido(texto)

    def _preguntar_rapido(self, texto: str):
        if hasattr(self, "respuesta"):
            self.respuesta.setText("…")
            self.respuesta.show()
        self.motor.enviar(texto)

    def _nueva_respuesta(self, texto: str):
        if hasattr(self, "respuesta"):
            self.respuesta.setText(texto if len(texto) <= 500 else texto[:500].rsplit(" ", 1)[0] + "…")
            self.respuesta.show()
        if self.isVisible():
            QTimer.singleShot(300, self.refrescar)

    def _alternar_voz(self):
        self.motor.voz_activada = not self.motor.voz_activada
        self.robot.silenciada = not self.motor.voz_activada
        if not self.motor.voz_activada:
            self.motor.voz.callar()
        self._pintar_voz()

    def _pintar_voz(self):
        self.boton_voz.setText("Voz activada" if self.motor.voz_activada else "Voz silenciada")
