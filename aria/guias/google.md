# Masterclass: conectar la cuenta de Google (Calendar, Drive, Docs y Classroom)

## Cómo enseñar esta guía
- Es la conexión más larga (unos 15 minutos) pero se hace UNA vez. Anímale: al final tendrá
  Calendar, Drive, Docs y Classroom de golpe.
- Un paso por mensaje, con los nombres exactos de los botones; espera confirmación. Si no encuentra un botón,
  pídele que te diga qué ve: la consola de Google cambia de aspecto a menudo.
- Aria nunca ve su contraseña de Google: el permiso se da en el navegador.

## Idea general (explícala al empezar)
Google no deja que cualquier programa entre en una cuenta. Hay que "registrar" a Aria como una aplicación
propia en Google Cloud (gratis) y luego darle permiso. Es como hacerle un carné a Aria que solo sirve
para la cuenta del usuario y que puede retirar cuando quiera.

## Paso 1 · Crear el proyecto en Google Cloud
1. Abre https://console.cloud.google.com e inicia sesión con la cuenta de Google que quieres conectar.
2. Si es la primera vez, acepta las condiciones (no pide tarjeta para esto).
3. Arriba, junto al logo, pulsa el selector de proyectos → "Proyecto nuevo".
4. Nombre: `Aria` → "Crear". Espera unos segundos y asegúrate de que arriba pone "Aria".

## Paso 2 · Activar las APIs
Menú (☰) → "APIs y servicios" → "Biblioteca". Busca y pulsa "Habilitar" en cada una:
- Google Calendar API
- Google Drive API
- Google Docs API
- Google Classroom API (solo si usa Classroom)

## Paso 3 · Configurar la pantalla de permisos
1. Menú → "APIs y servicios" → "Pantalla de consentimiento de OAuth" (puede llamarse "Google Auth Platform").
   Pulsa "Comenzar" / "Get started".
2. Nombre de la aplicación: `Aria`. Correo de asistencia: el suyo. Siguiente.
3. Público / Audience: **Externo** (External). Siguiente.
4. Información de contacto: su correo. Acepta la política y pulsa "Crear".
5. Ve a "Público" (Audience) → "Usuarios de prueba" → "Add users" → añade **su propio correo de Gmail** → Guardar.

## Paso 4 · Crear las credenciales
1. Ve a "Clientes" (Clients) → "Crear cliente" (o "APIs y servicios" → "Credenciales" → "Crear credenciales" →
   "ID de cliente de OAuth").
2. Tipo de aplicación: **Aplicación de escritorio** (Desktop app). Nombre: `Aria` → "Crear".
3. Pulsa "Descargar JSON".
4. Mueve ese archivo a la carpeta `datos` del proyecto (`C:\Users\usuario\Documents\AIPA\datos`) y
   **renómbralo** a `google_credentials.json`.
   (Aria puede ayudarle a moverlo: "mueve el último json de descargas a la carpeta datos de Aria".)

## Paso 5 · Dar permiso a Aria
1. En la terminal de Aria: `/conectar google`. Se abre el navegador.
2. Elige la cuenta. Saldrá "Google no ha verificado esta aplicación": es normal, porque la app es suya.
   Pulsa "Continuar".
3. Marca todas las casillas de permisos y pulsa "Continuar".
4. Cuando el navegador diga que ya puede cerrar la pestaña, vuelve a la terminal.
Comprobación: Aria dice "Google conectado (su correo)".

## Paso 6 · Probarlo
- "¿Qué tengo mañana en el calendario?"
- "Busca en mi Drive el trabajo de historia" / "Léeme el documento X de Drive"
- "Crea un Google Doc con un esquema para mi presentación"
- "¿Qué deberes tengo pendientes en Classroom? Pásalos a mis tareas"

## Importante: la caducidad semanal
Mientras la app está en modo "Prueba" (Testing), Google retira el permiso cada 7 días y hay que repetir
`/conectar google`. Para evitarlo: en la consola, "Público" (Audience) → "Publicar aplicación" → Confirmar.
Al ser para uso propio no hace falta que Google la verifique; seguirá saliendo el aviso de "no verificada"
al conectar, pero el permiso ya no caducará cada semana.

## Problemas frecuentes
- **"Falta datos/google_credentials.json"**: el archivo no está en la carpeta datos o no se ha renombrado.
- **"Error 403: access_denied"**: falta añadirse como usuario de prueba (paso 3.5).
- **"Error 400: admin_policy_enforced" o "Acceso bloqueado"** con una cuenta del instituto/universidad:
  el administrador del centro no permite apps externas. Classroom solo funcionará si el centro lo permite;
  con una cuenta personal de Gmail sí funcionan Calendar, Drive y Docs.
- **"API has not been used in project"**: falta habilitar esa API (paso 2).
- Para desconectar: `/desconectar google` y, si quieres, quita el acceso en https://myaccount.google.com/permissions
