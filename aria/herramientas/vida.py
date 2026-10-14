# Diario personal y visión de conjunto de lo que Aria sabe del usuario.
from datetime import date, timedelta

from aria.memoria import CATEGORIAS

GRUPO = "vida"
PALABRAS_CLAVE = ("diario", "me siento", "estado de animo", "animo", "como me ha ido", "mi dia ha", "hoy ha sido",
                  "desahog", "que sabes de mi", "sobre mi", "mi vida", "conoceme", "conocerme", "biografia",
                  "mi historia", "recuerdas", "recuerdo", "olvida", "olvidar", "corrige", "corregir", "ya no",
                  "equivoc", "error", "no es verdad", "cambiado")


def registrar(registro, ctx):
    memoria = ctx.memoria

    @registro.herramienta(
        "Escribe una entrada en el diario del usuario: cómo ha ido su día, qué siente, qué ha pasado. Resume "
        "con sus propias palabras lo esencial. Lo duradero (personas, hechos importantes) guárdalo además "
        "con guardar_memoria.",
        texto="La entrada del diario",
        animo="Estado de ánimo en una o dos palabras (opcional)",
        fecha="'AAAA-MM-DD' (vacío = hoy)",
    )
    def escribir_diario(texto: str, animo: str = "", fecha: str = "") -> str:
        id_entrada = memoria.escribir_diario(texto, animo, fecha)
        return f"Entrada de diario [{id_entrada}] guardada."

    @registro.herramienta(
        "Lee el diario: entradas de un periodo o que traten de algo.",
        desde="'AAAA-MM-DD' (vacío = hace 7 días)",
        hasta="'AAAA-MM-DD' (vacío = hoy)",
        buscar="Texto a buscar en el diario (si se indica, ignora las fechas)",
    )
    def leer_diario(desde: str = "", hasta: str = "", buscar: str = "") -> str:
        if buscar:
            entradas = memoria.buscar_diario(buscar)
        else:
            entradas = memoria.leer_diario(desde or (date.today() - timedelta(days=7)).isoformat(),
                                           hasta or date.today().isoformat())
        return "\n".join(f"[{i}] {f}{' (' + a + ')' if a else ''}: {t}" for i, f, t, a in entradas) \
            or "No hay entradas de diario con ese filtro."

    @registro.herramienta(
        "Resumen de todo lo que Aria sabe del usuario, por categorías, y qué áreas faltan por conocer. Úsalo "
        "cuando pregunte qué sabes de él o para guiar una conversación para conocerle mejor.",
        categoria=f"Una categoría concreta ({', '.join(CATEGORIAS)}) o vacío para todas",
    )
    def resumen_de_mi(categoria: str = "") -> str:
        recuerdos = memoria.todos(categoria)
        if not recuerdos:
            return "Aún no sé nada en esa categoría."
        por_categoria: dict[str, list] = {}
        for r in recuerdos:
            por_categoria.setdefault(r.categoria, []).append(r)
        lineas = [f"Sé {memoria.contar()} cosas del usuario."]
        for cat in CATEGORIAS:
            if cat in por_categoria:
                lineas.append(f"\n{cat.upper()} ({len(por_categoria[cat])}):")
                lineas += [f"  {r.describir()}" for r in por_categoria[cat][:25]]
        if not categoria:
            faltan = [c for c in CATEGORIAS if c not in por_categoria and c != "otros"]
            if faltan:
                lineas.append(f"\nÁreas de las que aún no sé nada: {', '.join(faltan)}")
        return "\n".join(lineas)

    @registro.herramienta(
        "Corrige un recuerdo (texto, categoría, importancia...). Úsala cuando un dato cambie, en vez de duplicarlo.",
        id_memoria="Id del recuerdo (búscalo antes con buscar_memoria)",
        texto="Nuevo texto",
        categoria="Nueva categoría",
        importancia="Nueva importancia 1-5 (0 = no cambiar)",
        sobre="Nuevo 'sobre'",
    )
    def actualizar_memoria(id_memoria: int, texto: str = "", categoria: str = "", importancia: int = 0,
                           sobre: str = "") -> str:
        ok = memoria.actualizar(id_memoria, texto=texto, categoria=categoria if categoria in CATEGORIAS else None,
                                importancia=importancia or None, sobre=sobre)
        return "Recuerdo actualizado." if ok else f"No existe el recuerdo {id_memoria} o no había cambios."

    @registro.herramienta(
        "Borra un recuerdo. Úsala cuando el usuario pida olvidar algo o un dato sea falso.",
        id_memoria="Id numérico del recuerdo (aparece entre corchetes)",
    )
    def olvidar_memoria(id_memoria: int) -> str:
        return "Olvidado." if memoria.olvidar(id_memoria) else f"No existe el recuerdo {id_memoria}."
