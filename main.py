# ASISTENTE PERSONAL - punto de entrada.
# La configuración está en aria/config.py.
#   python main.py              -> app de escritorio (mascota + ventana + voz)
#   python main.py --terminal   -> conversación en la terminal (y comandos /conectar)
#   python main.py --api        -> API HTTP (http://127.0.0.1:8765/docs)
import sys

if __name__ == "__main__":
    if "--api" in sys.argv:
        from aria.api import arrancar
        arrancar()
    elif "--terminal" in sys.argv:
        from aria.cli import main
        main()
    else:
        from aria.interfaz.app import main
        main()
