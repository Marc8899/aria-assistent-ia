# Pulsar para hablar: una tecla global (funciona aunque Aria no esté en primer plano).
# Si mientras se mantiene se pulsa otra tecla (p. ej. Ctrl+C), era un atajo: se cancela la escucha.
from typing import Callable

from pynput import keyboard

NOMBRES = {"ctrl_r": "Ctrl derecho", "ctrl_l": "Ctrl izquierdo", "alt_gr": "Alt Gr", "alt_r": "Alt derecho",
           "shift_r": "Mayús derecha", "menu": "tecla Menú", "pause": "Pausa", "scroll_lock": "Bloq Despl",
           "insert": "Insert"}


def nombre_tecla(clave: str) -> str:
    return NOMBRES.get(clave.lower(), clave.upper())


class TeclaHablar:
    def __init__(self, nombre: str, al_pulsar: Callable[[], None], al_soltar: Callable[[], None],
                 al_cancelar: Callable[[], None]):
        self.tecla = getattr(keyboard.Key, nombre.lower(), None) or keyboard.KeyCode.from_char(nombre.lower())
        self.al_pulsar, self.al_soltar, self.al_cancelar = al_pulsar, al_soltar, al_cancelar
        self._pulsada = False
        self._cancelada = False
        self._oyente = keyboard.Listener(on_press=self._pulsa, on_release=self._suelta, daemon=True)

    def iniciar(self):
        self._oyente.start()

    def _pulsa(self, tecla):
        if tecla == self.tecla:
            if not self._pulsada:  # ignora la autorrepetición del teclado
                self._pulsada, self._cancelada = True, False
                self.al_pulsar()
        elif self._pulsada and not self._cancelada:
            self._cancelada = True  # era un atajo de teclado, no una orden de voz
            self.al_cancelar()

    def _suelta(self, tecla):
        if tecla == self.tecla and self._pulsada:
            self._pulsada = False
            if not self._cancelada:
                self.al_soltar()


VK_PLAY_PAUSA = 0xB3
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105


class BotonAuriculares:
    """El botón de los auriculares llega a Windows como la tecla multimedia Play/Pausa.
    Se captura a bajo nivel y, si se pide, se bloquea para que no pause también la música."""

    def __init__(self, al_pulsar: Callable[[], None], al_soltar: Callable[[], None], bloquear: bool = True):
        self.al_pulsar, self.al_soltar, self.bloquear = al_pulsar, al_soltar, bloquear
        self._pulsado = False
        self._oyente = keyboard.Listener(win32_event_filter=self._filtro, daemon=True)

    def iniciar(self):
        self._oyente.start()

    def _filtro(self, mensaje, datos):
        if datos.vkCode != VK_PLAY_PAUSA:
            return True  # cualquier otra tecla sigue su camino
        if mensaje in (WM_KEYDOWN, WM_SYSKEYDOWN) and not self._pulsado:
            self._pulsado = True
            self.al_pulsar()
        elif mensaje in (WM_KEYUP, WM_SYSKEYUP) and self._pulsado:
            self._pulsado = False
            self.al_soltar()
        if self.bloquear:
            self._oyente.suppress_event()  # no llega a Spotify, YouTube...
        return False
