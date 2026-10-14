# La voz de Aria: Piper (local) + reproducción por los altavoces.
# Mientras habla, informa del volumen de cada trocito de audio para animar la boca de la mascota.
import queue
import re
import threading
from typing import Callable

import numpy as np

from aria import config


def texto_para_hablar(texto: str) -> str:
    """Quita lo que no se lee bien en voz alta: markdown, enlaces, emojis, listas largas."""
    texto = re.sub(r"https?://\S+", "el enlace", texto)
    texto = re.sub(r"`{1,3}[^`]*`{1,3}", "", texto)
    texto = re.sub(r"[*_#>|~]+", "", texto)
    texto = re.sub(r"^\s*[-•]\s*", "", texto, flags=re.M)
    texto = re.sub(r"\[(\d+)\]", r"número \1", texto)
    texto = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", texto)
    texto = re.sub(r"\s*\n+\s*", ". ", texto)
    texto = re.sub(r"\.\s*\.", ".", texto).strip()
    if len(texto) > config.VOZ_MAX_CARACTERES:
        corte = texto.rfind(".", 0, config.VOZ_MAX_CARACTERES)
        texto = texto[: corte + 1 if corte > 100 else config.VOZ_MAX_CARACTERES] + " El resto te lo dejo escrito."
    return texto


class Voz:
    def __init__(self):
        self._voz = None
        self._cola: queue.Queue = queue.Queue()
        self._parar = threading.Event()
        self.hablando = False
        self.al_nivel: Callable[[float], None] = lambda nivel: None       # 0..1, para la boca
        self.al_cambiar: Callable[[bool], None] = lambda hablando: None   # empieza / termina
        threading.Thread(target=self._bucle, daemon=True).start()

    def disponible(self) -> bool:
        return config.VOZ_MODELO.exists()

    def cargar(self):
        if self._voz is None:
            from piper import PiperVoice
            self._voz = PiperVoice.load(str(config.VOZ_MODELO))

    def decir(self, texto: str):
        texto = texto_para_hablar(texto)
        if texto and self.disponible():
            self._parar.clear()
            self._cola.put(texto)

    def callar(self):
        self._parar.set()
        while not self._cola.empty():
            try:
                self._cola.get_nowait()
            except queue.Empty:
                break

    def _bucle(self):
        import sounddevice as sd
        from piper import SynthesisConfig

        while True:
            texto = self._cola.get()
            try:
                self.cargar()
                ajustes = SynthesisConfig(speaker_id=config.VOZ_HABLANTE, length_scale=config.VOZ_VELOCIDAD)
                frecuencia = self._voz.config.sample_rate
                self.hablando = True
                self.al_cambiar(True)
                with sd.OutputStream(samplerate=frecuencia, channels=1, dtype="float32") as salida:
                    for trozo in self._voz.synthesize(texto, syn_config=ajustes):  # frase a frase
                        audio = trozo.audio_float_array.astype(np.float32)
                        paso = int(frecuencia * 0.04)  # bloques de 40 ms: boca fluida
                        for i in range(0, len(audio), paso):
                            if self._parar.is_set():
                                break
                            bloque = audio[i:i + paso]
                            self.al_nivel(min(1.0, float(np.sqrt(np.mean(bloque ** 2))) * 6))
                            salida.write(bloque.reshape(-1, 1))
                        if self._parar.is_set():
                            break
            except Exception as e:
                print(f"[voz] No he podido hablar: {e}")
            finally:
                self.hablando = False
                self.al_nivel(0.0)
                self.al_cambiar(False)
