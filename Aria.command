#!/bin/bash
# Doble clic: obre Aria al Mac.
cd "$(dirname "$0")"
open -a Ollama 2>/dev/null
sleep 2
.venv/bin/python main.py
