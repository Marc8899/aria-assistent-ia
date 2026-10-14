# Herramientas para construir, junto al usuario, su propia API dentro de mi_api/.
# Cada archivo de mi_api/ con un `router = APIRouter()` se publica en /mi/... al arrancar la API.
import ast
import re

from aria import config

GRUPO = "mi_api"
PALABRAS_CLAVE = ("api", "endpoint", "fastapi", "servidor", "swagger")
NOMBRE_VALIDO = re.compile(r"[a-z][a-z0-9_]*\.py")


def _rutas(codigo: str) -> list[str]:
    """Saca 'GET /algo' de los decoradores @router.get("/algo") sin ejecutar el código."""
    rutas = []
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in nodo.decorator_list:
                if (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                        and deco.func.attr in ("get", "post", "put", "patch", "delete")
                        and deco.args and isinstance(deco.args[0], ast.Constant)):
                    rutas.append(f"{deco.func.attr.upper()} /mi{deco.args[0].value}")
    return rutas


def registrar(registro, ctx):
    carpeta = config.CARPETA_MI_API

    @registro.herramienta("Lista los archivos de la API del usuario (carpeta mi_api) y los endpoints de cada uno.")
    def mi_api_listar() -> str:
        archivos = sorted(p for p in carpeta.glob("*.py") if p.name != "__init__.py")
        if not archivos:
            return "La API del usuario todavía no tiene archivos."
        lineas = []
        for archivo in archivos:
            try:
                rutas = _rutas(archivo.read_text(encoding="utf-8"))
            except SyntaxError as e:
                rutas = [f"(error de sintaxis: {e})"]
            lineas.append(f"{archivo.name}: {', '.join(rutas) or 'sin endpoints'}")
        return "\n".join(lineas) + f"\n(Arranca con 'python main.py --api' y pruébala en " \
                                   f"http://{config.API_HOST}:{config.API_PUERTO}/docs)"

    @registro.herramienta(
        "Muestra el código de un archivo de la API del usuario.",
        archivo="Nombre del archivo, p. ej. 'hola.py'",
    )
    def mi_api_ver(archivo: str) -> str:
        if not NOMBRE_VALIDO.fullmatch(archivo):
            return "Nombre no válido: minúsculas, números y _, terminado en .py."
        ruta = carpeta / archivo
        return ruta.read_text(encoding="utf-8") if ruta.exists() else f"No existe {archivo}."

    @registro.herramienta(
        "Crea o reemplaza un archivo de la API del usuario. El código debe definir `router = APIRouter()` "
        "de FastAPI. Explica antes el código al usuario; el sistema le pedirá aprobación.",
        confirmar=True,
        archivo="Nombre del archivo: minúsculas, números y _, terminado en .py",
        codigo="Código Python completo del archivo",
    )
    def mi_api_escribir(archivo: str, codigo: str) -> str:
        if not NOMBRE_VALIDO.fullmatch(archivo) or archivo == "__init__.py":
            return "Nombre no válido: minúsculas, números y _, terminado en .py."
        try:
            rutas = _rutas(codigo)
        except SyntaxError as e:
            return f"El código tiene un error de sintaxis (línea {e.lineno}): {e.msg}. Corrígelo y vuelve a intentarlo."
        if "router" not in codigo or "APIRouter" not in codigo:
            return "El archivo debe definir `router = APIRouter()` para que la API lo cargue."
        (carpeta / archivo).write_text(codigo, encoding="utf-8")
        return (f"Guardado {archivo} con: {', '.join(rutas) or 'sin endpoints'}. Si la API está arrancada "
                f"se recarga sola; pruébalo en http://{config.API_HOST}:{config.API_PUERTO}/docs")
