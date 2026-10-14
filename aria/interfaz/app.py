# Arranque de la app de escritorio: mascota + ventana + bandeja del sistema + voz.
import os
import subprocess
import sys
import threading

from PySide6.QtCore import QLockFile, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from aria import config, copias
from aria.asistente import Asistente, ErrorModelo, comprobar_modelo
from aria.contexto import construir
from aria.herramientas import crear_registro
from aria.interfaz.estilo import HOJA
from aria.interfaz.mascota import Bocadillo, Robot
from aria.interfaz.motor import Motor
from aria.interfaz.panel_lateral import PanelLateral
from aria.interfaz.ventana import VentanaPrincipal
from aria.voz.habla import Voz
from aria.voz.oido import Oido
from aria.voz.tecla import BotonAuriculares, BotonAuricularesMac, TeclaHablar, nombre_tecla


def _icono() -> QIcon:
    """Cabeza del robot en pequeño, para la bandeja del sistema y la ventana."""
    imagen = QPixmap(64, 64)
    imagen.fill(Qt.GlobalColor.transparent)
    p = QPainter(imagen)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#E9EEF5"))
    p.setPen(QColor("#8C97AA"))
    p.drawRoundedRect(QRectF(4, 12, 56, 46), 14, 14)
    p.setBrush(QColor("#1A2233"))
    p.drawRoundedRect(QRectF(11, 19, 42, 32), 9, 9)
    p.setBrush(QColor("#5CE1E6"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(20, 27, 7, 11), 3, 3)
    p.drawRoundedRect(QRectF(37, 27, 7, 11), 3, 3)
    p.drawEllipse(QRectF(28, 2, 8, 8))
    p.end()
    return QIcon(imagen)


def _registro_a_archivo():
    """Con pythonw (sin consola) no hay salida: los mensajes van a datos/aria.log."""
    if sys.stdout is None or sys.stderr is None:
        archivo = open(config.RAIZ / "datos" / "aria.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = archivo


def main():
    _registro_a_archivo()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(config.NOMBRE_ASISTENTE)
    app.setStyleSheet(HOJA)
    app.setWindowIcon(_icono())

    candado = QLockFile(str(config.RAIZ / "datos" / "aria.lock"))
    if not candado.tryLock(100):
        QMessageBox.information(None, "Aria", "Aria ya está abierta (mira la mascota o el icono junto al reloj).")
        return
    try:
        comprobar_modelo(config.MODELO)
    except ErrorModelo as e:
        QMessageBox.critical(None, "Aria", str(e))
        return
    try:
        copias.copia_diaria()
    except Exception as e:
        print(f"[aviso] Copia de seguridad diaria fallida: {e}")

    puente = {}
    ctx = construir(avisar=lambda mensaje: puente["motor"].aviso.emit(mensaje))
    asistente = Asistente(crear_registro(ctx), ctx)
    voz, oido = Voz(), Oido()
    motor = puente["motor"] = Motor(asistente, voz, oido)

    robot = Robot()
    bocadillo = Bocadillo(robot)
    ventana = VentanaPrincipal(ctx, motor)

    # --- Conexiones ---
    motor.estado_cambiado.connect(robot.poner_estado)
    motor.nivel_voz.connect(robot.poner_nivel)
    motor.respuesta.connect(lambda texto: bocadillo.mostrar(texto))
    motor.aviso.connect(lambda texto: bocadillo.mostrar(texto, 8))
    motor.error.connect(lambda texto: bocadillo.mostrar(f"Aviso: {texto}", 8))
    motor.mensaje_usuario.connect(lambda texto: bocadillo.mostrar(f"«{texto}»", 30) if not ventana.isVisible() else None)
    bocadillo.enviado.connect(motor.enviar)

    def abrir_ventana():
        ventana.showNormal()
        ventana.raise_()
        ventana.activateWindow()

    def abrir_red():
        abrir_ventana()
        ventana.pestanas.setCurrentIndex(ventana.pestanas.count() - 1)

    panel = PanelLateral(ctx, motor, abrir_ventana, robot, abrir_red)
    panel.activado = config.PANEL_LATERAL

    robot.abrir_ventana.connect(abrir_ventana)
    robot.escribir.connect(bocadillo.pedir_texto)
    robot.silenciar.connect(lambda silenciada: (setattr(motor, "voz_activada", not silenciada),
                                                voz.callar() if silenciada else None))
    robot.salir.connect(app.quit)

    def confirmar(nombre: str, argumentos: dict, caja: dict):
        detalle = "\n".join(f"• {k}: {str(v)[:400]}" for k, v in argumentos.items())
        respuesta = QMessageBox.question(None, "Aria quiere hacer algo",
                                         f"Aria quiere ejecutar «{nombre}» con:\n\n{detalle}\n\n¿Lo hago?")
        caja["ok"] = respuesta == QMessageBox.StandardButton.Yes
        caja["evento"].set()

    motor.pedir_confirmacion.connect(confirmar)

    # --- Bandeja del sistema ---
    bandeja = QSystemTrayIcon(_icono())
    bandeja.setToolTip(f"{config.NOMBRE_ASISTENTE} · mantén {nombre_tecla(config.TECLA_HABLAR)} para hablar")
    menu = QMenu()
    menu.addAction("Abrir Aria", abrir_ventana)
    menu.addAction("Mostrar mascota", lambda: (robot.show(), robot.raise_()))
    accion_leer = menu.addAction("Leer en voz alta también lo que escribo")
    accion_leer.setCheckable(True)
    accion_leer.toggled.connect(lambda activo: setattr(motor, "leer_siempre", activo))
    accion_panel = menu.addAction("Panel lateral al empujar el ratón a la derecha")
    accion_panel.setCheckable(True)
    accion_panel.setChecked(panel.activado)
    accion_panel.toggled.connect(lambda activo: setattr(panel, "activado", activo))
    if sys.platform == "win32":
        menu.addAction("Abrir terminal (para /conectar servicios)",
                   lambda: subprocess.Popen(["cmd", "/c", "start", "Aria (terminal)", sys.executable.replace(
                       "pythonw.exe", "python.exe"), str(config.RAIZ / "main.py"), "--terminal"], cwd=str(config.RAIZ)))
    menu.addSeparator()
    menu.addAction("Salir de Aria", app.quit)
    bandeja.setContextMenu(menu)
    bandeja.activated.connect(lambda motivo: abrir_ventana() if motivo == QSystemTrayIcon.ActivationReason.Trigger else None)
    bandeja.show()

    # --- Voz: carga en segundo plano (la primera vez la gráfica tarda unos segundos en prepararse) ---
    def cargar_voz():
        try:
            if voz.disponible():
                voz.cargar()
        except Exception as e:
            print(f"[voz] No se ha podido cargar la voz: {e}")
        try:
            if oido.disponible():
                oido.cargar()
                print(f"[oído] Whisper listo en la {oido.dispositivo}.")
        except Exception as e:
            print(f"[oído] No se ha podido cargar el reconocimiento de voz: {e}")

    threading.Thread(target=cargar_voz, daemon=True).start()
    tecla = TeclaHablar(config.TECLA_HABLAR, motor.tecla_pulsada, motor.tecla_soltada, motor.cancelar_escucha)
    tecla.iniciar()
    if config.BOTON_AURICULARES:
        clase = BotonAuricularesMac if sys.platform == "darwin" else BotonAuriculares
        boton = clase(motor.boton_pulsado, motor.boton_soltado, config.BOTON_AURICULARES_BLOQUEA_MUSICA)
        try:
            boton.iniciar()
        except Exception as e:
            print(f"[auriculares] No se ha podido activar el botón: {e}")

    robot.show()
    QTimer.singleShot(600, lambda: motor.saludar(hablar=voz.disponible()))
    codigo = app.exec()
    voz.callar()
    ctx.cerrar()
    candado.unlock()
    sys.exit(codigo)
