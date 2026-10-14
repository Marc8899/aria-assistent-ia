# La mascota de escritorio: un pequeño robot dibujado por código, siempre encima, que flota, parpadea,
# sigue el ratón con la mirada y mueve la boca al ritmo de su voz. Al lado, un bocadillo para sus frases
# y para escribirle.
import math
import random

from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMenu, QVBoxLayout, QWidget

from aria.interfaz.estilo import COLORES_ESTADO

ANCHO, ALTO = 170, 210
VENTANA_FLOTANTE = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)


class Robot(QWidget):
    abrir_ventana = Signal()
    escribir = Signal()
    silenciar = Signal(bool)
    salir = Signal()

    def __init__(self):
        super().__init__(None, VENTANA_FLOTANTE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(ANCHO, ALTO)
        from aria import config
        from aria.voz.tecla import nombre_tecla
        self.setToolTip(f"Aria · clic: escribir · doble clic: abrir · clic derecho: menú · "
                        f"mantén {nombre_tecla(config.TECLA_HABLAR)}: hablar")
        self.estado = "inactivo"
        self.silenciada = False
        self._t = 0.0
        self._nivel = 0.0          # volumen de la voz (boca)
        self._nivel_suave = 0.0
        self._parpadeo = 0.0       # 0 abierto, 1 cerrado
        self._proximo_parpadeo = 2.0
        self._mirada = QPointF(0, 0)
        self._arrastre: QPoint | None = None
        self._movido = False
        ajustes = QSettings("Aria", "Aria")
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.move(ajustes.value("mascota/pos", QPoint(pantalla.right() - ANCHO - 40, pantalla.bottom() - ALTO - 20)))
        self._reloj = QTimer(self, interval=33, timeout=self._animar)
        self._reloj.start()

    # ---------- Estado ----------

    def poner_estado(self, estado: str):
        self.estado = estado
        self.update()

    def poner_nivel(self, nivel: float):
        self._nivel = nivel

    # ---------- Animación ----------

    def _animar(self):
        dt = 0.033
        self._t += dt
        self._nivel_suave += (self._nivel - self._nivel_suave) * 0.45
        # Parpadeo aleatorio cada 2-6 s
        self._proximo_parpadeo -= dt
        if self._proximo_parpadeo <= 0:
            self._parpadeo = 1.0
            self._proximo_parpadeo = random.uniform(2.0, 6.0)
        self._parpadeo = max(0.0, self._parpadeo - dt * 7)
        # Los ojos siguen al ratón
        centro = self.mapToGlobal(QPoint(ANCHO // 2, 85))
        raton = QCursor.pos()
        dx, dy = raton.x() - centro.x(), raton.y() - centro.y()
        distancia = max(1.0, math.hypot(dx, dy))
        objetivo = QPointF(dx / distancia * min(6, distancia / 40), dy / distancia * min(4, distancia / 50))
        if self.estado == "pensando":
            objetivo = QPointF(math.sin(self._t * 2) * 5, -4)  # mira arriba, pensativo
        self._mirada += (objetivo - self._mirada) * 0.15
        self.update()

    # ---------- Dibujo ----------

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(COLORES_ESTADO.get(self.estado, "#5CE1E6"))
        flote = math.sin(self._t * 2.2) * 4
        cx = ANCHO / 2

        # Sombra en el "suelo" (se encoge al subir)
        sombra = 1 - (flote + 4) / 16
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, int(70 * sombra + 30)))
        p.drawEllipse(QPointF(cx, ALTO - 12), 42 * (0.8 + 0.2 * sombra), 7)

        p.translate(0, flote)
        metal = QColor("#E9EEF5")
        contorno = QPen(QColor("#8C97AA"), 2)

        # Brazos (se balancean; al hablar, gesticulan)
        balanceo = math.sin(self._t * 2.2) * 6 + (self._nivel_suave * 18 if self.estado == "hablando" else 0)
        for lado in (-1, 1):
            p.save()
            p.translate(cx + lado * 38, 150)
            p.rotate(lado * (20 + balanceo))
            p.setPen(contorno)
            p.setBrush(metal)
            p.drawRoundedRect(QRectF(-6, 0, 12, 30), 6, 6)
            p.restore()

        # Cuerpo con luz en el pecho
        cuerpo = QRectF(cx - 34, 128, 68, 52)
        degradado = QLinearGradient(cuerpo.topLeft(), cuerpo.bottomLeft())
        degradado.setColorAt(0, metal)
        degradado.setColorAt(1, QColor("#C9D2DF"))
        p.setPen(contorno)
        p.setBrush(degradado)
        p.drawRoundedRect(cuerpo, 16, 16)
        pulso = 0.6 + 0.4 * math.sin(self._t * (6 if self.estado != "inactivo" else 2))
        self._luz(p, QPointF(cx, 154), 9, color, pulso)

        # Antena con bola luminosa
        p.setPen(QPen(QColor("#8C97AA"), 3))
        p.drawLine(QPointF(cx, 42), QPointF(cx, 22))
        intensidad = 1.0 if self.estado in ("escuchando", "hablando") else (0.5 + 0.5 * math.sin(self._t * 5)
                                                                            if self.estado == "pensando" else 0.75)
        self._luz(p, QPointF(cx, 17), 8, color, intensidad, halo=True)

        # Orejas
        for lado in (-1, 1):
            p.setPen(contorno)
            p.setBrush(color.darker(130) if self.estado == "escuchando" else QColor("#B8C2D1"))
            alto = 30 + (6 * math.sin(self._t * 10) if self.estado == "escuchando" else 0)
            p.drawRoundedRect(QRectF(cx + lado * 60 - 7, 85 - alto / 2, 14, alto), 6, 6)

        # Cabeza
        cabeza = QRectF(cx - 56, 40, 112, 90)
        degradado = QLinearGradient(cabeza.topLeft(), cabeza.bottomLeft())
        degradado.setColorAt(0, QColor("#F6F8FB"))
        degradado.setColorAt(1, QColor("#CFD7E3"))
        p.setPen(contorno)
        p.setBrush(degradado)
        p.drawRoundedRect(cabeza, 28, 28)

        # Pantalla-cara
        cara = QRectF(cx - 44, 54, 88, 62)
        p.setPen(QPen(QColor("#0B0F17"), 2))
        p.setBrush(QColor("#1A2233"))
        p.drawRoundedRect(cara, 18, 18)

        # Ojos
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        alto_ojo = 18 * (1 - self._parpadeo) + 2 if self.estado != "escuchando" else 22 * (1 - self._parpadeo) + 2
        for lado in (-1, 1):
            ojo = QRectF(cx + lado * 18 - 7 + self._mirada.x(), 78 - alto_ojo / 2 + self._mirada.y(), 14, alto_ojo)
            p.drawRoundedRect(ojo, 6, 6)

        # Boca
        boca_y = 102
        if self.estado == "hablando":
            abertura = 3 + self._nivel_suave * 13
            p.drawRoundedRect(QRectF(cx - 10, boca_y - abertura / 2, 20, abertura), 5, 5)
        elif self.estado == "pensando":
            for i in range(3):
                fase = (self._t * 3 - i * 0.4) % 2
                p.setBrush(QColor(color.red(), color.green(), color.blue(), int(255 * (0.3 + 0.7 * max(0, 1 - fase)))))
                p.drawEllipse(QPointF(cx - 10 + i * 10, boca_y), 3, 3)
        elif self.estado == "escuchando":
            p.drawEllipse(QPointF(cx, boca_y), 5, 5)
        else:
            camino = QPainterPath()
            camino.moveTo(cx - 11, boca_y - 2)
            camino.quadTo(cx, boca_y + 7, cx + 11, boca_y - 2)
            p.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(camino)

        if self.silenciada:  # pequeño indicador de "voz apagada"
            p.setPen(QPen(QColor("#FF5C7A"), 3))
            p.drawLine(QPointF(cx + 42, 40), QPointF(cx + 54, 52))
            p.drawLine(QPointF(cx + 54, 40), QPointF(cx + 42, 52))
        p.end()

    @staticmethod
    def _luz(p: QPainter, centro: QPointF, radio: float, color: QColor, intensidad: float, halo=False):
        if halo:
            brillo = QRadialGradient(centro, radio * 3)
            brillo.setColorAt(0, QColor(color.red(), color.green(), color.blue(), int(120 * intensidad)))
            brillo.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(brillo)
            p.drawEllipse(centro, radio * 3, radio * 3)
        nucleo = QRadialGradient(centro, radio)
        nucleo.setColorAt(0, QColor("white"))
        nucleo.setColorAt(0.4, color.lighter(100 + int(40 * intensidad)))
        nucleo.setColorAt(1, color.darker(140))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(nucleo)
        p.drawEllipse(centro, radio, radio)

    # ---------- Ratón ----------

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._movido = False

    def mouseMoveEvent(self, e):
        if self._arrastre is not None and e.buttons() & Qt.MouseButton.LeftButton:
            nueva = e.globalPosition().toPoint() - self._arrastre
            if (nueva - self.pos()).manhattanLength() > 3:
                self._movido = True
            self.move(nueva)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._movido:
                QSettings("Aria", "Aria").setValue("mascota/pos", self.pos())
            else:
                QTimer.singleShot(220, self._clic_simple)  # espera por si es doble clic
            self._arrastre = None

    def _clic_simple(self):
        if not getattr(self, "_doble", False):
            self.escribir.emit()
        self._doble = False

    def mouseDoubleClickEvent(self, e):
        self._doble = True
        self.abrir_ventana.emit()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("Abrir Aria", self.abrir_ventana.emit)
        menu.addAction("Escribirle", self.escribir.emit)
        menu.addSeparator()
        accion = menu.addAction("Voz activada")
        accion.setCheckable(True)
        accion.setChecked(not self.silenciada)
        accion.toggled.connect(lambda activa: (setattr(self, "silenciada", not activa), self.silenciar.emit(not activa)))
        menu.addAction("Ocultar mascota", self.hide)
        menu.addSeparator()
        menu.addAction("Salir de Aria", self.salir.emit)
        menu.exec(e.globalPos())


class Bocadillo(QWidget):
    """Globo de texto junto al robot: muestra lo que dice Aria o deja escribirle."""
    enviado = Signal(str)

    def __init__(self, robot: Robot):
        super().__init__(None, VENTANA_FLOTANTE)
        self.robot = robot
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        disposicion = QVBoxLayout(self)
        disposicion.setContentsMargins(16, 12, 16, 22)
        self.etiqueta = QLabel(wordWrap=True)
        self.etiqueta.setStyleSheet("background: transparent; color: #EEC170; font-size: 10.5pt;")
        self.etiqueta.setMaximumWidth(330)
        self.entrada = QLineEdit(placeholderText="Escribe a Aria y pulsa Enter...")
        self.entrada.setStyleSheet("background: #222226; color: #EEC170; border: 1px solid #3E3E45; border-radius: 9px; padding: 7px; selection-background-color: #F58549;")
        self.entrada.returnPressed.connect(self._enviar)
        disposicion.addWidget(self.etiqueta)
        disposicion.addWidget(self.entrada)
        self._ocultar = QTimer(self, singleShot=True, timeout=self.hide)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        caja = QRectF(2, 2, self.width() - 4, self.height() - 16)
        camino = QPainterPath()
        camino.addRoundedRect(caja, 14, 14)
        pico = QPainterPath()
        x = self.width() - 46
        pico.moveTo(x, caja.bottom() - 1)
        pico.lineTo(x + 18, caja.bottom() - 1)
        pico.lineTo(x + 22, self.height() - 2)
        camino = camino.united(pico)
        p.setPen(QPen(QColor("#3E3E45"), 1.5))
        p.setBrush(QColor(43, 43, 48, 248))
        p.drawPath(camino)
        p.end()

    def _colocar(self):
        self.adjustSize()
        r = self.robot.frameGeometry()
        pantalla = QApplication.screenAt(r.center()) or QApplication.primaryScreen()
        zona = pantalla.availableGeometry()
        x = min(max(zona.left() + 4, r.center().x() - self.width() + 50), zona.right() - self.width() - 4)
        y = r.top() - self.height() + 18
        if y < zona.top():
            y = r.bottom()
        self.move(x, y)

    def mostrar(self, texto: str, segundos: float | None = None):
        self.entrada.hide()
        corto = texto if len(texto) <= 420 else texto[:420].rsplit(" ", 1)[0] + "… (sigue en la ventana)"
        self.etiqueta.setText(corto)
        self.etiqueta.setMinimumWidth(min(330, 60 + len(corto) * 6))  # que no quede una columna estrecha
        self.etiqueta.show()
        self._colocar()
        self.show()
        self.raise_()
        self._ocultar.start(int(1000 * (segundos or min(25, 4 + len(corto) * 0.06))))

    def pedir_texto(self):
        self._ocultar.stop()
        self.etiqueta.setText("¿Qué necesitas?")
        self.etiqueta.setMinimumWidth(300)
        self.entrada.show()
        self.entrada.clear()
        self._colocar()
        self.show()
        self.raise_()
        self.activateWindow()
        self.entrada.setFocus()

    def _enviar(self):
        texto = self.entrada.text().strip()
        if texto:
            self.enviado.emit(texto)
            self.mostrar("…", 60)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if not self.entrada.isVisible():
            self.hide()
