@echo off
rem Aria en modo terminal: para los comandos /conectar, /gmail, /exportar...
title Aria (terminal)
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py --terminal
pause
