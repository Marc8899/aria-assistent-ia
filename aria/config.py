# CONFIGURACIÓN - lo normal es que solo cambies cosas aquí.
from pathlib import Path

MODELO = "qwen3:14b"        # <- nombre EXACTO que sale en 'ollama list'
NOMBRE_ASISTENTE = "Aria"   # <- el nombre que quieras

# Tokens de contexto que pedimos a Ollama. Si se queda corto, Ollama recorta
# el principio de la conversación (¡incluido el system prompt!) sin avisar.
CONTEXTO_TOKENS = 16384

# Qwen3 puede "pensar" antes de responder. Más lento, a veces más preciso.
PENSAR = False

# Máximo de rondas de herramientas por mensaje (evita bucles infinitos).
MAX_PASOS_HERRAMIENTAS = 6

# Mensajes de conversación que se conservan (sin contar el system prompt).
MAX_MENSAJES_HISTORIAL = 40

# Rutas absolutas: así los datos son los mismos aunque arranques desde otra carpeta.
RAIZ = Path(__file__).resolve().parent.parent
RUTA_DB = RAIZ / "memoria.db"
RUTA_TAREAS = RAIZ / "datos" / "tareas.db"
RUTA_JUEGOS = RAIZ / "datos" / "juegos.json"
RUTA_APLICACIONES = RAIZ / "datos" / "aplicaciones.db"
RUTA_SALUD = RAIZ / "datos" / "salud.db"
CARPETA_MI_API = RAIZ / "mi_api"

# OBS (Herramientas > Ajustes del servidor WebSocket)
OBS_HOST = "localhost"
OBS_PUERTO = 4455

# Modo juego: abrir un juego de Steam/Epic = grabar la partida (y parar al cerrarlo).
GRABAR_AL_ABRIR_JUEGOS = True
ESPERA_GRABACION_SEGUNDOS = 15   # para los juegos sin perfil propio

# Voz (todo en local): Piper para hablar, Whisper para entender.
CARPETA_MODELOS = RAIZ / "datos" / "modelos"
VOZ_MODELO = CARPETA_MODELOS / "piper" / "es_ES-sharvard-medium.onnx"
VOZ_HABLANTE = 1              # en este modelo: 0 = voz masculina, 1 = femenina
VOZ_VELOCIDAD = 1.0           # >1 más lenta, <1 más rápida
VOZ_MAX_CARACTERES = 700      # respuestas más largas se leen hasta aquí (el resto queda escrito)
WHISPER_MODELO = CARPETA_MODELOS / "whisper" / "large-v3-turbo"
# Tecla para hablar: mantenla pulsada mientras hablas (funciona aunque Aria no esté en primer plano).
# Opciones: "ctrl_r" (Ctrl derecho), "alt_gr", "shift_r", "menu", "pause", "insert", "f8"... o una letra.
TECLA_HABLAR = "ctrl_r"

# Botón de los auriculares (llega como Play/Pausa). Mantener = escucha mientras lo pulsas;
# un toque = manos libres (escucha hasta que te callas o vuelves a pulsar).
BOTON_AURICULARES = True
BOTON_AURICULARES_BLOQUEA_MUSICA = True  # True: ese botón ya no pausa la música mientras Aria esté abierta
SILENCIO_FIN_FRASE = 1.5                 # segundos callado para dar por terminada la frase (manos libres)
SONIDOS_ESCUCHA = True                   # pitidos al empezar y terminar de escuchar

# Panel lateral: aparece al empujar el ratón contra el borde derecho de la pantalla.
PANEL_LATERAL = True
PANEL_SECCIONES = ["reloj", "preguntar", "hoy", "proximo", "accesos"]  # quita o reordena a tu gusto

# API de Aria (python main.py --api). 127.0.0.1 = solo accesible desde este PC.
API_HOST = "127.0.0.1"
API_PUERTO = 8765
