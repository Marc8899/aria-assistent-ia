# Nutrición y entrenamiento (datos/salud.db): comidas, entrenos, perfil físico y peso.
# Las calorías son aproximaciones orientativas, no consejo médico.
import difflib
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

from aria.alimentos import ALIMENTOS
from aria.texto import normalizar

ACTIVIDAD = {"sedentario": 1.2, "ligera": 1.375, "moderada": 1.55, "alta": 1.725, "muy alta": 1.9}
OBJETIVOS = {"perder": 0.85, "mantener": 1.0, "ganar": 1.1}
# Gasto energético (MET) por tipo de actividad e intensidad (baja, media, alta).
MET = {
    "fuerza": (3.5, 5.0, 6.0), "pesas": (3.5, 5.0, 6.0), "gimnasio": (3.5, 5.0, 6.0),
    "correr": (7.0, 9.8, 11.8), "running": (7.0, 9.8, 11.8), "caminar": (2.8, 3.5, 5.0),
    "senderismo": (5.3, 6.0, 7.8), "bici": (4.0, 7.5, 10.0), "ciclismo": (4.0, 7.5, 10.0),
    "spinning": (6.8, 8.5, 10.5), "nadar": (5.8, 7.0, 9.8), "natacion": (5.8, 7.0, 9.8),
    "futbol": (5.0, 7.0, 10.0), "baloncesto": (4.5, 6.5, 8.0), "padel": (4.5, 6.0, 7.5),
    "tenis": (5.0, 7.3, 8.0), "hiit": (6.0, 8.0, 10.0), "crossfit": (6.0, 8.0, 10.0),
    "boxeo": (5.5, 7.8, 12.0), "artes marciales": (5.3, 7.8, 10.3), "yoga": (2.0, 2.5, 4.0),
    "pilates": (2.8, 3.0, 4.0), "movilidad": (2.0, 2.5, 3.0), "estiramientos": (2.0, 2.3, 2.8),
    "baile": (4.0, 5.5, 7.8), "escalada": (5.8, 7.5, 9.5), "remo": (4.8, 7.0, 8.5),
    "eliptica": (4.6, 5.0, 6.5), "cardio": (5.0, 7.0, 9.0), "deporte": (4.5, 6.5, 8.5),
}
INTENSIDADES = {"baja": 0, "media": 1, "alta": 2}


@dataclass
class Alimento:
    nombre: str
    kcal: float
    proteinas: float
    hidratos: float
    grasas: float
    racion_g: float
    racion: str
    fuente: str = "base local"

    def describir(self) -> str:
        return (f"{self.nombre} ({self.fuente}): {self.kcal:g} kcal, P {self.proteinas:g} g, H {self.hidratos:g} g, "
                f"G {self.grasas:g} g por 100 g. Ración típica: {self.racion} ≈ {self.racion_g:g} g "
                f"({self.kcal * self.racion_g / 100:.0f} kcal)")


def _clave(texto: str) -> str:
    """Sin tildes y en singular aproximado: 'Tostadas' y 'tostada' coinciden."""
    return " ".join(p[:-1] if len(p) > 3 and p.endswith("s") else p for p in normalizar(texto).split())


_INDICE = {}
for _n, _sin, _k, _p, _h, _g, _rg, _r in ALIMENTOS:
    _a = Alimento(_n, _k, _p, _h, _g, _rg, _r)
    for _c in [_n, *_sin]:
        _INDICE.setdefault(_clave(_c), _a)


def buscar_exacto(nombre: str) -> Alimento | None:
    return _INDICE.get(_clave(nombre))


def buscar_local(nombre: str) -> Alimento | None:
    buscado = _clave(nombre)
    if buscado in _INDICE:
        return _INDICE[buscado]
    # El nombre más largo contenido en lo buscado ("pechuga de pollo a la plancha con limón" -> pollo a la plancha)
    contenidos = sorted((c for c in _INDICE if re.search(rf"\b{re.escape(c)}\b", buscado)), key=len, reverse=True)
    if contenidos:
        return _INDICE[contenidos[0]]
    parecidos = difflib.get_close_matches(buscado, _INDICE, n=1, cutoff=0.75)
    return _INDICE[parecidos[0]] if parecidos else None


def buscar_open_food_facts(nombre: str, limite: int = 5) -> list[Alimento]:
    """Productos de marca (Open Food Facts, base de datos abierta y gratuita)."""
    parametros = urllib.parse.urlencode({
        "q": nombre, "page_size": limite, "langs": "es",
        "fields": "product_name,brands,nutriments,serving_quantity,serving_size",
    })
    solicitud = urllib.request.Request(f"https://search.openfoodfacts.org/search?{parametros}",
                                       headers={"User-Agent": "Aria-asistente-personal/1.0"})
    with urllib.request.urlopen(solicitud, timeout=15) as r:
        productos = json.loads(r.read()).get("hits", [])
    resultados = []
    for p in productos:
        n = p.get("nutriments") or {}
        kcal = n.get("energy-kcal_100g")
        if kcal is None or not p.get("product_name"):
            continue
        marcas = p.get("brands") or ""
        marca = marcas[0] if isinstance(marcas, list) and marcas else str(marcas).split(",")[0]
        nombre_producto = p["product_name"] + (f" ({marca})" if marca else "")
        racion_g = float(p.get("serving_quantity") or 100)
        resultados.append(Alimento(nombre_producto, float(kcal), float(n.get("proteins_100g", 0)),
                                   float(n.get("carbohydrates_100g", 0)), float(n.get("fat_100g", 0)),
                                   racion_g, p.get("serving_size") or "100 g", "Open Food Facts"))
    return resultados


def interpretar_items(texto: str) -> list[dict]:
    """'pollo a la plancha: 150 g; arroz: 1 ración; galletas oreo: 3 unidades: 160 kcal' -> lista de items."""
    items = []
    for trozo in re.split(r"[;\n]+", texto):
        partes = [p.strip() for p in trozo.split(":") if p.strip()]
        if not partes:
            continue
        item = {"nombre": partes[0], "gramos": None, "raciones": None, "kcal": None}
        for parte in partes[1:]:
            p = normalizar(parte).replace(",", ".")
            numero = re.search(r"\d+(\.\d+)?", p)
            valor = float(numero.group()) if numero else 1.0
            if "kcal" in p or "calor" in p:
                item["kcal"] = valor
            elif re.search(r"racion|unidad|pieza|plato|vaso|taza|lata|bol|cucharad|puñado|puñado", p) \
                    or not re.search(r"\d", p):
                item["raciones"] = valor
            elif re.search(r"\d\s*(g|gr|gramos|ml|cl|l)\b", p) or valor > 20:
                item["gramos"] = valor * (10 if re.search(r"\dcl\b|\d\s+cl\b", p) else 1)
            else:  # un número pequeño sin unidad ("plátano: 1") son unidades/raciones
                item["raciones"] = valor
        items.append(item)
    return items


class Salud:
    def __init__(self, ruta):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """CREATE TABLE IF NOT EXISTS comidas (
                id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, momento TEXT NOT NULL DEFAULT '',
                descripcion TEXT NOT NULL DEFAULT '', items TEXT NOT NULL,
                kcal REAL NOT NULL, proteinas REAL NOT NULL, hidratos REAL NOT NULL, grasas REAL NOT NULL,
                creado TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entrenos (
                id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, tipo TEXT NOT NULL, duracion_min REAL NOT NULL,
                intensidad TEXT NOT NULL DEFAULT 'media', distancia_km REAL NOT NULL DEFAULT 0,
                ejercicios TEXT NOT NULL DEFAULT '[]', descripcion TEXT NOT NULL DEFAULT '',
                kcal REAL NOT NULL DEFAULT 0, creado TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS perfil (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pesos (fecha TEXT PRIMARY KEY, kg REAL NOT NULL);"""
        )
        self.db.commit()

    # ---------- Perfil ----------

    def perfil(self) -> dict:
        return {f["clave"]: f["valor"] for f in self.db.execute("SELECT clave, valor FROM perfil")}

    def actualizar_perfil(self, **campos):
        for clave, valor in campos.items():
            if valor not in (None, "", 0):
                self.db.execute("INSERT OR REPLACE INTO perfil (clave, valor) VALUES (?, ?)", (clave, str(valor)))
        if campos.get("peso"):
            self.db.execute("INSERT OR REPLACE INTO pesos (fecha, kg) VALUES (?, ?)",
                            (date.today().isoformat(), float(campos["peso"])))
        self.db.commit()

    def peso(self) -> float | None:
        valor = self.perfil().get("peso")
        return float(valor) if valor else None

    def historial_peso(self, limite: int = 10) -> list[tuple[str, float]]:
        return [(f["fecha"], f["kg"]) for f in
                self.db.execute("SELECT fecha, kg FROM pesos ORDER BY fecha DESC LIMIT ?", (limite,))][::-1]

    def objetivos(self) -> dict | None:
        """Metabolismo basal (Mifflin-St Jeor), gasto diario y objetivo calórico/proteico."""
        p = self.perfil()
        try:
            peso, altura, edad = float(p["peso"]), float(p["altura"]), float(p["edad"])
        except (KeyError, ValueError):
            return None
        basal = 10 * peso + 6.25 * altura - 5 * edad + (5 if p.get("sexo", "hombre").startswith("h") else -161)
        gasto = basal * ACTIVIDAD.get(p.get("actividad", "moderada"), 1.55)
        objetivo = p.get("objetivo", "mantener")
        return {"basal": round(basal), "gasto": round(gasto),
                "kcal": round(gasto * OBJETIVOS.get(objetivo, 1.0)),
                "proteinas": round(peso * (2.0 if objetivo in ("perder", "ganar") else 1.6)),
                "objetivo": objetivo}

    # ---------- Comidas ----------

    def calcular_items(self, items: list[dict]) -> tuple[list[dict], list[str]]:
        """Calcula kcal y macros de cada item. Devuelve (calculados, nombres_desconocidos)."""
        # "tostadas con aceite" (si no es un plato conocido) -> "tostadas" con la cantidad + "aceite: 1 ración"
        separados = []
        for item in items:
            partes = re.split(r"\s+(?:con|y)\s+", item["nombre"])
            if len(partes) > 1 and item["kcal"] is None and buscar_exacto(item["nombre"]) is None \
                    and all(buscar_local(p) for p in partes):
                separados.append({**item, "nombre": partes[0]})
                separados += [{"nombre": p, "gramos": None, "raciones": 1, "kcal": None} for p in partes[1:]]
            else:
                separados.append(item)
        items = separados
        calculados, desconocidos = [], []
        for item in items:
            alimento = buscar_local(item["nombre"])
            if alimento is None and item["kcal"] is None:
                desconocidos.append(item["nombre"])
                continue
            if alimento is None:  # el modelo ha dado una estimación directa
                calculados.append({"nombre": item["nombre"], "gramos": item["gramos"], "kcal": item["kcal"],
                                   "proteinas": 0, "hidratos": 0, "grasas": 0, "fuente": "estimación"})
                continue
            gramos = item["gramos"] or (item["raciones"] or 1) * alimento.racion_g
            factor = gramos / 100
            calculados.append({
                "nombre": item["nombre"], "alimento": alimento.nombre, "gramos": round(gramos),
                "kcal": round(item["kcal"] if item["kcal"] is not None else alimento.kcal * factor),
                "proteinas": round(alimento.proteinas * factor, 1), "hidratos": round(alimento.hidratos * factor, 1),
                "grasas": round(alimento.grasas * factor, 1), "fuente": alimento.fuente,
            })
        return calculados, desconocidos

    def registrar_comida(self, items: list[dict], momento="", descripcion="", fecha="") -> int:
        totales = {k: sum(i[k] for i in items) for k in ("kcal", "proteinas", "hidratos", "grasas")}
        cursor = self.db.execute(
            "INSERT INTO comidas (fecha, momento, descripcion, items, kcal, proteinas, hidratos, grasas, creado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fecha or date.today().isoformat(), momento, descripcion, json.dumps(items, ensure_ascii=False),
             totales["kcal"], totales["proteinas"], totales["hidratos"], totales["grasas"],
             datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return cursor.lastrowid

    def comidas(self, desde: str, hasta: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM comidas WHERE fecha BETWEEN ? AND ? ORDER BY fecha, id",
                               (desde, hasta)).fetchall()

    def borrar_comida(self, id_comida: int) -> bool:
        cursor = self.db.execute("DELETE FROM comidas WHERE id = ?", (id_comida,))
        self.db.commit()
        return cursor.rowcount > 0

    # ---------- Entrenos ----------

    def estimar_kcal_entreno(self, tipo: str, duracion_min: float, intensidad: str, distancia_km: float) -> float:
        peso = self.peso() or 70
        t = normalizar(tipo)
        clave = next((k for k in MET if k in t), "deporte")
        met = MET[clave][INTENSIDADES.get(intensidad, 1)]
        if clave in ("correr", "running") and distancia_km and duracion_min:
            met = max(6.0, distancia_km / (duracion_min / 60))  # MET ≈ velocidad en km/h al correr
        return round(met * peso * duracion_min / 60)

    def registrar_entreno(self, tipo, duracion_min, intensidad="media", distancia_km=0.0, ejercicios=None,
                          descripcion="", fecha="") -> tuple[int, float]:
        kcal = self.estimar_kcal_entreno(tipo, duracion_min, intensidad, distancia_km)
        cursor = self.db.execute(
            "INSERT INTO entrenos (fecha, tipo, duracion_min, intensidad, distancia_km, ejercicios, descripcion, kcal, creado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fecha or date.today().isoformat(), tipo, duracion_min, intensidad, distancia_km,
             json.dumps(ejercicios or [], ensure_ascii=False), descripcion, kcal,
             datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return cursor.lastrowid, kcal

    def entrenos(self, desde: str, hasta: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM entrenos WHERE fecha BETWEEN ? AND ? ORDER BY fecha, id",
                               (desde, hasta)).fetchall()

    def series_de(self, ejercicio: str) -> list[tuple[str, dict]]:
        """Todas las series registradas de un ejercicio: [(fecha, {series, reps, kg})]."""
        buscado = normalizar(ejercicio)
        resultado = []
        for fila in self.db.execute("SELECT fecha, ejercicios FROM entrenos ORDER BY fecha"):
            for e in json.loads(fila["ejercicios"]):
                if buscado in normalizar(e.get("ejercicio", "")):
                    resultado.append((fila["fecha"], e))
        return resultado

    def cerrar(self):
        self.db.close()


def interpretar_ejercicios(texto: str) -> list[dict]:
    """'press banca: 4x8x60; dominadas: 3x10; sentadilla 5x5 100kg' -> [{ejercicio, series, reps, kg}]."""
    ejercicios = []
    for trozo in re.split(r"[;\n]+", texto or ""):
        trozo = trozo.strip()
        if not trozo:
            continue
        nombre = re.split(r"[:\d]", trozo, maxsplit=1)[0].strip(" :-") or trozo
        numeros = re.search(r"(\d+)\s*[x×]\s*(\d+)(?:\s*[x×@]\s*(\d+(?:[.,]\d+)?))?", trozo)
        kg_suelto = re.search(r"(\d+(?:[.,]\d+)?)\s*kg", trozo)
        e = {"ejercicio": nombre}
        if numeros:
            e["series"], e["reps"] = int(numeros.group(1)), int(numeros.group(2))
            if numeros.group(3):
                e["kg"] = float(numeros.group(3).replace(",", "."))
        if kg_suelto and "kg" not in e:
            e["kg"] = float(kg_suelto.group(1).replace(",", "."))
        ejercicios.append(e)
    return ejercicios


def una_rm(kg: float, reps: int) -> float:
    """Repetición máxima estimada (fórmula de Epley)."""
    return round(kg * (1 + reps / 30), 1) if reps > 1 else kg
