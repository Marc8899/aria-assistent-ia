# Masterclass: OBS Studio para grabar partidas (y el modo juego de Aria)

## Cómo enseñar esta guía
- Pregunta qué quiere el usuario (solo grabar, o también emitir en directo) y qué sabe ya.
- Un paso por mensaje; espera confirmación. Puedes usar obs_estado para comprobar cómo va.
- Los nombres de menús pueden variar un poco según la versión y el idioma de OBS: si el usuario no
  encuentra algo, pídele que te diga qué ve.
- NUNCA pidas la contraseña del WebSocket en el chat: se introduce con `/conectar obs`.

## Conceptos
- **Escena**: una "pantalla" preparada (p. ej. "Juego", "Pausa"). Se cambia entre escenas.
- **Fuente**: lo que hay dentro de una escena: captura del juego, webcam, micrófono, imágenes, texto.
- **Grabar** guarda un vídeo en tu PC; **emitir** lo manda en directo a Twitch/YouTube.
- **WebSocket**: la "puerta" por la que Aria controla OBS (cambiar escena, grabar…).

## Paso 1 · Primer arranque y asistente de configuración
OBS ya está instalado en este PC. Ábrelo (o pide a Aria "abre OBS").
Si es la primera vez sale el asistente de autoconfiguración: elige "Optimizar solo para grabar"
y acepta lo que propone. Se puede repetir en Herramientas → Asistente de configuración automática.

## Paso 2 · Crear la escena del juego
1. Abajo a la izquierda, en "Escenas", pulsa "+" y llámala `Juego`.
2. En "Fuentes", pulsa "+" → "Captura de juego" → nombre "Juego" → Aceptar.
3. Modo: "Capturar cualquier aplicación a pantalla completa" (lo más cómodo), o "Capturar ventana
   específica" para elegir un juego concreto.
Comprobación: con un juego abierto, se ve en la vista previa de OBS.

## Paso 3 · El audio
En "Mezclador de audio" deberían aparecer "Audio del escritorio" (el sonido del juego) y "Mic/Aux"
(tu micrófono). Si no quieres tu voz, silencia Mic/Aux con el icono del altavoz.
Habla y mira que la barra del micro se mueve; pon un vídeo y mira que se mueve la del escritorio.

## Paso 4 · Calidad y dónde se guardan los vídeos
Ajustes → Salida (modo de salida "Simple"):
- Ruta de grabación: una carpeta con espacio, p. ej. `Vídeos\Partidas`.
- Calidad de grabación: "Alta calidad, tamaño de archivo medio".
- Formato: MKV o "MP4 fragmentado". Evita el MP4 normal: si OBS se cierra de golpe, el vídeo se pierde.
- Codificador: el de hardware si aparece (NVIDIA NVENC, AMD o Intel QuickSync); consume mucho menos.
Ajustes → Vídeo: resolución de salida 1920x1080 (o la de tu pantalla) y 60 FPS para juegos.
Comprobación: pulsa "Iniciar grabación", espera 10 s, "Detener grabación" y abre el vídeo en esa carpeta.

## Paso 5 · Activar el WebSocket para que Aria controle OBS
1. Menú Herramientas → "Ajustes del servidor WebSocket" (puede aparecer como "WebSocket Server Settings").
2. Marca "Activar servidor WebSocket". Puerto: 4455.
3. Deja marcado "Activar autenticación" y pulsa "Mostrar información de conexión" para ver la contraseña
   (o "Generar contraseña"). Copia la contraseña. Pulsa Aplicar/Aceptar.
4. En la terminal de Aria: `/conectar obs` y pega la contraseña.
Comprobación: Aria responde "OBS 3x.x conectado". Prueba: "¿qué escenas tengo en OBS?".

## Paso 6 · El modo juego
Funciona solo, sin configurar nada: al abrir cualquier juego de Steam o Epic ("abre el Red Dead",
"quiero jugar al Red Dead"), Aria abre OBS si hace falta, abre el juego, empieza a grabar cuando el juego
arranca (15 s después, para saltarse logos) y para la grabación cuando lo cierras. Avisa en la terminal
con [OBS] Grabando… y [OBS] Partida guardada en….
Juegos que no son de Steam/Epic (romhacks, mods, ports, juegos sueltos):
- Si ya tiene acceso directo en el escritorio o en el menú Inicio, basta con decir "X es un juego"
  (marcar_como_juego).
- Si es un .exe suelto o una carpeta llena de romhacks, se añade con anadir_juego pasando la ruta.
  Las carpetas se vigilan: lo que se meta después en ellas se detecta solo.
Personalizarlo (opcional, con configurar_juego) por juego:
1. Escena de OBS a poner antes de grabar (normalmente `Juego`; compruébalo con obs_estado).
2. Segundos de espera antes de grabar (más si el juego tiene intros largas).
Para desactivar la grabación automática: GRABAR_AL_ABRIR_JUEGOS = False en aria/config.py.

## Problemas frecuentes
- **Captura de juego en negro**: prueba a abrir OBS como administrador, o usa "Captura de ventana" o
  "Captura de pantalla" en vez de "Captura de juego". Algunos juegos con antitrampas bloquean la captura de juego.
- **Portátiles con dos gráficas y pantalla negra**: en Configuración de Windows → Pantalla → Gráficos,
  pon OBS en la misma gráfica que el juego.
- **El vídeo va a tirones**: baja la calidad o usa el codificador de hardware (paso 4).
- **Aria dice que no puede conectar con OBS**: OBS cerrado o WebSocket desactivado (paso 5).
- **Aria dice que la contraseña no coincide**: repite `/conectar obs` con la contraseña actual.
