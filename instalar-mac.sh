#!/bin/bash
# Instal·lació d'Aria al Mac (Apple Silicon). Només cal fer-ho una vegada:
#   bash instalar-mac.sh
set -e
cd "$(dirname "$0")"
MODELO="qwen3:8b"
URL_MODELS_VEU="https://github.com/Marc8899/aria-assistent-ia/releases/download/v1.0/Aria-models-veu.zip"

echo "== 1/5 Ollama"
OLLAMA="$(command -v ollama || true)"
[ -z "$OLLAMA" ] && [ -x /Applications/Ollama.app/Contents/Resources/ollama ] && OLLAMA=/Applications/Ollama.app/Contents/Resources/ollama
if [ -z "$OLLAMA" ]; then
  echo "Falta Ollama. S'obre la pàgina de descàrrega: instal·la'l, obre'l un cop i torna a executar aquest script."
  open "https://ollama.com/download/mac"
  exit 1
fi
open -a Ollama 2>/dev/null || true
for i in $(seq 1 30); do "$OLLAMA" list >/dev/null 2>&1 && break; sleep 1; done

echo "== 2/5 Model de llenguatge ($MODELO, uns 5 GB)"
"$OLLAMA" pull "$MODELO"

echo "== 3/5 Python i llibreries (uv)"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
"$UV" venv --python 3.13 .venv
"$UV" pip install --python .venv/bin/python -r requirements-mac.txt

echo "== 4/5 Models de veu (uns 1,5 GB)"
if [ -f datos/modelos/whisper/large-v3-turbo/model.bin ] && [ -f datos/modelos/piper/es_ES-sharvard-medium.onnx ]; then
  echo "Ja hi són."
else
  TMP="$(mktemp -d)"
  curl -L --fail -o "$TMP/models.zip" "$URL_MODELS_VEU"
  unzip -q "$TMP/models.zip" -d "$TMP"
  mkdir -p datos
  rm -rf datos/modelos
  mv "$TMP/Aria/datos/modelos" datos/modelos
  rm -rf "$TMP"
fi

echo "== 5/5 Accés directe"
chmod +x Aria.command

echo
echo "Fet! Obre Aria amb doble clic a Aria.command."
echo "La primera vegada, macOS demanarà permisos per a Terminal:"
echo "  - Micròfon (per parlar amb Aria)"
echo "  - Accessibilitat i Monitoratge de l'entrada (per a la tecla Opció dreta)"
echo "  - Automatització de Microsoft Word (per escriure-hi en directe)"
echo "Es donen a Configuració del Sistema > Privacitat i seguretat."
