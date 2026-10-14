# Ejemplo: el endpoint más sencillo posible. Pruébalo en /docs -> GET /mi/hola
from fastapi import APIRouter

router = APIRouter(tags=["mi api"])


@router.get("/hola")
def hola(nombre: str = "mundo"):
    """Saluda. Prueba a cambiar el parámetro `nombre`."""
    return {"mensaje": f"¡Hola, {nombre}!"}
