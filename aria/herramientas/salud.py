# Nutrición (calorías aproximadas) y entrenamiento (registro, progreso, calorías quemadas).
import json
from datetime import date, timedelta

from aria.salud import ACTIVIDAD, OBJETIVOS, buscar_local, buscar_open_food_facts, interpretar_ejercicios, \
    interpretar_items, una_rm

GRUPO = "salud"
PALABRAS_CLAVE = ("comido", "comer", "comida", "desayun", "almorz", "almuerzo", "cena", "cenado", "merienda",
                  "merendado", "calori", "kcal", "proteina", "dieta", "macro", "alimento", "bebido", "picado",
                  "entren", "gym", "gimnasio", "ejercicio", "series", "repeticiones", "correr", "corrido", "cardio",
                  "pesas", "press", "sentadilla", "peso muerto", "dominadas", "peso", "kilos", "adelgazar",
                  "volumen", "definir", "musculo", "partido", "nadar", "bici")
AVISO = "Estimación orientativa, no consejo médico."


def registrar(registro, ctx):
    salud = ctx.salud

    def _totales_dia(dia: str) -> dict:
        comidas = salud.comidas(dia, dia)
        entrenos = salud.entrenos(dia, dia)
        return {"kcal": sum(c["kcal"] for c in comidas), "proteinas": sum(c["proteinas"] for c in comidas),
                "hidratos": sum(c["hidratos"] for c in comidas), "grasas": sum(c["grasas"] for c in comidas),
                "quemadas": sum(e["kcal"] for e in entrenos), "comidas": comidas}

    @registro.herramienta(
        "Registra lo que ha comido el usuario y calcula calorías y macros aproximados. Estima tú las cantidades "
        "razonables si no las dice (p. ej. 'un plato de macarrones' = 1 ración). Si un alimento no está en la "
        "base de datos, indica tu estimación de kcal con el formato 'nombre: 100 g: 250 kcal'.",
        alimentos="Lista 'alimento: cantidad' separada por ';'. Cantidad en g/ml ('150 g') o raciones ('1 ración', "
                  "'2 unidades'). Ej.: 'macarrones con tomate: 1 ración; pan: 40 g; coca cola: 1 lata'",
        momento="desayuno, almuerzo, comida, merienda, cena o picoteo",
        fecha="'AAAA-MM-DD' (vacío = hoy)",
    )
    def registrar_comida(alimentos: str, momento: str = "", fecha: str = "") -> str:
        calculados, desconocidos = salud.calcular_items(interpretar_items(alimentos))
        if desconocidos:
            return (f"No conozco: {', '.join(desconocidos)}. Busca con buscar_alimento o vuelve a registrarlo "
                    f"todo indicando tu estimación con 'nombre: gramos: kcal'. No he guardado nada.")
        if not calculados:
            return "No he entendido ningún alimento."
        salud.registrar_comida(calculados, momento, alimentos, fecha)
        dia = fecha or date.today().isoformat()
        total = sum(i["kcal"] for i in calculados)
        detalle = "; ".join(f"{i['nombre']} ~{i['gramos'] or '?'} g = {i['kcal']} kcal" for i in calculados)
        acumulado = _totales_dia(dia)
        objetivos = salud.objetivos()
        texto = f"Registrado ({momento or 'comida'}): {detalle}. Total ≈ {total:.0f} kcal. Hoy llevas ≈ {acumulado['kcal']:.0f} kcal"
        if objetivos:
            texto += f" de {objetivos['kcal']} objetivo (proteínas {acumulado['proteinas']:.0f}/{objetivos['proteinas']} g)"
        return texto + f". {AVISO}"

    @registro.herramienta(
        "Resumen de nutrición: calorías y macros comidos, calorías quemadas entrenando y comparación con su objetivo.",
        fecha="'AAAA-MM-DD' (vacío = hoy)",
        dias="Días hacia atrás a incluir (1 = solo ese día; 7 = media semanal)",
    )
    def resumen_nutricion(fecha: str = "", dias: int = 1) -> str:
        final = date.fromisoformat(fecha) if fecha else date.today()
        objetivos = salud.objetivos()
        lineas = []
        if dias <= 1:
            t = _totales_dia(final.isoformat())
            lineas.append(f"{final}: ≈ {t['kcal']:.0f} kcal (P {t['proteinas']:.0f} g · H {t['hidratos']:.0f} g · "
                          f"G {t['grasas']:.0f} g). Quemadas entrenando ≈ {t['quemadas']:.0f} kcal.")
            for c in t["comidas"]:
                lineas.append(f"  [{c['id']}] {c['momento'] or 'comida'}: {c['descripcion']} ≈ {c['kcal']:.0f} kcal")
        else:
            totales = [_totales_dia((final - timedelta(days=d)).isoformat()) for d in range(dias)]
            con_datos = [t for t in totales if t["kcal"]]
            if not con_datos:
                return "No hay comidas registradas en ese periodo."
            media = sum(t["kcal"] for t in con_datos) / len(con_datos)
            media_p = sum(t["proteinas"] for t in con_datos) / len(con_datos)
            lineas.append(f"Media de {len(con_datos)} días con registro: ≈ {media:.0f} kcal/día, {media_p:.0f} g proteína/día.")
        if objetivos:
            lineas.append(f"Objetivo ({objetivos['objetivo']}): {objetivos['kcal']} kcal y {objetivos['proteinas']} g de "
                          f"proteína al día (gasto estimado {objetivos['gasto']} kcal).")
        else:
            lineas.append("Sin objetivo calculado: falta el perfil físico (perfil_fisico).")
        return "\n".join(lineas) + f"\n{AVISO}"

    @registro.herramienta(
        "Busca un alimento o producto y sus calorías/macros por 100 g: primero en la base local, y si se pide o no "
        "está, en Open Food Facts (productos de marca).",
        nombre="Alimento o producto (con marca si la tiene)",
        en_internet="true para buscar productos de marca en Open Food Facts",
    )
    def buscar_alimento(nombre: str, en_internet: bool = False) -> str:
        local = buscar_local(nombre)
        if local and not en_internet:
            return local.describir()
        try:
            productos = buscar_open_food_facts(nombre)
        except Exception as e:
            productos, error = [], f" (Open Food Facts no responde: {e})"
        else:
            error = ""
        lineas = [p.describir() for p in productos]
        if local:
            lineas.insert(0, local.describir())
        return "\n".join(lineas) or f"No encuentro '{nombre}'{error}. Estima tú las calorías."

    @registro.herramienta(
        "Registra un entrenamiento y estima las calorías quemadas.",
        tipo="Tipo: fuerza/gimnasio, correr, bici, nadar, caminar, futbol, padel, hiit, yoga...",
        duracion_minutos="Duración en minutos",
        ejercicios="Para fuerza: 'press banca: 4x8x60; sentadilla: 5x5x100; dominadas: 3x10' (series x reps x kg)",
        intensidad="baja, media o alta",
        distancia_km="Distancia en km (correr, bici, nadar...)",
        notas="Sensaciones u observaciones",
        fecha="'AAAA-MM-DD' (vacío = hoy)",
    )
    def registrar_entrenamiento(tipo: str, duracion_minutos: float, ejercicios: str = "", intensidad: str = "media",
                                distancia_km: float = 0, notas: str = "", fecha: str = "") -> str:
        lista = interpretar_ejercicios(ejercicios)
        _, kcal = salud.registrar_entreno(tipo, duracion_minutos, intensidad, distancia_km, lista, notas, fecha)
        texto = f"Entreno registrado: {tipo}, {duracion_minutos:g} min"
        if distancia_km:
            texto += f", {distancia_km:g} km ({duracion_minutos / distancia_km:.1f} min/km)"
        if lista:
            texto += ". Ejercicios: " + "; ".join(
                f"{e['ejercicio']} {e.get('series', '?')}x{e.get('reps', '?')}" + (f" @ {e['kg']:g} kg" if "kg" in e else "")
                for e in lista)
        aviso_peso = "" if salud.peso() else " (con 70 kg por defecto: dime tu peso para afinar)"
        return texto + f". Quemadas ≈ {kcal:.0f} kcal{aviso_peso}. {AVISO}"

    @registro.herramienta(
        "Historial de entrenamiento: sesiones recientes, o la progresión de un ejercicio concreto (mejor peso, "
        "1RM estimada, volumen) para ver si mejora.",
        ejercicio="Ejercicio concreto (p. ej. 'press banca'); vacío = sesiones recientes",
        dias="Días hacia atrás para las sesiones recientes",
    )
    def historial_entrenamiento(ejercicio: str = "", dias: int = 30) -> str:
        if ejercicio:
            series = salud.series_de(ejercicio)
            if not series:
                return f"No hay registros de '{ejercicio}'."
            lineas = [f"Progresión de {ejercicio}:"]
            mejor = 0
            for fecha, e in series[-20:]:
                rm = una_rm(e.get("kg", 0), e.get("reps", 1)) if e.get("kg") else 0
                marca = " ← récord" if rm > mejor else ""
                mejor = max(mejor, rm)
                lineas.append(f"  {fecha}: {e.get('series', '?')}x{e.get('reps', '?')}"
                              + (f" @ {e['kg']:g} kg (1RM est. {rm:g} kg){marca}" if e.get("kg") else ""))
            return "\n".join(lineas)
        desde = (date.today() - timedelta(days=dias)).isoformat()
        sesiones = salud.entrenos(desde, date.today().isoformat())
        if not sesiones:
            return f"No hay entrenos en los últimos {dias} días."
        lineas = [f"{len(sesiones)} entrenos en {dias} días ({sum(s['duracion_min'] for s in sesiones):.0f} min, "
                  f"≈ {sum(s['kcal'] for s in sesiones):.0f} kcal):"]
        for s in sesiones:
            ejercicios = ", ".join(e["ejercicio"] for e in json.loads(s["ejercicios"]))
            lineas.append(f"  {s['fecha']} {s['tipo']} {s['duracion_min']:g} min"
                          + (f" {s['distancia_km']:g} km" if s["distancia_km"] else "")
                          + (f" · {ejercicios}" if ejercicios else "") + (f" · {s['descripcion']}" if s["descripcion"] else ""))
        return "\n".join(lineas)

    @registro.herramienta(
        "Consulta o actualiza el perfil físico (peso, altura, edad, sexo, actividad, objetivo) y calcula el gasto "
        "calórico y los objetivos diarios. Cada vez que diga su peso, actualízalo aquí.",
        peso="Peso en kg (0 = no cambiar)",
        altura="Altura en cm (0 = no cambiar)",
        edad="Edad en años (0 = no cambiar)",
        sexo="hombre o mujer",
        actividad=f"Nivel de actividad: {', '.join(ACTIVIDAD)}",
        objetivo=f"Objetivo: {', '.join(OBJETIVOS)}",
    )
    def perfil_fisico(peso: float = 0, altura: float = 0, edad: int = 0, sexo: str = "", actividad: str = "",
                      objetivo: str = "") -> str:
        if actividad and actividad not in ACTIVIDAD:
            return f"Actividad no válida. Opciones: {', '.join(ACTIVIDAD)}"
        if objetivo and objetivo not in OBJETIVOS:
            return f"Objetivo no válido. Opciones: {', '.join(OBJETIVOS)}"
        salud.actualizar_perfil(peso=peso, altura=altura, edad=edad, sexo=sexo, actividad=actividad, objetivo=objetivo)
        p = salud.perfil()
        texto = "Perfil: " + ", ".join(f"{k} {v}" for k, v in sorted(p.items())) if p else "Perfil vacío."
        objetivos = salud.objetivos()
        if objetivos:
            texto += (f"\nMetabolismo basal ≈ {objetivos['basal']} kcal · gasto diario ≈ {objetivos['gasto']} kcal · "
                      f"objetivo ({objetivos['objetivo']}) ≈ {objetivos['kcal']} kcal y {objetivos['proteinas']} g de proteína.")
        else:
            faltan = [c for c in ("peso", "altura", "edad") if c not in p]
            texto += f"\nPara calcular objetivos falta: {', '.join(faltan)}."
        historial = salud.historial_peso()
        if len(historial) > 1:
            texto += "\nEvolución del peso: " + " → ".join(f"{kg:g} ({f[5:]})" for f, kg in historial)
        return texto + f"\n{AVISO}"
