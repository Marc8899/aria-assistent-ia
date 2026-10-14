# Calculadora segura: evalúa solo aritmética, nunca código arbitrario.
import ast
import math
import operator

GRUPO = "calculo"
PALABRAS_CLAVE = None  # siempre disponible

OPERADORES = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}
FUNCIONES = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp, "abs": abs, "round": round,
}
CONSTANTES = {"pi": math.pi, "e": math.e}


def _evaluar(nodo):
    if isinstance(nodo, ast.Expression):
        return _evaluar(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return nodo.value
    if isinstance(nodo, ast.Name) and nodo.id in CONSTANTES:
        return CONSTANTES[nodo.id]
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERADORES:
        izquierda, derecha = _evaluar(nodo.left), _evaluar(nodo.right)
        if isinstance(nodo.op, ast.Pow) and abs(derecha) > 1000:
            raise ValueError("exponente demasiado grande")
        return OPERADORES[type(nodo.op)](izquierda, derecha)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERADORES:
        return OPERADORES[type(nodo.op)](_evaluar(nodo.operand))
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in FUNCIONES:
        return FUNCIONES[nodo.func.id](*[_evaluar(a) for a in nodo.args])
    raise ValueError("expresión no permitida")


def registrar(registro, ctx):
    @registro.herramienta(
        "Calcula una expresión matemática exacta. Úsala siempre en vez de calcular de cabeza.",
        expresion="Expresión, p. ej. '(1250*0.21)+sqrt(16)'. Usa ** para potencias.",
    )
    def calcular(expresion: str) -> str:
        return str(_evaluar(ast.parse(expresion.replace("^", "**"), mode="eval")))
