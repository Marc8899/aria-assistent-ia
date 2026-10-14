# El oído de Aria: graba del micrófono mientras se mantiene la tecla y transcribe con Whisper (local).
# Usa la gráfica si puede (≈0,2 s por frase) y si no, el procesador.
import glob
import os
import threading
import time

import numpy as np

from aria import config

FRECUENCIA = 16000
UMBRAL_VOZ = 0.015  # volumen a partir del cual se considera que alguien habla


def pitido(subiendo: bool = True):
    """Pitido corto (dos notas) para indicar que empieza o termina la escucha."""
    if not config.SONIDOS_ESCUCHA:
        return
    import sounddevice as sd
    frecuencia = 22050
    notas = (660, 990) if subiendo else (880, 560)
    t = np.linspace(0, 0.07, int(frecuencia * 0.07), endpoint=False)
    envolvente = np.minimum(1, np.minimum(t, 0.07 - t) * 60)
    onda = np.concatenate([0.25 * np.sin(2 * np.pi * f * t) * envolvente for f in notas]).astype(np.float32)
    try:
        sd.play(onda, frecuencia)
    except Exception:
        pass


def _preparar_cuda():
    """Las librerías de NVIDIA (cuBLAS, cuDNN) vienen como paquetes de Python: hay que decirle a Windows dónde."""
    import nvidia  # paquete de namespace instalado por nvidia-cublas-cu12 / nvidia-cudnn-cu12
    for raiz in list(nvidia.__path__):
        for carpeta in glob.glob(os.path.join(raiz, "*", "bin")):
            os.add_dll_directory(carpeta)
            os.environ["PATH"] = carpeta + os.pathsep + os.environ["PATH"]


class ErrorOido(Exception):
    pass


class Oido:
    def __init__(self):
        self._modelo = None
        self.dispositivo = ""
        self._grabando = False
        self._trozos: list[np.ndarray] = []
        self._flujo = None
        self._candado = threading.Lock()

    def disponible(self) -> bool:
        return (config.WHISPER_MODELO / "model.bin").exists()

    @staticmethod
    def hay_microfono() -> bool:
        import sounddevice as sd
        try:
            return sd.query_devices(kind="input")["max_input_channels"] > 0
        except Exception:
            return False

    def cargar(self):
        """Carga el modelo (en la gráfica si se puede) y lo calienta: la primera transcripción es lenta."""
        with self._candado:
            if self._modelo is not None:
                return
            from faster_whisper import WhisperModel
            try:
                _preparar_cuda()
                modelo = WhisperModel(str(config.WHISPER_MODELO), device="cuda", compute_type="float16")
                modelo.transcribe(np.zeros(FRECUENCIA, dtype=np.float32), language="es")  # calentamiento
                self._modelo, self.dispositivo = modelo, "gráfica"
            except Exception as e:
                print(f"[oído] La gráfica no está disponible ({e}); uso el procesador.")
                self._modelo = WhisperModel(str(config.WHISPER_MODELO), device="cpu", compute_type="int8")
                self.dispositivo = "procesador"

    def empezar(self):
        import sounddevice as sd
        if self._grabando:
            return
        if not self.hay_microfono():
            raise ErrorOido("No hay ningún micrófono conectado o activado en Windows.")
        self._trozos = []
        self._inicio = self._ultimo_sonido = time.time()
        self._hubo_voz = False
        self._flujo = sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype="float32", callback=self._recibir)
        self._flujo.start()
        self._grabando = True

    def _recibir(self, datos, *_):
        self._trozos.append(datos.copy())
        if float(np.sqrt(np.mean(datos ** 2))) > UMBRAL_VOZ:
            self._ultimo_sonido = time.time()
            self._hubo_voz = True

    def frase_terminada(self, silencio: float) -> bool:
        """Para el modo manos libres: ¿ya se ha hablado y luego se lleva `silencio` segundos callado?"""
        return self._hubo_voz and time.time() - self._ultimo_sonido > silencio

    def nadie_habla(self, segundos: float) -> bool:
        return not self._hubo_voz and time.time() - self._inicio > segundos

    def terminar_sin_transcribir(self):
        if self._grabando:
            self._grabando = False
            self._flujo.stop()
            self._flujo.close()
            self._trozos = []

    def terminar(self) -> str:
        """Para de grabar y devuelve lo que se ha dicho ('' si no se ha entendido nada)."""
        if not self._grabando:
            return ""
        self._grabando = False
        self._flujo.stop()
        self._flujo.close()
        if not self._trozos:
            return ""
        audio = np.concatenate(self._trozos).flatten()
        if len(audio) < FRECUENCIA * 0.3 or float(np.abs(audio).max()) < 0.01:
            return ""  # demasiado corto o silencio
        self.cargar()
        segmentos, _ = self._modelo.transcribe(audio, language="es", beam_size=1, vad_filter=True)
        return " ".join(s.text.strip() for s in segmentos).strip()
