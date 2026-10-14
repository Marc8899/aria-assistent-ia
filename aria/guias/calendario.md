# Masterclass: conectar el calendario (Apple Calendar o Google Calendar)

## Cómo enseñar esta guía
- Pregunta primero qué calendario usa: el de Apple (iPhone, Mac, iCloud) o el de Google.
- Si es Google, usa la guía 'google' (con la misma conexión van Drive, Docs y Classroom).
- Un paso por mensaje; espera confirmación. NUNCA pidas la contraseña en el chat.

## Qué hará Aria con el calendario (explícalo al empezar)
- Ver la agenda ("¿qué tengo mañana?") y tenerla presente en cada conversación.
- Cuando el usuario le cuente una tarea con fecha, mirar si ya está en el calendario y, si no, añadirla.
- Crear eventos y, si quiere, poner sus bloques de tiempo en el calendario.
- Borrar eventos solo con su aprobación.

## Apple Calendar (iCloud)
Aria se conecta a iCloud con una **contraseña específica de app**: una clave que solo sirve para esto,
que se puede anular cuando quieras y que no da acceso al resto de la cuenta de Apple.

### Paso 1 · Comprobar la autenticación de doble factor
Las contraseñas específicas solo existen si el Apple ID tiene doble factor (casi todas las cuentas
lo tienen ya). En el iPhone: Ajustes → [tu nombre] → Inicio de sesión y seguridad → "Autenticación de doble
factor: Activada".

### Paso 2 · Crear la contraseña específica de app
1. Abre https://account.apple.com e inicia sesión con tu Apple ID.
2. Ve a "Inicio de sesión y seguridad" → "Contraseñas específicas de app".
3. Pulsa "+" (o "Generar contraseña"), escribe `Aria` y confirma.
4. Aparece una clave con el formato `xxxx-xxxx-xxxx-xxxx`. Cópiala: no se vuelve a mostrar.

### Paso 3 · Conectar Aria
1. En la terminal de Aria: `/conectar icloud`
2. Escribe tu Apple ID (el correo con el que entras en iCloud).
3. Pega la contraseña específica (no se ve al pegar) y pulsa Enter.
Comprobación: Aria dice "Apple Calendar conectado (N calendarios)".

### Paso 4 · Probarlo
- "¿Qué tengo esta semana en el calendario?"
- "Apúntame que el jueves a las 17:00 tengo dentista" → crea la tarea y, si no está, el evento.

### Problemas frecuentes
- **"Unauthorized" o 401**: el Apple ID o la clave están mal copiados, o se usó la contraseña normal de Apple.
  Genera otra contraseña específica y repite `/conectar icloud`.
- **Los eventos aparecen en un calendario que no quiero**: Aria usa el primer calendario de la cuenta;
  en la app Calendario puedes moverlos.
- Para desconectar: `/desconectar icloud` y anula la clave en account.apple.com.

## Cambiar de calendario
Si tiene los dos conectados: `/calendario icloud` o `/calendario google` elige cuál usa Aria.
