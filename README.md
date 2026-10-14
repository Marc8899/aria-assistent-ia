# Aria — Assistent Personal IA (AIPA)

Prototip d'assistent personal intel·ligent que funciona **completament en local**, desenvolupat com a part pràctica del Treball de Recerca *Assistent Personal IA* (Batxillerat, Institut Vilanova del Vallès), de Marc Corchón.

Aria envolta un model de llenguatge obert (**Qwen3:14b**, executat amb **Ollama**) amb tot allò que el model no té per si sol: instruccions, context temporal, memòria persistent, organització (tasques, projectes, hàbits, blocs de temps), 87 eines i mesures de seguretat. S'hi pot parlar per veu (Whisper i Piper, en local) des d'una aplicació d'escriptori amb mascota.

## Requisits

- Windows 10/11
- Python 3.13
- [Ollama](https://ollama.com) amb el model `qwen3:14b` (`ollama pull qwen3:14b`)
- Targeta gràfica NVIDIA amb ~12 GB de VRAM o més (recomanat 16 GB)
- Per a la veu, models a `datos/modelos/`:
  - `piper/es_ES-sharvard-medium.onnx` (+ `.onnx.json`)
  - `whisper/large-v3-turbo/` (format CTranslate2 per a faster-whisper)

## Instal·lació i ús

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

- `Aria.bat` (o `python main.py`): aplicació d'escriptori
- `python main.py --terminal`: conversa a la terminal (i comandes `/conectar`)
- `python main.py --api`: API HTTP a http://127.0.0.1:8765/docs

La configuració és a `aria/config.py`.

## Estructura

```
main.py                 punt d'entrada (app, terminal o API)
aria/
  asistente.py          orquestrador: bucle de conversa i d'eines
  prompt.py             instruccions del sistema i nota de context
  config.py             configuració
  memoria.py, tareas.py, planificacion.py, salud.py ...   dades (SQLite)
  herramientas/         les 87 eines que pot fer servir el model, per grups
  guias/                guies que el model consulta quan les necessita
  interfaz/             aplicació d'escriptori (PySide6): finestra, mascota, panell
  voz/                  oïda (Whisper), parla (Piper) i tecla per parlar
  api.py, cli.py        altres maneres d'accedir a Aria
mi_api/                 API personal d'exemple
```

## Privacitat

Totes les dades de l'usuari (memòria, tasques, salut...) es guarden en bases de dades locals a `datos/` i `memoria.db`, que **no formen part d'aquest repositori**. Les contrasenyes i tokens es guarden a l'Administrador de credencials de Windows.

## Nota sobre el desenvolupament

El disseny, la lògica, les decisions i les proves són de l'autor; el codi s'ha escrit amb programació assistida per IA (Claude Code), tal com s'explica a l'apartat 12.3.3 del treball.
