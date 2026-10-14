# Perfiles de "modo juego": qué abrir, qué escena de OBS usar y cuándo grabar.
# Se guardan en datos/juegos.json (puedes editarlo a mano si quieres).
import json
from dataclasses import asdict, dataclass

from aria.texto import normalizar


@dataclass
class PerfilJuego:
    nombre: str              # cómo lo llama el usuario ("el red dead")
    aplicacion: str          # nombre en la lista de aplicaciones
    escena_obs: str = ""     # escena a poner antes de grabar ("" = no cambiar)
    espera_segundos: int = 15
    proceso: str = ""        # p. ej. "RDR2.exe": si se indica, la grabación para al cerrar el juego


class Juegos:
    def __init__(self, ruta):
        self.ruta = ruta
        self._perfiles: dict[str, PerfilJuego] = {}
        if ruta.exists():
            for datos in json.loads(ruta.read_text(encoding="utf-8")):
                perfil = PerfilJuego(**datos)
                self._perfiles[normalizar(perfil.nombre)] = perfil

    def _guardar(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = [asdict(p) for p in self._perfiles.values()]
        self.ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def configurar(self, perfil: PerfilJuego):
        self._perfiles[normalizar(perfil.nombre)] = perfil
        self._guardar()

    def listar(self) -> list[PerfilJuego]:
        return list(self._perfiles.values())

    def buscar(self, nombre: str) -> PerfilJuego | None:
        buscado = normalizar(nombre)
        if buscado in self._perfiles:
            return self._perfiles[buscado]
        for clave, perfil in self._perfiles.items():
            if buscado in clave or clave in buscado or buscado in normalizar(perfil.aplicacion):
                return perfil
        return None

    def buscar_por_app(self, nombre_app: str) -> PerfilJuego | None:
        return next((p for p in self._perfiles.values() if p.aplicacion == nombre_app), None)

    def borrar(self, nombre: str) -> bool:
        perfil = self.buscar(nombre)
        if perfil is None:
            return False
        del self._perfiles[normalizar(perfil.nombre)]
        self._guardar()
        return True
