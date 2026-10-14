@echo off
rem Doble clic: abre Aria (mascota de escritorio + ventana). Sin ventana de consola.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" main.py
