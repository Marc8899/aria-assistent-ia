# El motor de la app: une el cerebro (Asistente), la voz, el oído y la interfaz.
# El modelo trabaja en otro hilo para que la ventana y la mascota no se congelen; todo lo que cambia
# se comunica con señales de Qt, que llegan siempre al hilo de la interfaz.
import threading
import time

from PySide6.QtCore import QObject, Signal

from aria import config
from aria.asistente import Asistente
from aria.texto import quitar_emojis
from aria.voz.tecla import nombre_tecla
from aria.voz.habla import Voz
from aria.voz.oido import ErrorOido, Oido, pitido


class Motor(QObject):
    estado_cambiado = Signal(str)        # inactivo, escuchando, pensando, hablando
    mensaje_usuario = Signal(str)
    respuesta = Signal(str)
    herramienta = Signal(str, str)
    aviso = Signal(str)
    error = Signal(str)
    nivel_voz = Signal(float)
    datos_cambiados = Signal()
    pedir_confirmacion = Signal(str, dict, object)

    def __init__(self, asistente: Asistente, voz: Voz, oido: Oido):
        super().__init__()
        self.asistente, self.voz, self.oido = asistente, voz, oido
        self.estado = "inactivo"
        self.ocupado = False
        self.voz_activada = True
        self.leer_siempre = False  # leer en voz alta también lo que se escribe (no solo lo que se dice)
        voz.al_nivel = self.nivel_voz.emit
        voz.al_cambiar = lambda hablando: self._estado("hablando" if hablando else "inactivo")

    def _estado(self, estado: str):
        self.estado = estado
        self.estado_cambiado.emit(estado)

    # ---------- Conversación ----------

    def enviar(self, texto: str, por_voz: bool = False):
        if self.ocupado:
            self.error.emit("Un momento, todavía estoy con lo anterior.")
            return
        self.voz.callar()
        self.mensaje_usuario.emit(texto)
        self._lanzar(lambda **op: self.asistente.responder(texto, **op), hablar=por_voz)

    def saludar(self, hablar: bool = True):
        self._lanzar(self.asistente.saludar, hablar=hablar)

    def reiniciar(self):
        if not self.ocupado:
            self.asistente.reiniciar()

    def _lanzar(self, funcion, hablar: bool):
        self.ocupado = True
        self._estado("pensando")
        threading.Thread(target=self._trabajar, args=(funcion, hablar), daemon=True).start()

    def _trabajar(self, funcion, hablar: bool):
        va_a_hablar = False
        try:
            texto = quitar_emojis(funcion(al_usar_herramienta=lambda n, a: self.herramienta.emit(n, str(a)),
                                          confirmar=self._confirmar))
            self.respuesta.emit(texto)
            if self.voz_activada and (hablar or self.leer_siempre) and self.voz.disponible():
                va_a_hablar = True
                self.voz.decir(texto)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")
        finally:
            self.ocupado = False
            self.datos_cambiados.emit()
            if not va_a_hablar:
                self._estado("inactivo")

    def _confirmar(self, nombre: str, argumentos: dict) -> bool:
        """Se llama desde el hilo del modelo: pide a la interfaz un diálogo y espera la respuesta."""
        caja = {"evento": threading.Event(), "ok": False}
        self.pedir_confirmacion.emit(nombre, dict(argumentos), caja)
        caja["evento"].wait()
        return caja["ok"]

    # ---------- Pulsar para hablar ----------

    def tecla_pulsada(self):
        if self.voz.hablando:
            self.voz.callar()  # pulsar la tecla también la interrumpe
        if self.ocupado or self.estado == "escuchando":
            return
        if not self.oido.disponible():
            self.error.emit("Falta el modelo de reconocimiento de voz (datos/modelos/whisper).")
            return
        try:
            self.oido.empezar()
            self._inicio_escucha = time.time()
            self._estado("escuchando")
            pitido(subiendo=True)
        except ErrorOido as e:
            self.error.emit(str(e))

    def cancelar_escucha(self):
        """Se ha pulsado otra tecla a la vez (un atajo como Ctrl+C): se descarta sin avisar."""
        self._manos_libres = False
        if self.estado == "escuchando":
            self.oido.terminar_sin_transcribir()
            self._estado("inactivo")

    def tecla_soltada(self):
        if self.estado != "escuchando":
            return
        if time.time() - getattr(self, "_inicio_escucha", 0) < 0.4:  # toque accidental
            self.cancelar_escucha()
            return
        self._terminar_escucha()

    def _terminar_escucha(self):
        self._manos_libres = False
        pitido(subiendo=False)
        self._estado("pensando")
        threading.Thread(target=self._transcribir, daemon=True).start()

    # ---------- Botón de los auriculares: mantener o un toque (manos libres) ----------

    def boton_pulsado(self):
        if self.estado == "escuchando" and getattr(self, "_manos_libres", False):
            self._terminar_escucha()  # segundo toque: "ya he terminado"
            return
        self.tecla_pulsada()

    def boton_soltado(self):
        if self.estado != "escuchando" or getattr(self, "_manos_libres", False):
            return
        if time.time() - getattr(self, "_inicio_escucha", 0) < 0.5:
            # Fue un toque: seguimos escuchando hasta que se calle (muchos auriculares no envían "mantener").
            self._manos_libres = True
            threading.Thread(target=self._vigilar_manos_libres, daemon=True).start()
        else:
            self._terminar_escucha()

    def _vigilar_manos_libres(self):
        while self.estado == "escuchando" and getattr(self, "_manos_libres", False):
            if self.oido.frase_terminada(config.SILENCIO_FIN_FRASE) or time.time() - self._inicio_escucha > 30:
                self._terminar_escucha()
                return
            if self.oido.nadie_habla(8):
                self.cancelar_escucha()
                pitido(subiendo=False)
                self.aviso.emit("No te he oído. Pulsa otra vez el botón cuando quieras hablar.")
                return
            time.sleep(0.1)

    def _transcribir(self):
        try:
            texto = self.oido.terminar()
        except Exception as e:
            self._estado("inactivo")
            self.error.emit(f"No he podido entenderte: {e}")
            return
        if not texto:
            self._estado("inactivo")
            self.aviso.emit(f"No te he oído bien. Mantén {nombre_tecla(config.TECLA_HABLAR)} mientras hablas.")
            return
        self._estado("inactivo")
        self.enviar(texto, por_voz=True)
