# Masterclass: conectar Gmail con Aria

## Cómo enseñar esta guía
- Un paso por mensaje. Explica el porqué en una o dos frases y espera a que el usuario diga que lo ha hecho.
- NUNCA pidas la contraseña ni la contraseña de aplicación en el chat. Se introduce con `/conectar gmail`.
- Si el usuario se atasca, mira la sección "Problemas frecuentes".

## Idea general (explícala al empezar)
Aria lee el correo con IMAP (el protocolo estándar para leer correo) y lo envía con SMTP.
Para entrar no usa la contraseña normal de Google, sino una **contraseña de aplicación**: una clave de
16 letras que solo sirve para el correo, que se puede borrar cuando quieras y que no da acceso al resto
de la cuenta. Se guarda cifrada en el Administrador de credenciales de Windows, nunca en el chat.
Requisitos: una cuenta de Gmail y el móvil a mano. Tiempo: unos 5 minutos.

## Paso 1 · Activar la verificación en dos pasos
Google solo permite contraseñas de aplicación si la cuenta tiene verificación en dos pasos.
1. Abre https://myaccount.google.com/security
2. En "Cómo inicias sesión en Google", pulsa "Verificación en 2 pasos".
3. Si pone "Activada", este paso ya está. Si no, sigue el asistente (normalmente con tu móvil).
Comprobación: en esa página aparece "La verificación en 2 pasos está activada".

## Paso 2 · Crear la contraseña de aplicación
1. Abre https://myaccount.google.com/apppasswords (puede pedirte la contraseña de Google).
2. En "Nombre de la aplicación" escribe `Aria` y pulsa "Crear".
3. Aparece un recuadro con 16 letras (en grupos de 4). Cópialas: Google no las vuelve a mostrar.
   No hace falta quitar los espacios.
Comprobación: en la lista de contraseñas de aplicación aparece "Aria".

## Paso 3 · Comprobar que IMAP está activado
En casi todas las cuentas actuales IMAP viene siempre activado y no hay que tocar nada.
Si quieres comprobarlo: Gmail en el navegador → rueda dentada → "Ver todos los ajustes" →
pestaña "Reenvío y correo POP/IMAP". Si aparece la opción "Habilitar IMAP", márcala y guarda.

## Paso 4 · Conectar Aria
1. En la terminal de Aria escribe: `/conectar gmail`
2. Escribe tu dirección de Gmail.
3. Pega la contraseña de aplicación (al pegarla no se ve nada: es normal) y pulsa Enter.
Comprobación: Aria responde "Gmail conectado (tu dirección)".

## Paso 5 · Probarlo
Pídele cosas como:
- "¿Tengo correos sin leer?" (mira todas las cuentas)
- "Busca los correos de Amazon de esta semana"
- "Léeme el último correo de mi jefe"
- "Responde al correo de Laura diciendo que el sábado me va bien"
- "Escribe un correo a ana@ejemplo.com desde la cuenta del trabajo diciendo que llego tarde"
- "Mueve los correos de la universidad a una carpeta llamada Uni"
- "Manda a la papelera las newsletters de hace más de un mes"
- "Archiva todo lo de Amazon ya leído" / "Marca como leídos los correos de LinkedIn"
Antes de enviar, mover, archivar o mandar a la papelera, Aria te enseña qué va a hacer y pregunta
"¿Lo hago? (s/n)".

## Varias cuentas
- Repite `/conectar gmail` con cada cuenta (cada una necesita su propia contraseña de aplicación,
  creada desde esa cuenta de Google). Ponle un alias: "personal", "trabajo", "uni"...
- Al leer, Aria mira todas las cuentas a la vez; para enviar u organizar usa la principal, salvo que digas
  cuál ("desde la del trabajo").
- `/gmail` muestra las cuentas; `/gmail principal correo@gmail.com` elige la principal.

## Seguridad y cómo desconectar
- Leer no marca nada como leído.
- "Eliminar" manda a la Papelera de Gmail: se puede recuperar durante 30 días. Aria nunca borra para siempre.
- Nunca envía, mueve ni manda a la papelera sin que lo apruebes.
- Para desconectar una cuenta: `/desconectar gmail correo@gmail.com` y, si quieres anular la clave del
  todo, bórrala en https://myaccount.google.com/apppasswords

## Problemas frecuentes
- **"La opción que buscas no está disponible" al abrir apppasswords**: falta la verificación en dos pasos
  (paso 1), o es una cuenta de trabajo/estudios cuyo administrador lo bloquea, o tienes activada la
  Protección Avanzada de Google.
- **"Application-specific password required"**: se ha puesto la contraseña normal en vez de la de aplicación.
- **"Invalid credentials" / "AUTHENTICATIONFAILED"**: dirección o clave mal copiadas. Repite `/conectar gmail`;
  si sigue fallando, crea una contraseña de aplicación nueva.
- **Cuentas que no son Gmail** (Outlook, Yahoo...): esta conexión es solo para Gmail por ahora.
