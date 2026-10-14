# Masterclass: qué es una API y cómo crear la tuya (con FastAPI)

## Cómo enseñar esta guía
- Pregunta qué sabe de programación y adapta el nivel. Usa analogías.
- Un paso por mensaje; espera confirmación. Primero que use la API de Aria, luego que cree la suya.
- Cuando escribáis código juntos: explícalo línea a línea ANTES de guardarlo con mi_api_escribir
  (el sistema le pedirá aprobación). Empieza simple y añade una cosa cada vez.
- Usa mi_api_listar y mi_api_ver para ver lo que ya tiene.

## Conceptos (con la analogía del restaurante)
- **API**: el camarero entre tú y la cocina. Tú pides con un formato acordado y te traen el plato,
  sin necesidad de entrar en la cocina. Es la forma en que un programa le pide cosas a otro.
- **HTTP**: el idioma en el que se hacen los pedidos por la red.
- **Endpoint**: cada cosa que se puede pedir, con su dirección: `/tareas`, `/mi/hola`…
- **Métodos**: GET (leer), POST (crear), PATCH/PUT (modificar), DELETE (borrar).
- **JSON**: el formato de los datos: `{"titulo": "Comprar pan", "prioridad": "alta"}`.
- **Parámetros**: de ruta (`/tareas/5`), de consulta (`/hola?nombre=Ana`) o en el cuerpo (JSON, en POST/PATCH).
- **Códigos de estado**: 200 bien, 201 creado, 401 sin permiso, 404 no existe, 422 datos incorrectos, 500 error del servidor.
- **Clave de API**: una contraseña que va en cada pedido (aquí, en la cabecera `X-API-Key`).

## Paso 1 · Arrancar la API de Aria
En una terminal nueva, dentro de la carpeta del proyecto:
```
.venv\Scripts\python main.py --api
```
Muestra la dirección y la clave. La API solo es accesible desde este PC (127.0.0.1).
El comando `/api` en la terminal de Aria también enseña la clave.

## Paso 2 · Explorarla en /docs
1. Abre http://127.0.0.1:8765/docs : es una página que FastAPI genera sola para probar la API.
2. Prueba `GET /estado` → "Try it out" → "Execute". Debe devolver 200 y la hora.
3. Pulsa "Authorize" (arriba a la derecha), pega la clave y acepta.
4. Prueba `GET /tareas`, luego `POST /tareas` con `{"titulo": "Probar la API", "prioridad": "alta"}`.
5. Prueba `POST /chat` con `{"mensaje": "¿qué tareas tengo?"}`: estás hablando con Aria desde la API.

### Qué tiene la API de Aria (grupos que verá en /docs)
- **general**: `POST /chat` (hablar con Aria; devuelve también qué herramientas usó), `GET /contexto`
  (lo que Aria tiene presente ahora), `GET /exportar` (todos sus datos en un JSON).
- **memoria**: `GET /memorias?q=...` (buscar), `POST /memorias` (guardar un recuerdo), `PATCH`/`DELETE`,
  `GET /memorias/resumen`. **diario**: `GET`/`POST /diario`.
- **tareas** y **proyectos** (con su kanban en `GET /proyectos/{id}`).
- **hábitos y plan**: `GET/POST /habitos`, `POST /habitos/{id}/marcar`, `GET /plan?fecha=...`, `POST /bloques`.
- **salud**: `POST /comidas` (calcula calorías), `GET /nutricion`, `POST/GET /entrenos`, `GET/PATCH /perfil-fisico`.
- **mi api**: lo que construya el usuario en `mi_api/`.
Idea para enseñar: con un "Atajo" del iPhone o una app de automatización que haga un POST a `/comidas` o
`/diario`, puede apuntar cosas desde el móvil sin abrir Aria (para eso la API tendría que ser accesible
desde el móvil: paso avanzado, ver Seguridad).

## Paso 3 · Llamarla desde fuera (para entender que es "solo HTTP")
Desde la terminal de Windows (curl.exe viene con Windows):
```
curl.exe http://127.0.0.1:8765/estado
curl.exe -H "X-API-Key: TU_CLAVE" http://127.0.0.1:8765/tareas
```
Desde Python (`pip install requests`):
```python
import requests
r = requests.get("http://127.0.0.1:8765/tareas", headers={"X-API-Key": "TU_CLAVE"})
print(r.status_code, r.json())
```

## Paso 4 · Tu API: cómo está organizada
Todo lo que pongas en la carpeta `mi_api/` se publica en `/mi/...`. Ya hay un ejemplo, `mi_api/hola.py`:
```python
from fastapi import APIRouter          # herramienta de FastAPI para agrupar endpoints
router = APIRouter(tags=["mi api"])    # Aria busca esta variable `router` en cada archivo

@router.get("/hola")                    # cuando alguien haga GET a /mi/hola...
def hola(nombre: str = "mundo"):        # ...se ejecuta esta función; `nombre` es un parámetro de consulta
    return {"mensaje": f"¡Hola, {nombre}!"}   # lo que devuelvas se convierte en JSON
```
Prueba en /docs: `GET /mi/hola` con nombre = tu nombre.
La API se recarga sola cada vez que cambia un archivo de `mi_api/`.

## Paso 5 · Diseñar la API del usuario
Antes de programar, decidid juntos:
1. ¿Para qué sirve? (p. ej. "llevar mis gastos", "mi colección de juegos", "notas rápidas desde el móvil").
2. ¿Qué datos hay? (p. ej. un gasto = concepto, cantidad, fecha, categoría).
3. ¿Qué endpoints? Haz una tabla: método + ruta + qué hace. Ejemplo:
   - GET /gastos → listar · POST /gastos → añadir · DELETE /gastos/{id} → borrar · GET /gastos/resumen → total por categoría

## Paso 6 · Construirla poco a poco (un endpoint cada vez, probándolo en /docs)
1. Un GET que devuelva datos fijos (para ver que funciona).
2. Un modelo de datos con Pydantic y un POST para crear:
   ```python
   from pydantic import BaseModel
   class Gasto(BaseModel):
       concepto: str
       cantidad: float
   ```
   FastAPI valida solo: si mandas texto en `cantidad`, responde 422.
3. Guardar los datos de verdad: primero en un archivo JSON; cuando crezca, en SQLite
   (guárdalos en la carpeta `datos/`).
4. Errores claros: `from fastapi import HTTPException` y `raise HTTPException(404, "No existe")`.
5. Parámetros de ruta: `@router.delete("/gastos/{id_gasto}")` con `def borrar(id_gasto: int)`.

## Seguridad
- Todo lo de `/mi/...` exige la misma clave que el resto de la API.
- La API escucha solo en este PC. Publicarla en internet es un paso avanzado (túneles como Tailscale o
  Cloudflare Tunnel, HTTPS…): hazlo solo cuando entiendas los riesgos.
- Nunca escribas contraseñas ni tokens dentro del código.

## Problemas frecuentes
- **"[mi_api] No he podido cargar X.py"** en la terminal de la API: el archivo tiene un error; el mensaje dice cuál.
- **401**: falta la clave o está mal (botón Authorize en /docs, cabecera X-API-Key fuera).
- **422**: los datos enviados no tienen el formato esperado; la respuesta dice qué campo falla.
- **"address already in use"**: la API ya está arrancada en otra terminal.
