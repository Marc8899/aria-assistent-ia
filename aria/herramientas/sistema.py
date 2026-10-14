# Especificaciones y estado del PC.
import json
import platform
import shutil
import subprocess
import time

import psutil

from aria.archivos import tamano_legible

GRUPO = "sistema"
PALABRAS_CLAVE = ("pc", "ordenador", "especificaciones", "specs", "ram", "memoria ram", "cpu", "procesador",
                  "grafica", "gpu", "disco", "espacio libre", "almacenamiento", "bateria", "rendimiento",
                  "temperatura", "va lento", "consume", "windows", "hardware", "placa base")


def _cim() -> dict:
    comando = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; [pscustomobject]@{"
        "cpu=(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name);"
        "gpus=@(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name });"
        "placa=(Get-CimInstance Win32_BaseBoard | ForEach-Object { \"$($_.Manufacturer) $($_.Product)\" });"
        "equipo=(Get-CimInstance Win32_ComputerSystem | ForEach-Object { \"$($_.Manufacturer) $($_.Model)\" });"
        "so=(Get-CimInstance Win32_OperatingSystem | ForEach-Object { \"$($_.Caption) ($($_.Version))\" });"
        "ram_mhz=(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1 -ExpandProperty Speed);"
        "modulos=@(Get-CimInstance Win32_PhysicalMemory).Count"
        "} | ConvertTo-Json -Compress"
    )
    salida = subprocess.run(["powershell", "-NoProfile", "-Command", comando], capture_output=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode("utf-8", errors="replace")
    return json.loads(salida or "{}")


def _nvidia() -> list[str]:
    if not shutil.which("nvidia-smi"):
        return []
    r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    lineas = []
    for fila in r.stdout.strip().splitlines():
        nombre, usada, total, uso, temp = [c.strip() for c in fila.split(",")]
        lineas.append(f"{nombre}: VRAM {usada}/{total} MB, uso {uso} %, {temp} °C")
    return lineas


def registrar(registro, ctx):
    cache = {}

    @registro.herramienta("Especificaciones del PC: procesador, RAM, gráfica, discos, placa base y sistema operativo.")
    def info_pc() -> str:
        if "info" not in cache:
            cim = _cim()
            discos = []
            for particion in psutil.disk_partitions():
                try:
                    uso = psutil.disk_usage(particion.mountpoint)
                except OSError:
                    continue
                discos.append(f"{particion.device} {tamano_legible(uso.total)} ({tamano_legible(uso.free)} libres)")
            ram = psutil.virtual_memory().total
            cache["info"] = "\n".join([
                f"Equipo: {cim.get('equipo', '?')} · Placa base: {cim.get('placa', '?')}",
                f"Sistema: {cim.get('so', platform.platform())}",
                f"Procesador: {(cim.get('cpu') or platform.processor()).strip()} "
                f"({psutil.cpu_count(logical=False)} núcleos / {psutil.cpu_count()} hilos)",
                f"RAM: {tamano_legible(ram)} ({cim.get('modulos', '?')} módulos a {cim.get('ram_mhz', '?')} MHz)",
                f"Gráfica: {', '.join(cim.get('gpus') or ['?'])}",
                f"Discos: {'; '.join(discos)}",
            ])
        nvidia = _nvidia()
        return cache["info"] + (f"\nGPU NVIDIA ahora: {'; '.join(nvidia)}" if nvidia else "")

    @registro.herramienta("Estado actual del PC: uso de CPU, RAM, disco, gráfica, batería y qué programas consumen más.")
    def estado_pc() -> str:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        procesos = []
        for p in psutil.process_iter(["name", "memory_info"]):
            try:
                procesos.append((p.info["memory_info"].rss, p.info["name"]))
            except (psutil.Error, TypeError, AttributeError):
                continue
        # Agrupar por nombre (Chrome tiene decenas de procesos)
        por_nombre: dict[str, int] = {}
        for memoria, nombre in procesos:
            por_nombre[nombre] = por_nombre.get(nombre, 0) + memoria
        top = sorted(por_nombre.items(), key=lambda x: x[1], reverse=True)[:6]
        lineas = [
            f"CPU: {cpu:.0f} % · RAM: {ram.percent:.0f} % ({tamano_legible(ram.used)} de {tamano_legible(ram.total)})",
            "Lo que más RAM usa: " + ", ".join(f"{n} {tamano_legible(m)}" for n, m in top),
            f"Encendido desde hace {(time.time() - psutil.boot_time()) / 3600:.1f} h",
        ]
        bateria = psutil.sensors_battery()
        if bateria:
            lineas.append(f"Batería: {bateria.percent:.0f} %{' (cargando)' if bateria.power_plugged else ''}")
        lineas += [f"GPU: {g}" for g in _nvidia()]
        uso_c = psutil.disk_usage("C:\\")
        lineas.append(f"Disco C: {uso_c.percent:.0f} % usado ({tamano_legible(uso_c.free)} libres)")
        return "\n".join(lineas)
